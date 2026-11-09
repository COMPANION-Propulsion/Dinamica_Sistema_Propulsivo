"""Esecuzione della run di dinamica S4: legge INPUT_S4_dinamica.py, simula i tre assi, scrive i risultati.

Cartella: output/<data-ora>_RUN-S4-dinamica_<etichetta>_<impronta>/
    grafici/01_moto_tre_assi, 02_spazio_massimo
    dati/riepilogo.json, dati/serie_temporali.csv
    INPUT_usato.py, log.txt
"""
import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import dinamica as DY
from . import volo as VO
from . import output as OUT

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSI = "XYZ"
COL = ["#1f5bd8", "#e8590c", "#2b8a3e"]
SEZIONI = ("ESECUZIONE", "CORPO", "ATTUATORE", "MANOVRA", "DISTURBO", "REGOLATORE", "ENERGIA", "RUOTE")


def carica_input(percorso):
    spec = importlib.util.spec_from_file_location("input_dinamica", percorso)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = {k: dict(getattr(mod, k)) for k in SEZIONI}
    _controlla(cfg)
    return cfg


def _controlla(c):
    err = []
    for sez, chiavi in (("ATTUATORE", ("spinta_max_positiva_N", "spinta_max_negativa_N")),
                        ("MANOVRA", ("distanza_m",)), ("DISTURBO", ("ampiezza_g", "frequenza_Hz", "fase_gradi"))):
        for k in chiavi:
            if len(c[sez][k]) != 3:
                err.append(f"{sez}['{k}'] deve avere 3 valori [X, Y, Z]")
    if c["CORPO"]["massa_kg"] <= 0:
        err.append("massa_kg deve essere maggiore di zero")
    if c["MANOVRA"]["profilo"] not in ("minimo_jerk", "gradino"):
        err.append("MANOVRA['profilo'] deve essere 'minimo_jerk' o 'gradino'")
    if c["MANOVRA"]["tempo_manovra_s"] <= 0 or c["MANOVRA"]["finestra_s"] < c["MANOVRA"]["tempo_manovra_s"]:
        err.append("serve 0 < tempo_manovra_s <= finestra_s")
    if c["ATTUATORE"]["tempo_salita_90_s"] <= 0:
        err.append("tempo_salita_90_s deve essere maggiore di zero")
    elif c["ESECUZIONE"]["passo_integrazione_s"] > c["ATTUATORE"]["tempo_salita_90_s"] / 2.3 / 2:
        err.append("passo_integrazione_s troppo grande rispetto al ritardo dell'attuatore (t90 / 2,3): "
                   "l'integrazione diventerebbe instabile; usa un passo <= t90 / 4,6")
    if err:
        raise ValueError("Errori in input:\n - " + "\n - ".join(err))


def impronta(cfg):
    return hashlib.sha1(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:8]


def _crea_cartella(cfg, imp, base):
    et = cfg["ESECUZIONE"].get("etichetta") or (
        f"m{cfg['CORPO']['massa_kg']:.2f}kg_d{cfg['MANOVRA']['distanza_m'][0]:.2f}m_t{cfg['MANOVRA']['tempo_manovra_s']:.1f}s")
    et = re.sub(r"[^A-Za-z0-9.+-]+", "-", et).strip("-")
    nome = f"{dt.datetime.now():%Y%m%d-%H%M%S}_RUN-S4-dinamica_{et}_{imp}"
    percorso = os.path.join(base, nome)
    k = 2
    while os.path.exists(percorso):
        percorso = os.path.join(base, f"{nome}_{k}")
        k += 1
    for sotto in ("grafici", "dati"):
        os.makedirs(os.path.join(percorso, sotto), exist_ok=True)
    return percorso


def _salva(fig, percorso, formati):
    out = []
    for f in formati:
        p = f"{percorso}.{f}"
        fig.savefig(p, bbox_inches="tight")
        out.append(p)
    plt.close(fig)
    return out


