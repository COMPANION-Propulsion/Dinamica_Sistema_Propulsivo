"""Autorità di controllo, tolleranza ai guasti e indice d'ingestione.

Allocazione: ogni 'modo' di attuazione (una ventola, o il verso inverso di
una reversibile) produce alla massima spinta un vettore di forza e
momento w_k (6 componenti).  Con comandi 0 <= u_k <= 1 e, per ogni ventola,
somma dei suoi modi <= 1, si cerca con programmazione lineare la massima
forza pura (o il massimo momento puro) in una direzione.  Le ventole
unidirezionali hanno u >= 0; quelle reversibili hanno due modi (avanti e
indietro).

Indice d'ingestione (screening, NON una previsione CFD): rapporto tra la
velocità di aspirazione di una presa attiva, valutata sul bordo del getto
più vicino, e la velocità locale del getto.
  getto tondo: velocità sull'asse = V_e fino a 6,2 D (nucleo), poi 6,2 V_e D / x;
               semi-larghezza b = D/2 + 0,11 x
  presa a filo parete: pozzo emisferico, v = Q / (2 pi r^2), attenuato
               (1 + cos gamma)/2 per i punti di lato o dietro la faccia.
Soglie (INPUT.py): < 0,05 trascurabile, > 0,20 probabile ingestione.
"""
import itertools
import math
import numpy as np
from scipy.optimize import linprog

DIREZIONI = {"+X": (0, 1), "-X": (0, -1), "+Y": (1, 1), "-Y": (1, -1), "+Z": (2, 1), "-Z": (2, -1)}


def _lp_max(W, gruppi, target_idx, target_dir, vincoli_zero):
    """max t con W u = t * e_target (componente target), altre componenti in vincoli_zero = 0."""
    n = W.shape[1]
    if n == 0:
        return 0.0, np.zeros(0)
    c = np.zeros(n + 1); c[-1] = -1.0
    A_eq, b_eq = [], []
    for i in range(6):
        riga = np.zeros(n + 1)
        riga[:n] = W[i]
        if i == target_idx:
            riga[-1] = -target_dir
            A_eq.append(riga); b_eq.append(0.0)
        elif i in vincoli_zero:
            A_eq.append(riga); b_eq.append(0.0)
    A_ub, b_ub = [], []
    for g in gruppi:
        riga = np.zeros(n + 1)
        riga[g] = 1.0
        A_ub.append(riga); b_ub.append(1.0)
    bounds = [(0, 1)] * n + [(0, None)]
    res = linprog(c, A_ub=np.array(A_ub) if A_ub else None, b_ub=b_ub if b_ub else None,
                  A_eq=np.array(A_eq), b_eq=b_eq, bounds=bounds, method="highs")
    if not res.success:
        return 0.0, np.zeros(n)
    return float(res.x[-1]), res.x[:n]


def autorita(modi, escludi=None):
    """Massima forza pura per ogni verso e massimo momento puro per asse.

    modi: lista di dict {"unita": nome, "w": array(6) [Fx,Fy,Fz,Mx,My,Mz] alla massima spinta}
    """
    escludi = escludi or set()
    modi = [m for m in modi if m["unita"] not in escludi]
    if not modi:
        return {k: 0.0 for k in DIREZIONI}, {k: 0.0 for k in ("Mx", "My", "Mz")}, {}
    W = np.array([m["w"] for m in modi]).T
    unita = sorted(set(m["unita"] for m in modi))
    gruppi = [[i for i, m in enumerate(modi) if m["unita"] == u] for u in unita]
    forze, uso = {}, {}
    for nome, (ax, sg) in DIREZIONI.items():
        t, u = _lp_max(W, gruppi, ax, sg, vincoli_zero=[i for i in range(6) if i != ax])
        forze[nome] = t
        uso[nome] = [modi[i]["unita"] for i in range(len(modi)) if u[i] > 1e-6]
    momenti = {}
    for j, nome in enumerate(("Mx", "My", "Mz")):
        t1, _ = _lp_max(W, gruppi, 3 + j, 1, vincoli_zero=[i for i in range(6) if i != 3 + j])
        t2, _ = _lp_max(W, gruppi, 3 + j, -1, vincoli_zero=[i for i in range(6) if i != 3 + j])
        momenti[nome] = min(t1, t2)
    return forze, momenti, uso


def tolleranza_guasti(modi, F_richiesta):
    """Per ogni guasto singolo di ventola: minima forza pura residua / richiesta."""
    unita = sorted(set(m["unita"] for m in modi))
    peggiore, chi = math.inf, None
    for u in unita:
        f, _, _ = autorita(modi, escludi={u})
        r = min(f.values()) / F_richiesta
        if r < peggiore:
            peggiore, chi = r, u
    return peggiore, chi


# ------------------------------------------------------------------ ingestione
def indice_ingestione(uscita, presa):
    """uscita: {pos (m), getto (versore), D (m), V (m/s)}; presa: {pos, normale, Q (m3/s), D (m)}."""
    P_j = np.asarray(uscita["pos"], float)
    n_j = np.asarray(uscita["getto"], float)
    D_j, V_j = uscita["D"], uscita["V"]
    P_i = np.asarray(presa["pos"], float)
    m_i = np.asarray(presa["normale"], float)
    Q_i, D_i = presa["Q"], presa["D"]
    if V_j <= 0 or Q_i <= 0:
        return 0.0
    peggiore = 0.0
    for x in np.linspace(0, 15 * D_j, 61):
        C = P_j + x * n_j
        b = D_j / 2 + 0.11 * x
        u_c = V_j if x <= 6.2 * D_j else 6.2 * V_j * D_j / x
        dv = C - P_i
        dist = np.linalg.norm(dv)
        d_e = max(dist - b, D_i / 2)
        cosg = float(dv @ m_i) / max(dist, 1e-9)
        att = max(0.0, (1 + cosg) / 2)
        v_s = att * Q_i / (2 * math.pi * d_e ** 2)
        peggiore = max(peggiore, v_s / u_c)
    return peggiore


def comandi_combinati(n_assi_max=3):
    """Tutte le combinazioni di versi su 1..n assi diversi (es. +X, +X-Y, +X+Y+Z...)."""
    out = []
    assi = ["X", "Y", "Z"]
    for k in range(1, n_assi_max + 1):
        for comb in itertools.combinations(assi, k):
            for segni in itertools.product("+-", repeat=k):
                out.append(tuple(s + a for s, a in zip(segni, comb)))
    return out
