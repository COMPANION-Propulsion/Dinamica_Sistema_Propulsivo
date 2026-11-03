"""Libreria delle correlazioni di perdita di carico.

Ogni coefficiente K è riferito a una velocità precisa, indicata nella
docstring: Delta p = K * 1/2 * rho * v_rif^2. Sbagliare la velocità di
riferimento è l'errore più comune nei calcoli di rete: per questo ogni
funzione la dichiara.

Fonti principali
  [IDL] I.E. Idelchik, Handbook of Hydraulic Resistance, 3rd ed.
  [MIL] D.S. Miller, Internal Flow Systems, 2nd ed.
  [HAA] S.E. Haaland, J. Fluids Eng. 105 (1983) 89-90.
  [GIB] A.H. Gibson, diffusori conici (riportato in [IDL] e [MIL]).
  [AMCA] AMCA Publication 201, Fans and Systems (effetto di sistema).
Le funzioni restituiscono (K, avvisi) quando la correlazione può uscire
dal suo campo di validità.
"""
import math
import numpy as np


# --------------------------------------------------------------- attrito
def fattore_attrito(Re, rugosita_relativa=0.0):
    """Fattore d'attrito di Darcy lambda.

    Laminare (Re <= 2300): 64/Re.  Turbolento (Re >= 4000): Haaland [HAA],
    scarto < 2 % rispetto a Colebrook.  Transizione: interpolazione lineare
    tra i due valori agli estremi (scelta prudente: in transizione il valore
    reale oscilla).
    """
    if Re <= 0:
        return 0.0
    if Re <= 2300.0:
        return 64.0 / Re

    def haaland(R):
        return (-1.8 * math.log10((rugosita_relativa / 3.7) ** 1.11 + 6.9 / R)) ** -2

    if Re >= 4000.0:
        return haaland(Re)
    f_lam, f_tur = 64.0 / 2300.0, haaland(4000.0)
    w = (Re - 2300.0) / 1700.0
    return (1 - w) * f_lam + w * f_tur


# --------------------------------------------------------------- griglie
_RE_GRIGLIA = np.array([50, 100, 150, 200, 300, 400, 500])
_KRE_GRIGLIA = np.array([1.44, 1.24, 1.14, 1.08, 1.04, 1.01, 1.00])


def k_griglia(porosita, Re_filo):
    """Griglia a fili tondi [IDL, diagr. 8-6].

    K riferito alla velocità a monte nella sezione piena della griglia.
    K = k_Re * [1.3 (1 - f) + (1/f - 1)^2], con f = area libera / area
    totale e Re_filo = (v / f) d_filo / nu.
    """
    avvisi = []
    f = float(porosita)
    if not 0.2 <= f <= 0.95:
        avvisi.append(f"porosità griglia {f:.2f} fuori dal campo 0,2-0,95 della correlazione")
    k_quad = 1.3 * (1 - f) + (1 / f - 1) ** 2
    if Re_filo >= 500:
        k_re = 1.0
    elif Re_filo >= 50:
        k_re = float(np.interp(math.log(Re_filo), np.log(_RE_GRIGLIA), _KRE_GRIGLIA))
    else:
        k_re = 1.44 * (50.0 / max(Re_filo, 1.0)) ** 0.3
        avvisi.append(f"Re del filo {Re_filo:.0f} < 50: correzione estrapolata")
    return k_re * k_quad, avvisi


# --------------------------------------------------------------- imbocco
_RD_IMB = np.array([0.0, 0.02, 0.04, 0.06, 0.10, 0.15, 0.20])
_K_IMB = np.array([0.50, 0.28, 0.24, 0.15, 0.09, 0.04, 0.03])


def k_imbocco(r_su_D):
    """Imbocco a filo parete con bordo raggiato [IDL diagr. 3-4, ASHRAE].

    K riferito alla velocità nel condotto. r/D = 0 è lo spigolo vivo (0,5).
    """
    return float(np.interp(max(r_su_D, 0.0), _RD_IMB, _K_IMB))


