"""Riga di comando della dinamica di volo: input.py -> risultati/<caso>/.

Sequenza: lettura e controllo dell'input, verifiche contro soluzioni analitiche (una volta); poi, per ogni catena
del dimensionamento indicata da CASO["nome"] / CASO["varianti"] (una sola nel caso senza confronto statore; Statore e
NoStatore; i casi di una serie): analisi delle pale, margine di fase e, per ogni ambiente attivo di AMBIENTI,
simulazione dei tre assi, Monte Carlo, potenza totale, spazio massimo e tempo minimo, ruote (propulsore.py) e file di
uscita in risultati/<caso>/[<catena>/]<ambiente>/; infine CONFRONTO.md di ogni catena e, con più catene,
CONFRONTO_catene.* (confronto_catene.py).

    python run_dinamica.py --elenca     stampa le catene trovate e le cartelle di uscita, senza simulare
"""
import argparse
import copy
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
from . import dimensionamento as DM
from . import export as EX
from . import pale as PA
from . import propulsore as DY
from . import volo as VO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))    # cartella del progetto
INPUT_FILE = os.path.join(ROOT, "input.py")
ASSI = "XYZ"
SEZIONI = ("ESECUZIONE", "CORPO", "ATTUATORE", "MANOVRA", "DISTURBO", "REGOLATORE", "ENERGIA", "RUOTE", "PALE", "MOTORE")
# sezioni che un ambiente può sovrascrivere (le chiavi dell'ambiente si fondono sulla sezione di base)
SEZ_AMBIENTE = ("CORPO", "ATTUATORE", "MANOVRA", "DISTURBO", "REGOLATORE", "ENERGIA", "RUOTE")
PROFILI = tuple(VO.PROFILI)
# chiavi di ESECUZIONE che non cambiano i risultati: fuori dall'impronta
SOLO_FORMA = ("etichetta", "cartella_output", "formato_grafici", "verifiche")
CHIAVI_DISTURBO = ("bias_g", "rumore_sigma_g", "rumore_banda_Hz", "velocita_iniziale_m_s", "sinusoide_ampiezza_g",
                   "sinusoide_frequenza_Hz", "sinusoide_fase_gradi", "campioni_monte_carlo", "seme")
# indicatori riassunti nel Monte Carlo (sui valori assoluti): media, 95° percentile, massimo
STAT_MC = ("errore_a_T_mm", "errore_finale_mm", "errore_max_mm", "sovraelongazione_mm", "spinta_su_massima",
           "tempo_in_saturazione_s", "energia_J")
# indicatori della potenza totale (somma dei tre assi)
STAT_POTENZA = ("potenza_picco_W", "energia_J", "potenza_media_W", "corrente_picco_A")


# ---------------------------------------------------------------- input
def leggi_input(percorso):
    """Dizionari dell'input (SEZIONI), CASO e AMBIENTI, senza i dati del dimensionamento; controlla le chiavi doppie."""
    spec = importlib.util.spec_from_file_location("input_dinamica", percorso)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = {k: dict(getattr(mod, k)) for k in SEZIONI}
    cfg["CASO"] = {**CA.CASO_PREDEFINITO, **dict(getattr(mod, "CASO", None) or {})}
    amb = getattr(mod, "AMBIENTI", None)
    if not amb:
        raise ValueError("manca la sezione AMBIENTI in input.py (un ambiente per soluzione, vedi input.py)")
    cfg["AMBIENTI"] = {str(k): dict(v) for k, v in dict(amb).items()}
    doppi = DM.chiavi_vietate(cfg)
    if doppi:
        raise ValueError("Errori in input:" + chr(10) + " - " + (chr(10) + " - ").join(doppi))
    for sez, k in (("ENERGIA", "rendimento_elettrico"), ("ENERGIA", "tensione_batteria_V"),
                   ("RUOTE", "squilibrio_coppia"), ("RUOTE", "vortice_residuo_statore")):
        if k not in cfg[sez]:
            raise ValueError(f"manca {sez}['{k}'] in input.py (serve per i dati importati dal dimensionamento)")
    return cfg


def trova_catene(cfg, radice_dimensionamento=None):
    """Catene del dimensionamento di CASO["nome"] / CASO["varianti"] (vedi dimensionamento.trova_catene)."""
    return DM.trova_catene(radice_dimensionamento, cfg["CASO"].get("nome"), cfg["CASO"].get("varianti", "tutte"))


def cfg_catena(base, catena):
    """Copia dell'input con i dati di una catena importati e controllati; cfg["DIMENSIONAMENTO"] li descrive."""
    cfg = copy.deepcopy(base)
    valori, fonti, avvisi = DM.importa(cfg, catena)
    DM.applica(cfg, valori)
    cfg["DIMENSIONAMENTO"] = {"caso": os.path.basename(os.path.normpath(catena.radice_caso)), "etichetta": catena.etichetta,
                              "variante": catena.variante, "valori": valori, "fonti": fonti, "avvisi": avvisi}
    _controlla(cfg)
    return cfg


