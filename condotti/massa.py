"""Bilancio di massa del cubo: telaio, condotti, propulsione, componenti.

Serve a confrontare le configurazioni sulla massa che ciascuna si porta
dietro solo per avere quei condotti, e a vedere se l'obiettivo di massa è a
rischio.  Ogni voce è una stima parametrica con i parametri in INPUT.py
(sezione TELAIO, valori SEGNAPOSTO finché non si pesa un prototipo).

Voci (kg)
  guscio            pannelli delle 6 facce: rho * t_equivalente * area, meno le superfici
                    dei volumetti d'angolo (il vertice è aperto).
  telaio            longheroni sugli spigoli, meno i tratti tolti dai volumetti; 8 nodi di vertice.
  condotti          pareti dei tubi, curve e ugelli: rho * pi (D + t) t * lunghezza
  alloggiamenti     anello più spesso attorno al rotore (lunghezza della ventola) + statore
  staffe            1 ogni 'passo_staffe_mm' di condotto + 1 per curva, massa proporzionale a D
  bocche            flangia attorno a ogni foro nel guscio (se ci sono) + rete delle griglie
  motori e rotori, regolatori ESC, cablaggi della propulsione
  viteria e colla   frazione delle voci strutturali
  componenti        batteria, ruote, avionica, sensori... (COMPONENTI e MASSE_FISSE)
"""
import math
import numpy as np

from .costruttore import _segmenti, _lunghezza_seq

STRUTTURALI = ("guscio", "telaio", "struttura portante", "condotti", "alloggiamenti ventola", "staffe", "bocche (flange e griglie)")
GRUPPI = {
    "telaio e guscio": ("guscio", "telaio", "struttura portante", "viteria e colla"),
    "condotti e supporti": ("condotti", "alloggiamenti ventola", "staffe", "bocche (flange e griglie)"),
    "propulsione (motori, ESC, cavi)": ("motori e rotori", "regolatori ESC", "cablaggi propulsione"),
    "componenti fissi": ("componenti fissi",),
}


def _tubo(rho, D_mm, t_mm, L_mm):
    return rho * math.pi * (D_mm + t_mm) / 1000 * t_mm / 1000 * L_mm / 1000


def _sul_guscio(pos, h):
    pos = np.asarray(pos)
    return abs(np.max(np.abs(pos)) - h) < 1.0


