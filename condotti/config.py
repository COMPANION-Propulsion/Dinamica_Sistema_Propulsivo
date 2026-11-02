"""Lettura di input.py e database_scenari.py, grandezze derivate."""
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


def carica(percorso_input, percorso_database):
    inp = _carica_modulo(percorso_input, "input_utente")
    db = _carica_modulo(percorso_database, "database_scenari")
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
        "esc_4in1_mm": tuple(inp.ESC_4IN1_MM),
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
    scenari = list(db.SCENARI)
    sel = cfg["esecuzione"]["scenari"]
    if sel != "tutti":
        scenari = [s for s in scenari if s["id"] in sel]
    _verifica(cfg, scenari)
    # grandezze derivate
    m = cfg["missione"]
    if m["spinta_per_asse_N"] is None:
        a_res = m["disturbo_residuo_g"] * 9.81
        a_tr = 4 * m["distanza_traslazione_m"] / m["tempo_traslazione_s"] ** 2
        m["spinta_per_asse_N"] = m["margine_spinta"] * m["massa_cubo_kg"] * (a_res + a_tr)
        m["origine_spinta"] = "k_m · m · (n g + 4 d / t²), come in Propulsione_dimensionamento.xlsx"
    else:
        m["origine_spinta"] = "imposta in input.py"
    cfg["arie"] = {k: crea_aria(k, v["p"], v["T"]) for k, v in cfg["ambienti"].items()}
    cfg["aria_progetto"] = cfg["arie"][cfg["ambiente_progetto"]]
    return cfg, scenari, inp


def _verifica(cfg, scenari):
    errori = []
    g = cfg["geometria"]
    if g["parete_condotto_mm"] < 0.6:
        errori.append("parete del condotto sotto 0,6 mm: non stampabile")
    if not 0 < cfg["elementi"]["porosita_griglia_ingresso"] < 1:
        errori.append("porosità della griglia d'ingresso fuori da (0, 1)")
    if cfg["ambiente_progetto"] not in cfg["ambienti"]:
        errori.append("AMBIENTE_PROGETTO non è tra gli AMBIENTI")
    ids = [s["id"] for s in scenari]
    if len(ids) != len(set(ids)):
        errori.append("id di scenario duplicati nel database")
    for s in scenari:
        for k in ("id", "nome", "topologia", "descrizione"):
            if k not in s:
                errori.append(f"scenario senza campo '{k}'")
    if not scenari:
        errori.append("nessuno scenario selezionato")
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
