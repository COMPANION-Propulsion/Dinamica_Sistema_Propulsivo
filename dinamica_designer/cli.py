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

import numpy as np

from . import caso as CA
from . import confronto_analisi as CF
from . import export as EX
from . import pale as PA
from . import propulsore as DY
from . import volo as VO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))    # cartella del progetto
INPUT_FILE = os.path.join(ROOT, "input.py")
ASSI = "XYZ"
SEZIONI = ("ESECUZIONE", "CORPO", "ATTUATORE", "MANOVRA", "DISTURBO", "REGOLATORE", "ENERGIA", "RUOTE", "PALE")
# chiavi di ESECUZIONE che non cambiano i risultati: fuori dall'impronta
SOLO_FORMA = ("etichetta", "cartella_output", "formato_grafici", "verifiche")
CHIAVI_DISTURBO = ("bias_g", "rumore_sigma_g", "rumore_banda_Hz", "velocita_iniziale_m_s", "sinusoide_ampiezza_g",
                   "sinusoide_frequenza_Hz", "sinusoide_fase_gradi", "campioni_monte_carlo", "seme")
# indicatori riassunti nel Monte Carlo (sui valori assoluti): media, 95° percentile, massimo
STAT_MC = ("errore_a_T_mm", "errore_finale_mm", "errore_max_mm", "sovraelongazione_mm", "spinta_su_massima",
           "tempo_in_saturazione_s", "energia_J")


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
    di = c["DISTURBO"]
    if "ampiezza_g" in di:
        raise ValueError("DISTURBO ha il formato vecchio (ampiezza_g, frequenza_Hz, fase_gradi): usa le chiavi "
                         "bias_g, rumore_sigma_g, rumore_banda_Hz, velocita_iniziale_m_s, sinusoide_*, "
                         "campioni_monte_carlo, seme (vedi input.py)")
    mancanti = [k for k in CHIAVI_DISTURBO if k not in di]
    if mancanti:
        raise ValueError(f"mancano in DISTURBO: {', '.join(mancanti)}")
    for sez, chiavi in (("ATTUATORE", ("spinta_max_positiva_N", "spinta_max_negativa_N")),
                        ("MANOVRA", ("distanza_m",)),
                        ("DISTURBO", ("sinusoide_ampiezza_g", "sinusoide_frequenza_Hz", "sinusoide_fase_gradi"))):
        for k in chiavi:
            if len(c[sez][k]) != 3:
                err.append(f"{sez}['{k}'] deve avere 3 valori [X, Y, Z]")
    for k in ("bias_g", "rumore_sigma_g", "velocita_iniziale_m_s"):
        if di[k] < 0:
            err.append(f"DISTURBO['{k}'] non può essere negativo (è un modulo)")
    if di["rumore_banda_Hz"] <= 0:
        err.append("DISTURBO['rumore_banda_Hz'] deve essere maggiore di zero")
    if not isinstance(di["campioni_monte_carlo"], int) or di["campioni_monte_carlo"] < 0:
        err.append("DISTURBO['campioni_monte_carlo'] deve essere un intero >= 0")
    pa = c["PALE"]
    for k in ("lunghezza_mm", "larghezza_mm", "spessore_mm"):
        if pa[k] <= 0:
            err.append(f"PALE['{k}'] deve essere maggiore di zero")
    if pa["raggio_mozzo_mm"] < 0:
        err.append("PALE['raggio_mozzo_mm'] non può essere negativo")
    if not 0 < pa["densita_min_kg_m3"] <= pa["densita_max_kg_m3"]:
        err.append("PALE: serve 0 < densita_min_kg_m3 <= densita_max_kg_m3")
    if pa["numero_pale"] < 2 or pa["campioni"] < 1:
        err.append("PALE: servono almeno 2 pale e almeno 1 campione")
    if c["REGOLATORE"].get("polo_integrale_su_wn", 0.0) < 0:
        err.append("REGOLATORE['polo_integrale_su_wn'] non può essere negativo")
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
def _simula_asse(cfg, i, a_dist, v0):
    m = cfg["CORPO"]["massa_kg"]
    at, ma, rg = cfg["ATTUATORE"], cfg["MANOVRA"], cfg["REGOLATORE"]
    rif = VO.riferimento_minjerk if ma["profilo"] == "minimo_jerk" else VO.riferimento_gradino
    return VO.simula_asse(
        m, at["spinta_max_positiva_N"][i], at["tempo_salita_90_s"], rg["frequenza_propria_rad_s"],
        rg["smorzamento"], ma["distanza_m"][i], ma["tempo_manovra_s"], a_dist, ma["finestra_s"],
        cfg["ESECUZIONE"]["passo_integrazione_s"], rg["feedforward_riferimento"], rif,
        F_max_neg=at["spinta_max_negativa_N"][i], v0=v0, alfa_integrale=rg.get("polo_integrale_su_wn", 0.0))


