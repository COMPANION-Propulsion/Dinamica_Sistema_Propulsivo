"""Realizzabilità pratica e numero di parti.

Il punteggio di realizzabilità (0-1) combina, con pesi in INPUT.py:
  parti      numero di pezzi stampati (i condotti più lunghi del piatto di
             stampa si dividono in più pezzi con giunti)
  curve      numero di curve e raggio minimo (R/D < 1 richiede supporti)
  attuatori  motori (cablaggi, regolatori, guasti)
  stampa     quota di pezzi che non stanno sul piatto o richiedono supporti
I riferimenti (0 punti / 1 punto) sono in REALIZZABILITA.
La massa è in massa.py.
"""
import math

from .costruttore import _segmenti, _lunghezza_seq


def _scala(x, x0, x1):
    """0 a x0, 1 a x1 (funziona anche con x1 < x0), limitato a [0, 1]."""
    if x1 == x0:
        return 1.0
    return float(min(max((x - x0) / (x1 - x0), 0.0), 1.0))


def caratteristiche(layout, cfg):
    mat = cfg["materiali"][cfg["materiale_condotto"]]
    piatto = mat["stampabile_max_mm"]
    n_parti, n_curve, R_min, lung_tot = 0, 0, math.inf, 0.0
    n_lunghi, n_supporti, firme = 0, 0, set()
    n_motori = len(layout.unita)
    n_prese = len(layout.unita)
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
        n_parti += 1                              # alloggiamento ventola + statore
        firme.add(tuple(sorted(firma)))
    n_parti += n_prese + n_uscite                 # griglie
    return {"parti": n_parti, "curve": n_curve,
            "R_su_D_minimo": R_min if R_min < math.inf else None,
            "lunghezza_condotti_mm": lung_tot, "condotti_oltre_piatto": n_lunghi,
            "pezzi_con_supporti": n_supporti, "tipi_di_pezzo_diversi": len(firme),
            "motori": n_motori, "attuatori": n_motori,
            "prese": n_prese, "uscite": n_uscite}


def punteggio_realizzabilita(car, cfg):
    r = cfg["realizzabilita"]
    p = r["pesi"]
    s_parti = _scala(car["parti"], *r["parti_rif"])
    s_curve = _scala(car["curve"], *r["curve_rif"])
    if car["R_su_D_minimo"] is not None and car["R_su_D_minimo"] < 0.75:
        s_curve *= 0.8
    s_att = _scala(car["attuatori"], *r["attuatori_rif"])
    tot_p = max(car["parti"], 1)
    s_stampa = 1 - min((car["condotti_oltre_piatto"] + car["pezzi_con_supporti"]) / tot_p * 3, 1.0)
    s_stampa = 0.8 * s_stampa + 0.2 * _scala(car["tipi_di_pezzo_diversi"], 8, 1)
    sub = {"parti": s_parti, "curve": s_curve, "attuatori": s_att, "stampa": s_stampa}
    tot = sum(p[k] * sub[k] for k in p) / sum(p.values())
    return tot, sub
