"""Dinamica di volo del cubo: massa puntiforme nel baricentro, tre assi indipendenti.

Per ogni asse (la spinta è allineata agli assi e il cubo è trattato come massa puntiforme):

    m dv/dt = F - m a_d(t)        a_d = disturbo di accelerazione del volo parabolico (nel riferimento del cubo)
    tau dF/dt = F_cmd - F         attuatore del primo ordine, tau = t90 / 2,3
    F_cmd = sat( m [ kp (x_rif - x) + kd (v_rif - v) + ki int(x_rif - x) dt ] )    saturato a F_max
            (+ m a_rif se il feedforward è attivo)

Guadagni per assegnazione dei poli (s + alfa wn)(s^2 + 2 zeta wn s + wn^2):
    kp = (1 + 2 zeta alfa) wn^2,  kd = (2 zeta + alfa) wn,  ki = alfa wn^3       alfa = 0: PD puro
L'integrale si ferma quando il comando satura (anti-windup per integrazione condizionata).

Disturbo del volo parabolico (riferimento del cubo): bias costante + rumore gaussiano a media nulla limitato
in banda + sinusoide facoltativa; il cubo parte con una velocità iniziale v0 (rilascio imperfetto).

Riferimento: spostamento da fermo a fermo di d in un tempo T con profilo a minimo jerk (polinomio di quinto grado),
a gradino oppure bang-bang (accelerazione 4 d / T^2 per T/2, poi l'opposta: il profilo del dimensionamento).
simula_asse accetta anche N disturbi e N velocità iniziali insieme (Monte Carlo vettorizzato).

Ambiente (pressione dell'aria): i dati dell'attuatore sono quelli di progetto, alla pressione di progetto p0.
Con sigma = p / p0 (stessa temperatura, ventole a geometria e giri fissati, leggi di similitudine):

    spinta massima dell'ambiente   F_max = F_max,progetto x sigma             (stessi giri massimi)
    potenza per una spinta F       P = P_rif (F / F_rif)^esponente / sqrt(sigma)
                                   (la stessa spinta in aria meno densa chiede più giri)

sigma = 1 riproduce esattamente gli indicatori di progetto.  La potenza totale è la somma dei tre assi,
la corrente di picco è la potenza totale di picco divisa per la tensione della batteria.

Solo numpy.  Unità SI (m, s, kg, N, rad/s) salvo diversa indicazione.
"""
import math
import numpy as np

G0 = 9.80665


# ---------------------------------------------------------------- riferimento e disturbo
def riferimento_minjerk(t, d, T):
    """Posizione, velocità e accelerazione di riferimento: da 0 a d in T secondi, da fermo a fermo."""
    s = np.clip(np.asarray(t, float) / T, 0.0, 1.0)
    x = d * (10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5)
    v = d / T * (30 * s ** 2 - 60 * s ** 3 + 30 * s ** 4)
    a = d / T ** 2 * (60 * s - 180 * s ** 2 + 120 * s ** 3)
    fuori = np.asarray(t, float) >= T
    return x, np.where(fuori, 0.0, v), np.where(fuori, 0.0, a)


def riferimento_gradino(t, d, T=0.0):
    t = np.asarray(t, float)
    return np.full_like(t, d), np.zeros_like(t), np.zeros_like(t)


def riferimento_bang_bang(t, d, T):
    """Da fermo a fermo in T con accelerazione 4 d / T^2 per T/2 e l'opposta per T/2; poi fermo in d."""
    t = np.asarray(t, float)
    a0 = 4.0 * d / T ** 2
    prima = t < T / 2
    dopo = (t >= T / 2) & (t < T)
    x = np.where(prima, 0.5 * a0 * t ** 2,
                 np.where(dopo, d - 0.5 * a0 * (T - t) ** 2, d))
    v = np.where(prima, a0 * t, np.where(dopo, a0 * (T - t), 0.0))
    a = np.where(prima, a0, np.where(dopo, -a0, 0.0))
    return x, v, a


PROFILI = {"minimo_jerk": riferimento_minjerk, "gradino": riferimento_gradino, "bang_bang": riferimento_bang_bang}


def disturbo_sinusoidale(t, ampiezza_g, frequenza_Hz, fase_deg):
    """Accelerazione di disturbo (m/s^2)."""
    return ampiezza_g * G0 * np.sin(2 * math.pi * frequenza_Hz * np.asarray(t, float) + math.radians(fase_deg))