def _indicatori(cfg, i, s):
    at, ma, en = cfg["ATTUATORE"], cfg["MANOVRA"], cfg["ENERGIA"]
    F_max = max(at["spinta_max_positiva_N"][i], at["spinta_max_negativa_N"][i])
    return VO.indicatori(s, ma["distanza_m"][i], ma["tempo_manovra_s"], ma["tolleranza_posizione_mm"] / 1000,
                         F_max, en["potenza_rif_W"], en["spinta_rif_N"], en["esponente"],
                         cfg["ESECUZIONE"]["passo_integrazione_s"])


def simula(cfg):
    """Caso peggiore: bias e v0 col modulo pieno su ogni asse, contro il moto, senza rumore.

    Ritorna (serie per asse, indicatori per asse).
    """
    di = cfg["DISTURBO"]
    serie, ind = [], []
    for i in range(3):
        verso = 1.0 if cfg["MANOVRA"]["distanza_m"][i] >= 0 else -1.0
        # m dv/dt = F - m a_d: a_d > 0 frena un moto positivo
        a_fn = (lambda t, i=i, verso=verso: verso * di["bias_g"] * VO.G0 + VO.disturbo_sinusoidale(
            t, di["sinusoide_ampiezza_g"][i], di["sinusoide_frequenza_Hz"][i], di["sinusoide_fase_gradi"][i]))
        s = _simula_asse(cfg, i, a_fn, -verso * di["velocita_iniziale_m_s"])
        serie.append(s)
        ind.append(_indicatori(cfg, i, s))
    return serie, ind


def monte_carlo(cfg):
    """Campioni casuali del disturbo: bias e v0 in direzione casuale, rumore in banda, fasi casuali.

    Ritorna None se campioni_monte_carlo = 0; altrimenti un dizionario con le statistiche per asse (JSON),
    gli inviluppi dell'errore ("inviluppo", array) e una riga per campione ("righe").
    """
    di, ma = cfg["DISTURBO"], cfg["MANOVRA"]
    N = di["campioni_monte_carlo"]
    if N <= 0:
        return None
    dt = cfg["ESECUZIONE"]["passo_integrazione_s"]
    n = int(round(ma["finestra_s"] / dt)) + 1
    t = np.arange(n) * dt
    rng = np.random.default_rng(di["seme"])
    u_bias, u_v0 = VO.direzioni_casuali(rng, N), VO.direzioni_casuali(rng, N)
    fasi = rng.uniform(0.0, 2 * math.pi, (N, 3))
    tol = ma["tolleranza_posizione_mm"]
    passo = max(1, int(round(0.01 / dt)))
    assi, inv, ind_tutti = {}, {"t": t[::passo]}, []
    for i in range(3):
        rum = VO.rumore_in_banda(n, dt, di["rumore_sigma_g"] * VO.G0, di["rumore_banda_Hz"], rng, N)
        ad = (di["bias_g"] * VO.G0 * u_bias[:, i:i + 1] + rum + di["sinusoide_ampiezza_g"][i] * VO.G0
              * np.sin(2 * math.pi * di["sinusoide_frequenza_Hz"][i] * t + fasi[:, i:i + 1]))
        s = _simula_asse(cfg, i, ad, di["velocita_iniziale_m_s"] * u_v0[:, i])
        ind = [_indicatori(cfg, i, VO.campione(s, j)) for j in range(N)]
        ind_tutti.append(ind)
        e = (s["x_rif"] - s["x"])[:, ::passo] * 1000
        inv[ASSI[i]] = {"p5": np.percentile(e, 5, axis=0), "p50": np.percentile(e, 50, axis=0),
                        "p95": np.percentile(e, 95, axis=0), "min": e.min(axis=0), "max": e.max(axis=0),
                        "finale": e[:, -1]}
        stat = {}
        for k in STAT_MC:
            a = np.abs([x[k] for x in ind])
            stat[k] = {"media": float(a.mean()), "p95": float(np.percentile(a, 95)), "max": float(a.max())}
        t_ass = np.array([x["tempo_assestamento_s"] if x["tempo_assestamento_s"] is not None else np.inf for x in ind])
        p95 = float(np.percentile(t_ass, 95, method="higher"))      # senza interpolare: t_ass contiene inf
        stat["tempo_assestamento_s"] = {"media": float(t_ass[np.isfinite(t_ass)].mean()) if np.isfinite(t_ass).any() else None,
                                        "p95": p95 if math.isfinite(p95) else None,
                                        "max": float(t_ass.max()) if np.isfinite(t_ass).all() else None}
        assi[ASSI[i]] = {"statistiche": stat, "quota_assestati": float(np.isfinite(t_ass).mean()),
                         "quota_in_tolleranza_a_T": float(np.mean([abs(x["errore_a_T_mm"]) <= tol for x in ind]))}
        del s, rum, ad
    tutti = np.array([[ind_tutti[i][j]["tempo_assestamento_s"] is not None for i in range(3)] for j in range(N)])
    righe = []
    for j in range(N):
        r = {"campione": j, **{f"bias_{a}_mg": di["bias_g"] * u_bias[j, i] * 1000 for i, a in enumerate(ASSI)},
             **{f"v0_{a}_mm_s": di["velocita_iniziale_m_s"] * u_v0[j, i] * 1000 for i, a in enumerate(ASSI)}}
        for i, a in enumerate(ASSI):
            x = ind_tutti[i][j]
            r.update({f"errore_a_T_{a}_mm": x["errore_a_T_mm"], f"errore_finale_{a}_mm": x["errore_finale_mm"],
                      f"assestamento_{a}_s": x["tempo_assestamento_s"], f"energia_{a}_J": x["energia_J"]})
        righe.append(r)
    return {"campioni": N, "seme": di["seme"], "assi": assi, "quota_tutti_assestati": float(tutti.all(axis=1).mean()),
            "inviluppo": inv, "righe": righe}


