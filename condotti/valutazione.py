"""Valutazione completa di un progetto (scenario + diametro + elementi).

Catena:
  1 geometria e spazio interno (voxel, zone riservate, componenti)
  2 fluidodinamica al punto di progetto per ogni classe di unità uguali
  3 autorità di controllo, guasti, ingestione dei getti
  4 dinamica (salita della spinta, margine di fase, ruote di reazione)
  5 struttura (frequenze, Campbell, instabilità, carichi in g, rigidezza)
  6 realizzabilità, robustezza, punteggi
"""
import copy
import itertools
import math
import numpy as np

from . import geometria as G
from . import rete as R
from . import prestazioni as PR
from . import dinamica as DY
from . import struttura as ST
from . import realizzabilita as RZ
from .scenari import genera_layout
from .costruttore import costruisci_unita, costruisci_plenum, _segmenti
from .realizzabilita import _scala


# =========================================================================
# 1. Geometria e spazio
# =========================================================================
def _dims_esc(cfg, n_motori):
    a, b, c = cfg["esc_4in1_mm"]
    n = math.ceil(n_motori / 4)
    return (a, b, c * n)


def valuta_geometria(sc, D, cfg, variante=None, colloca_componenti=None):
    sc2 = dict(sc, **(variante or {}))
    g = cfg["geometria"]
    td = g["parete_condotto_mm"]
    lay = genera_layout(sc2, D, 1.0, cfg)
    gioco, coppia = G.gioco_minimo(lay, td)
    vox = cfg["esecuzione"]["risoluzione_voxel_mm"]
    gr = G.Griglia3D(g["lato_cubo_mm"], g["parete_cubo_mm"], vox)
    for u in lay.unita:
        for p, q, r, _ in G.tubi_unita(u, td):
            gr.capsula(p, q, r, G.COD_CONDOTTI)
    # servo delle valvole: piccolo box accanto al primo tratto del ramo
    for u in lay.unita:
        for vv in u.valvole:
            perc = u.rami[vv["ramo"]]
            m = 0.5 * (perc.punti[0] + perc.punti[1])
            d = perc.punti[1] - perc.punti[0]
            d = d / max(np.linalg.norm(d), 1e-9)
            n_ = np.cross(d, np.eye(3)[u.asse])
            if np.linalg.norm(n_) < 1e-6:
                n_ = np.cross(d, np.eye(3)[(u.asse + 1) % 3])
            n_ = n_ / np.linalg.norm(n_)
            c = m + n_ * (perc.D / 2 + td + 12)
            gr.box(c - np.array([12, 12, 12]), c + np.array([12, 12, 12]), G.COD_EXTRA)
    # ingresso dell'aria nel plenum: corridoio libero dietro la griglia
    if lay.plenum is not None:
        ax, sg = lay.plenum["faccia"]
        mn, mx = G.box_dietro_faccia(lay.L, lay.parete, ax, sg, 100, 100, 25)
        gr.box(mn, mx, G.COD_EXTRA)
    f_condotti = gr.volume_frazione({G.COD_CONDOTTI})
    f_extra = gr.volume_frazione({G.COD_EXTRA})
    sovrapp = {}
    for nome, (ax, sg, wu, wv, dep) in cfg["zone_riservate"].items():
        mn, mx = G.box_dietro_faccia(lay.L, lay.parete, ax, sg, wu, wv, dep)
        n_occ = gr.conta_box(mn, mx)
        if n_occ:
            sovrapp[nome] = n_occ * vox ** 3 / 1000.0          # cm^3
        gr.box(mn, mx, G.COD_RISERVATO)
    f_libero_prima = 1 - gr.volume_frazione()
    viol_facce = _bocche_in_zone_centrali(lay, cfg)
    irrealizzabile = any("IRREALIZZABILE" in a for a in lay.avvisi)
    if colloca_componenti is None:     # inutile collocare se i condotti sono già inammissibili
        colloca_componenti = gioco >= 0 and not sovrapp and not viol_facce and not irrealizzabile
    # componenti
    occ_base = gr.occ.copy()
    comp = dict(cfg["componenti"])
    for k, v in comp.items():
        if v["dim"] is None:
            comp[k] = dict(v, dim=_dims_esc(cfg, len(lay.unita)))
    nomi = list(comp.keys())
    batt = [n for n in nomi if comp[n]["criterio"] == "faccia_sportellino"]
    altri = [n for n in nomi if n not in batt]
    migliore = None
    ordini = list(itertools.permutations(altri))[:4] if colloca_componenti else []
    if not ordini:
        migliore = (0, {n: None for n in nomi}, occ_base.copy())
    for perm in ordini:
        gr.occ = occ_base.copy()
        collocati = {}
        for n in batt + list(perm):
            vinc = cfg["faccia_sportellino"] if comp[n]["criterio"] == "faccia_sportellino" else None
            r = G.colloca(gr, comp[n]["dim"], "centro", G.COD_COMP, vincolo_faccia=vinc)
            collocati[n] = r
        n_ok = sum(1 for r in collocati.values() if r is not None)
        if migliore is None or n_ok > migliore[0]:
            migliore = (n_ok, collocati, gr.occ.copy())
        if n_ok == len(nomi):
            break
    n_ok, collocati, occ_finale = migliore
    gr.occ = occ_finale
    f_libero_dopo = 1 - gr.volume_frazione()
    # i componenti che non entrano occupano comunque volume: si sottraggono,
    # altrimenti un progetto che non li accoglie sembrerebbe il più spazioso
    V_int = (2 * gr.h_int) ** 3
    V_mancanti = sum(float(np.prod(comp[n]["dim"])) for n, r in collocati.items() if r is None)
    f_libero_dopo = f_libero_dopo - V_mancanti / V_int
    cubo = G.cubo_libero_massimo(gr.occ, vox)
    sfera = G.sfera_libera_massima(gr.occ, vox)
    car = RZ.caratteristiche(lay, cfg)
    return {"layout": lay, "D": D, "variante": variante or {}, "gioco_min_mm": gioco, "coppia_critica": coppia,
            "frazione_condotti": f_condotti, "frazione_extra": f_extra, "frazione_libera_prima": f_libero_prima,
            "frazione_libera_dopo": f_libero_dopo, "sovrapposizioni_zone_cm3": sovrapp,
            "bocche_in_zone_centrali": viol_facce, "componenti": collocati,
            "componenti_tutti": n_ok == len(nomi), "componenti_valutati": bool(colloca_componenti),
            "cubo_libero_mm": cubo, "sfera_libera_mm": sfera,
            "realizzabilita": car, "irrealizzabile": irrealizzabile, "griglia": gr,
            "occ_senza_componenti": occ_base}