def dati_dimensionamento(dim):
    """Dati importati da una catena, come si scrivono in dati_dimensionamento.json (e si passano al confronto)."""
    info = dim["valori"].get("_info") or {}
    return {"caso": dim["caso"], "etichetta": dim["etichetta"], "variante": dim["variante"],
            "L_disk_m": info.get("L_disk_m"), "masse_g": info.get("masse_g"),
            "fonte_coppia_residua": info.get("fonte_coppia_residua"),
            "valori": dim["valori"], "fonti": dim["fonti"], "avvisi": dim["avvisi"]}


def carica_input(percorso, radice_dimensionamento=None):
    """Dizionari dell'input (SEZIONI) più CASO, con i dati della prima catena del dimensionamento importati e controllati.

    I dati di progetto (massa, manovra, spinta, potenza, pale, t90) si leggono dalle catene del dimensionamento indicate
    da CASO["nome"] (senza il suffisso "__xxx") e CASO["varianti"], cercate in radice_dimensionamento (predefinita:
    ../Dimensionamento_Sistema_Propulsivo/risultati).  Il risultato della prima catena è in cfg["DIMENSIONAMENTO"]; la
    run importa ogni catena con cfg_catena().
    """
    base = leggi_input(percorso)
    return cfg_catena(base, trova_catene(base, radice_dimensionamento)[0])


def ambienti_attivi(cfg):
    return [n for n, a in cfg["AMBIENTI"].items() if a.get("attivo", True)]


def cfg_ambiente(cfg, nome):
    """Input di un ambiente: sezioni di base con le sovrascritture dell'ambiente, spinta massima x sigma.

    Aggiunge cfg["AMBIENTE"] con nome, pressione, sigma = pressione / pressione di progetto, fattore di
    potenza 1 / sqrt(sigma) e spinta massima di progetto.
    """
    a = cfg["AMBIENTI"][nome]
    c = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cfg.items() if k != "AMBIENTI"}
    for sez in SEZ_AMBIENTE:
        c[sez].update(a.get(sez, {}))
    at = c["ATTUATORE"]
    sigma = a["pressione_Pa"] / at["pressione_progetto_Pa"]
    c["AMBIENTE"] = {"nome": nome, "pressione_Pa": a["pressione_Pa"], "sigma": sigma,
                     "fattore_potenza": 1.0 / math.sqrt(sigma),
                     "spinta_max_progetto_N": [float(f) for f in at["spinta_max_positiva_N"]]}
    for k in ("spinta_max_positiva_N", "spinta_max_negativa_N"):
        at[k] = [float(f) for f in VO.spinta_ambiente(at[k], sigma)]
    return c


def _controlla_ambienti(c):
    """Struttura di AMBIENTI e chiavi nuove di ATTUATORE ed ENERGIA; ritorna l'elenco degli errori."""
    err = []
    if "pressione_progetto_Pa" not in c["ATTUATORE"]:
        err.append("manca ATTUATORE['pressione_progetto_Pa']")
    if "tensione_batteria_V" not in c["ENERGIA"]:
        err.append("manca ENERGIA['tensione_batteria_V']")
    if err:
        return err
    if c["ATTUATORE"]["pressione_progetto_Pa"] <= 0 or c["ENERGIA"]["tensione_batteria_V"] <= 0:
        err.append("ATTUATORE['pressione_progetto_Pa'] ed ENERGIA['tensione_batteria_V'] devono essere maggiori di zero")
    for n, a in c["AMBIENTI"].items():
        if not n or n == "Pale" or any(ch in n for ch in '<>:"/|?*' + chr(92)):
            err.append(f"AMBIENTI: nome '{n}' non valido come cartella ('Pale' è riservato)")
        if "pressione_Pa" not in a or not a["pressione_Pa"] > 0:
            err.append(f"AMBIENTI['{n}']['pressione_Pa'] mancante o non positiva")
        ignote = sorted(set(a) - {"attivo", "pressione_Pa"} - set(SEZ_AMBIENTE))
        if ignote:
            err.append(f"AMBIENTI['{n}']: chiavi sconosciute {', '.join(ignote)} (ammesse: attivo, pressione_Pa, "
                       f"{', '.join(SEZ_AMBIENTE)})")
    if not ambienti_attivi(c):
        err.append("AMBIENTI: nessun ambiente attivo")
    return err


def _controlla(c):
    err = _controlla_ambienti(c)
    if not err:
        for cx in [c] + [cfg_ambiente(c, n) for n in ambienti_attivi(c)]:
            for e in _controlla_sezioni(cx):
                if e not in err:
                    err.append(e)
    unknown = sorted(set(c["CASO"]) - set(CA.CASO_PREDEFINITO))
    if unknown:
        err.append(f"chiavi sconosciute in CASO: {', '.join(unknown)}")
    try:
        DM._selezione_varianti(c["CASO"].get("varianti", "tutte"))
    except ValueError as e:
        err.append(str(e))
    if err:
        raise ValueError("Errori in input:" + chr(10) + " - " + (chr(10) + " - ").join(err))


