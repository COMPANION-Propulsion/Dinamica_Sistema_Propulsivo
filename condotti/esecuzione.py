"""Motore comune delle tre run (RUN_generica, RUN_S4_interazione, RUN_S4_dinamica).

Le tre run differiscono solo per il file di input, per il nome della run e per quali
grafici di scenario / confronto producono: la sequenza è la stessa.
  1  verifiche fisiche del codice contro risultati noti (si ferma se una fallisce)
  2  per ogni scenario attivo: ottimizzazione di lato, diametro, varianti geometriche,
     Venturi, ventola e motore; valutazione di spazio, perdite, controllo,
     dinamica, struttura, massa, realizzabilità
  3  grafici, Excel e riepilogo in una cartella nuova:
     output/<data-ora>_<nome run>_<etichetta>_<impronta>/
"""
import argparse
import copy
import csv
import datetime as dt
import json
import math
import os
import sys
import time
import traceback

import numpy as np

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # cartella del progetto
for _flusso in (sys.stdout, sys.stderr):        # accenti e simboli anche nella console di Windows
    try:
        _flusso.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from .config import carica, impronta
from .ottimizzazione import ottimizza_scenario
from . import grafici as GR
from . import output as OUT
from . import report_excel as XL
from . import verifiche as VF
from .ventole import libreria_motori, libreria_ventole

# gruppi di grafici di scenario (vedi grafici_scenario)
TUTTI_I_GRUPPI = {"viste", "sezioni", "profili", "ventola", "spinta", "perdite", "dinamica", "struttura", "ingestione"}


def _json(o):
    if isinstance(o, dict):
        return {str(k): _json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_json(v) for v in o.tolist()]
    if isinstance(o, (np.floating, np.integer)):
        o = o.item()
    if isinstance(o, float) and (math.isinf(o) or math.isnan(o)):
        return None
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o
    return str(o)


def grafici_scenario(r, cfg, cartella, formati, log, gruppi=TUTTI_I_GRUPPI):
    out = []
    sid = r["scenario"]["id"]
    o = r["ottimo"]
    base = os.path.join(cartella, "grafici", sid)
    tit = f"{sid} — {r['scenario']['nome']} — lato L = {o['L']:.0f} mm"
    try:
        if "viste" not in gruppi:
            raise StopIteration
        out += [("viste", p) for p in GR.grafico_viste(o["geometria"], cfg, tit, os.path.join(base, "01_viste_layout"), formati)]
    except StopIteration:
        pass
    except Exception:
        log("   (viste non disegnate)\n" + traceback.format_exc())
    if "sezioni" in gruppi and o["geometria"]["layout"].solidi:
        try:
            out += [("sezioni", p) for p in GR.grafico_sezioni(o["geometria"], cfg, tit, os.path.join(base, "10_sezioni_struttura"), formati)]
        except Exception:
            log("   (sezioni non disegnate)\n" + traceback.format_exc())
    c = o.get("completo")
    if not c:
        return out
    a = o["aero"]
    cl = max(a["classi"], key=lambda x: x["P_el"])
    un = copy.deepcopy(cl["unita_rete"])
    arie = cfg["arie"]
    amb = cfg["ambiente_progetto"]
    N_req, N_lim = cl["N_req"], cl["N_lim"]
    N_lista = [0.5 * N_req, 0.75 * N_req, N_req] + ([N_lim] if N_lim > 1.05 * N_req else [])
    mot = libreria_motori(cfg["motori"])[c["motore"]]
    Z = libreria_ventole(cfg["tipi_ventola"])[c["tipo_ventola"]].Z
    passi = [
        ("profili", lambda: GR.grafico_profili(un, arie, N_lista, amb, tit, os.path.join(base, "02_profili_giri"), formati)),
        ("profili", lambda: GR.grafico_profili_ambienti(un, arie, N_req, tit, os.path.join(base, "03_profili_ambienti"), formati)),
        ("ventola", lambda: GR.grafico_mappa_ventola(un, arie, amb, N_req, N_lim, tit, os.path.join(base, "04_mappa_ventola"), formati)),
        ("spinta", lambda: GR.grafico_spinta_giri(un, arie, mot, cfg, N_req, N_lim, cl["F_unita"], tit, os.path.join(base, "05_spinta_giri_potenza"), formati)),
        ("perdite", lambda: GR.grafico_perdite_unita(cl, tit, os.path.join(base, "06_perdite"), formati)),
        ("dinamica", lambda: GR.grafico_salita(c["storia_salita"], N_req, c["t_salita_90"], tit, os.path.join(base, "07_salita_spinta"), formati, c["t_inversione"])),
        ("struttura", lambda: GR.grafico_campbell(c["f1_Hz"], Z, N_req, N_lim, tit, os.path.join(base, "08_campbell"), formati)),
        ("ingestione", lambda: GR.grafico_ingestione(c["ingestione_per_comando"], cfg, tit, os.path.join(base, "09_ingestione"), formati)),
    ]
    for gruppo, f in passi:
        if gruppo not in gruppi:
            continue
        try:
            out += [(gruppo, p) for p in f()]
        except Exception:
            log(f"   (grafico {gruppo} non disegnato)\n" + traceback.format_exc())
    return out