def _bocche_in_zone_centrali(lay, cfg):
    half = cfg["zona_centrale_facce_mm"] / 2
    h = lay.L / 2
    viol = []
    bocche = []
    for u in lay.unita:
        if u.ingresso is not None:
            bocche.append((u.nome + " presa", u.ingresso["pos"], u.ingresso["D"] / 2))
        for k, us in enumerate(u.uscite):
            bocche.append((f"{u.nome} uscita {k + 1}", us["pos"], us["D"] / 2))
    for nome, pos, r in bocche:
        pos = np.asarray(pos)
        ax = int(np.argmax(np.abs(pos)))
        if abs(abs(pos[ax]) - h) > 1.0:
            continue
        faccia = (ax, 1 if pos[ax] > 0 else -1)
        if faccia == cfg["faccia_libera"]:
            continue
        uu, vv = (ax + 1) % 3, (ax + 2) % 3
        dx = max(abs(pos[uu]) - half, 0.0)
        dy = max(abs(pos[vv]) - half, 0.0)
        if math.hypot(dx, dy) < r:
            viol.append(f"{nome} nella zona centrale della faccia {'+-'[faccia[1] < 0]}{'XYZ'[ax]}")
    return viol


def geometria_ammissibile(gm):
    return (gm["gioco_min_mm"] >= 0 and not gm["sovrapposizioni_zone_cm3"] and not gm["irrealizzabile"]
            and not gm["bocche_in_zone_centrali"])


# =========================================================================
# 2. Fluidodinamica
# =========================================================================
def _firma(u):
    parti = []
    for perc in [u.tronco] + list(u.rami):
        parti.append((round(float(np.sum(perc.lunghezze())), 1), tuple(round(a, 1) for a in perc.angoli()),
                      round(perc.D, 2)))
    return (tuple(parti), u.da_plenum, u.reversibile, len(u.rami))


