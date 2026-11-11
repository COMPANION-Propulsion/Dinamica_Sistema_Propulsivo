"""Controllo dei dati copiati a mano dal dimensionamento della propulsione.

input.py della dinamica riporta a mano i risultati di ../Dimensionamento_Sistema_Propulsivo (fonte [DIM]).  Qui si
confrontano con il caso del dimensionamento che ha lo stesso nome di CASO["nome"], oppure, se non c'è, con
l'ultimo caso calcolato (risultati/<caso>/1_spinta/spinta.json più recente):

    1_spinta/spinta.json             massa, distanza, tempo, disturbo residuo, spinta di una faccia
    3_ventola/00_sintesi/report.json numero di pale, giri, potenza all'albero, raggio del mozzo

    2_venturi/05_convergenza/design.json   case.p_amb: pressione di progetto, contro ATTUATORE["pressione_progetto_Pa"]

    potenza elettrica per asse = ugelli per faccia x potenza all'albero / ENERGIA["rendimento_elettrico"]

Il disturbo non va confrontato per uguaglianza: nel dimensionamento disturbo_residuo_g è il caso peggiore con cui si
dimensiona la spinta, nella dinamica il bias di ogni ambiente è un disturbo realistico.  Si avvisa solo se il bias
di un ambiente attivo (AMBIENTI, sovrascrittura di DISTURBO sopra la base) SUPERA disturbo_residuo_g.

Tempo di salita, braccio della spinta e disposizione delle ventole non escono dal dimensionamento: restano input
della dinamica.  Il controllo avvisa soltanto, non ferma la run.
"""
import glob
import json
import os

TOLL_MISSIONE = 0.01       # scarto relativo ammesso sui dati di missione
TOLL_PRESSIONE = 0.01      # scarto relativo ammesso sulla pressione di progetto
TOLL_RISULTATI = 0.05      # scarto relativo ammesso sui risultati copiati (spinta, potenza, giri)


def caso_dimensionamento(cartella_progetto, nome=None):
    """Cartella del caso del dimensionamento da confrontare, o None."""
    base = os.path.join(os.path.dirname(cartella_progetto), "Dimensionamento_Sistema_Propulsivo", "risultati")
    if nome and os.path.isfile(os.path.join(base, str(nome), "1_spinta", "spinta.json")):
        return os.path.join(base, str(nome))
    casi = glob.glob(os.path.join(base, "*", "1_spinta", "spinta.json"))
    return os.path.dirname(os.path.dirname(max(casi, key=os.path.getmtime))) if casi else None


def _json(*parti):
    f = os.path.join(*parti)
    if not os.path.isfile(f):
        return None
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def confronta(cfg, cartella_progetto):
    """Ritorna (nome del caso confrontato o None, elenco di avvisi)."""
    caso = caso_dimensionamento(cartella_progetto, cfg["CASO"].get("nome"))
    if caso is None:
        return None, ["nessun caso del dimensionamento trovato in ../Dimensionamento_Sistema_Propulsivo/risultati: "
                      "i dati [DIM] dell'input non sono stati controllati"]
    avvisi = []

    def controlla(nome, qui, la, unita, toll):
        if la is not None and abs(qui - la) > toll * max(abs(qui), abs(la), 1e-12):
            avvisi.append(f"{nome} = {qui:g} {unita}, il dimensionamento dà {la:.4g} {unita}")

    s = _json(caso, "1_spinta", "spinta.json")
    ma, at, en, pa = cfg["MANOVRA"], cfg["ATTUATORE"], cfg["ENERGIA"], cfg["PALE"]
    inp = s["input"]
    controlla("CORPO['massa_kg']", cfg["CORPO"]["massa_kg"], inp.get("massa"), "kg", TOLL_MISSIONE)
    controlla("MANOVRA['distanza_m'] (massima)", max(abs(d) for d in ma["distanza_m"]), inp.get("distanza"), "m", TOLL_MISSIONE)
    controlla("MANOVRA['tempo_manovra_s']", ma["tempo_manovra_s"], inp.get("tempo"), "s", TOLL_MISSIONE)
    dist_dim = inp.get("disturbo_residuo_g")
    for nome_amb, amb in cfg["AMBIENTI"].items():
        if not amb.get("attivo", True) or dist_dim is None:
            continue
        bias = {**cfg["DISTURBO"], **amb.get("DISTURBO", {})}["bias_g"]
        if bias > dist_dim * (1 + 1e-9):
            avvisi.append(f"AMBIENTI['{nome_amb}'] bias_g = {bias:g} g supera il disturbo residuo con cui il "
                          f"dimensionamento ha calcolato la spinta ({dist_dim:g} g)")
    controlla("ENERGIA['spinta_rif_N']", en["spinta_rif_N"], s.get("T_totale_N"), "N", TOLL_RISULTATI)
    F_max = min(at["spinta_max_positiva_N"] + at["spinta_max_negativa_N"])
    if s.get("T_totale_N") is not None and F_max > s["T_totale_N"] * (1 + TOLL_RISULTATI):
        avvisi.append(f"ATTUATORE: spinta massima {F_max:g} N oltre la spinta di progetto di una faccia "
                      f"({s['T_totale_N']:.4g} N): serve la curva di potenza del dimensionamento per giustificarla")
    controlla("RUOTE['spinta_per_unita_N']", cfg["RUOTE"]["spinta_per_unita_N"], s.get("T_ugello_N"), "N", TOLL_RISULTATI)

    prog = _json(caso, "2_venturi", "05_convergenza", "design.json")
    if prog and isinstance(prog.get("case"), dict):
        controlla("ATTUATORE['pressione_progetto_Pa']", at["pressione_progetto_Pa"], prog["case"].get("p_amb"), "Pa",
                  TOLL_PRESSIONE)

    rep = _json(caso, "3_ventola", "00_sintesi", "report.json")
    best = (rep or {}).get("best")
    if not best:
        avvisi.append("il caso del dimensionamento non ha ancora una ventola accettata (3_ventola): potenza, giri e "
                      "pale dell'input sono stime non controllate")
    else:
        d, c = best["design"], best["cases"][0]
        eta = en.get("rendimento_elettrico", 1.0)
        controlla("ENERGIA['potenza_rif_W']", en["potenza_rif_W"], inp["n_ugelli"] * c["shaft_power_W"] / eta, "W", TOLL_RISULTATI)
        controlla("PALE['giri_progetto_rpm']", pa["giri_progetto_rpm"], c["rpm"], "giri/min", TOLL_RISULTATI)
        controlla("PALE['raggio_mozzo_mm']", pa["raggio_mozzo_mm"], 500 * d["hub_diameter_m"], "mm", TOLL_RISULTATI)
        if int(pa["numero_pale"]) != int(d["blade_count"]):
            avvisi.append(f"PALE['numero_pale'] = {pa['numero_pale']}, il dimensionamento ha scelto {d['blade_count']} pale")
    return os.path.basename(caso), avvisi