def spazio_e_tempo(cfg):
    """Spazio massimo nel tempo della manovra e tempo minimo per la distanza, alla spinta massima."""
    m, ma, at, di = cfg["CORPO"]["massa_kg"], cfg["MANOVRA"], cfg["ATTUATORE"], cfg["DISTURBO"]
    spazio = []
    for i in range(3):
        F = min(at["spinta_max_positiva_N"][i], at["spinta_max_negativa_N"][i])
        a_d = (di["bias_g"] + di["sinusoide_ampiezza_g"][i]) * VO.G0
        d0, d1 = VO.spazio_massimo(m, F, a_d, ma["tempo_manovra_s"])
        t0_, t1_ = VO.tempo_minimo(m, F, a_d, ma["distanza_m"][i])
        spazio.append({"asse": ASSI[i], "spinta_N": F, "spazio_max_senza_disturbo_m": float(d0),
                       "spazio_max_con_disturbo_m": float(d1), "tempo_min_senza_disturbo_s": t0_,
                       "tempo_min_con_disturbo_s": t1_ if math.isfinite(t1_) else None,
                       "disturbo_sulla_spinta": a_d * m / F})
    return spazio


def attuatore_e_ruote(cfg):
    """Margine di fase (anello simulato e PD di riferimento alle bande richieste) e bilancio delle ruote."""
    at, ma, ru, rg = cfg["ATTUATORE"], cfg["MANOVRA"], cfg["RUOTE"], cfg["REGOLATORE"]
    pm = {wc: DY.margine_fase(at["tempo_salita_90_s"], wc) for wc in ru["frequenze_margine_fase_rad_s"]}
    kp, kd, ki = VO.guadagni(rg["frequenza_propria_rad_s"], rg["smorzamento"], rg.get("polo_integrale_su_wn", 0.0))
    wc, pma = DY.margine_fase_anello(kp, kd, ki, at["tempo_salita_90_s"] / 2.3)
    anello = {"pulsazione_taglio_rad_s": wc, "margine_gradi": pma}
    rw = DY.bilancio_ruote(cfg["ENERGIA"]["spinta_rif_N"], ru["scostamento_baricentro_mm"] / 1000, ru["braccio_coppia_m"],
                           ru["squilibrio_coppia"], ru["spinta_per_unita_N"], ru["coppia_reazione_rotori_Nm"],
                           ru["momento_rotori_in_avvio_Nms"], ma["finestra_s"], ru["momento_ruote_max_Nms"])
    return pm, rw, anello


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
    log(f"{EX.descrivi_regolatore(rg)}; attuatore t90 = {at['tempo_salita_90_s']} s")
    log(f"Disturbo: {EX.descrivi_disturbo(di)}")
    run_anl, avvisi_anl = CF.confronta(cfg, ROOT)
    log(f"Dati [ANL] dell'input confrontati con la run dell'analisi {run_anl}: "
        + ("coerenti" if not avvisi_anl else f"{len(avvisi_anl)} differenze") if run_anl else "Dati [ANL] non controllati")
    for a in avvisi_anl:
        log(f"  ATTENZIONE: {a}")
    serie, ind = simula(cfg)
    mc = monte_carlo(cfg)
    pale = PA.analizza(cfg["PALE"], m, max(max(at["spinta_max_positiva_N"]), max(at["spinta_max_negativa_N"])))
    spazio = spazio_e_tempo(cfg)
    pm, rw, anello = attuatore_e_ruote(cfg)

    log("\nRISULTATI PER ASSE, CASO PEGGIORE (bias e v0 col modulo pieno su ogni asse, contro il moto)")
    log(f"  {'asse':<5}{'err a T':>10}{'err max':>10}{'sovra':>9}{'assest.':>10}{'F max':>9}{'F/Fmax':>8}{'sat.':>7}{'energia':>10}")
    for i, x in enumerate(ind):
        ass = f"{x['tempo_assestamento_s']:.2f} s" if x["tempo_assestamento_s"] is not None else "oltre"
        log(f"  {ASSI[i]:<5}{x['errore_a_T_mm']:>8.1f}mm{x['errore_max_mm']:>8.1f}mm{x['sovraelongazione_mm']:>7.1f}mm"
            f"{ass:>10}{x['spinta_max_usata_N']:>7.2f} N{x['spinta_su_massima']:>8.0%}{x['tempo_in_saturazione_s']:>5.2f} s"
            f"{x['energia_J']:>8.0f} J")
    if mc:
        log(f"\nMONTE CARLO ({mc['campioni']} campioni, seme {mc['seme']}): |errore| media / 95° percentile / massimo")
        for a, x in mc["assi"].items():
            st = x["statistiche"]
            log(f"  {a}: a fine manovra {st['errore_a_T_mm']['media']:.1f} / {st['errore_a_T_mm']['p95']:.1f} / "
                f"{st['errore_a_T_mm']['max']:.1f} mm; a fine finestra {st['errore_finale_mm']['media']:.1f} / "
                f"{st['errore_finale_mm']['p95']:.1f} / {st['errore_finale_mm']['max']:.1f} mm; "
                f"assestati {x['quota_assestati']:.0%}")
        log(f"  assestati su tutti e tre gli assi entro la finestra: {mc['quota_tutti_assestati']:.0%}")
    pa, pg, pmc = cfg["PALE"], pale["caso_peggiore"], pale["monte_carlo"]
    log(f"\nPALE ({pa['numero_pale']} per rotore, {pa['lunghezza_mm']:g} x {pa['larghezza_mm']:g} x {pa['spessore_mm']:g} mm, "
        f"densità {pa['densita_min_kg_m3']:g}-{pa['densita_max_kg_m3']:g} kg/m³, {pale['frequenza_Hz']:.0f} Hz ai giri di progetto)")
    log(f"  massa di una pala {pale['massa_pala_g']['min']:.3f}-{pale['massa_pala_g']['max']:.3f} g; squilibrio "
        f"{pmc['squilibrio_g_mm']['media']:.3f} g·mm in media, {pg['squilibrio_g_mm']:.3f} g·mm nel caso peggiore")
    log(f"  forza rotante di una ventola: {pmc['forza_N']['media']:.2f} N in media, {pmc['forza_N']['p95']:.2f} N al 95 %, "
        f"{pg['forza_N']:.2f} N nel caso peggiore ({pale['forza_peggiore_su_spinta']:.0%} della spinta massima)")
    log(f"  oscillazione del cubo: {pg['spostamento_cubo_um']:.3f} µm per ventola, "
        f"{pale['spostamento_peggiore_su_un_asse_um']:.3f} µm con {pale['ventole_fuori_asse']} ventole in fase")
    log(f"  momento angolare di un rotore {pale['momento_angolare_rotore_Nms']:.2e} N·m·s; residuo di una coppia "
        f"controrotante {pale['residuo_coppia_Nms']['p95']:.1e} N·m·s al 95 % ({pale['residuo_coppia_Nms']['peggiore']:.1e} peggiore)")
    log("\nSPAZIO MASSIMO E TEMPO MINIMO (spinta massima, da fermo a fermo)")
    for s in spazio:
        tmin = f"{s['tempo_min_con_disturbo_s']:.2f} s" if s["tempo_min_con_disturbo_s"] else "impossibile"
        log(f"  asse {s['asse']}: in {ma['tempo_manovra_s']} s al massimo {s['spazio_max_senza_disturbo_m']:.3f} m "
            f"({s['spazio_max_con_disturbo_m']:.3f} m con il disturbo nel caso peggiore); per {ma['distanza_m'][ASSI.index(s['asse'])]} m "
            f"servono almeno {s['tempo_min_senza_disturbo_s']:.2f} s ({tmin} con disturbo); il disturbo è il "
            f"{s['disturbo_sulla_spinta']:.0%} della spinta massima")
    log("\nATTUATORE E RUOTE")
    log(f"  tempo di salita al 90 %: {at['tempo_salita_90_s']:.3f} s")
    log(f"  margine di fase dell'anello simulato ({'PID' if rg.get('polo_integrale_su_wn', 0.0) else 'PD'} + attuatore): {anello['margine_gradi']:.1f}° "
        f"alla pulsazione di taglio {anello['pulsazione_taglio_rad_s']:.2f} rad/s")
    if not anello["margine_gradi"] >= 45.0:
        log(f"  ATTENZIONE: margine di fase dell'anello sotto 45° ({anello['margine_gradi']:.1f}°): "
            "ritardo dell'attuatore troppo alto per questa banda")
    log("  per confronto, regolatore PD di riferimento con zero a wc/3 (non è l'anello simulato): "
        + ", ".join(f"{p:.0f}° a {wc:g} rad/s" for wc, p in pm.items()))
    log(f"  ruote di reazione: momento in finestra {rw['H_finestra']:.3f} N·m·s = {rw['quota_ruota']:.0%} della capacità "
        f"({ru['momento_ruote_max_Nms']} N·m·s)" + ("  -> SATURANO" if rw["quota_ruota"] > 1 else ""))

    # file di uscita
    formati = es["formato_grafici"]
    scritti = []
    scritti += EX.grafico_moto(serie, cfg, os.path.join(cart, "01_grafici", "01_moto_tre_assi"), formati)
    scritti += EX.grafico_spazio_massimo(cfg, os.path.join(cart, "01_grafici", "02_spazio_massimo"), formati)
    scritti.append(EX.scrivi_serie(serie, es["passo_integrazione_s"], os.path.join(cart, "02_dati", "serie_temporali.csv")))
    if mc:
        scritti += EX.grafico_monte_carlo(mc, cfg, os.path.join(cart, "01_grafici", "03_monte_carlo"), formati)
        scritti.append(EX.scrivi_monte_carlo(mc, os.path.join(cart, "02_dati", "monte_carlo.csv")))
    scritti += EX.grafico_pale(pale, cfg, os.path.join(cart, "01_grafici", "04_pale"), formati)
    riep = {"data": f"{dt.datetime.now():%d/%m/%Y %H:%M}", "impronta": imp, "massa_kg": m,
            "assi": {ASSI[i]: ind[i] for i in range(3)},
            "monte_carlo": {k: v for k, v in mc.items() if k not in ("inviluppo", "righe")} if mc else None,
            "pale": {k: v for k, v in pale.items() if k != "U_campioni_g_mm"},
            "spazio_massimo": spazio,
            "margine_fase_gradi": {str(k): v for k, v in pm.items()}, "margine_fase_anello": anello, "t_salita_90_s": at["tempo_salita_90_s"], "ruote": rw,
            "confronto_analisi": {"run": run_anl, "avvisi": avvisi_anl}}
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