def _condotto(layout):
    """Lunghezza e spostamento reali del condotto (mm), se la geometria ha questi parametri."""
    par = layout.parametri
    if "lunghezza_condotto_mm" not in par:
        return None
    return (f"lunghezza {par['lunghezza_condotto_mm']:.0f} mm, spostamento lungo lo spigolo "
            f"{par['spostamento_mm']:+.1f} mm (limite estremità {par['estremita_max_mm']:.0f} mm)")


def main(nome_run, file_input_predefinito, descrizione, gruppi=TUTTI_I_GRUPPI, con_confronto=True):
    """Esegue una run.  gruppi: grafici di scenario da produrre; con_confronto: grafici di confronto tra scenari."""
    ap = argparse.ArgumentParser(description=descrizione, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=os.path.join(QUI, file_input_predefinito),
                    help=f"file di input (predefinito: {file_input_predefinito})")
    ap.add_argument("--veloce", action="store_true", help="come ESECUZIONE['modalita'] = 'veloce'")
    args = ap.parse_args()
    t0 = time.time()
    cfg, scenari, _ = carica(args.input)
    es = cfg["esecuzione"]
    es["etichetta"] = nome_run + (f"_{es['etichetta']}" if es.get("etichetta") else "")

    # 1. verifiche fisiche ------------------------------------------------------
    if es.get("verifiche_fisiche", True):
        print("Verifiche fisiche del codice...")
        ok, tot = VF.esegui()
        print(f"   {ok}/{tot} verifiche superate\n")
        if ok < tot:
            print("Una verifica fisica è fallita: l'analisi non parte, i risultati non sarebbero affidabili.")
            return None

    # 2. analisi ----------------------------------------------------------------
    if args.veloce or es.get("modalita", "completa") == "veloce":
        cfg["ottimizzazione"]["diametri_mm"] = cfg["ottimizzazione"]["diametri_mm"][::2]
        cfg["ottimizzazione"]["sigma"] = [0.8, 1.0]
        cfg["lati_cubo_mm"] = cfg["lati_cubo_mm"][::2]
        es["risoluzione_voxel_mm"] = max(es["risoluzione_voxel_mm"], 6.0)
        for s in scenari:
            if "varianti_geometria" in s:
                s["varianti_geometria"] = {k: v[::2] for k, v in s["varianti_geometria"].items()}
    imp = impronta(cfg, scenari)
    base_out = os.path.join(QUI, es["cartella_output"])
    cart = OUT.crea_cartella(cfg, scenari, imp, base_out)
    OUT.copia_input(cart, args.input)
    if not con_confronto:      # una sola configurazione: niente confronti
        os.rmdir(os.path.join(cart, "grafici", "confronto"))
    flog = open(os.path.join(cart, "log.txt"), "w", encoding="utf-8")

    def log(msg):
        print(msg)
        flog.write(msg + "\n")
        flog.flush()

    mis = cfg["missione"]
    log(f"Esecuzione {nome_run} (input: {os.path.basename(args.input)}): {cart}")
    log(f"Spinta richiesta per asse: {mis['spinta_per_asse_N']:.3f} N ({mis['origine_spinta']}, "
        f"massa {mis['massa_per_spinta_kg']} kg)")
    log(f"Massa: obiettivo {mis['massa_obiettivo_kg']:.2f} kg, massima ammessa {mis['massa_massima_kg']:.2f} kg")
    log(f"Ambiente di progetto: {cfg['ambiente_progetto']}  rho = {cfg['aria_progetto'].rho:.4f} kg/m³")
    lati = cfg["lati_cubo_mm"]
    log(f"Lato del cubo: intervallo {cfg['geometria']['lato_cubo_min_mm']:.0f}-{cfg['geometria']['lato_cubo_max_mm']:.0f} mm, "
        f"passo {cfg['geometria']['lato_cubo_passo_mm']:.0f} mm: {len(lati)} lati analizzati per ogni scenario "
        f"({', '.join(f'{x:.0f}' for x in lati)})")
    risultati = []
    for sc in scenari:
        log(f"\n== {sc['id']}: {sc['nome']}")
        try:
            risultati.append(ottimizza_scenario(sc, cfg, log))
        except Exception:
            log("   ERRORE nello scenario:\n" + traceback.format_exc())

    # 3. grafici, Excel, dati -----------------------------------------------------
    formati = es["formato_grafici"]
    grafici = []
    log("\nGrafici per scenario...")
    for r in risultati:
        grafici += [(f"{r['scenario']['id']} · {g}", p) for g, p in grafici_scenario(r, cfg, cart, formati, log, gruppi)]
    if con_confronto:
        log("Grafici di confronto...")
        try:
            grafici += [("confronto", p) for p in GR.confronto(risultati, cfg, os.path.join(cart, "grafici", "confronto"), formati)]
        except Exception:
            log("   (confronto non completo)\n" + traceback.format_exc())
    info = {"cartella": os.path.basename(cart), "data": f"{dt.datetime.now():%d/%m/%Y %H:%M}", "impronta": imp}
    xlsx = os.path.join(cart, "excel", "Confronto_scenari.xlsx")
    log("Excel di confronto...")
    XL.scrivi(xlsx, risultati, cfg, scenari, info, grafici)
    riep = []
    with open(os.path.join(cart, "dati", "progetti.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["scenario", "L_mm", "variante", "D_mm", "geometria_ammissibile", "ammissibile", "punteggio", "sigma",
                    "ventola", "motore", "P_asse_W", "libero_dopo", "condotti", "massa_kg", "violazioni"])
        for r in risultati:
            for p in r["progetti"]:
                c, a, g = p.get("completo"), p.get("aero"), p["geometria"]
                w.writerow([r["scenario"]["id"], p["L"], json.dumps(p["variante"]), p["D"], p["geometria_ammissibile"],
                            c["ammissibile"] if c else "", round(c["punteggio_totale"], 4) if c else "",
                            c["sigma"] if c else "", c["tipo_ventola"] if c else "", c["motore"] if c else "",
                            round(a["P_asse_max"], 2) if a else "", round(g["frazione_libera_dopo"], 4),
                            round(g["frazione_condotti"], 4), round(c["massa_totale_kg"], 3) if c else "",
                            "; ".join(c["violazioni"]) if c else ""])
            o = r["ottimo"]
            c = o.get("completo")
            riep.append({"scenario": r["scenario"]["id"], "L_mm": o["L"], "D_mm": o["D"], "variante": o["variante"],
                         "ammissibile": bool(c and c["ammissibile"]),
                         "punteggio_totale": c["punteggio_totale"] if c else None,
                         "punteggi": c["punteggi"] if c else None, "violazioni": c["violazioni"] if c else None,
                         "avvisi": c.get("avvisi") if c else None,
                         "P_asse_W": o["aero"]["P_asse_max"] if o.get("aero") else None,
                         "libero_dopo": o["geometria"]["frazione_libera_dopo"],
                         "massa_totale_kg": c["massa_totale_kg"] if c else None,
                         "massa_voci_kg": c["massa"]["voci"] if c else None,
                         "tipo_ventola": c["tipo_ventola"] if c else None, "motore": c["motore"] if c else None,
                         "sigma": c["sigma"] if c else None,
                         "condotto": _condotto(o["geometria"]["layout"])})
    with open(os.path.join(cart, "dati", "riepilogo.json"), "w", encoding="utf-8") as fh:
        json.dump(_json({"esecuzione": info, "lato_cubo_intervallo_mm": [cfg["geometria"]["lato_cubo_min_mm"],
                                                                      cfg["geometria"]["lato_cubo_max_mm"]],
                         "lato_cubo_passo_mm": cfg["geometria"]["lato_cubo_passo_mm"],
                         "spinta_per_asse_N": mis["spinta_per_asse_N"],
                         "massa_obiettivo_kg": mis["massa_obiettivo_kg"], "massa_massima_kg": mis["massa_massima_kg"],
                         "scenari": riep}), fh, indent=2, ensure_ascii=False)
    amm = [x for x in riep if x["ammissibile"]]
    vinc = max(amm, key=lambda x: x["punteggio_totale"])["scenario"] if amm else "nessuno ammissibile"
    OUT.registra(base_out, {"data": info["data"], "cartella": info["cartella"], "impronta": imp,
                            "etichetta": es.get("etichetta", ""), "scenari": len(scenari),
                            "vincitore": vinc, "durata_s": round(time.time() - t0)})

    # riepilogo a schermo -----------------------------------------------------------
    log("\nRIEPILOGO (progetto ottimo di ogni scenario, dal migliore)")
    log(f"  {'scenario':<26}{'punteggio':>10}{'L':>7}{'D':>7}{'potenza':>12}{'libero':>8}{'massa':>9}  stato")
    for x in sorted(riep, key=lambda x: -(x["punteggio_totale"] or -1)):
        stato = "ammissibile" if x["ammissibile"] else "NON ammissibile: " + "; ".join(x["violazioni"] or ["—"])
        pt = f"{x['punteggio_totale']:.3f}" if x["punteggio_totale"] is not None else "—"
        P = f"{x['P_asse_W']:.0f} W/asse" if x["P_asse_W"] else "—"
        m = f"{x['massa_totale_kg']:.2f} kg" if x["massa_totale_kg"] else "—"
        log(f"  {x['scenario']:<26}{pt:>10}{x['L_mm']:>5.0f}mm{x['D_mm']:>5.0f}mm{P:>12}{x['libero_dopo']:>8.0%}{m:>9}  {stato}")
        g_ = cfg["geometria"]
        if x["L_mm"] <= g_["lato_cubo_min_mm"] + 1e-6 or x["L_mm"] >= g_["lato_cubo_max_mm"] - 1e-6:
            lim = "inferiore" if x["L_mm"] <= g_["lato_cubo_min_mm"] + 1e-6 else "superiore"
            log(f"  {'':<26}   ATTENZIONE: il lato ottimo è al limite {lim} dell'intervallo: "
                f"l'ottimo vero potrebbe stare fuori, valuta di allargarlo")
        if x["variante"]:
            log(f"  {'':<26}   ottimo con: " + ", ".join(f"{k} = {v}" for k, v in x["variante"].items()))
        if x["condotto"]:
            log(f"  {'':<26}   condotto: {x['condotto']}")
        for a in (x.get("avvisi") or []):
            log(f"  {'':<26}   avviso: {a}")
    log("\nLATO OTTIMO DEL CUBO (per ogni scenario, dentro l'intervallo analizzato)")
    for x in sorted(riep, key=lambda x: -(x["punteggio_totale"] or -1)):
        log(f"  {x['scenario']:<26} L = {x['L_mm']:.0f} mm" + ("" if x["ammissibile"] else "   (progetto non ammissibile)"))
    log(f"\nVincitore tra gli ammissibili: {vinc}")
    log(f"Finito in {time.time() - t0:.0f} s. Risultati in {cart}")
    flog.close()
    return cart