def simula(cfg):
    """Simula i tre assi; ritorna (serie per asse, indicatori per asse)."""
    m = cfg["CORPO"]["massa_kg"]
    at, ma, di, rg, en = cfg["ATTUATORE"], cfg["MANOVRA"], cfg["DISTURBO"], cfg["REGOLATORE"], cfg["ENERGIA"]
    dtp = cfg["ESECUZIONE"]["passo_integrazione_s"]
    rif = VO.riferimento_minjerk if ma["profilo"] == "minimo_jerk" else VO.riferimento_gradino
    serie, ind = [], []
    for i in range(3):
        s = VO.simula_asse(
            m, at["spinta_max_positiva_N"][i], at["tempo_salita_90_s"], rg["frequenza_propria_rad_s"],
            rg["smorzamento"], ma["distanza_m"][i], ma["tempo_manovra_s"],
            lambda t, i=i: VO.disturbo_sinusoidale(t, di["ampiezza_g"][i], di["frequenza_Hz"][i], di["fase_gradi"][i]),
            ma["finestra_s"], dtp, rg["feedforward_riferimento"], rif, F_max_neg=at["spinta_max_negativa_N"][i])
        serie.append(s)
        F_max = max(at["spinta_max_positiva_N"][i], at["spinta_max_negativa_N"][i])
        ind.append(VO.indicatori(s, ma["distanza_m"][i], ma["tempo_manovra_s"], ma["tolleranza_posizione_mm"] / 1000,
                                 F_max, en["potenza_rif_W"], en["spinta_rif_N"], en["esponente"], dtp))
    return serie, ind


def grafico_moto(serie, cfg, percorso, formati):
    ma, at = cfg["MANOVRA"], cfg["ATTUATORE"]
    fig, ax = plt.subplots(4, 3, figsize=(13, 10), sharex=True)
    for i, s in enumerate(serie):
        t = s["t"]
        a = ax[0, i]
        a.plot(t, s["x_rif"] * 1000, "k--", lw=1, label="riferimento")
        a.plot(t, s["x"] * 1000, color=COL[i], label="posizione")
        tol = ma["tolleranza_posizione_mm"]
        a.axhspan(ma["distanza_m"][i] * 1000 - tol, ma["distanza_m"][i] * 1000 + tol, color="#adb5bd", alpha=0.3)
        a.set_title(f"asse {ASSI[i]}"); a.set_ylabel("x (mm)"); a.legend(fontsize=7)
        ax[1, i].plot(t, s["v"] * 1000, color=COL[i]); ax[1, i].plot(t, s["v_rif"] * 1000, "k--", lw=1)
        ax[1, i].set_ylabel("v (mm/s)")
        ax[2, i].plot(t, s["F_cmd"], color="#adb5bd", label="comando")
        ax[2, i].plot(t, s["F"], color=COL[i], label="spinta")
        for F in (at["spinta_max_positiva_N"][i], -at["spinta_max_negativa_N"][i]):
            ax[2, i].axhline(F, color="#c92a2a", lw=0.8, ls=":")
        ax[2, i].set_ylabel("F (N)"); ax[2, i].legend(fontsize=7)
        ax[3, i].plot(t, s["a_dist"] / VO.G0 * 1000, color="#868e96")
        ax[3, i].set_ylabel("disturbo (mg)"); ax[3, i].set_xlabel("t (s)")
        for r in range(4):
            ax[r, i].axvline(ma["tempo_manovra_s"], color="#868e96", lw=0.6, ls=":")
    fig.suptitle("S4 — moto sui tre assi: posizione, velocità, spinta, disturbo (massa puntiforme, PD)")
    return _salva(fig, percorso, formati)


def grafico_spazio_massimo(cfg, percorso, formati):
    m = cfg["CORPO"]["massa_kg"]
    ma, at, di = cfg["MANOVRA"], cfg["ATTUATORE"], cfg["DISTURBO"]
    t = np.linspace(0.5, ma["finestra_s"], 100)
    fig, ax = plt.subplots(figsize=(8, 5))
    for i in range(3):
        F = min(at["spinta_max_positiva_N"][i], at["spinta_max_negativa_N"][i])
        a_d = di["ampiezza_g"][i] * VO.G0
        d0, d1 = VO.spazio_massimo(m, F, a_d, t)
        ax.plot(t, d0, color=COL[i], label=f"{ASSI[i]} senza disturbo")
        ax.plot(t, d1, color=COL[i], ls="--", label=f"{ASSI[i]} disturbo nel caso peggiore")
    ax.axhline(ma["distanza_m"][0], color="k", lw=0.8, ls=":")
    ax.axvline(ma["tempo_manovra_s"], color="k", lw=0.8, ls=":")
    ax.set_xlabel("tempo della manovra (s)"); ax.set_ylabel("spazio massimo da fermo a fermo (m)")
    ax.set_title("Spazio percorribile in un tempo dato alla spinta massima (accelera t/2, frena t/2)")
    ax.legend(fontsize=7)
    return _salva(fig, percorso, formati)


