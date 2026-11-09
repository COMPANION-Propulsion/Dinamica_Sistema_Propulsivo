"""Lettura del file di input (dati e scenari), controlli, grandezze derivate."""
import importlib.util
import hashlib
import json
import math
import os

from .aria import crea_aria


def _carica_modulo(percorso, nome):
    spec = importlib.util.spec_from_file_location(nome, percorso)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lati_del_cubo(g):
    """Lati del cubo da analizzare (mm): da min a max con il passo dato; il massimo è sempre incluso."""
    a, b, passo = g["lato_cubo_min_mm"], g["lato_cubo_max_mm"], g["lato_cubo_passo_mm"]
    n = int(math.floor((b - a) / passo + 1e-9)) + 1
    lati = [round(a + k * passo, 6) for k in range(n)]
    if lati[-1] < b - 1e-6:
        lati.append(float(b))
    return lati


def cfg_con_lato(cfg, lato_mm):
    """Copia (superficiale) della configurazione con un lato del cubo fissato."""
    c = dict(cfg)
    c["geometria"] = dict(cfg["geometria"], lato_cubo_mm=float(lato_mm))
    return c


def carica(percorso_input):
    inp = _carica_modulo(percorso_input, "input_utente")
    cfg = {
        "esecuzione": dict(inp.ESECUZIONE),
        "missione": dict(inp.MISSIONE),
        "ambienti": dict(inp.AMBIENTI),
        "ambiente_progetto": inp.AMBIENTE_PROGETTO,
        "geometria": dict(inp.GEOMETRIA),
        "zone_riservate": dict(inp.ZONE_RISERVATE),
        "zona_centrale_facce_mm": inp.ZONA_CENTRALE_FACCE_MM,
        "faccia_sportellino": tuple(inp.FACCIA_SPORTELLINO),
        "faccia_libera": tuple(inp.FACCIA_LIBERA),
        "componenti": dict(inp.COMPONENTI),
        "masse_fisse": dict(inp.MASSE_FISSE),
        "esc_4in1_mm": tuple(inp.ESC_4IN1_MM),
        "telaio": dict(inp.TELAIO),
        "elementi": dict(inp.ELEMENTI),
        "tipi_ventola": dict(inp.TIPI_VENTOLA),
        "motori": dict(inp.MOTORI),
        "elettrico": dict(inp.ELETTRICO),
        "rotore": dict(inp.ROTORE),
        "limiti": dict(inp.LIMITI),
        "materiali": dict(inp.MATERIALI),
        "materiale_condotto": inp.MATERIALE_CONDOTTO,
        "carichi": dict(inp.CARICHI),
        "ottimizzazione": dict(inp.OTTIMIZZAZIONE),
        "realizzabilita": dict(inp.REALIZZABILITA),
    }
    scenari = [dict(s) for s in inp.SCENARI if s.get("attivo", True)]
    _verifica(cfg, scenari)
    # grandezze derivate
    m = cfg["missione"]
    if m["spinta_per_asse_N"] is None:
        a_res = m["disturbo_residuo_g"] * 9.81
        a_tr = 4 * m["distanza_traslazione_m"] / m["tempo_traslazione_s"] ** 2
        m["spinta_per_asse_N"] = m["margine_spinta"] * m["massa_per_spinta_kg"] * (a_res + a_tr)
        m["origine_spinta"] = "k_m · m · (n g + 4 d / t²), come in Propulsione_dimensionamento.xlsx"
    else:
        m["origine_spinta"] = "imposta in INPUT.py"
    # la spinta richiesta è proporzionale alla massa: serve per ricontrollarla con la massa stimata
    m["spinta_per_kg_N"] = m["spinta_per_asse_N"] / m["massa_per_spinta_kg"]
    if m.get("massa_massima_kg") is None:
        m["massa_massima_kg"] = m["massa_per_spinta_kg"]
    cfg["lati_cubo_mm"] = lati_del_cubo(cfg["geometria"])
    cfg["arie"] = {k: crea_aria(k, v["p"], v["T"]) for k, v in cfg["ambienti"].items()}
    cfg["aria_progetto"] = cfg["arie"][cfg["ambiente_progetto"]]
    return cfg, scenari, inp


def _verifica(cfg, scenari):
    errori = []
    g = cfg["geometria"]
    if g["parete_condotto_mm"] < 0.6:
        errori.append("parete del condotto sotto 0,6 mm: non stampabile")
    for k in ("lato_cubo_min_mm", "lato_cubo_max_mm", "lato_cubo_passo_mm"):
        if k not in g:
            errori.append(f"GEOMETRIA senza '{k}' (il lato del cubo è un intervallo: min, max, passo)")
    if all(k in g for k in ("lato_cubo_min_mm", "lato_cubo_max_mm", "lato_cubo_passo_mm")):
        if not 0 < g["lato_cubo_min_mm"] <= g["lato_cubo_max_mm"]:
            errori.append("lato del cubo: serve 0 < lato_cubo_min_mm <= lato_cubo_max_mm")
        if g["lato_cubo_passo_mm"] <= 0:
            errori.append("lato_cubo_passo_mm deve essere maggiore di zero")
    if not 0 < cfg["elementi"]["porosita_griglia_ingresso"] < 1:
        errori.append("porosità della griglia d'ingresso fuori da (0, 1)")
    if cfg["ambiente_progetto"] not in cfg["ambienti"]:
        errori.append("AMBIENTE_PROGETTO non è tra gli AMBIENTI")
    if cfg["materiale_condotto"] not in cfg["materiali"]:
        errori.append("MATERIALE_CONDOTTO non è tra i MATERIALI")
    if cfg["telaio"]["materiale_guscio"] not in cfg["materiali"]:
        errori.append("TELAIO['materiale_guscio'] non è tra i MATERIALI")
    m = cfg["missione"]
    if m.get("massa_massima_kg") is not None and m["massa_massima_kg"] <= m["massa_obiettivo_kg"]:
        errori.append("massa_massima_kg deve essere maggiore di massa_obiettivo_kg")
    pesi = cfg["ottimizzazione"]["pesi"]
    noti = {"spazio", "perdite", "semplicita", "robustezza", "dinamica", "massa", "ingestione"}
    if set(pesi) - noti:
        errori.append(f"criteri sconosciuti nei pesi: {sorted(set(pesi) - noti)} (ammessi: {sorted(noti)})")
    ids = [s["id"] for s in scenari]
    if len(ids) != len(set(ids)):
        errori.append("id di scenario duplicati in SCENARI")
    from .scenari import GENERATORI
    for s in scenari:
        for k in ("id", "nome", "topologia", "descrizione"):
            if k not in s:
                errori.append(f"scenario senza campo '{k}'")
        if s.get("topologia") not in GENERATORI:
            errori.append(f"{s.get('id')}: topologia '{s.get('topologia')}' sconosciuta (ammesse: {list(GENERATORI)})")
    if not scenari:
        errori.append("nessuno scenario attivo in SCENARI")
    if errori:
        raise ValueError("Errori in input:\n - " + "\n - ".join(errori))


def impronta(cfg, scenari):
    """Hash breve degli input: stessa impronta = stessi dati."""
    def pulito(o):
        if isinstance(o, dict):
            return {k: pulito(v) for k, v in o.items() if k not in ("arie", "aria_progetto")}
        if isinstance(o, (list, tuple)):
            return [pulito(x) for x in o]
        if isinstance(o, float):
            return round(o, 9)
        return o
    testo = json.dumps({"cfg": pulito(cfg), "scenari": scenari}, sort_keys=True, default=str)
    return hashlib.sha1(testo.encode()).hexdigest()[:8]