def rumore_in_banda(n, dt, sigma, banda_Hz, rng, campioni=1):
    """Rumore gaussiano a media nulla, passa-basso ideale a banda_Hz, deviazione standard sigma.

    Rumore bianco di varianza unitaria filtrato in frequenza: il filtro tiene banda / f_Nyquist della varianza,
    quindi si riscala di sqrt(f_Nyquist / banda).  Ritorna un array (campioni, n).
    """
    w = rng.standard_normal((campioni, n))
    if sigma == 0:
        return np.zeros((campioni, n))
    f_nyq = 0.5 / dt
    if banda_Hz >= f_nyq:
        return sigma * w
    W = np.fft.rfft(w, axis=-1)
    W[:, np.fft.rfftfreq(n, dt) > banda_Hz] = 0.0
    return sigma * math.sqrt(f_nyq / banda_Hz) * np.fft.irfft(W, n, axis=-1)


def direzioni_casuali(rng, campioni):
    """Versori distribuiti uniformemente sulla sfera, array (campioni, 3)."""
    u = rng.standard_normal((campioni, 3))
    return u / np.linalg.norm(u, axis=1, keepdims=True)


def guadagni(wn, zeta, alfa=0.0):
    """kp, kd, ki per i poli (s + alfa wn)(s^2 + 2 zeta wn s + wn^2); alfa = 0 dà il PD."""
    return (1 + 2 * zeta * alfa) * wn ** 2, (2 * zeta + alfa) * wn, alfa * wn ** 3


# ---------------------------------------------------------------- simulazione di un asse
def simula_asse(m, F_max, t90, wn, zeta, d, T, a_dist, t_fin, dt=1e-3, feedforward=False,
                riferimento=riferimento_minjerk, F_max_neg=None, v0=0.0, alfa_integrale=0.0):
    """Simula un asse.  Ritorna le serie temporali.

    a_dist: funzione a_dist(t) oppure array di accelerazioni di disturbo (m/s^2), forma (n,) o (N, n) per N
    campioni insieme; v0: velocità iniziale, scalare o (N,).  Con N campioni le serie hanno forma (N, n).
    """
    tau = max(t90 / 2.3, 1e-9)
    F_neg = F_max if F_max_neg is None else F_max_neg
    kp, kd, ki = guadagni(wn, zeta, alfa_integrale)
    n = int(round(t_fin / dt)) + 1
    t = np.arange(n) * dt
    xr, vr, ar = riferimento(t, d, T)
    ad = np.asarray(a_dist(t) if callable(a_dist) else a_dist, float)
    v0 = np.asarray(v0, float)
    gruppo = ad.ndim == 2 or v0.ndim == 1
    N = max(ad.shape[0] if ad.ndim == 2 else 1, v0.size)
    ad = np.broadcast_to(np.atleast_2d(ad), (N, n))
    x = np.zeros((N, n)); v = np.zeros((N, n)); F = np.zeros((N, n)); Fc = np.zeros((N, n))
    sat = np.zeros((N, n), bool)
    xs, vs, Fs, xi = np.zeros(N), np.broadcast_to(v0, (N,)).copy(), np.zeros(N), np.zeros(N)

    def deriv(vv, FF, Fcmd, a_d):
        return vv, (FF - m * a_d) / m, (Fcmd - FF) / tau

    for k in range(n):
        x[:, k], v[:, k], F[:, k] = xs, vs, Fs
        e = xr[k] - xs
        cmd = m * (kp * e + kd * (vr[k] - vs) + ki * xi)
        if feedforward:
            cmd = cmd + m * ar[k]
        Fc[:, k] = np.clip(cmd, -F_neg, F_max)
        sat[:, k] = Fc[:, k] != cmd
        if k == n - 1:
            break
        if ki:
            xi = xi + np.where(sat[:, k], 0.0, e * dt)
        a0, a1, a2 = ad[:, k], 0.5 * (ad[:, k] + ad[:, k + 1]), ad[:, k + 1]
        k1 = deriv(vs, Fs, Fc[:, k], a0)
        k2 = deriv(vs + 0.5 * dt * k1[1], Fs + 0.5 * dt * k1[2], Fc[:, k], a1)
        k3 = deriv(vs + 0.5 * dt * k2[1], Fs + 0.5 * dt * k2[2], Fc[:, k], a1)
        k4 = deriv(vs + dt * k3[1], Fs + dt * k3[2], Fc[:, k], a2)
        xs = xs + dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        vs = vs + dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        Fs = Fs + dt / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
    s = {"t": t, "x": x, "v": v, "F": F, "F_cmd": Fc, "x_rif": xr, "v_rif": vr, "a_dist": np.array(ad), "saturato": sat}
    if not gruppo:
        for c in ("x", "v", "F", "F_cmd", "a_dist", "saturato"):
            s[c] = s[c][0]
    return s