def bilancio_massa(layout, cfg, motore, D_mm, volume_struttura_mm3=0.0):
    te = cfg["telaio"]
    el = cfg["elementi"]
    mat_c = cfg["materiali"][cfg["materiale_condotto"]]
    mat_g = cfg["materiali"][te["materiale_guscio"]]
    td = cfg["geometria"]["parete_condotto_mm"]
    L = layout.L
    h = L / 2
    n = len(layout.unita)
    voci = {}
    # --- bocche: fori nel guscio (se una presa o uscita sta sulla faccia) e griglie
    fori, griglie = [], []
    for u in layout.unita:
        if _sul_guscio(u.ingresso["pos"], h):
            fori.append(u.ingresso["D"])
        fori += [us["D"] for us in u.uscite if _sul_guscio(us["pos"], h)]
        if el["griglia_ingresso"]:
            griglie.append(u.ingresso["D"])
        if el["griglia_uscita"]:
            griglie += [us["D"] for us in u.uscite]
    A_fori = sum(math.pi * d * d / 4 for d in fori)
    # --- volumetti d'angolo: si tolgono le superfici di guscio e i tratti di longherone
    A_vert, L_vert = 0.0, 0.0
    for mn, mx in layout.tacche:
        d = np.abs(np.asarray(mx) - np.asarray(mn))
        A_vert += d[0] * d[1] + d[1] * d[2] + d[0] * d[2]
        L_vert += float(np.sum(d))
    # --- guscio
    A_guscio = 6 * L * L - A_fori - A_vert
    voci["guscio"] = mat_g["rho"] * te["spessore_equivalente_guscio_mm"] / 1000 * A_guscio * 1e-6
    # --- telaio
    L_long = 12 * L - L_vert
    n_nodi = 8
    voci["telaio"] = te["massa_longherone_g_per_m"] / 1000 * L_long / 1000 + n_nodi * te["massa_nodo_g"] / 1000
    # --- struttura portante (pareti piene e travi attorno ai condotti): sostituisce guscio, telaio e staffe.
    # Si stampa con riempimento parziale: la massa è densità x riempimento x volume pieno.
    portante = "spessore_parete_faccia_mm" in layout.parametri
    voci["struttura portante"] = 0.0
    if portante:
        phi = layout.parametri["riempimento"]
        skin = (6 * L * L - A_fori - A_vert) * cfg["geometria"]["parete_cubo_mm"]      # mm^3: pelle esterna
        voci["struttura portante"] = mat_g["rho"] * phi * (volume_struttura_mm3 + skin) * 1e-9
        voci["guscio"] = 0.0
        voci["telaio"] = 0.0
    # --- condotti, alloggiamenti, staffe
    m_cond, n_staffe, L_cond = 0.0, 0, 0.0
    for u in layout.unita:
        for perc in [u.tronco] + list(u.rami):
            seq, _ = _segmenti(perc)
            Lp = _lunghezza_seq(seq)
            L_cond += Lp
            m_cond += _tubo(mat_c["rho"], perc.D, td, Lp)
            n_staffe += math.ceil(Lp / te["passo_staffe_mm"]) + sum(1 for x in seq if x[0] == "curva")
    voci["condotti"] = m_cond
    t_h = te["spessore_alloggiamento_ventola_mm"]
    L_f = el["lunghezza_ventola_su_D"] * D_mm
    n_stat = sum(1 for u in layout.unita if u.statore and el["statore"])
    voci["alloggiamenti ventola"] = (n * _tubo(mat_c["rho"], D_mm, t_h, L_f)
                                     + n_stat * te["massa_statore_g_a_D30"] / 1000 * (D_mm / 30) ** 2)
    voci["staffe"] = 0.0 if portante else n_staffe * te["massa_staffa_g_a_D30"] / 1000 * D_mm / 30
    # --- bocche
    w, t_f = te["larghezza_flangia_bocca_mm"], te["spessore_flangia_bocca_mm"]
    m_fl = sum(mat_g["rho"] * t_f / 1000 * math.pi * ((d / 2 + w) ** 2 - (d / 2) ** 2) * 1e-6 for d in fori)
    m_gr = sum(te["densita_rete_griglia_g_m2"] / 1000 * math.pi * d * d / 4 * 1e-6 for d in griglie)
    voci["bocche (flange e griglie)"] = m_fl + m_gr
    # --- propulsione
    rot = cfg["rotore"]
    m_rot = rot["massa_rif_g"] / 1000 * (D_mm / rot["D_rif_mm"]) ** 3
    voci["motori e rotori"] = n * (motore.massa_g / 1000 + m_rot)
    voci["regolatori ESC"] = math.ceil(n / 4) * te["massa_esc_4in1_g"] / 1000
    voci["cablaggi propulsione"] = n * te["massa_cablaggio_per_motore_g"] / 1000
    voci["viteria e colla"] = te["frazione_viteria_colla"] * sum(voci[k] for k in STRUTTURALI)
    # --- componenti fissi
    fissi = {k: v["massa_kg"] for k, v in cfg["componenti"].items() if v.get("massa_kg") is not None}
    fissi.update(cfg["masse_fisse"])
    voci["componenti fissi"] = sum(fissi.values())
    tot = sum(voci.values())
    gruppi = {g: sum(voci[k] for k in ks) for g, ks in GRUPPI.items()}
    return {"voci": voci, "gruppi": gruppi, "totale": tot, "componenti": fissi,
            "dipendente_dalla_configurazione": tot - voci["componenti fissi"],
            "dettagli": {"lato_cubo_mm": L, "area_guscio_m2": A_guscio * 1e-6, "fori_nel_guscio": len(fori),
                         "superficie_vertici_tolta_m2": A_vert * 1e-6,
                         "longheroni_m": L_long / 1000, "nodi": n_nodi, "staffe": n_staffe,
                         "lunghezza_condotti_mm": L_cond}}