def main(nome_run, input_predefinito, descrizione):
    ap = argparse.ArgumentParser(description=descrizione, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=os.path.join(QUI, input_predefinito),
                    help=f"file di input (predefinito: {input_predefinito})")
    args = ap.parse_args()
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    t0 = time.time()
    cfg = carica_input(args.input)
    es = cfg["ESECUZIONE"]
    if es.get("verifiche", True):
        from . import verifiche as VF
        ok, tot = VF.esegui(stampa=lambda *a, **k: None)
        print(f"Verifiche fisiche del codice: {ok}/{tot} superate")
        if ok < tot:
            print("Una verifica è fallita: la simulazione non parte.")
            return None
    imp = impronta(cfg)
    base = os.path.join(QUI, es["cartella_output"])
    os.makedirs(base, exist_ok=True)
    cart = _crea_cartella(cfg, imp, base)
    OUT.copia_input(cart, args.input)
    flog = open(os.path.join(cart, "log.txt"), "w", encoding="utf-8")

    def log(msg=""):
        print(msg)
        flog.write(msg + "\n")
        flog.flush()

    m, ma, at, di, rg = cfg["CORPO"]["massa_kg"], cfg["MANOVRA"], cfg["ATTUATORE"], cfg["DISTURBO"], cfg["REGOLATORE"]
    log(f"Esecuzione {nome_run} (input: {os.path.basename(args.input)}): {cart}")
    log(f"Massa {m:.2f} kg nel baricentro; manovra {ma['distanza_m']} m in {ma['tempo_manovra_s']} s "
        f"(profilo {ma['profilo']}), finestra {ma['finestra_s']} s")
    log(f"PD: wn = {rg['frequenza_propria_rad_s']} rad/s, zeta = {rg['smorzamento']}"
        f"{', con feedforward' if rg['feedforward_riferimento'] else ''}; attuatore t90 = {at['tempo_salita_90_s']} s")
    log(f"Disturbo: {di['ampiezza_g']} g a {di['frequenza_Hz']} Hz, fasi {di['fase_gradi']} gradi")
    serie, ind = simula(cfg)

    # spazio massimo e tempo minimo
    spazio = []
    for i in range(3):
        F = min(at["spinta_max_positiva_N"][i], at["spinta_max_negativa_N"][i])
        a_d = di["ampiezza_g"][i] * VO.G0
        d0, d1 = VO.spazio_massimo(m, F, a_d, ma["tempo_manovra_s"])
        t0_, t1_ = VO.tempo_minimo(m, F, a_d, ma["distanza_m"][i])
        spazio.append({"asse": ASSI[i], "spinta_N": F, "spazio_max_senza_disturbo_m": float(d0),
                       "spazio_max_con_disturbo_m": float(d1), "tempo_min_senza_disturbo_s": t0_,
                       "tempo_min_con_disturbo_s": t1_ if math.isfinite(t1_) else None,
                       "disturbo_sulla_spinta": a_d * m / F})
    # margine di fase e ruote (modelli di dinamica.py)
    ru = cfg["RUOTE"]
    pm = {wc: DY.margine_fase(at["tempo_salita_90_s"], wc) for wc in ru["frequenze_margine_fase_rad_s"]}
    F_asse = cfg["ENERGIA"]["spinta_rif_N"]
    rw = DY.bilancio_ruote(F_asse, ru["scostamento_baricentro_mm"] / 1000, ru["braccio_coppia_m"], ru["squilibrio_coppia"],
                           ru["spinta_per_unita_N"], ru["coppia_reazione_rotori_Nm"], ru["momento_rotori_in_avvio_Nms"],
                           ma["finestra_s"], ru["momento_ruote_max_Nms"])

    log("\nRISULTATI PER ASSE")
    log(f"  {'asse':<5}{'err a T':>10}{'err max':>10}{'sovra':>9}{'assest.':>10}{'F max':>9}{'F/Fmax':>8}{'sat.':>7}{'energia':>10}")
    for i, x in enumerate(ind):
        ass = f"{x['tempo_assestamento_s']:.2f} s" if x["tempo_assestamento_s"] is not None else "oltre"
        log(f"  {ASSI[i]:<5}{x['errore_a_T_mm']:>8.1f}mm{x['errore_max_mm']:>8.1f}mm{x['sovraelongazione_mm']:>7.1f}mm"
            f"{ass:>10}{x['spinta_max_usata_N']:>7.2f} N{x['spinta_su_massima']:>8.0%}{x['tempo_in_saturazione_s']:>5.2f} s"
            f"{x['energia_J']:>8.0f} J")
    log("\nSPAZIO MASSIMO E TEMPO MINIMO (spinta massima, da fermo a fermo)")
    for s in spazio:
        tmin = f"{s['tempo_min_con_disturbo_s']:.2f} s" if s["tempo_min_con_disturbo_s"] else "impossibile"
        log(f"  asse {s['asse']}: in {ma['tempo_manovra_s']} s al massimo {s['spazio_max_senza_disturbo_m']:.3f} m "
            f"({s['spazio_max_con_disturbo_m']:.3f} m con il disturbo nel caso peggiore); per {ma['distanza_m'][ASSI.index(s['asse'])]} m "
            f"servono almeno {s['tempo_min_senza_disturbo_s']:.2f} s ({tmin} con disturbo); il disturbo è il "
            f"{s['disturbo_sulla_spinta']:.0%} della spinta massima")
    log("\nATTUATORE E RUOTE")
    log(f"  tempo di salita al 90 %: {at['tempo_salita_90_s']:.3f} s;  margine di fase: "
        + ", ".join(f"{p:.0f}° a {wc:g} rad/s" for wc, p in pm.items()))
    log(f"  ruote di reazione: momento in finestra {rw['H_finestra']:.3f} N·m·s = {rw['quota_ruota']:.0%} della capacità "
        f"({ru['momento_ruote_max_Nms']} N·m·s)" + ("  -> SATURANO" if rw["quota_ruota"] > 1 else ""))

    # grafici e dati
    formati = es["formato_grafici"]
    for p in grafico_moto(serie, cfg, os.path.join(cart, "grafici", "01_moto_tre_assi"), formati):
        log(f"  grafico: {os.path.relpath(p, cart)}")
    for p in grafico_spazio_massimo(cfg, os.path.join(cart, "grafici", "02_spazio_massimo"), formati):
        log(f"  grafico: {os.path.relpath(p, cart)}")
    with open(os.path.join(cart, "dati", "serie_temporali.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["t_s"] + [f"{c}_{a}" for a in ASSI for c in ("x_m", "x_rif_m", "v_m_s", "F_N", "F_cmd_N", "a_dist_m_s2")])
        passo = max(1, int(round(0.01 / es["passo_integrazione_s"])))
        for k in range(0, len(serie[0]["t"]), passo):
            riga = [round(float(serie[0]["t"][k]), 6)]
            for s in serie:
                riga += [round(float(s[c][k]), 6) for c in ("x", "x_rif", "v", "F", "F_cmd", "a_dist")]
            w.writerow(riga)
    riep = {"data": f"{dt.datetime.now():%d/%m/%Y %H:%M}", "impronta": imp, "massa_kg": m,
            "assi": {ASSI[i]: ind[i] for i in range(3)}, "spazio_massimo": spazio,
            "margine_fase_gradi": {str(k): v for k, v in pm.items()}, "t_salita_90_s": at["tempo_salita_90_s"], "ruote": rw}
    with open(os.path.join(cart, "dati", "riepilogo.json"), "w", encoding="utf-8") as fh:
        json.dump(riep, fh, indent=2, ensure_ascii=False, default=float)
    OUT.registra(base, {"data": riep["data"], "cartella": os.path.basename(cart), "impronta": imp,
                        "etichetta": nome_run + (f"_{es['etichetta']}" if es.get("etichetta") else ""),
                        "scenari": 1, "vincitore": "—", "durata_s": round(time.time() - t0)})
    log(f"\nFinito in {time.time() - t0:.0f} s. Risultati in {cart}")
    flog.close()
    return cart
