"""Rigidezza e verifiche strutturali dei condotti.

Tubo a parete sottile tra due appoggi (estremi del tratto dritto più lungo):
  I = pi/64 (Do^4 - Di^4),  A = pi/4 (Do^2 - Di^2),  m' = rho A
  trave appoggiata:     f_t = (pi / (2 L^2)) sqrt(E I / m')
  massa della ventola M a distanza a (b = L - a):  k = 3 E I L / (a^2 b^2)
  combinazione di Dunkerley (stima per difetto):  1/f^2 = 1/f_t^2 + 1/f_M^2
Campbell: eccitazioni 1 x giro (sbilanciamento), Z x giro (passaggio pale)
e 2 Z x giro nel campo di giri di esercizio.
Instabilità a pressione esterna (tubo lungo):  p_cr = 2 E / (1 - nu^2) (t / D_m)^3.
Flessione per accelerazione n g della massa della ventola a metà campata:
  M_f = M n g L / 4,   sigma = M_f (Do/2) / I.
"""
import math
import numpy as np


def proprieta_tubo(D_mm, t_mm):
    Di = D_mm / 1000
    Do = Di + 2 * t_mm / 1000
    I = math.pi / 64 * (Do ** 4 - Di ** 4)
    A = math.pi / 4 * (Do ** 2 - Di ** 2)
    return Di, Do, I, A


def frequenza_tratto(L_mm, D_mm, t_mm, mat, M_kg=0.0, a_frazione=0.5):
    if L_mm <= 1:
        return math.inf
    L = L_mm / 1000
    Di, Do, I, A = proprieta_tubo(D_mm, t_mm)
    mprime = mat["rho"] * A
    f_t = math.pi / (2 * L * L) * math.sqrt(mat["E"] * I / mprime)
    if M_kg <= 0:
        return f_t
    a = max(min(a_frazione, 0.95), 0.05) * L
    b = L - a
    k = 3 * mat["E"] * I * L / (a * a * b * b)
    f_M = math.sqrt(k / M_kg) / (2 * math.pi)
    return 1 / math.sqrt(1 / f_t ** 2 + 1 / f_M ** 2)


def campbell(f1, N_min, N_max, Z):
    """Eccitazioni che attraversano f1 nel campo di giri: lista di (nome, giri di risonanza)."""
    out = []
    for nome, k in (("1 x giro", 1), (f"{Z} x giro (passaggio pale)", Z), (f"{2 * Z} x giro", 2 * Z)):
        N_ris = f1 * 60 / k
        if N_min <= N_ris <= N_max:
            out.append((nome, N_ris))
    return out


def margine_campbell(f1, N_op, Z):
    """Distanza relativa minima tra f1 e le eccitazioni al punto di esercizio."""
    ecc = [k * N_op / 60 for k in (1, Z, 2 * Z)]
    return min(abs(f1 - e) / f1 for e in ecc)


def pressione_critica(D_mm, t_mm, mat):
    Dm = (D_mm + t_mm) / 1000
    return 2 * mat["E"] / (1 - mat["nu"] ** 2) * (t_mm / 1000 / Dm) ** 3


def sforzo_flessione(L_mm, D_mm, t_mm, M_kg, n_g):
    if L_mm <= 1:
        return 0.0
    _, Do, I, _ = proprieta_tubo(D_mm, t_mm)
    Mf = M_kg * n_g * 9.81 * (L_mm / 1000) / 4
    return Mf * (Do / 2) / I


def rigidezza_telaio(layout, t_mm, mat):
    """Rigidezza flessionale equivalente portata dai condotti (N m^2) per ciascun asse.

    Somma, per i tratti paralleli all'asse, di E (I_proprio + A r^2 / 2) pesata
    con la frazione di lato coperta: misura relativa di quanto i condotti,
    se incollati alla struttura, irrigidiscono il cubo.
    """
    out = np.zeros(3)
    for u in layout.unita:
        for perc in [u.tronco] + list(u.rami):
            P = perc.punti
            for i in range(len(P) - 1):
                d = P[i + 1] - P[i]
                ln = np.linalg.norm(d)
                if ln < 1e-6:
                    continue
                ax = int(np.argmax(np.abs(d)))
                if abs(d[ax]) / ln < 0.98:
                    continue
                _, Do, I, A = proprieta_tubo(perc.D, t_mm)
                m = 0.5 * (P[i] + P[i + 1]) / 1000
                r2 = float(m @ m - m[ax] ** 2)
                out[ax] += mat["E"] * (I + A * r2 / 2) * (ln / layout.L)
    return out
