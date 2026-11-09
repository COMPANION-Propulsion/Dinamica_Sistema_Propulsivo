"""Dinamica di volo del cubo: massa puntiforme nel baricentro, tre assi indipendenti.

Per ogni asse (la spinta è allineata agli assi e il cubo è trattato come massa puntiforme):

    m dv/dt = F - m a_d(t)        a_d = disturbo di accelerazione del volo parabolico (nel riferimento del cubo)
    tau dF/dt = F_cmd - F         attuatore del primo ordine, tau = t90 / 2,3
    F_cmd = sat( m [ wn^2 (x_rif - x) + 2 zeta wn (v_rif - v) ] )    regolatore PD, saturato a F_max
            (+ m a_rif se il feedforward è attivo)

Riferimento: spostamento da fermo a fermo di d in un tempo T con profilo a minimo jerk (polinomio di quinto grado).

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


def disturbo_sinusoidale(t, ampiezza_g, frequenza_Hz, fase_deg):
    """Accelerazione di disturbo (m/s^2)."""
    return ampiezza_g * G0 * np.sin(2 * math.pi * frequenza_Hz * np.asarray(t, float) + math.radians(fase_deg))


# ---------------------------------------------------------------- simulazione di un asse
def simula_asse(m, F_max, t90, wn, zeta, d, T, a_dist, t_fin, dt=1e-3, feedforward=False,
                riferimento=riferimento_minjerk, F_max_neg=None):
    """Simula un asse; a_dist(t) -> accelerazione di disturbo (m/s^2).  Ritorna le serie temporali."""
    tau = max(t90 / 2.3, 1e-9)
    F_neg = F_max if F_max_neg is None else F_max_neg
    n = int(round(t_fin / dt)) + 1
    t = np.arange(n) * dt
    xr, vr, ar = riferimento(t, d, T)
    ad = a_dist(t)
    x = np.zeros(n); v = np.zeros(n); F = np.zeros(n); Fc = np.zeros(n)
    sat = np.zeros(n, bool)
    xs, vs, Fs = 0.0, 0.0, 0.0

    def deriv(vv, FF, Fcmd, a_d):
        return vv, (FF - m * a_d) / m, (Fcmd - FF) / tau

    for k in range(n):
        x[k], v[k], F[k] = xs, vs, Fs
        cmd = m * (wn ** 2 * (xr[k] - xs) + 2 * zeta * wn * (vr[k] - vs))
        if feedforward:
            cmd += m * ar[k]
        Fc[k] = min(max(cmd, -F_neg), F_max)
        sat[k] = Fc[k] != cmd
        if k == n - 1:
            break
        a0, a1 = ad[k], 0.5 * (ad[k] + ad[k + 1])
        k1 = deriv(vs, Fs, Fc[k], a0)
        k2 = deriv(vs + 0.5 * dt * k1[1], Fs + 0.5 * dt * k1[2], Fc[k], a1)
        k3 = deriv(vs + 0.5 * dt * k2[1], Fs + 0.5 * dt * k2[2], Fc[k], a1)
        k4 = deriv(vs + dt * k3[1], Fs + dt * k3[2], Fc[k], ad[k + 1])
        xs += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        vs += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        Fs += dt / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
    return {"t": t, "x": x, "v": v, "F": F, "F_cmd": Fc, "x_rif": xr, "v_rif": vr, "a_dist": ad, "saturato": sat}


# ---------------------------------------------------------------- indicatori
def indicatori(s, d, T, tolleranza_m, F_max, P_rif_W, F_rif_N, esponente, dt):
    t, x, e = s["t"], s["x"], s["x_rif"] - s["x"]
    i_T = int(np.searchsorted(t, T))
    i_T = min(i_T, len(t) - 1)
    fuori = np.where(np.abs(e) > tolleranza_m)[0]
    t_ass = float(t[fuori[-1]]) if len(fuori) else 0.0
    t_ass = None if (len(fuori) and fuori[-1] == len(t) - 1) else t_ass
    sov = float(max(np.max(x) - d, 0.0)) if d >= 0 else float(max(d - np.min(x), 0.0))
    P = P_rif_W * (np.abs(s["F"]) / max(F_rif_N, 1e-12)) ** esponente
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