def _controlla_sezioni(c):
    """Controlli sulle sezioni (di base o già fuse con un ambiente); ritorna l'elenco degli errori."""
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
    if c["MANOVRA"]["profilo"] not in PROFILI:
        err.append("MANOVRA['profilo'] deve essere " + " oppure ".join(f"'{p}'" for p in PROFILI))
    if c["MANOVRA"]["tempo_manovra_s"] <= 0 or c["MANOVRA"]["finestra_s"] < c["MANOVRA"]["tempo_manovra_s"]:
        err.append("serve 0 < tempo_manovra_s <= finestra_s")
    if c["ATTUATORE"]["tempo_salita_90_s"] <= 0:
        err.append("tempo_salita_90_s deve essere maggiore di zero")
    elif c["ESECUZIONE"]["passo_integrazione_s"] > c["ATTUATORE"]["tempo_salita_90_s"] / 2.3 / 2:
        err.append("passo_integrazione_s troppo grande rispetto al ritardo dell'attuatore (t90 / 2,3): "
                   "l'integrazione diventerebbe instabile; usa un passo <= t90 / 4,6")
    return err


def impronta(cfg):
    """Hash breve dei dati che cambiano i risultati: stessa impronta = stessi risultati."""
    dati = {k: v for k, v in cfg.items() if k not in ("CASO", "AMBIENTI", "DIMENSIONAMENTO")}
    dati["DIMENSIONAMENTO"] = cfg["DIMENSIONAMENTO"]["caso"]      # i valori importati sono già nelle sezioni
    dati["AMBIENTI"] = {n: {k: v for k, v in a.items() if k != "attivo"} for n, a in cfg["AMBIENTI"].items()
                        if a.get("attivo", True)}
    dati["ESECUZIONE"] = {k: v for k, v in cfg["ESECUZIONE"].items() if k not in SOLO_FORMA}
    return hashlib.sha1(json.dumps(dati, sort_keys=True, default=str).encode()).hexdigest()[:8]


def impronta_run(imps, piatto):
    """Impronta della run: quella della catena unica (struttura piatta), altrimenti un hash delle impronte di tutte le
    catene con le loro etichette (imps: {etichetta: impronta o None se l'importazione è fallita})."""
    if piatto:
        return next(iter(imps.values()))
    return hashlib.sha1(json.dumps(imps, sort_keys=True).encode()).hexdigest()[:8]


def nome_automatico(cfg, imp):
    return (f"m{cfg['CORPO']['massa_kg']:.2f}kg_d{cfg['MANOVRA']['distanza_m'][0]:.2f}m"
            f"_t{cfg['MANOVRA']['tempo_manovra_s']:.1f}s_h{imp}")


# ---------------------------------------------------------------- calcolo
# cfg qui sotto è l'input di un ambiente (cfg_ambiente): spinta massima già moltiplicata per sigma
def _simula_asse(cfg, i, a_dist, v0):
    m = cfg["CORPO"]["massa_kg"]
    at, ma, rg = cfg["ATTUATORE"], cfg["MANOVRA"], cfg["REGOLATORE"]
    rif = VO.PROFILI[ma["profilo"]]
    return VO.simula_asse(
        m, at["spinta_max_positiva_N"][i], at["tempo_salita_90_s"], rg["frequenza_propria_rad_s"],
        rg["smorzamento"], ma["distanza_m"][i], ma["tempo_manovra_s"], a_dist, ma["finestra_s"],
        cfg["ESECUZIONE"]["passo_integrazione_s"], rg["feedforward_riferimento"], rif,
        F_max_neg=at["spinta_max_negativa_N"][i], v0=v0, alfa_integrale=rg.get("polo_integrale_su_wn", 0.0))


def _potenza(cfg, F):
    """Potenza elettrica di un asse nell'ambiente (vedi VO.potenza_elettrica)."""
    en = cfg["ENERGIA"]
    return VO.potenza_elettrica(F, en["potenza_rif_W"], en["spinta_rif_N"], en["esponente"], cfg["AMBIENTE"]["sigma"])


def _indicatori(cfg, i, s):
    at, ma, en = cfg["ATTUATORE"], cfg["MANOVRA"], cfg["ENERGIA"]
    F_max = max(at["spinta_max_positiva_N"][i], at["spinta_max_negativa_N"][i])
    return VO.indicatori(s, ma["distanza_m"][i], ma["tempo_manovra_s"], ma["tolleranza_posizione_mm"] / 1000,
                         F_max, en["potenza_rif_W"], en["spinta_rif_N"], en["esponente"],
                         cfg["ESECUZIONE"]["passo_integrazione_s"], cfg["AMBIENTE"]["sigma"])


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


def potenza_caso_peggiore(cfg, serie):
    """Potenza elettrica totale (somma dei tre assi) nel caso peggiore.

    Ritorna (indicatori scalari, potenza dei tre assi, potenza totale) con le curve come array.
    """
    P_assi = [_potenza(cfg, s["F"]) for s in serie]
    r = VO.potenza_totale(P_assi, serie[0]["t"], cfg["ENERGIA"]["tensione_batteria_V"])
    P_tot = r.pop("P_tot")
    return {k: float(v) for k, v in r.items()}, P_assi, P_tot


