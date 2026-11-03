"""Elementi di condotto e risolutore della rete fluidodinamica 1D.

Ipotesi (valide per il problema e verificate in uscita):
  - flusso incomprimibile: Mach di punta < 0,3 (controllato);
  - aria aspirata da ferma: pressione totale all'imbocco = p_ambiente;
  - getto libero subsonico: pressione statica all'uscita = p_ambiente;
  - spinta = flusso di quantità di moto del getto, beta rho A_e v_e^2
    (nessun termine di pressione, aria ferma lontano dal cubo);
  - equazione dell'energia lungo il condotto:
      p0(s) = p0(0) - somma perdite + Dp_ventola
    con p0 = p + 1/2 rho alpha v^2 (alpha = coefficiente di energia cinetica).
Per ogni unità vale:  Dp_ventola(Q) = perdite(Q) + 1/2 rho alpha_e v_e^2
"""
from dataclasses import dataclass, field
import math
import numpy as np
from scipy.optimize import brentq

from . import perdite as P


def area(D):
    return math.pi * D * D / 4.0


# =========================================================================
# Elementi
# =========================================================================
@dataclass
class Elemento:
    nome: str
    L: float = 0.0                # lunghezza lungo l'asse (m)

    def D_in(self):
        raise NotImplementedError

    def D_out(self):
        return self.D_in()

    def A_locale(self, x):
        """Area di passaggio a distanza x dall'inizio dell'elemento."""
        Di, Do = self.D_in(), self.D_out()
        if self.L <= 0:
            return area(Do)
        t = min(max(x / self.L, 0.0), 1.0)
        return area(Di + (Do - Di) * t)

    def dp(self, Q, aria, ctx):
        return 0.0

    def categoria(self):
        return "altro"

    def frazione_attrito(self):
        """Quota della perdita distribuita lungo L (per i profili)."""
        return 0.0


@dataclass
class Griglia(Elemento):
    D: float = 0.05
    porosita: float = 0.6
    d_filo: float = 0.5e-3
    avvisi: list = field(default_factory=list)

    def D_in(self):
        return self.D

    def dp(self, Q, aria, ctx):
        v = Q / area(self.D)
        Re_f = (v / self.porosita) * self.d_filo / aria.nu
        K, av = P.k_griglia(self.porosita, Re_f)
        self.avvisi = av
        return K * aria.q(v)

    def categoria(self):
        return "griglie"


@dataclass
class Imbocco(Elemento):
    D: float = 0.05
    r_su_D: float = 0.1

    def D_in(self):
        return self.D

    def dp(self, Q, aria, ctx):
        return P.k_imbocco(self.r_su_D) * aria.q(Q / area(self.D))

    def categoria(self):
        return "imbocco"


@dataclass
class Tratto(Elemento):
    D1: float = 0.05
    D2: float = None
    rugosita: float = 20e-6       # m (stampa 3D lisciata ~ 10-50 micron)
    n_sub: int = 8

    def D_in(self):
        return self.D1

    def D_out(self):
        return self.D2 if self.D2 else self.D1

    def dp(self, Q, aria, ctx):
        if self.L <= 0:
            return 0.0
        tot, n = 0.0, self.n_sub
        for i in range(n):
            x = (i + 0.5) / n * self.L
            A = self.A_locale(x)
            D = math.sqrt(4 * A / math.pi)
            v = Q / A
            lam = P.fattore_attrito(v * D / aria.nu, self.rugosita / D)
            tot += lam * (self.L / n) / D * aria.q(v)
        return tot

    def categoria(self):
        return "attrito"

    def frazione_attrito(self):
        return 1.0


@dataclass
class Curva(Elemento):
    D: float = 0.05
    R: float = 0.05
    angolo: float = 90.0
    rugosita: float = 20e-6
    avvisi: list = field(default_factory=list)

    def D_in(self):
        return self.D

    def dp(self, Q, aria, ctx):
        v = Q / area(self.D)
        Re = v * self.D / aria.nu
        K, av = P.k_curva(self.R / self.D, self.angolo, Re)
        self.avvisi = av
        lam = P.fattore_attrito(Re, self.rugosita / self.D)
        return (K + lam * self.L / self.D) * aria.q(v)

    def categoria(self):
        return "curve"


@dataclass
class EffettoSistema(Elemento):
    D: float = 0.05
    K: float = 0.0
    descrizione: str = ""

    def D_in(self):
        return self.D

    def dp(self, Q, aria, ctx):
        return self.K * aria.q(Q / area(self.D))

    def categoria(self):
        return "effetto di sistema"


@dataclass
class ElementoVentola(Elemento):
    ventola: object = None
    N: float = 0.0

    def D_in(self):
        return self.ventola.D

    def A_locale(self, x):
        return self.ventola.area_anello

    def guadagno(self, Q, aria):
        return self.ventola.stato(Q, self.N, aria)["dp_utile"]

    def categoria(self):
        return "ventola"