# --------------------------------------------------------------- curve
def k_curva(R_su_D, angolo_deg, Re):
    """Curva liscia a sezione circolare [IDL diagr. 6-1].

    K (solo parte locale, l'attrito sull'arco si somma a parte) riferito
    alla velocità nel condotto: K = A1(delta) * B1(R/D) * k_Re.
    A1: 0.9 sin(delta) fino a 70°, 1 a 90°, 0.7 + 0.35 delta/90 da 100°.
    B1: 0.21 / (R/D)^2.5 per R/D < 1;  0.21 / sqrt(R/D) per R/D >= 1.
    Sotto R/D = 0.5 la formula diverge: si usa il gomito a spigolo vivo
    (K ~ 1.1 a 90°, scalato con A1) e si segnala.
    k_Re = 1 + 4400/Re (indicativa [IDL] per Re < 2e5, limitata a 1.5).
    """
    avvisi = []
    d = abs(angolo_deg)
    if d < 1e-6:
        return 0.0, avvisi
    if d <= 70:
        A1 = 0.9 * math.sin(math.radians(d))
    elif d <= 90:
        A1 = float(np.interp(d, [70, 90], [0.9 * math.sin(math.radians(70)), 1.0]))
    elif d <= 100:
        A1 = float(np.interp(d, [90, 100], [1.0, 0.7 + 0.35 * 100 / 90]))
    else:
        A1 = 0.7 + 0.35 * d / 90
    if R_su_D < 0.5:
        avvisi.append(f"raggio di curvatura R/D = {R_su_D:.2f} < 0,5: trattata come gomito a spigolo vivo")
        B1 = 1.1
    elif R_su_D < 1.0:
        B1 = 0.21 / R_su_D ** 2.5
    else:
        B1 = 0.21 / math.sqrt(R_su_D)
    k_re = min(1.0 + 4400.0 / max(Re, 1.0), 1.5) if Re < 2e5 else 1.0
    return A1 * B1 * k_re, avvisi


# --------------------------------------------------------------- ugello / diffusore
_ANG_GIB = np.array([4, 6, 8, 10, 15, 20, 30, 45, 60, 180])
_PHI_GIB = np.array([0.14, 0.13, 0.135, 0.16, 0.27, 0.43, 0.81, 1.0, 1.05, 1.0])


def k_ugello(sigma, semiangolo_deg):
    """Tratto conico a valle della ventola (Venturi convergente o diffusore).

    sigma = A_uscita / A_ingresso.
    Convergente (sigma < 1): K = 0.02 + 0.05 (semiangolo/30°), riferito
      alla velocità di USCITA; perdita piccola, ma restringere aumenta la
      velocità del getto e quindi la potenza a pari spinta.
    Divergente (sigma > 1, Gibson [GIB]): Dp = phi(2 theta) (1 - 1/sigma)^2
      * 1/2 rho v_in^2; si restituisce K riferito alla velocità di USCITA
      (moltiplicando per sigma^2).  Oltre 12° di angolo totale c'è rischio
      di distacco.
    Ritorna (K_rif_uscita, avvisi).
    """
    avvisi = []
    th = abs(semiangolo_deg)
    if abs(sigma - 1.0) < 1e-6:
        return 0.0, avvisi
    if sigma < 1.0:
        if th > 30:
            avvisi.append(f"convergente con semiangolo {th:.0f}° > 30°: perdita sottostimata")
        return 0.02 + 0.05 * min(th, 45) / 30.0, avvisi
    ang_tot = 2 * th
    phi = float(np.interp(ang_tot, _ANG_GIB, _PHI_GIB))
    if ang_tot > 12:
        avvisi.append(f"diffusore con angolo totale {ang_tot:.0f}° > 12°: rischio di distacco della vena")
    k_in = phi * (1 - 1 / sigma) ** 2
    return k_in * sigma ** 2, avvisi


# --------------------------------------------------------------- effetto di sistema
def k_effetto_sistema_curva_monte(R_su_D, distanza_su_D):
    """Curva a monte della ventola a meno di 2,5 D (effetto di sistema).

    Valori indicativi ispirati ad AMCA 201: il profilo distorto che arriva
    sulla girante peggiora la ventola come una perdita aggiuntiva.
    K riferito alla velocità nel condotto, decresce linearmente a zero a 2,5 D.
    """
    if distanza_su_D >= 2.5:
        return 0.0
    K0 = float(np.interp(R_su_D, [0.5, 0.75, 1.0, 1.5, 2.0, 3.0], [1.2, 0.8, 0.5, 0.4, 0.3, 0.2]))
    return K0 * (1 - max(distanza_su_D, 0.0) / 2.5)


def k_effetto_sistema_valle(distanza_su_D, con_statore):
    """Curva a valle della ventola a meno di 2,5 D.

    Senza statore il flusso esce con vortice e la perdita aumenta.
    Valori indicativi (AMCA 201): 0,3 senza statore, 0,1 con statore.
    K riferito alla velocità nel condotto.
    """
    if distanza_su_D >= 2.5:
        return 0.0
    K0 = 0.1 if con_statore else 0.3
    return K0 * (1 - max(distanza_su_D, 0.0) / 2.5)