def monte_carlo(cfg):
    """Campioni casuali del disturbo: bias e v0 in direzione casuale, rumore in banda, fasi casuali.

    Ritorna None se campioni_monte_carlo = 0; altrimenti un dizionario con le statistiche per asse (JSON),
    quelle della potenza totale, gli inviluppi dell'errore ("inviluppo", array) e una riga per campione ("righe").
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
    assi, inv, ind_tutti, P_assi = {}, {"t": t[::passo]}, [], []
    for i in range(3):
        rum = VO.rumore_in_banda(n, dt, di["rumore_sigma_g"] * VO.G0, di["rumore_banda_Hz"], rng, N)
        ad = (di["bias_g"] * VO.G0 * u_bias[:, i:i + 1] + rum + di["sinusoide_ampiezza_g"][i] * VO.G0
              * np.sin(2 * math.pi * di["sinusoide_frequenza_Hz"][i] * t + fasi[:, i:i + 1]))
        s = _simula_asse(cfg, i, ad, di["velocita_iniziale_m_s"] * u_v0[:, i])
        ind = [_indicatori(cfg, i, VO.campione(s, j)) for j in range(N)]
        ind_tutti.append(ind)
        P_assi.append(_potenza(cfg, s["F"]))
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
    tot = VO.potenza_totale(P_assi, t, cfg["ENERGIA"]["tensione_batteria_V"])
    del P_assi
    potenza = {k: {"media": float(tot[k].mean()), "p95": float(np.percentile(tot[k], 95)), "max": float(tot[k].max())}
               for k in STAT_POTENZA}
    tutti = np.array([[ind_tutti[i][j]["tempo_assestamento_s"] is not None for i in range(3)] for j in range(N)])
    righe = []
    for j in range(N):
        r = {"campione": j, **{f"bias_{a}_mg": di["bias_g"] * u_bias[j, i] * 1000 for i, a in enumerate(ASSI)},
             **{f"v0_{a}_mm_s": di["velocita_iniziale_m_s"] * u_v0[j, i] * 1000 for i, a in enumerate(ASSI)}}
        for i, a in enumerate(ASSI):
            x = ind_tutti[i][j]
            r.update({f"errore_a_T_{a}_mm": x["errore_a_T_mm"], f"errore_finale_{a}_mm": x["errore_finale_mm"],
                      f"assestamento_{a}_s": x["tempo_assestamento_s"], f"energia_{a}_J": x["energia_J"]})
        r.update({"potenza_picco_totale_W": float(tot["potenza_picco_W"][j]), "energia_totale_J": float(tot["energia_J"][j]),
                  "corrente_picco_A": float(tot["corrente_picco_A"][j])})
        righe.append(r)
    return {"campioni": N, "seme": di["seme"], "assi": assi, "quota_tutti_assestati": float(tutti.all(axis=1).mean()),
            "potenza_totale": potenza, "inviluppo": inv, "righe": righe}


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


def margine_fase(cfg):
    """Margine di fase (anello simulato e PD di riferimento alle bande richieste): non dipende dall'ambiente."""
    at, ru, rg = cfg["ATTUATORE"], cfg["RUOTE"], cfg["REGOLATORE"]
    pm = {wc: DY.margine_fase(at["tempo_salita_90_s"], wc) for wc in ru["frequenze_margine_fase_rad_s"]}
    kp, kd, ki = VO.guadagni(rg["frequenza_propria_rad_s"], rg["smorzamento"], rg.get("polo_integrale_su_wn", 0.0))
    wc, pma = DY.margine_fase_anello(kp, kd, ki, at["tempo_salita_90_s"] / 2.3)
    return pm, {"pulsazione_taglio_rad_s": wc, "margine_gradi": pma}


def ruote(cfg):
    """Bilancio del momento angolare delle ruote di reazione nella finestra dell'ambiente."""
    ma, ru = cfg["MANOVRA"], cfg["RUOTE"]
    return DY.bilancio_ruote(cfg["ENERGIA"]["spinta_rif_N"], ru["scostamento_baricentro_mm"] / 1000, ru["braccio_coppia_m"],
                             ru["squilibrio_coppia"], ru["spinta_per_unita_N"], ru["coppia_reazione_rotori_Nm"],
                             ru["momento_rotori_in_avvio_Nms"], ma["finestra_s"], ru["momento_ruote_max_Nms"])


