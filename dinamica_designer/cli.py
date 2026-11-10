"""Riga di comando della dinamica di volo: input.py -> risultati/<caso>/.

Sequenza: lettura e controllo dell'input, verifiche contro soluzioni analitiche, simulazione dei
tre assi, spazio massimo e tempo minimo, margine di fase e ruote (propulsore.py), file di uscita.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import sys
import time

from . import caso as CA
from . import export as EX
from . import propulsore as DY
from . import volo as VO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))    # cartella del progetto
INPUT_FILE = os.path.join(ROOT, "input.py")
ASSI = "XYZ"
SEZIONI = ("ESECUZIONE", "CORPO", "ATTUATORE", "MANOVRA", "DISTURBO", "REGOLATORE", "ENERGIA", "RUOTE")
# chiavi di ESECUZIONE che non cambiano i risultati: fuori dall'impronta
SOLO_FORMA = ("etichetta", "cartella_output", "formato_grafici", "verifiche")


# ---------------------------------------------------------------- input
def carica_input(percorso):
    """Dizionari dell'input (SEZIONI) più CASO, controllati."""
    spec = importlib.util.spec_from_file_location("input_dinamica", percorso)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = {k: dict(getattr(mod, k)) for k in SEZIONI}
    cfg["CASO"] = {**CA.CASO_PREDEFINITO, **dict(getattr(mod, "CASO", None) or {})}
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
    unknown = sorted(set(c["CASO"]) - set(CA.CASO_PREDEFINITO))
    if unknown:
        err.append(f"chiavi sconosciute in CASO: {', '.join(unknown)}")
    if err:
        raise ValueError("Errori in input:\n - " + "\n - ".join(err))


def impronta(cfg):
    """Hash breve dei dati che cambiano i risultati: stessa impronta = stessi risultati."""
    dati = {k: v for k, v in cfg.items() if k != "CASO"}
    dati["ESECUZIONE"] = {k: v for k, v in cfg["ESECUZIONE"].items() if k not in SOLO_FORMA}
    return hashlib.sha1(json.dumps(dati, sort_keys=True, default=str).encode()).hexdigest()[:8]


def nome_automatico(cfg, imp):
    return (f"m{cfg['CORPO']['massa_kg']:.2f}kg_d{cfg['MANOVRA']['distanza_m'][0]:.2f}m"
            f"_t{cfg['MANOVRA']['tempo_manovra_s']:.1f}s_h{imp}")


# ---------------------------------------------------------------- calcolo
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


def spazio_e_tempo(cfg):
    """Spazio massimo nel tempo della manovra e tempo minimo per la distanza, alla spinta massima."""
    m, ma, at, di = cfg["CORPO"]["massa_kg"], cfg["MANOVRA"], cfg["ATTUATORE"], cfg["DISTURBO"]
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
    return spazio


def attuatore_e_ruote(cfg):
    """Margine di fase per le bande richieste e bilancio delle ruote (modelli di propulsore.py)."""
    at, ma, ru = cfg["ATTUATORE"], cfg["MANOVRA"], cfg["RUOTE"]
    pm = {wc: DY.margine_fase(at["tempo_salita_90_s"], wc) for wc in ru["frequenze_margine_fase_rad_s"]}
    rw = DY.bilancio_ruote(cfg["ENERGIA"]["spinta_rif_N"], ru["scostamento_baricentro_mm"] / 1000, ru["braccio_coppia_m"],
                           ru["squilibrio_coppia"], ru["spinta_per_unita_N"], ru["coppia_reazione_rotori_Nm"],
                           ru["momento_rotori_in_avvio_Nms"], ma["finestra_s"], ru["momento_ruote_max_Nms"])
    return pm, rw