def classi(layout):
    out = {}
    for u in layout.unita:
        out.setdefault(_firma(u), []).append(u)
    return list(out.values())


def unita_per_verso(layout):
    """Numero di unità che spingono in ciascun verso (le reversibili contano nei due)."""
    cont = {k: 0 for k in PR.DIREZIONI}
    for u in layout.unita:
        for k, (ax, sg) in PR.DIREZIONI.items():
            e = np.zeros(3); e[ax] = sg
            if float(u.verso @ e) > 0.9 or (u.reversibile and abs(float(u.verso @ e)) > 0.9):
                cont[k] += 1
    return cont


def N_limite(ventola, motore, cfg, aria):
    lim = cfg["limiti"]
    N_v = motore.N_max(cfg["elettrico"]["tensione_bus_V"], 0.0, cfg["elettrico"]["duty_massimo"])
    N_mach = lim["mach_punta_max"] * aria.a * 60 / (math.pi * ventola.D)
    N_u = lim["velocita_punta_max_m_s"] * 60 / (math.pi * ventola.D)
    return min(N_v, N_mach, N_u), {"tensione": N_v, "mach": N_mach, "velocita_punta": N_u}


def valuta_aero(lay_aero, cfg, D, sigma, tipo, motore, aria=None, completo=True):
    """Punto di progetto per ogni classe di unità; None se la spinta non si raggiunge."""
    aria = aria or cfg["aria_progetto"]
    F_asse = cfg["missione"]["spinta_per_asse_N"]
    cont = unita_per_verso(lay_aero)
    n_min = min(v for v in cont.values()) if cont else 0
    if n_min == 0:
        return None
    el = cfg["elettrico"]
    out = {"classi": [], "avvisi": []}
    Q_stima = 0.0
    for cl in classi(lay_aero):
        ug = cl[0]
        un, av = costruisci_unita(ug, cfg, tipo, D, sigma, motore)
        if un.ventola.nu > 0.7:
            return None
        pl = None
        if lay_aero.plenum is not None:
            pl, _ = costruisci_plenum(lay_aero, cfg, 0.05)
        N_lim, lim_det = N_limite(un.ventola, motore, cfg, aria)
        n_dir = max(min(cont[k] for k, (ax, sg) in PR.DIREZIONI.items() if ax == ug.asse), 1)
        F_u = F_asse / n_dir
        N_req = R.N_per_spinta(un, F_u, aria, N_lim, pl, direzione=ug.verso)
        if N_req is None:
            return None
        un.imposta_N(N_req)
        sol = R.risolvi([un], aria, pl)[un.nome]
        b = R.bilancio_unita(un, sol, aria)
        st = b["stato_ventola"]
        omega = N_req * 2 * math.pi / 60
        mp = motore.punto(st["coppia"], N_req, el["tensione_bus_V"], cfg["elementi"]["rendimento_esc"],
                          el["duty_massimo"])
        U = un.ventola.U(N_req)
        ve = [q / R.area(r.uscita.D) for q, r in zip(sol["Q_rami"], un.rami)]
        frac_perdite = b["P_perdite"] / max(b["P_utile_ventola"], 1e-9)
        # spinta massima (per l'allocazione) e modi con valvola parzializzata
        modi = []
        if completo:
            for u_ in cl:
                modi.extend(_modi_unita(u_, cfg, tipo, D, sigma, motore, aria, N_lim, pl, None))
        un.imposta_N(N_req)
        out["classi"].append({
            "unita": [u_.nome for u_ in cl], "asse": ug.asse, "n_per_verso": n_dir, "F_unita": F_u,
            "N_req": N_req, "N_lim": N_lim, "limiti_N": lim_det, "Q": sol["Q"], "Q_rami": sol["Q_rami"],
            "v_uscita": ve, "dp_ventola": st["dp_utile"], "phi": st["phi"], "psi": st["psi"], "eta": st["eta"],
            "Re_pala": st["Re"], "stallo": st["stallo"], "U_punta": U, "Mach_punta": U / aria.a,
            "nu_mozzo": un.ventola.nu, "P_albero": st["P_albero"], "P_el": mp["P_el"], "I": mp["I"],
            "V": mp["V"], "duty": mp["duty"], "eta_motore": mp["eta_motore"],
            "ok_tensione": mp["ok_tensione"], "ok_corrente": mp["ok_corrente"],
            "perdite_W": b["perdite_cat_W"], "perdite_Pa": b["perdite_cat_Pa"], "P_perdite": b["P_perdite"],
            "P_getto": b["P_getto"], "P_utile": b["P_utile_ventola"], "frazione_perdite": frac_perdite,
            "coppia_rotore": st["coppia"], "coppia_corpo": st["coppia_corpo"], "omega": omega,
            "momento_unita": b["momento"], "forza_unita": b["forza"], "modi": modi, "avvisi": av,
            "unita_rete": un, "plenum": pl})
        Q_stima += sol["Q"]
    # potenza per asse (caso peggiore) e di picco
    P_asse = {}
    for c in out["classi"]:
        for nome in c["unita"]:
            ax = [u for u in lay_aero.unita if u.nome == nome][0].asse
            P_asse[ax] = max(P_asse.get(ax, 0.0), c["n_per_verso"] * c["P_el"])
    out["P_asse"] = P_asse
    out["P_asse_max"] = max(P_asse.values())
    out["P_picco_3assi"] = sum(sorted(P_asse.values(), reverse=True)[:cfg["missione"]["assi_contemporanei_max"]])
    out["I_picco"] = out["P_picco_3assi"] / el["tensione_bus_V"]
    out["ok_motore"] = all(c["ok_tensione"] and c["ok_corrente"] for c in out["classi"])
    out["ok_mach"] = all(c["Mach_punta"] <= cfg["limiti"]["mach_punta_max"] for c in out["classi"])
    out["stallo"] = any(c["stallo"] for c in out["classi"])
    # accoppiamento del plenum: tre assi insieme
    out["calo_spinta_3assi"] = _calo_plenum(lay_aero, out, cfg, aria) if completo else 0.0
    return out