# ---------------------------------------------------------------- un ambiente
def esegui_ambiente(cfg, cart, nome_caso, imp, data, pm, anello, log):
    """Simula e scrive la soluzione di un ambiente in cart (già preparata); ritorna il riepilogo (dizionario)."""
    amb, ma, at, di = cfg["AMBIENTE"], cfg["MANOVRA"], cfg["ATTUATORE"], cfg["DISTURBO"]
    en, es = cfg["ENERGIA"], cfg["ESECUZIONE"]
    log(f"\n{'=' * 100}\nAMBIENTE {amb['nome']}: pressione {amb['pressione_Pa']:g} Pa, sigma = {amb['sigma']:.4f}")
    log(f"  spinta massima {at['spinta_max_positiva_N']} N (+), {at['spinta_max_negativa_N']} N (-) "
        f"(progetto {amb['spinta_max_progetto_N']} N x sigma); fattore di potenza 1/sqrt(sigma) = {amb['fattore_potenza']:.4f}")
    log(f"  manovra {ma['distanza_m']} m in {ma['tempo_manovra_s']} s (profilo {ma['profilo']}), finestra {ma['finestra_s']} s")
    log(f"  disturbo: {EX.descrivi_disturbo(di)}")
    serie, ind = simula(cfg)
    pot, P_assi, P_tot = potenza_caso_peggiore(cfg, serie)
    mc = monte_carlo(cfg)
    spazio = spazio_e_tempo(cfg)
    rw = ruote(cfg)

    log("\nRISULTATI PER ASSE, CASO PEGGIORE (bias e v0 col modulo pieno su ogni asse, contro il moto)")
    log(f"  {'asse':<5}{'err a T':>10}{'err max':>10}{'sovra':>9}{'assest.':>10}{'F max':>9}{'F/Fmax':>8}{'sat.':>7}{'energia':>10}")
    for i, x in enumerate(ind):
        ass = f"{x['tempo_assestamento_s']:.2f} s" if x["tempo_assestamento_s"] is not None else "oltre"
        log(f"  {ASSI[i]:<5}{x['errore_a_T_mm']:>8.1f}mm{x['errore_max_mm']:>8.1f}mm{x['sovraelongazione_mm']:>7.1f}mm"
            f"{ass:>10}{x['spinta_max_usata_N']:>7.2f} N{x['spinta_su_massima']:>8.0%}{x['tempo_in_saturazione_s']:>5.2f} s"
            f"{x['energia_J']:>8.1f} J")
    log(f"  POTENZA TOTALE (3 assi, {en['tensione_batteria_V']:g} V): picco {pot['potenza_picco_W']:.2f} W, energia "
        f"{pot['energia_J']:.1f} J, media {pot['potenza_media_W']:.2f} W, corrente di picco {pot['corrente_picco_A']:.3f} A")
    if mc:
        log(f"\nMONTE CARLO ({mc['campioni']} campioni, seme {mc['seme']}): |errore| media / 95° percentile / massimo")
        for a, x in mc["assi"].items():
            st = x["statistiche"]
            log(f"  {a}: a fine manovra {st['errore_a_T_mm']['media']:.2f} / {st['errore_a_T_mm']['p95']:.2f} / "
                f"{st['errore_a_T_mm']['max']:.2f} mm; a fine finestra {st['errore_finale_mm']['media']:.2f} / "
                f"{st['errore_finale_mm']['p95']:.2f} / {st['errore_finale_mm']['max']:.2f} mm; "
                f"assestati {x['quota_assestati']:.0%}")
        log(f"  assestati su tutti e tre gli assi entro la finestra: {mc['quota_tutti_assestati']:.0%}")
        pt = mc["potenza_totale"]
        log("  potenza totale, media / 95° percentile / massimo: " + "; ".join(
            f"{nome} {pt[k]['media']:.{d}f} / {pt[k]['p95']:.{d}f} / {pt[k]['max']:.{d}f} {u}"
            for k, nome, u, d in (("potenza_picco_W", "picco", "W", 2), ("energia_J", "energia", "J", 1),
                                  ("potenza_media_W", "media", "W", 2), ("corrente_picco_A", "corrente di picco", "A", 3))))
    log("\nSPAZIO MASSIMO E TEMPO MINIMO (spinta massima dell'ambiente, da fermo a fermo)")
    for s in spazio:
        tmin = f"{s['tempo_min_con_disturbo_s']:.2f} s" if s["tempo_min_con_disturbo_s"] else "impossibile"
        log(f"  asse {s['asse']}: in {ma['tempo_manovra_s']} s al massimo {s['spazio_max_senza_disturbo_m']:.3f} m "
            f"({s['spazio_max_con_disturbo_m']:.3f} m con il disturbo nel caso peggiore); per {ma['distanza_m'][ASSI.index(s['asse'])]} m "
            f"servono almeno {s['tempo_min_senza_disturbo_s']:.2f} s ({tmin} con disturbo); il disturbo è il "
            f"{s['disturbo_sulla_spinta']:.1%} della spinta massima")
    log(f"  ruote di reazione: momento in finestra {rw['H_finestra']:.3f} N·m·s = {rw['quota_ruota']:.0%} della capacità "
        f"({cfg['RUOTE']['momento_ruote_max_Nms']} N·m·s)" + ("  -> SATURANO" if rw["quota_ruota"] > 1 else ""))

    formati = es["formato_grafici"]
    scritti = []
    scritti += EX.grafico_moto(serie, cfg, (P_assi, P_tot), os.path.join(cart, "01_grafici", "01_moto_tre_assi"), formati)
    scritti += EX.grafico_spazio_massimo(cfg, os.path.join(cart, "01_grafici", "02_spazio_massimo"), formati)
    scritti.append(EX.scrivi_serie(serie, P_assi, P_tot, es["passo_integrazione_s"],
                                   os.path.join(cart, "02_dati", "serie_temporali.csv")))
    if mc:
        scritti += EX.grafico_monte_carlo(mc, cfg, os.path.join(cart, "01_grafici", "03_monte_carlo"), formati)
        scritti.append(EX.scrivi_monte_carlo(mc, os.path.join(cart, "02_dati", "monte_carlo.csv")))
    riep = {"data": data, "impronta": imp, "ambiente": {**amb}, "massa_kg": cfg["CORPO"]["massa_kg"],
            "disturbo": {k: di[k] for k in ("bias_g", "rumore_sigma_g", "rumore_banda_Hz", "velocita_iniziale_m_s")},
            "finestra_s": ma["finestra_s"], "tempo_manovra_s": ma["tempo_manovra_s"],
            "spinta_max_N": {"positiva": at["spinta_max_positiva_N"], "negativa": at["spinta_max_negativa_N"]},
            "assi": {ASSI[i]: ind[i] for i in range(3)}, "potenza_totale": pot,
            "monte_carlo": {k: v for k, v in mc.items() if k not in ("inviluppo", "righe")} if mc else None,
            "spazio_massimo": spazio,
            "margine_fase_gradi": {str(k): v for k, v in pm.items()}, "margine_fase_anello": anello,
            "t_salita_90_s": at["tempo_salita_90_s"], "ruote": rw}
    scritti.append(EX.scrivi_riepilogo(riep, os.path.join(cart, "00_sintesi", "riepilogo.json")))
    rel = [os.path.relpath(p, cart).replace(os.sep, "/") for p in scritti]
    ris = EX.scrivi_risultato(riep, cfg, nome_caso, sorted(["00_sintesi/RISULTATO.md"] + rel),
                              os.path.join(cart, "00_sintesi", "RISULTATO.md"))
    for p in [ris] + scritti:
        log(f"  scritto: {amb['nome']}/{os.path.relpath(p, cart)}".replace(os.sep, "/"))
    return riep


