"""Realizzabilità pratica, numero di parti, massa della propulsione, robustezza.

Il punteggio di realizzabilità (0-1) combina, con pesi in input.py:
  parti      numero di pezzi stampati (i condotti più lunghi del piatto di
             stampa si dividono in più pezzi con giunti)
  curve      numero di curve e raggio minimo (R/D < 1 richiede supporti)
  giunzioni  biforcazioni da stampare in un pezzo unico
  attuatori  motori + servo delle valvole (cablaggi, regolatori, guasti)
  stampa     quota di pezzi che non stanno sul piatto o richiedono supporti
I riferimenti (0 punti / 1 punto) sono in REALIZZABILITA.
"""
import math
import numpy as np

from .costruttore import _segmenti, _lunghezza_seq


def _scala(x, x0, x1):
    """0 a x0, 1 a x1 (funziona anche con x1 < x0), limitato a [0, 1]."""
    if x1 == x0:
        return 1.0
    return float(min(max((x - x0) / (x1 - x0), 0.0), 1.0))


def caratteristiche(layout, cfg):
    mat = cfg["materiali"][cfg["materiale_condotto"]]
    piatto = mat["stampabile_max_mm"]
    n_parti, n_curve, n_giunz, R_min, lung_tot = 0, 0, 0, math.inf, 0.0
    n_lunghi, n_supporti, firme = 0, 0, set()
    n_motori = len(layout.unita)
    n_servo = sum(len(u.valvole) for u in layout.unita)
    n_prese = sum(1 for u in layout.unita if u.ingresso is not None) + (1 if layout.plenum else 0)
    n_uscite = sum(len(u.uscite) for u in layout.unita)
    for u in layout.unita:
        percorsi = [u.tronco] + list(u.rami)
        firma = []
        for perc in percorsi:
            seq, _ = _segmenti(perc)
            L = _lunghezza_seq(seq)
            lung_tot += L
            pezzi = max(1, math.ceil(L / piatto))
            n_parti += pezzi
            if pezzi > 1:
                n_lunghi += 1
            for s in seq:
                if s[0] == "curva":
                    n_curve += 1
                    rd = s[1] / perc.D
                    R_min = min(R_min, rd)
                    if rd < 1.0:
                        n_supporti += 1
            firma.append((round(L), tuple(round(a) for a in perc.angoli())))
        if u.rami:
            n_giunz += 1
            n_parti += 1                          # corpo della giunzione
        n_parti += 1                              # alloggiamento ventola + statore
        firme.add(tuple(sorted(firma)))
    n_parti += n_prese + n_uscite                 # griglie
    n_parti += n_servo                            # corpi valvola
    return {"parti": n_parti, "curve": n_curve, "giunzioni": n_giunz,
            "R_su_D_minimo": R_min if R_min < math.inf else None,
            "lunghezza_condotti_mm": lung_tot, "condotti_oltre_piatto": n_lunghi,
            "pezzi_con_supporti": n_supporti, "tipi_di_pezzo_diversi": len(firme),
            "motori": n_motori, "servo": n_servo, "attuatori": n_motori + n_servo,
            "prese": n_prese, "uscite": n_uscite}


def punteggio_realizzabilita(car, cfg):
    r = cfg["realizzabilita"]
    p = r["pesi"]
    s_parti = _scala(car["parti"], *r["parti_rif"])
    s_curve = _scala(car["curve"], *r["curve_rif"])
    if car["R_su_D_minimo"] is not None and car["R_su_D_minimo"] < 0.75:
        s_curve *= 0.8
    s_giunz = _scala(car["giunzioni"], 6, 0)
    s_att = _scala(car["attuatori"], *r["attuatori_rif"])
    tot_p = max(car["parti"], 1)
    s_stampa = 1 - min((car["condotti_oltre_piatto"] + car["pezzi_con_supporti"]) / tot_p * 3, 1.0)
    s_stampa = 0.8 * s_stampa + 0.2 * _scala(car["tipi_di_pezzo_diversi"], 8, 1)
    sub = {"parti": s_parti, "curve": s_curve, "giunzioni": s_giunz, "attuatori": s_att, "stampa": s_stampa}
    tot = sum(p[k] * sub[k] for k in p) / sum(p.values())
    return tot, sub


def massa_propulsione(layout, cfg, motore, D_mm):
    mat = cfg["materiali"][cfg["materiale_condotto"]]
    t = cfg["geometria"]["parete_condotto_mm"]
    m = 0.0
    for u in layout.unita:
        for perc in [u.tronco] + list(u.rami):
            seq, _ = _segmenti(perc)
            L = _lunghezza_seq(seq) / 1000
            m += mat["rho"] * math.pi * (perc.D + t) / 1000 * t / 1000 * L
    n = len(layout.unita)
    rot = cfg["rotore"]
    m_rot = rot["massa_rif_g"] / 1000 * (D_mm / rot["D_rif_mm"]) ** 3
    m += n * (motore.massa_g / 1000 + m_rot)
    m += math.ceil(n / 4) * 0.012                                # schede ESC 4-in-1
    m += sum(len(u.valvole) for u in layout.unita) * 0.010      # micro servo
    m += (sum(1 for u in layout.unita if u.ingresso is not None) + sum(len(u.uscite) for u in layout.unita)) * 0.004
    if layout.plenum:
        m += 0.03
    return m
