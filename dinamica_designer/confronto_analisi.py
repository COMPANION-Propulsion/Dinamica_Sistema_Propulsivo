"""Controllo dei dati copiati a mano dall'analisi delle configurazioni.

input.py della dinamica riporta a mano alcuni risultati di ../Analisi_Configurazioni (fonte [ANL]).  Qui si
confrontano con l'ultima run archiviata dell'analisi, risultati/archivio_output/<run>/dati/riepilogo.json, e con
l'input che quella run ha usato:

    ENERGIA["spinta_rif_N"]    contro  spinta_per_asse_N della run
    ENERGIA["potenza_rif_W"]   contro  P_asse_W dello scenario
    CORPO["massa_kg"], MANOVRA["distanza_m"], MANOVRA["tempo_manovra_s"]
                               contro  massa_per_spinta_kg, distanza_traslazione_m, tempo_traslazione_s della run

Spinta massima, tempo di salita, braccio e giri non sono nel riepilogo.json dell'analisi (stanno nei fogli Excel):
restano da controllare a mano.  Il controllo avvisa soltanto, non ferma la run.
"""
import glob
import importlib.util
import json
import os

TOLLERANZA = 0.01          # scarto relativo oltre il quale si avvisa
SCENARIO = "S4"            # inizio del nome dello scenario dell'analisi a cui si riferisce la dinamica


def ultima_run(cartella_progetto):
    """Cartella dell'ultima run archiviata dell'analisi (i nomi cominciano con data e ora), o None."""
    base = os.path.join(os.path.dirname(cartella_progetto), "Analisi_Configurazioni", "risultati", "archivio_output")
    run = sorted(d for d in glob.glob(os.path.join(base, "*")) if os.path.isfile(os.path.join(d, "dati", "riepilogo.json")))
    return run[-1] if run else None


def _missione(cartella_run):
    """Dizionario di missione dell'input usato dalla run (quello con distanza_traslazione_m), o {}."""
    for f in glob.glob(os.path.join(cartella_run, "[Ii][Nn][Pp][Uu][Tt]_usato.py")):
        try:
            spec = importlib.util.spec_from_file_location("input_analisi_usato", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception:
            return {}
        for v in vars(mod).values():
            if isinstance(v, dict) and "distanza_traslazione_m" in v:
                return v
    return {}


def _diverso(a, b):
    return abs(a - b) > TOLLERANZA * max(abs(a), abs(b), 1e-12)


def confronta(cfg, cartella_progetto):
    """Ritorna (nome della run confrontata o None, elenco di avvisi)."""
    run = ultima_run(cartella_progetto)
    if run is None:
        return None, ["nessuna run dell'analisi trovata in ../Analisi_Configurazioni/risultati/archivio_output: "
                      "i dati [ANL] dell'input non sono stati controllati"]
    with open(os.path.join(run, "dati", "riepilogo.json"), encoding="utf-8") as fh:
        r = json.load(fh)
    avvisi = []
    en = cfg["ENERGIA"]
    F = r.get("spinta_per_asse_N")
    if F is not None and _diverso(en["spinta_rif_N"], F):
        avvisi.append(f"ENERGIA['spinta_rif_N'] = {en['spinta_rif_N']:g} N, l'analisi dà {F:.4f} N")
    sc = [s for s in r.get("scenari", []) if str(s.get("scenario", "")).startswith(SCENARIO)]
    if not sc:
        avvisi.append(f"la run dell'analisi non contiene lo scenario {SCENARIO}: potenza non controllata")
    elif _diverso(en["potenza_rif_W"], sc[0]["P_asse_W"]):
        avvisi.append(f"ENERGIA['potenza_rif_W'] = {en['potenza_rif_W']:g} W, l'analisi dà {sc[0]['P_asse_W']:.2f} W "
                      f"per {sc[0]['scenario']}")
    mis = _missione(run)
    if not mis:
        avvisi.append("input usato dalla run dell'analisi non leggibile: massa, distanza e tempo non controllati")
    else:
        ma = cfg["MANOVRA"]
        coppie = (("CORPO['massa_kg']", cfg["CORPO"]["massa_kg"], "massa_per_spinta_kg", "kg"),
                  ("MANOVRA['distanza_m'] (massima)", max(abs(d) for d in ma["distanza_m"]), "distanza_traslazione_m", "m"),
                  ("MANOVRA['tempo_manovra_s']", ma["tempo_manovra_s"], "tempo_traslazione_s", "s"))
        for nome, qui, chiave, unita in coppie:
            la = mis.get(chiave)
            if la is not None and _diverso(qui, la):
                avvisi.append(f"{nome} = {qui:g} {unita}, la run dell'analisi è stata fatta con {chiave} = {la:g} {unita}: "
                              f"i dati [ANL] dell'input vengono da una missione diversa, rifare l'analisi e ricopiarli")
    return os.path.basename(run), avvisi