def campione(s, j):
    """Serie del campione j di una simulazione a N campioni."""
    return {k: (a[j] if isinstance(a, np.ndarray) and a.ndim == 2 else a) for k, a in s.items()}


# ---------------------------------------------------------------- indicatori
def spinta_ambiente(F_progetto, sigma):
    """Spinta massima nell'ambiente: F_progetto x sigma (stessi giri massimi)."""
    return np.asarray(F_progetto, float) * sigma


def potenza_elettrica(F, P_rif_W, F_rif_N, esponente, sigma=1.0):
    """Potenza elettrica per erogare la spinta F: P_rif (|F| / F_rif)^esponente / sqrt(sigma)."""
    return P_rif_W * (np.abs(F) / max(F_rif_N, 1e-12)) ** esponente / math.sqrt(sigma)


def potenza_totale(P_assi, t, tensione_V):
    """Somma dei tre assi nel tempo e suoi indicatori (array: forma (n,) o (N, n)).

    Ritorna P_tot e, sull'ultimo asse (tempo): picco, energia, media (energia / durata), corrente di picco.
    """
    P = np.sum(np.asarray(P_assi, float), axis=0)
    E = np.trapezoid(P, t, axis=-1)
    pic = np.max(P, axis=-1)
    return {"P_tot": P, "potenza_picco_W": pic, "energia_J": E,
            "potenza_media_W": E / (t[-1] - t[0]), "corrente_picco_A": pic / tensione_V}


def indicatori(s, d, T, tolleranza_m, F_max, P_rif_W, F_rif_N, esponente, dt, sigma=1.0):
    t, x, e = s["t"], s["x"], s["x_rif"] - s["x"]
    i_T = int(np.searchsorted(t, T))
    i_T = min(i_T, len(t) - 1)
    fuori = np.where(np.abs(e) > tolleranza_m)[0]
    t_ass = float(t[fuori[-1]]) if len(fuori) else 0.0
    t_ass = None if (len(fuori) and fuori[-1] == len(t) - 1) else t_ass
    sov = float(max(np.max(x) - d, 0.0)) if d >= 0 else float(max(d - np.min(x), 0.0))
    P = potenza_elettrica(s["F"], P_rif_W, F_rif_N, esponente, sigma)
    return {
        "errore_a_T_mm": float(e[i_T] * 1000),
        "errore_max_mm": float(np.max(np.abs(e)) * 1000),
        "errore_finale_mm": float(e[-1] * 1000),
        "sovraelongazione_mm": sov * 1000,
        "tempo_assestamento_s": t_ass,
        "spinta_max_usata_N": float(np.max(np.abs(s["F"]))),
        "spinta_su_massima": float(np.max(np.abs(s["F"])) / F_max),
        "tempo_in_saturazione_s": float(np.sum(s["saturato"]) * dt),
        "energia_J": float(np.trapezoid(P, t)),
        "potenza_picco_W": float(np.max(P)),
        "velocita_max_m_s": float(np.max(np.abs(s["v"]))),
    }


# ---------------------------------------------------------------- spazio massimo e tempo minimo
def spazio_massimo(m, F_max, a_dist_ampiezza, t):
    """Spazio massimo da fermo a fermo in t secondi (accelera per t/2, frena per t/2), a spinta costante.

    Ritorna (senza disturbo, con disturbo nel caso peggiore): nel peggiore il disturbo sottrae la sua
    ampiezza all'accelerazione in tutta la manovra.
    """
    a0 = F_max / m
    a1 = max(a0 - a_dist_ampiezza, 0.0)
    t = np.asarray(t, float)
    return a0 * t ** 2 / 4, a1 * t ** 2 / 4


def tempo_minimo(m, F_max, a_dist_ampiezza, d):
    """Tempo minimo per spostarsi di d da fermo a fermo (senza disturbo, caso peggiore)."""
    a0, a1 = F_max / m, max(F_max / m - a_dist_ampiezza, 0.0)
    return 2 * math.sqrt(d / a0), (2 * math.sqrt(d / a1) if a1 > 0 else math.inf)