@dataclass
class Ugello(Elemento):
    D1: float = 0.05
    D2: float = 0.045
    semiangolo: float = 10.0
    rugosita: float = 20e-6
    avvisi: list = field(default_factory=list)

    def D_in(self):
        return self.D1

    def D_out(self):
        return self.D2

    def dp(self, Q, aria, ctx):
        sigma = (self.D2 / self.D1) ** 2
        K, av = P.k_ugello(sigma, self.semiangolo)
        self.avvisi = av
        v_e = Q / area(self.D2)
        Dm = 0.5 * (self.D1 + self.D2)
        vm = Q / area(Dm)
        lam = P.fattore_attrito(vm * Dm / aria.nu, self.rugosita / Dm)
        return K * aria.q(v_e) + lam * self.L / Dm * aria.q(vm)

    def categoria(self):
        return "ugello"


@dataclass
class Uscita(Elemento):
    D: float = 0.045
    alfa_e: float = 1.03          # coefficiente di energia cinetica del getto
    beta_e: float = 1.02          # coefficiente di quantità di moto del getto
    direzione_getto: tuple = (1.0, 0.0, 0.0)
    posizione: tuple = (0.0, 0.0, 0.0)   # m, rispetto al centro del cubo

    def D_in(self):
        return self.D

    def categoria(self):
        return "uscita"


# =========================================================================
# Unità (una ventola con i suoi condotti)
# =========================================================================
@dataclass
class Ramo:
    nome: str
    elementi: list
    uscita: Uscita


@dataclass
class UnitaRete:
    nome: str
    tronco: list                  # elementi dall'imbocco alla fine del condotto
    rami: list                    # un solo Ramo: coda (griglia d'uscita) e uscita
    ventola: object               # Ventola
    reversibile: bool = False

    def elemento_ventola(self):
        for e in self.tronco:
            if isinstance(e, ElementoVentola):
                return e
        raise ValueError("unità senza ventola")

    def imposta_N(self, N):
        self.elemento_ventola().N = N


def _perdite_lista(elementi, Q, aria, ctx):
    tot, per_cat = 0.0, {}
    for e in elementi:
        if isinstance(e, ElementoVentola):
            continue
        d = e.dp(Q, aria, ctx)
        tot += d
        per_cat[e.categoria()] = per_cat.get(e.categoria(), 0.0) + d
    return tot, per_cat


def _residuo(u, Q, aria, ctx):
    """Salto della ventola meno perdite meno energia cinetica del getto (Pa)."""
    gain = u.elemento_ventola().guadagno(Q, aria)
    r = u.rami[0]
    loss_t, _ = _perdite_lista(u.tronco, Q, aria, ctx)
    loss_r, _ = _perdite_lista(r.elementi, Q, aria, ctx)
    ke = r.uscita.alfa_e * aria.q(Q / area(r.uscita.D))
    return gain - loss_t - loss_r - ke


def _risolvi_singola(u, aria, ctx):
    """Portata di equilibrio: radice scalare con brentq (robusta)."""
    ev = u.elemento_ventola()
    Qmax = u.ventola.Q_max(ev.N)
    if Qmax <= 0:
        return 0.0
    f = lambda Q: _residuo(u, Q, aria, ctx)
    lo = Qmax * 1e-4
    if f(lo) <= 0:
        return 0.0
    if f(Qmax) >= 0:
        return Qmax
    return brentq(f, lo, Qmax, xtol=1e-9, rtol=1e-8)


def risolvi(unita, aria, ctx=None):
    """Punto di funzionamento di ogni unità (le unità sono indipendenti).

    unita: lista di UnitaRete con N già impostato.
    Ritorna dict nome_unita -> {"Q_rami": [Q], "Q": Q, "p_in_rel": 0}.
    """
    ctx = ctx or {}
    out = {}
    for u in unita:
        Q = _risolvi_singola(u, aria, ctx)
        out[u.nome] = {"Q_rami": [Q], "Q": Q, "p_in_rel": 0.0}
    return out