# ---------------------------------------------------------------- run
def run(input_file=INPUT_FILE, nome_run="dinamica"):
    """Esegue la run; ritorna la cartella del caso (None se le verifiche falliscono)."""
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    t0 = time.time()
    cfg = carica_input(input_file)
    es = cfg["ESECUZIONE"]
    if es.get("verifiche", True):
        from . import verifiche as VF
        ok, tot = VF.esegui(stampa=lambda *a, **k: None)
        print(f"Verifiche della dinamica: {ok}/{tot} superate")
        if ok < tot:
            print("Una verifica è fallita: la simulazione non parte.")
            return None
    imp = impronta(cfg)
    base = os.path.join(ROOT, es.get("cartella_output", "risultati"))
    os.makedirs(base, exist_ok=True)
    nome = CA.nome_caso(cfg["CASO"], nome_automatico(cfg, imp))
    cart = CA.prepara(base, nome, imp, cfg["CASO"]["sovrascrivi"], input_file)
    flog = open(os.path.join(cart, "log.txt"), "w", encoding="utf-8")

    def log(msg=""):
        print(msg)
        flog.write(msg + "\n")
        flog.flush()

    m, ma, at, di, rg = cfg["CORPO"]["massa_kg"], cfg["MANOVRA"], cfg["ATTUATORE"], cfg["DISTURBO"], cfg["REGOLATORE"]
    ru = cfg["RUOTE"]
    log(f"Esecuzione {nome_run} (input: {os.path.basename(input_file)}): {cart}")
    log(f"Massa {m:.2f} kg nel baricentro; manovra {ma['distanza_m']} m in {ma['tempo_manovra_s']} s "
        f"(profilo {ma['profilo']}), finestra {ma['finestra_s']} s")
    log(f"PD: wn = {rg['frequenza_propria_rad_s']} rad/s, zeta = {rg['smorzamento']}"
        f"{', con feedforward' if rg['feedforward_riferimento'] else ''}; attuatore t90 = {at['tempo_salita_90_s']} s")
    log(f"Disturbo: {di['ampiezza_g']} g a {di['frequenza_Hz']} Hz, fasi {di['fase_gradi']} gradi")
    serie, ind = simula(cfg)
    spazio = spazio_e_tempo(cfg)
    pm, rw = attuatore_e_ruote(cfg)

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

    # file di uscita
    formati = es["formato_grafici"]
    scritti = []
    scritti += EX.grafico_moto(serie, cfg, os.path.join(cart, "01_grafici", "01_moto_tre_assi"), formati)
    scritti += EX.grafico_spazio_massimo(cfg, os.path.join(cart, "01_grafici", "02_spazio_massimo"), formati)
    scritti.append(EX.scrivi_serie(serie, es["passo_integrazione_s"], os.path.join(cart, "02_dati", "serie_temporali.csv")))
    riep = {"data": f"{dt.datetime.now():%d/%m/%Y %H:%M}", "impronta": imp, "massa_kg": m,
            "assi": {ASSI[i]: ind[i] for i in range(3)}, "spazio_massimo": spazio,
            "margine_fase_gradi": {str(k): v for k, v in pm.items()}, "t_salita_90_s": at["tempo_salita_90_s"], "ruote": rw}
    scritti.append(EX.scrivi_riepilogo(riep, os.path.join(cart, "00_sintesi", "riepilogo.json")))
    rel = [os.path.relpath(p, cart).replace(os.sep, "/") for p in scritti]
    ris = EX.scrivi_risultato(riep, cfg, nome, sorted(["00_sintesi/RISULTATO.md"] + rel) + ["input_usato.py", "log.txt"],
                              os.path.join(cart, "00_sintesi", "RISULTATO.md"))
    log("")
    for p in [ris] + scritti:
        log(f"  scritto: {os.path.relpath(p, cart)}")
    CA.registra(base, {"data": riep["data"], "caso": nome, "impronta": imp, "run": nome_run,
                       "durata_s": round(time.time() - t0)})
    log(f"\nFinito in {time.time() - t0:.0f} s. Risultati in {cart}")
    flog.close()
    return cart


def main(argv=None, descrizione=__doc__):
    ap = argparse.ArgumentParser(description=descrizione, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=INPUT_FILE, help="file di input (predefinito: input.py)")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        cart = run(args.input)
    except ValueError as e:
        print(f"Errore: {e}")
        return 1
    return 0 if cart else 2
