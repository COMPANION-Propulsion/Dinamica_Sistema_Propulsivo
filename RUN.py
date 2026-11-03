"""ANALISI DEI CONDOTTI DI COMPANION — l'unico script da lanciare.

    python RUN.py            (oppure il tasto Run dell'editor)

Legge tutti i dati da INPUT.py (si modifica solo quello), poi:
  1  verifiche fisiche del codice contro risultati noti (si ferma se una fallisce)
  2  per ogni scenario attivo: ottimizzazione di diametro, varianti geometriche,
     Venturi, ventola e motore; valutazione di spazio, perdite, controllo,
     dinamica, struttura, massa, realizzabilità
  3  grafici, Excel di confronto e riepilogo in una cartella nuova:
     output/<data-ora>_<etichetta>_<impronta>/
         grafici/<scenario>/   viste, profili, mappa ventola, spinta-giri, perdite, salita, Campbell, ingestione
         grafici/confronto/    punteggi, radar, Pareto, sensibilità, perdite, spazio, stabilità, ruote,
                               autorità, struttura, ambiente, bilancio di massa
         excel/Confronto_scenari.xlsx
         dati/riepilogo.json, dati/progetti.csv
         INPUT_usato.py, log.txt
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

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
for _flusso in (sys.stdout, sys.stderr):        # accenti e simboli anche nella console di Windows
    try:
        _flusso.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from condotti.config import carica, impronta                     # noqa: E402
from condotti.ottimizzazione import ottimizza_scenario            # noqa: E402
from condotti import grafici as GR                                # noqa: E402
from condotti import output as OUT                                # noqa: E402
from condotti import report_excel as XL                           # noqa: E402
from condotti import verifiche as VF                              # noqa: E402
from condotti.ventole import libreria_motori, libreria_ventole    # noqa: E402


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


def grafici_scenario(r, cfg, cartella, formati, log):
    out = []
    sid = r["scenario"]["id"]
    o = r["ottimo"]
    base = os.path.join(cartella, "grafici", sid)
    tit = f"{sid} — {r['scenario']['nome']}"
    try:
        out += [("viste", p) for p in GR.grafico_viste(o["geometria"], cfg, tit, os.path.join(base, "01_viste_layout"), formati)]
    except Exception:
        log("   (viste non disegnate)\n" + traceback.format_exc())
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=os.path.join(QUI, "INPUT.py"), help="file di input (predefinito: INPUT.py)")
    ap.add_argument("--veloce", action="store_true", help="come ESECUZIONE['modalita'] = 'veloce'")
    args = ap.parse_args()
    t0 = time.time()
    cfg, scenari, _ = carica(args.input)
    es = cfg["esecuzione"]

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
        es["risoluzione_voxel_mm"] = max(es["risoluzione_voxel_mm"], 6.0)
        for s in scenari:
            if "varianti_geometria" in s:
                s["varianti_geometria"] = {k: v[::2] for k, v in s["varianti_geometria"].items()}
    imp = impronta(cfg, scenari)
    base_out = os.path.join(QUI, es["cartella_output"])
    cart = OUT.crea_cartella(cfg, scenari, imp, base_out)
    OUT.copia_input(cart, args.input)
    flog = open(os.path.join(cart, "log.txt"), "w", encoding="utf-8")

    def log(msg):
        print(msg)
        flog.write(msg + "\n")
        flog.flush()

    mis = cfg["missione"]
    log(f"Esecuzione: {cart}")
    log(f"Spinta richiesta per asse: {mis['spinta_per_asse_N']:.3f} N ({mis['origine_spinta']}, "
        f"massa {mis['massa_per_spinta_kg']} kg)")
    log(f"Massa: obiettivo {mis['massa_obiettivo_kg']:.2f} kg, massima ammessa {mis['massa_massima_kg']:.2f} kg")
    log(f"Ambiente di progetto: {cfg['ambiente_progetto']}  rho = {cfg['aria_progetto'].rho:.4f} kg/m³")
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
        grafici += [(f"{r['scenario']['id']} · {g}", p) for g, p in grafici_scenario(r, cfg, cart, formati, log)]
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
        w.writerow(["scenario", "variante", "D_mm", "geometria_ammissibile", "ammissibile", "punteggio", "sigma",
                    "ventola", "motore", "P_asse_W", "libero_dopo", "condotti", "massa_kg", "violazioni"])
        for r in risultati:
            for p in r["progetti"]:
                c, a, g = p.get("completo"), p.get("aero"), p["geometria"]
                w.writerow([r["scenario"]["id"], json.dumps(p["variante"]), p["D"], p["geometria_ammissibile"],
                            c["ammissibile"] if c else "", round(c["punteggio_totale"], 4) if c else "",
                            c["sigma"] if c else "", c["tipo_ventola"] if c else "", c["motore"] if c else "",
                            round(a["P_asse_max"], 2) if a else "", round(g["frazione_libera_dopo"], 4),
                            round(g["frazione_condotti"], 4), round(c["massa_totale_kg"], 3) if c else "",
                            "; ".join(c["violazioni"]) if c else ""])
            o = r["ottimo"]
            c = o.get("completo")
            riep.append({"scenario": r["scenario"]["id"], "D_mm": o["D"], "variante": o["variante"],
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
        json.dump(_json({"esecuzione": info, "spinta_per_asse_N": mis["spinta_per_asse_N"],
                         "massa_obiettivo_kg": mis["massa_obiettivo_kg"], "massa_massima_kg": mis["massa_massima_kg"],
                         "scenari": riep}), fh, indent=2, ensure_ascii=False)
    amm = [x for x in riep if x["ammissibile"]]
    vinc = max(amm, key=lambda x: x["punteggio_totale"])["scenario"] if amm else "nessuno ammissibile"
    OUT.registra(base_out, {"data": info["data"], "cartella": info["cartella"], "impronta": imp,
                            "etichetta": es.get("etichetta", ""), "scenari": len(scenari),
                            "vincitore": vinc, "durata_s": round(time.time() - t0)})

    # riepilogo a schermo -----------------------------------------------------------
    log("\nRIEPILOGO (progetto ottimo di ogni scenario, dal migliore)")
    log(f"  {'scenario':<26}{'punteggio':>10}{'D':>7}{'potenza':>12}{'libero':>8}{'massa':>9}  stato")
    for x in sorted(riep, key=lambda x: -(x["punteggio_totale"] or -1)):
        stato = "ammissibile" if x["ammissibile"] else "NON ammissibile: " + "; ".join(x["violazioni"] or ["—"])
        pt = f"{x['punteggio_totale']:.3f}" if x["punteggio_totale"] is not None else "—"
        P = f"{x['P_asse_W']:.0f} W/asse" if x["P_asse_W"] else "—"
        m = f"{x['massa_totale_kg']:.2f} kg" if x["massa_totale_kg"] else "—"
        log(f"  {x['scenario']:<26}{pt:>10}{x['D_mm']:>5.0f}mm{P:>12}{x['libero_dopo']:>8.0%}{m:>9}  {stato}")
        if x["variante"]:
            log(f"  {'':<26}   ottimo con: " + ", ".join(f"{k} = {v}" for k, v in x["variante"].items()))
        if x["condotto"]:
            log(f"  {'':<26}   condotto: {x['condotto']}")
        for a in (x.get("avvisi") or []):
            log(f"  {'':<26}   avviso: {a}")
    log(f"\nVincitore tra gli ammissibili: {vinc}")
    log(f"Finito in {time.time() - t0:.0f} s. Risultati in {cart}")
    flog.close()
    return cart


if __name__ == "__main__":
    main()