def _modi_unita(ug, cfg, tipo, D, sigma, motore, aria, N_lim, pl, b_rif):
    """Vettori forza-momento alla massima spinta (con valvole e verso inverso)."""
    un, _ = costruisci_unita(ug, cfg, tipo, D, sigma, motore)
    un.imposta_N(N_lim)
    modi = []
    sol = R.risolvi([un], aria, pl)[un.nome]
    b = R.bilancio_unita(un, sol, aria)
    modi.append({"unita": ug.nome, "modo": "pieno", "w": np.concatenate([b["forza"], b["momento"]])})
    a_min = cfg["elementi"]["apertura_minima_valvola"]
    for vv in ug.valvole:
        ctx = {"aperture": {vv["nome"]: a_min}}
        sol = R.risolvi([un], aria, pl, ctx)[un.nome]
        b = R.bilancio_unita(un, sol, aria, ctx)
        modi.append({"unita": ug.nome, "modo": f"{vv['nome']} al {a_min:.0%}",
                     "w": np.concatenate([b["forza"], b["momento"]])})
    if ug.reversibile:
        F = -modi[0]["w"][:3]
        r = np.asarray(ug.ingresso["pos"]) / 1000
        modi.append({"unita": ug.nome, "modo": "inverso", "w": np.concatenate([F, np.cross(r, F)])})
    return modi


def _calo_plenum(lay, aero, cfg, aria):
    if lay.plenum is None:
        return 0.0
    # una unità per asse, ciascuna al proprio N di progetto
    scelte = {}
    for c in aero["classi"]:
        for nome in c["unita"]:
            ug = [u for u in lay.unita if u.nome == nome][0]
            if ug.asse not in scelte:
                scelte[ug.asse] = (c, nome)
    reti = []
    for ax, (c, nome) in scelte.items():
        un = copy.deepcopy(c["unita_rete"])
        un.nome = nome
        un.imposta_N(c["N_req"])
        reti.append((un, c))
    pl = aero["classi"][0]["plenum"]
    sol = R.risolvi([u for u, _ in reti], aria, pl)
    cali = []
    for un, c in reti:
        b = R.bilancio_unita(un, sol[un.nome], aria)
        cali.append(1 - b["spinta"] / c["F_unita"])
    return max(cali)