# =========================================================================
# Risultati derivati
# =========================================================================
def bilancio_unita(u, sol, aria, ctx=None):
    """Spinte, perdite per categoria, potenze e coppie di una unità risolta.

    Le perdite si sommano come POTENZA (Q * Dp).  'perdite_cat_Pa' è la
    pressione equivalente riferita alla portata (potenza / Q).
    """
    ctx = ctx or {}
    Qr = sol["Q_rami"]
    Qt = sum(Qr)
    ev = u.elemento_ventola()
    st = u.ventola.stato(Qt, ev.N, aria)
    loss_t, cat = _perdite_lista(u.tronco, Qt, aria, ctx)
    cat_W = {k: v * Qt for k, v in cat.items()}
    spinte, forze, P_getto = [], np.zeros(3), 0.0
    momenti = np.zeros(3)
    for Qb, r in zip(Qr, u.rami):
        lb, cb = _perdite_lista(r.elementi, Qb, aria, ctx)
        for k, v in cb.items():
            cat_W[k] = cat_W.get(k, 0.0) + v * Qb
        A = area(r.uscita.D)
        ve = Qb / A
        F = r.uscita.beta_e * aria.rho * A * ve * ve
        d = np.array(r.uscita.direzione_getto, float)
        f_vec = -F * d                                  # la spinta è opposta al getto
        forze += f_vec
        momenti += np.cross(np.array(r.uscita.posizione, float), f_vec)
        spinte.append(F)
        P_getto += 0.5 * aria.rho * A * ve ** 3 * r.uscita.alfa_e
    P_perdite = sum(cat_W.values())
    return {"Q": Qt, "Q_rami": Qr, "spinte_rami": spinte, "forza": forze, "momento": momenti,
            "spinta": float(np.linalg.norm(forze)), "stato_ventola": st,
            "perdite_cat_W": {k: float(v) for k, v in cat_W.items()},
            "perdite_cat_Pa": {k: float(v / max(Qt, 1e-12)) for k, v in cat_W.items()},
            "P_perdite": float(P_perdite), "P_getto": float(P_getto),
            "P_utile_ventola": float(Qt * st["dp_utile"]),
            "dp_ventola": float(st["dp_utile"]), "p_in_rel": sol["p_in_rel"]}


def profilo_percorso(elementi, Q, aria, p0_iniziale, ctx, n_per_tratto=12):
    """Profilo lungo la coordinata curvilinea s di una lista di elementi.

    Ritorna dict con s, A, v, p0, p (pressioni relative all'ambiente) e i
    confini/nomi degli elementi.  Le perdite concentrate sono applicate a
    metà elemento (o all'inizio se L = 0); l'attrito è distribuito.
    """
    s_list, A_list, p0_list, conf = [], [], [], []
    s, p0 = 0.0, p0_iniziale
    for e in elementi:
        conf.append((s, e.nome, e.categoria()))
        if isinstance(e, ElementoVentola):
            gain = e.guadagno(Q, aria)
            n = max(n_per_tratto // 2, 2)
            for i in range(n + 1):
                x = e.L * i / n
                s_list.append(s + x)
                A_list.append(e.A_locale(x))
                p0_list.append(p0 + gain * (i / n))
            p0 += gain
            s += e.L
            continue
        d = e.dp(Q, aria, ctx)
        fa = e.frazione_attrito()
        if e.L <= 0:
            s_list.append(s); A_list.append(e.A_locale(0)); p0_list.append(p0)
            p0 -= d
            s_list.append(s); A_list.append(e.A_locale(0)); p0_list.append(p0)
            continue
        n = n_per_tratto
        for i in range(n + 1):
            x = e.L * i / n
            loc = (1 - fa) * d * (1.0 if x >= e.L / 2 else 0.0)
            dist = fa * d * (i / n)
            s_list.append(s + x)
            A_list.append(e.A_locale(x))
            p0_list.append(p0 - loc - dist)
        p0 -= d
        s += e.L
    s_arr, A_arr, p0_arr = map(np.array, (s_list, A_list, p0_list))
    v = Q / A_arr
    p = p0_arr - 0.5 * aria.rho * v * v
    return {"s": s_arr, "A": A_arr, "v": v, "p0": p0_arr, "p": p, "confini": conf}


def profili_unita(u, sol, aria, ctx=None):
    """Profili del tronco e della coda d'uscita (la coda prosegue la coordinata s)."""
    ctx = ctx or {}
    Qt = sol["Q"]
    pr_t = profilo_percorso(u.tronco, Qt, aria, sol["p_in_rel"], ctx)
    out = {"tronco": pr_t, "rami": []}
    for Qb, r in zip(sol["Q_rami"], u.rami):
        pr = profilo_percorso(r.elementi, Qb, aria, pr_t["p0"][-1], ctx)
        pr["s"] = pr["s"] + pr_t["s"][-1]
        # punto di uscita
        A = area(r.uscita.D)
        ve = Qb / A
        pr["p_uscita_statica"] = pr["p0"][-1] - r.uscita.alfa_e * aria.q(ve)
        out["rami"].append(pr)
    return out


def N_per_spinta(u, F_obiettivo, aria, N_max, ctx=None, direzione=None):
    """Giri necessari per la spinta F_obiettivo (sulla direzione nominale)."""
    ctx = ctx or {}

    def spinta(N):
        u.imposta_N(N)
        sol = risolvi([u], aria, ctx)[u.nome]
        b = bilancio_unita(u, sol, aria, ctx)
        if direzione is not None:
            return float(np.dot(b["forza"], direzione))
        return b["spinta"]

    if spinta(N_max) < F_obiettivo:
        return None
    return brentq(lambda N: spinta(N) - F_obiettivo, 100.0, N_max, xtol=1.0, rtol=1e-6)