# ---------------------------------------------------------------- run
def esegui_catena(cfg, cart, nome, imp, data, log):
    """Una catena del dimensionamento: pale, margine di fase e tutti gli ambienti attivi in cart (già preparata)."""
    es = cfg["ESECUZIONE"]
    attivi = ambienti_attivi(cfg)
    m, at, rg = cfg["CORPO"]["massa_kg"], cfg["ATTUATORE"], cfg["REGOLATORE"]
    log(f"Massa {m:.2f} kg nel baricentro; ambienti attivi: {', '.join(attivi)}")
    log(f"{EX.descrivi_regolatore(rg)}; attuatore t90 = {at['tempo_salita_90_s']} s; "
        f"dati di progetto alla pressione {at['pressione_progetto_Pa']:g} Pa")
    dim = cfg["DIMENSIONAMENTO"]
    var = f", variante {dim['variante']}" if dim["variante"] else ""
    log(f"\nDATI DAL DIMENSIONAMENTO (caso {dim['caso']}{var}):")
    for k, x in dim["valori"].items():
        if not k.startswith("_"):
            log(f"  {k:<36}{EX.formatta_valore(x):<30}{dim['fonti'][k]}")
    J = dim["valori"]["_J"]
    log(f"  inerzia dell'albero: pale {J['pale']:.3g} + mozzo {J['mozzo']:.3g} + motore {J['motore']:.3g} = "
        f"{J['totale']:.3g} kg·m²; salita al 90 % dei giri in {J['salita_s']:.3f} s")
    for a in dim["avvisi"]:
        log(f"  ATTENZIONE: {a}")
    os.makedirs(cart, exist_ok=True)
    with open(os.path.join(cart, "dati_dimensionamento.json"), "w", encoding="utf-8") as fh:
        json.dump(dati_dimensionamento(dim), fh, indent=1, ensure_ascii=False)

    # calcoli che non dipendono dall'ambiente: una volta sola per catena
    pale = PA.analizza(cfg["PALE"], m, max(max(at["spinta_max_positiva_N"]), max(at["spinta_max_negativa_N"])))
    pm, anello = margine_fase(cfg)
    pa, pg, pmc = cfg["PALE"], pale["caso_peggiore"], pale["monte_carlo"]
    log(f"\nPALE (non dipendono dall'ambiente; {pa['numero_pale']} per rotore, {pa['lunghezza_mm']:g} x {pa['larghezza_mm']:g} x "
        f"{pa['spessore_mm']:g} mm, densità {pa['densita_min_kg_m3']:g}-{pa['densita_max_kg_m3']:g} kg/m³, "
        f"{pale['frequenza_Hz']:.0f} Hz ai giri di progetto)")
    log(f"  massa di una pala {pale['massa_pala_g']['min']:.3f}-{pale['massa_pala_g']['max']:.3f} g; squilibrio "
        f"{pmc['squilibrio_g_mm']['media']:.3f} g·mm in media, {pg['squilibrio_g_mm']:.3f} g·mm nel caso peggiore")
    log(f"  forza rotante di una ventola: {pmc['forza_N']['media']:.2f} N in media, {pmc['forza_N']['p95']:.2f} N al 95 %, "
        f"{pg['forza_N']:.2f} N nel caso peggiore ({pale['forza_peggiore_su_spinta']:.0%} della spinta massima di progetto)")
    log(f"  oscillazione del cubo: {pg['spostamento_cubo_um']:.3f} µm per ventola, "
        f"{pale['spostamento_peggiore_su_un_asse_um']:.3f} µm con {pale['ventole_fuori_asse']} ventole in fase")
    log(f"  momento angolare di un rotore {pale['momento_angolare_rotore_Nms']:.2e} N·m·s; residuo di una coppia "
        f"controrotante {pale['residuo_coppia_Nms']['p95']:.1e} N·m·s al 95 % ({pale['residuo_coppia_Nms']['peggiore']:.1e} peggiore)")
    log("\nATTUATORE")
    log(f"  tempo di salita al 90 %: {at['tempo_salita_90_s']:.3f} s")
    log(f"  margine di fase dell'anello simulato ({'PID' if rg.get('polo_integrale_su_wn', 0.0) else 'PD'} + attuatore): {anello['margine_gradi']:.1f}° "
        f"alla pulsazione di taglio {anello['pulsazione_taglio_rad_s']:.2f} rad/s")
    if not anello["margine_gradi"] >= 45.0:
        log(f"  ATTENZIONE: margine di fase dell'anello sotto 45° ({anello['margine_gradi']:.1f}°): "
            "ritardo dell'attuatore troppo alto per questa banda")
    log("  per confronto, regolatore PD di riferimento con zero a wc/3 (non è l'anello simulato): "
        + ", ".join(f"{p:.0f}° a {wc:g} rad/s" for wc, p in pm.items()))
    scritti_pale = [EX.scrivi_pale(pale, cfg, os.path.join(cart, "Pale"), cfg["ESECUZIONE"]["formato_grafici"])]

    riepiloghi, cfgs = {}, {}
    for nome_amb in attivi:
        cfgs[nome_amb] = cfg_ambiente(cfg, nome_amb)
        riepiloghi[nome_amb] = esegui_ambiente(cfgs[nome_amb], os.path.join(cart, nome_amb), nome, imp, data, pm, anello, log)

    confronto = EX.scrivi_confronto(riepiloghi, cfgs, nome, data, dim, os.path.join(cart, "CONFRONTO.md"))
    log("")
    for p in scritti_pale + [confronto]:
        log(f"  scritto: {os.path.relpath(p, cart)}".replace(os.sep, "/"))
    return riepiloghi