# =========================================================================
# 3-6. Valutazione completa
# =========================================================================
def valuta_completo(gm, aero, cfg, sc, tipo, motore, sigma):
    lay = gm["layout"]
    aria = cfg["aria_progetto"]
    lim = cfg["limiti"]
    F_asse = cfg["missione"]["spinta_per_asse_N"]
    res = {"scenario": sc["id"], "D": gm["D"], "sigma": sigma, "tipo_ventola": tipo.nome, "motore": motore.nome,
           "variante": gm["variante"]}
    # --- autorità e guasti
    modi = [m for c in aero["classi"] for m in c["modi"]]
    forze, momenti, uso = PR.autorita(modi)
    tol, guasto = PR.tolleranza_guasti(modi, F_asse)
    res.update({"forza_max_N": forze, "momento_max_Nm": momenti, "uso_per_verso": uso,
                "tolleranza_guasto": tol, "guasto_peggiore": guasto})
    # --- ingestione
    res.update(_ingestione(lay, aero, uso, cfg))
    # --- dinamica
    c0 = max(aero["classi"], key=lambda c: c["P_el"])
    rot = cfg["rotore"]
    m_rot = rot["massa_rif_g"] / 1000 * (gm["D"] / rot["D_rif_mm"]) ** 3
    J = motore.J_rotore + rot["k_inerzia"] * m_rot * (gm["D"] / 2000) ** 2
    t90, storia = DY.tempo_salita(motore, J, c0["N_req"], c0["coppia_rotore"],
                                  cfg["elettrico"]["tensione_bus_V"], cfg["elettrico"]["duty_massimo"])
    t_inv = DY.tempo_inversione(motore, J, c0["N_req"], c0["coppia_rotore"],
                                cfg["elettrico"]["tensione_bus_V"]) if any(u.reversibile for u in lay.unita) else None
    t_frenata = t_inv if t_inv is not None else t90
    pm = {wc: DY.margine_fase(t_frenata, wc) for wc in (1.0, 2.0, 4.0)}
    braccio = np.linalg.norm(c0["momento_unita"]) / max(np.linalg.norm(c0["forza_unita"]), 1e-9)
    accoppiate = c0["n_per_verso"] >= 2
    sq = lim["differenza_spinta_coppia"]
    reaz = sq * c0["coppia_corpo"] if accoppiate else c0["coppia_corpo"]
    H_rot = 0.0 if accoppiate else J * c0["omega"]
    rw = DY.bilancio_ruote(F_asse, cfg["geometria"]["scostamento_baricentro_mm"] / 1000, braccio, sq,
                           c0["F_unita"], reaz, H_rot, cfg["missione"]["finestra_libera_s"],
                           lim["momento_ruote_max_Nms"])
    tau_desat = min(momenti.values())
    t_desat = lim["momento_ruote_max_Nms"] / tau_desat if tau_desat > 1e-6 else math.inf
    res.update({"J_rotore": J, "t_salita_90": t90, "storia_salita": storia, "t_inversione": t_inv,
                "t_cambio_verso": t_frenata, "margine_fase": pm, "tau_max_PM45_2rads": DY.tau_max_per_margine(2.0),
                "ruote": rw, "coppia_desaturazione": tau_desat, "t_desaturazione": t_desat,
                "braccio_spinta_m": braccio})
    # --- struttura
    mat = cfg["materiali"][cfg["materiale_condotto"]]
    td = cfg["geometria"]["parete_condotto_mm"]
    ug = [u for u in lay.unita if u.nome == c0["unita"][0]][0]
    span, a_fr = _campata_ventola(ug)
    M_f = motore.massa_g / 1000 + m_rot
    f1 = ST.frequenza_tratto(span, gm["D"], td, mat, M_f, a_fr)
    cross = ST.campbell(f1, 0.3 * c0["N_req"], c0["N_lim"], tipo.Z)
    marg_c = ST.margine_campbell(f1, c0["N_req"], tipo.Z)
    p_cr = ST.pressione_critica(gm["D"], td, mat)
    un = c0["unita_rete"]
    un.imposta_N(c0["N_lim"])
    sol = R.risolvi([un], aria, c0["plenum"])[un.nome]
    prf = R.profili_unita(un, sol, aria)
    p_min = min(float(np.min(prf["tronco"]["p"])), *[float(np.min(r["p"])) for r in prf["rami"]])
    un.imposta_N(c0["N_req"])
    suzione = max(-p_min, 1.0)
    s18 = ST.sforzo_flessione(span, gm["D"], td, M_f, cfg["carichi"]["g_ipergravita"])
    s9 = ST.sforzo_flessione(span, gm["D"], td, M_f, cfg["carichi"]["g_atterraggio_emergenza"])
    EI = ST.rigidezza_telaio(lay, td, mat)
    m_prop = RZ.massa_propulsione(lay, cfg, motore, gm["D"])
    res.update({"campata_ventola_mm": span, "f1_Hz": f1, "risonanze_campbell": cross, "margine_campbell": marg_c,
                "p_critica_Pa": p_cr, "suzione_max_Pa": suzione, "margine_instabilita": p_cr / suzione,
                "sforzo_1_8g_MPa": s18 / 1e6, "sforzo_9g_MPa": s9 / 1e6,
                "margine_sforzo_9g": mat["sigma_snervamento"] / max(s9, 1.0),
                "EI_condotti_Nm2": EI, "massa_propulsione_kg": m_prop})
    # --- punteggi
    car = gm["realizzabilita"]
    s_real, sub_real = RZ.punteggio_realizzabilita(car, cfg)
    ott = cfg["ottimizzazione"]
    s_spazio = _scala(gm["frazione_libera_dopo"], *ott["scala_volume_libero"])
    if not gm["componenti_tutti"]:
        s_spazio *= 0.3
    frac_p = max(c["frazione_perdite"] for c in aero["classi"])
    s_perdite = 0.7 * _scala(aero["P_asse_max"], *ott["scala_potenza_asse_W"]) + 0.3 * (1 - min(frac_p, 1.0))
    s_rob = 0.6 * _scala(tol, 0.0, 1.0) + 0.3 * _scala(car["servo"], 12, 0) + 0.1 * (0.0 if lay.plenum else 1.0)
    s_ing = _scala(res["ingestione_peggiore"], lim["indice_ingestione_critico"], lim["indice_ingestione_attenzione"])
    s_din = (0.4 * _scala(t_frenata, *ott["scala_tempo_salita_s"]) + 0.4 * s_ing
             + 0.2 * _scala(t_desat, 30.0, 2.0))
    punteggi = {"spazio": s_spazio, "perdite": s_perdite, "semplicita": s_real, "robustezza": s_rob,
                "dinamica": s_din}
    pesi = ott["pesi"]
    totale = sum(pesi[k] * punteggi[k] for k in pesi) / sum(pesi.values())
    P_ax = max(aero["P_asse_max"], 1e-9)
    res["assi_pieni_ammessi"] = int(min(3, (cfg["elettrico"]["corrente_max_pacco_A"] * cfg["elettrico"]["tensione_bus_V"]) // P_ax))
    viol = _violazioni(gm, aero, res, cfg)
    res.update({"punteggi": punteggi, "sotto_realizzabilita": sub_real, "punteggio_totale": totale,
                "violazioni": viol, "ammissibile": not viol, "avvisi": avvisi_progetto(gm, aero, res, cfg)})
    return res


def _campata_ventola(ug):
    """Lunghezza del segmento di polilinea che contiene la ventola e posizione relativa."""
    P = ug.tronco.punti
    s = 0.0
    for i in range(len(P) - 1):
        ln = float(np.linalg.norm(P[i + 1] - P[i]))
        if s <= ug.s_ventola <= s + ln:
            return ln, (ug.s_ventola - s) / ln
        s += ln
    return float(np.linalg.norm(P[-1] - P[-2])), 0.5


def _ingestione(lay, aero, uso, cfg):
    per_unita = {}
    for c in aero["classi"]:
        for nome in c["unita"]:
            per_unita[nome] = c
    comandi = PR.comandi_combinati(cfg["missione"]["assi_contemporanei_max"])
    risultati = {}
    pl = lay.plenum
    for cmd in comandi:
        attive = set()
        for verso in cmd:
            attive.update(uso.get(verso, []))
        uscite, prese = [], []
        Q_plenum = 0.0
        for u in lay.unita:
            if u.nome not in attive:
                continue
            c = per_unita[u.nome]
            inv = False
            if u.reversibile:
                sg = [1 if v[0] == "+" else -1 for v in cmd if "XYZ".index(v[1]) == u.asse]
                inv = bool(sg) and float(u.verso[u.asse]) * sg[0] < 0
            for k, us in enumerate(u.uscite):
                if inv:
                    uscite.append({"pos": np.asarray(u.ingresso["pos"]) / 1000, "getto": np.asarray(u.ingresso["normale"]),
                                   "D": u.ingresso["D"] / 1000, "V": c["v_uscita"][0], "unita": u.nome})
                else:
                    uscite.append({"pos": np.asarray(us["pos"]) / 1000, "getto": np.asarray(us["getto"]),
                                   "D": us["D"] / 1000, "V": c["v_uscita"][min(k, len(c["v_uscita"]) - 1)],
                                   "unita": u.nome})
            if u.da_plenum:
                Q_plenum += c["Q"]
            elif inv:
                prese.append({"pos": np.asarray(u.uscite[0]["pos"]) / 1000, "normale": -np.asarray(u.uscite[0]["getto"]),
                              "Q": c["Q"], "D": u.uscite[0]["D"] / 1000, "unita": u.nome})
            else:
                prese.append({"pos": np.asarray(u.ingresso["pos"]) / 1000, "normale": np.asarray(u.ingresso["normale"]),
                              "Q": c["Q"], "D": u.ingresso["D"] / 1000, "unita": u.nome})
        if pl is not None and Q_plenum > 0:
            A_g = aero["classi"][0]["plenum"].A_griglia
            prese.append({"pos": np.asarray(pl["pos"]) / 1000, "normale": np.asarray(pl["normale"]),
                          "Q": Q_plenum, "D": math.sqrt(4 * A_g / math.pi), "unita": "plenum"})
        peggiore, coppia = 0.0, None
        for us in uscite:
            for pr in prese:
                if pr["unita"] == us["unita"]:
                    continue
                idx = PR.indice_ingestione(us, pr)
                if idx > peggiore:
                    peggiore, coppia = idx, (us["unita"], pr["unita"])
        risultati[" ".join(cmd)] = {"indice": peggiore, "coppia": coppia}
    vals = [r["indice"] for r in risultati.values()]
    crit = [k for k, r in risultati.items() if r["indice"] > cfg["limiti"]["indice_ingestione_critico"]]
    return {"ingestione_per_comando": risultati, "ingestione_peggiore": max(vals) if vals else 0.0,
            "comandi_critici": crit}


def _violazioni(gm, aero, res, cfg):
    v = []
    if gm["irrealizzabile"]:
        v.append("geometria irrealizzabile (zone d'estremità oltre il mezzo spigolo)")
    if gm["gioco_min_mm"] < 0:
        v.append(f"condotti che si intersecano ({gm['gioco_min_mm']:.1f} mm)")
    if gm["sovrapposizioni_zone_cm3"]:
        v.append("condotti dentro moduli riservati: " + ", ".join(gm["sovrapposizioni_zone_cm3"]))
    if gm["bocche_in_zone_centrali"]:
        v.append("bocche nelle zone centrali delle facce")
    if not gm["componenti_tutti"]:
        mancanti = [k for k, r in gm["componenti"].items() if r is None]
        v.append("componenti che non entrano: " + ", ".join(mancanti))
    if not aero["ok_motore"]:
        v.append("motore oltre tensione o corrente")
    if not aero["ok_mach"]:
        v.append("Mach di punta oltre il limite")
    return v


def avvisi_progetto(gm, aero, res, cfg):
    """Aspetti da tenere d'occhio che non bloccano il progetto."""
    a = []
    I_pk = cfg["elettrico"]["corrente_max_pacco_A"]
    if aero["I_picco"] > I_pk:
        a.append(f"con {cfg['missione']['assi_contemporanei_max']} assi a piena spinta servono {aero['I_picco']:.1f} A "
                 f"(pacco {I_pk:.0f} A): ammessi {res['assi_pieni_ammessi']} assi pieni insieme")
    if aero["stallo"]:
        a.append("ventola vicina alla zona di stallo al punto di progetto")
    if res["risonanze_campbell"]:
        a.append("il condotto attraversa una risonanza durante l'accelerazione della ventola")
    if res["comandi_critici"]:
        a.append(f"ingestione critica in {len(res['comandi_critici'])} comandi su più assi")
    if res["ruote"]["quota_ruota"] > 1:
        a.append("le ruote di reazione saturano nella finestra libera")
    if aero.get("calo_spinta_3assi", 0) > 0.05:
        a.append(f"plenum condiviso: -{aero['calo_spinta_3assi']:.0%} di spinta con 3 assi")
    return a
