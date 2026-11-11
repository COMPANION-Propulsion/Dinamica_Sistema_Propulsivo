"""Disturbo delle pale: rotori con pale stampate in 3D, ognuna con una densità un po' diversa.

Ogni pala è un parallelepipedo: lunghezza radiale L, larghezza (corda) c, spessore t, attaccato al mozzo di
raggio R_mozzo, quindi con il baricentro a r_cg = R_mozzo + L / 2.  Se le Z pale di un rotore hanno masse diverse, il baricentro del rotore esce
dall'asse e nasce lo squilibrio statico

    U = r_cg | sum_k m_k exp(i 2 pi k / Z) |           [kg m]

che a omega dà una forza rotante nel piano del rotore F = U omega^2, alla frequenza dei giri.  Sul cubo libero
(massa M) la forza a frequenza così alta, centinaia di Hz contro una banda del controllo sotto 1 Hz, non viene
contrastata dal regolatore: il cubo oscilla come una massa libera con ampiezza

    x = F / (M omega^2) = U / M      (non dipende dai giri)
    v = U omega / M,   a = U omega^2 / M

Per questo il disturbo non entra nella simulazione nel tempo (servirebbe un passo sotto 1/(20 f)): le ampiezze
sono in forma chiusa.  Il caso peggiore con Z pale in [m_min, m_max] è un gruppo di j pale vicine alla massa
massima e le altre alla minima: U = (m_max - m_min) r_cg max_j sin(j pi / Z) / sin(pi / Z), cioè
(m_max - m_min) r_cg con 2 o 3 pale, di più con 4 pale o più.

Momento angolare: ogni rotore porta H = (I_pale + J_motore) omega.  Le ventole di una coppia girano in versi
opposti; se le pale hanno densità diverse i due H non si annullano e il residuo va alle ruote di reazione.
"""
import math

import numpy as np


def geometria(pa):
    """Dimensioni di una pala (m) e volume (m^3) dal dizionario PALE."""
    L = pa["lunghezza_mm"] / 1000
    c, t = pa["larghezza_mm"] / 1000, pa["spessore_mm"] / 1000
    r_cg = pa["raggio_mozzo_mm"] / 1000 + L / 2
    return {"L_m": L, "corda_m": c, "spessore_m": t, "r_cg_m": r_cg, "volume_m3": L * c * t}


def squilibrio(masse, r_cg):
    """Squilibrio statico U (kg m) di un rotore; masse (..., Z), pale equispaziate."""
    masse = np.asarray(masse, float)
    Z = masse.shape[-1]
    fasi = np.exp(2j * math.pi * np.arange(Z) / Z)
    return np.abs(masse @ fasi) * r_cg


def fattore_peggiore(Z):
    """max |somma dei versori di un gruppo di pale|: j pale vicine, sin(j pi / Z) / sin(pi / Z) per j = Z // 2."""
    return max(math.sin(j * math.pi / Z) / math.sin(math.pi / Z) for j in range(1, Z))


def inerzia_pale(masse, g):
    """Momento d'inerzia attorno all'asse del rotore (kg m^2) delle pale: m (L^2 + c^2) / 12 + m r_cg^2.

    Con la corda tutta nel piano del rotore (calettamento nullo): è un limite superiore.
    """
    masse = np.asarray(masse, float)
    return np.sum(masse, axis=-1) * ((g["L_m"] ** 2 + g["corda_m"] ** 2) / 12 + g["r_cg_m"] ** 2)


def _stat(a):
    a = np.asarray(a, float)
    return {"media": float(a.mean()), "p95": float(np.percentile(a, 95)), "max": float(a.max())}


def analizza(pa, massa_cubo, spinta_max_N=None):
    """Disturbo delle pale: valori nominali, caso peggiore e Monte Carlo sulle densità delle pale."""
    g = geometria(pa)
    Z, N = int(pa["numero_pale"]), int(pa["campioni"])
    rho_min, rho_max = pa["densita_min_kg_m3"], pa["densita_max_kg_m3"]
    m_min, m_max = rho_min * g["volume_m3"], rho_max * g["volume_m3"]
    m_nom = 0.5 * (m_min + m_max)
    w = pa["giri_progetto_rpm"] * 2 * math.pi / 60
    w_max = pa["giri_massimi_rpm"] * 2 * math.pi / 60
    rng = np.random.default_rng(pa["seme"])

    # Monte Carlo: densità di ogni pala uniforme in [rho_min, rho_max], indipendente dalle altre
    masse = rng.uniform(rho_min, rho_max, (N, Z)) * g["volume_m3"]
    U = squilibrio(masse, g["r_cg_m"])
    U_peggiore = (m_max - m_min) * g["r_cg_m"] * fattore_peggiore(Z)
    I_nom = inerzia_pale(np.full(Z, m_nom), g)
    # coppia controrotante: due rotori estratti a caso, residuo del momento angolare (pale soltanto, il motore è uguale)
    masse_b = rng.uniform(rho_min, rho_max, (N, Z)) * g["volume_m3"]
    dH = np.abs(inerzia_pale(masse, g) - inerzia_pale(masse_b, g)) * w
    dH_peggiore = (inerzia_pale(np.full(Z, m_max), g) - inerzia_pale(np.full(Z, m_min), g)) * w

    def ampiezze(Uv):
        return {"squilibrio_g_mm": Uv * 1e6, "forza_N": Uv * w ** 2, "forza_ai_giri_massimi_N": Uv * w_max ** 2,
                "accelerazione_cubo_g": Uv * w ** 2 / massa_cubo / 9.80665,
                "spostamento_cubo_um": Uv / massa_cubo * 1e6, "velocita_cubo_mm_s": Uv * w / massa_cubo * 1e3}

    mc = {k: _stat(v) for k, v in ampiezze(U).items()}
    pg = {k: float(v) for k, v in ampiezze(U_peggiore).items()}
    ris = {
        "geometria_mm": {"lunghezza": g["L_m"] * 1e3, "corda": g["corda_m"] * 1e3, "spessore": g["spessore_m"] * 1e3,
                         "raggio_baricentro": g["r_cg_m"] * 1e3},
        "massa_pala_g": {"min": m_min * 1e3, "nominale": m_nom * 1e3, "max": m_max * 1e3},
        "frequenza_Hz": w / (2 * math.pi), "frequenza_ai_giri_massimi_Hz": w_max / (2 * math.pi),
        "monte_carlo": mc, "caso_peggiore": pg, "campioni": N, "seme": pa["seme"],
        "ventole_fuori_asse": int(pa["ventole_fuori_asse"]),
        "forza_peggiore_su_un_asse_N": pg["forza_N"] * pa["ventole_fuori_asse"],
        "spostamento_peggiore_su_un_asse_um": pg["spostamento_cubo_um"] * pa["ventole_fuori_asse"],
        "inerzia_pale_kgm2": float(I_nom),
        "momento_angolare_rotore_Nms": float((I_nom + pa["inerzia_rotore_motore_kgm2"]) * w),
        "residuo_coppia_Nms": {**_stat(dH), "peggiore": float(dH_peggiore)},
        "U_campioni_g_mm": U * 1e6,     # array, per il grafico (fuori dal JSON)
    }
    if spinta_max_N:
        ris["forza_peggiore_su_spinta"] = pg["forza_N"] / spinta_max_N
    return ris