def pianifica(cfg, catene, radice_dimensionamento=None):
    """Dove vanno le uscite: ritorna (cartella dei risultati, nome del caso, struttura piatta, [(catena, cartella di uscita)])."""
    base = os.path.join(ROOT, cfg["ESECUZIONE"].get("cartella_output", "risultati"))
    nome = CA.nome_caso(cfg["CASO"], "")
    piatto = len(catene) == 1 and catene[0].variante is None
    cart = os.path.join(base, nome)
    return base, nome, piatto, [(c, DM.cartella_uscita(cart, c, piatto)) for c in catene]


def elenca(cfg, catene, radice_dimensionamento=None):
    """Stampa le catene trovate e la cartella di uscita di ognuna (non simula)."""
    base, nome, piatto, piano = pianifica(cfg, catene, radice_dimensionamento)
    radice = radice_dimensionamento or DM.RADICE_PREDEFINITA
    print(f"CASO['nome'] = {cfg['CASO'].get('nome')!r}, CASO['varianti'] = {cfg['CASO'].get('varianti', 'tutte')!r}")
    print(f"Radice del dimensionamento: {os.path.abspath(radice)}")
    print(f"Catene trovate: {len(piano)}; risultati in {os.path.join(base, nome)}"
          + (" (struttura piatta: un solo caso senza varianti)" if piatto else " (una sottocartella per catena)"))
    for i, (c, out) in enumerate(piano, 1):
        print(f"  {i}. {c.etichetta}" + (f"   [variante {c.variante}]" if c.variante else "   [senza varianti]"))
        print(f"       dimensionamento: {os.path.abspath(c.cartella)}")
        print(f"       spinta:          {os.path.abspath(c.spinta_json)}")
        print(f"       uscita:          {os.path.abspath(out)}")
    return piano


def run(input_file=INPUT_FILE, nome_run="dinamica", radice_dimensionamento=None, solo_elenco=False):
    """Esegue la run; ritorna la cartella del caso (None se le verifiche falliscono)."""
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    t0 = time.time()
    base_cfg = leggi_input(input_file)
    catene = trova_catene(base_cfg, radice_dimensionamento)           # errore se il nome non indica nulla
    if solo_elenco:
        elenca(base_cfg, catene, radice_dimensionamento)
        return os.path.join(*pianifica(base_cfg, catene)[:2])
    cfgs, falliti = {}, {}
    for c in catene:
        try:
            cfgs[c.etichetta] = cfg_catena(base_cfg, c)
        except ValueError as e:
            if len(catene) == 1:
                raise
            falliti[c.etichetta] = str(e)
    if not cfgs:
        raise ValueError("nessuna catena importabile:" + chr(10) + " - " + (chr(10) + " - ").join(
            f"{k}: {v}" for k, v in falliti.items()))
    es = base_cfg["ESECUZIONE"]
    if es.get("verifiche", True):
        from . import verifiche as VF
        ok, tot = VF.esegui(stampa=lambda *a, **k: None)
        print(f"Verifiche della dinamica: {ok}/{tot} superate")
        if ok < tot:
            print("Una verifica è fallita: la simulazione non parte.")
            return None
    base, nome, piatto, piano = pianifica(base_cfg, catene, radice_dimensionamento)
    imp = impronta_run({c.etichetta: (impronta(cfgs[c.etichetta]) if c.etichetta in cfgs else None) for c in catene}, piatto)
    attivi = ambienti_attivi(base_cfg)
    os.makedirs(base, exist_ok=True)
    cart = CA.prepara(base, nome, imp, base_cfg["CASO"]["sovrascrivi"], input_file, attivi,
                      [] if piatto else [c.etichetta for c in catene],
                      [c.etichetta for c in catene if c.etichetta in cfgs])        # una volta sola
    flog = open(os.path.join(cart, "log.txt"), "w", encoding="utf-8")

    def log(msg=""):
        print(msg)
        flog.write(msg + "\n")
        flog.flush()

    data = f"{dt.datetime.now():%d/%m/%Y %H:%M}"
    log(f"Esecuzione {nome_run} (input: {os.path.basename(input_file)}): {cart}")
    if not piatto:
        log(f"{len(catene)} catene del dimensionamento: " + ", ".join(c.etichetta for c in catene))
    elenco_catene = []
    for c, out in piano:
        nome_c = nome if piatto else f"{nome}/{c.etichetta}"
        if c.etichetta in falliti:
            stato, dati = f"importazione fallita: {falliti[c.etichetta]}", None
            log(f"\n{'#' * 100}\nCATENA {c.etichetta}: {stato}")
        else:
            cfg = cfgs[c.etichetta]
            dati = dati_dimensionamento(cfg["DIMENSIONAMENTO"])
            if not piatto:
                log(f"\n{'#' * 100}\nCATENA {c.etichetta} ({c.cartella})")
            try:
                esegui_catena(cfg, out, nome_c, imp, data, log)
                stato = "ok"
            except Exception as e:                      # una catena che fallisce non ferma le altre
                if len(catene) == 1:
                    flog.close()
                    raise
                stato = f"{type(e).__name__}: {e}"
                log(f"  ERRORE nella catena {c.etichetta}: {stato}")
        elenco_catene.append({"etichetta": c.etichetta, "cartella_out": out, "stato": stato,
                              "variante": c.variante, "dati": dati})
    if len(catene) > 1:
        try:
            from .confronto_catene import scrivi_confronto_catene
            for p in scrivi_confronto_catene(cart, elenco_catene):
                log(f"  scritto: {os.path.relpath(p, cart)}".replace(os.sep, "/"))
        except Exception as e:                          # ImportError compreso
            log(f"  ATTENZIONE: confronto tra le catene non scritto ({type(e).__name__}: {e})")
    CA.registra(base, {"data": data, "caso": nome, "impronta": imp, "run": nome_run,
                       "durata_s": round(time.time() - t0)})
    log(f"\nFinito in {time.time() - t0:.0f} s. Risultati in {cart}")
    for x in elenco_catene:
        if x["stato"] != "ok":
            log(f"  catena {x['etichetta']}: {x['stato']}")
    flog.close()
    if not any(x["stato"] == "ok" for x in elenco_catene):
        raise ValueError("nessuna catena è stata simulata: vedi log.txt")
    return cart


def main(argv=None, descrizione=__doc__):
    ap = argparse.ArgumentParser(description=descrizione, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=INPUT_FILE, help="file di input (predefinito: input.py)")
    ap.add_argument("--elenca", action="store_true",
                    help="stampa le catene del dimensionamento trovate e la cartella di uscita di ognuna, senza simulare")
    ap.add_argument("--radice-dimensionamento", default=None, metavar="CARTELLA",
                    help="cartella dei risultati del dimensionamento "
                         "(predefinita: ../Dimensionamento_Sistema_Propulsivo/risultati)")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        cart = run(args.input, radice_dimensionamento=args.radice_dimensionamento, solo_elenco=args.elenca)
    except ValueError as e:
        print(f"Errore: {e}")
        return 1
    return 0 if cart else 2
