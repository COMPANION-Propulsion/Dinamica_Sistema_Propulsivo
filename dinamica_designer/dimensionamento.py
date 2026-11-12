"""Import dei dati dal dimensionamento della propulsione.

I dati di progetto (massa, manovra, spinta, potenza, giri, pale, tempo di salita) non si scrivono in input.py: si
leggono dal caso di ../Dimensionamento_Sistema_Propulsivo/risultati/<caso>/ che ha lo stesso nome di CASO["nome"]
(la parte prima di "__": "RUN_6kg__prova1" usa il caso "RUN_6kg").  Fonti, per ogni caso:

    1_spinta/spinta.json                       massa, distanza, tempo, n. ugelli, disturbo residuo
    2_venturi/05_convergenza/design.json       case.p_amb: pressione di progetto
    4_sistema/04_cfd/condotto_con_ventola.json spinta_con_ventola_N: spinta di un ugello con la ventola vera
    3_ventola/00_sintesi/report.json           best.design (pale, mozzo), best.cases[0] (potenza, coppia, giri)
    3_ventola/00_sintesi/confronto_pale.json   inerzia delle pale della scelta
    3_ventola/03_cad/CAD_info.json             diametro, mozzo, volume della pala
    3_ventola/02_excel/sections.csv            corde della pala
    4_sistema/00_sintesi/curva_potenza.json    esponente della potenza, giri massimi

Un dato mancante ferma la run con un errore che dice quale file e quale campo.
"""
import csv
import glob
import json
import math
import os
import types

import numpy as np

from . import propulsore as DY

SEP_VARIANTE = "__"
RADICE_PREDEFINITA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                  "Dimensionamento_Sistema_Propulsivo", "risultati")

# chiavi che arrivano dal dimensionamento: (sezione, chiave); vietate in input.py e in AMBIENTI
CHIAVI_IMPORTATE = (
    ("CORPO", "massa_kg"),
    ("MANOVRA", "distanza_m"), ("MANOVRA", "tempo_manovra_s"),
    ("ATTUATORE", "pressione_progetto_Pa"), ("ATTUATORE", "spinta_max_positiva_N"),
    ("ATTUATORE", "spinta_max_negativa_N"), ("ATTUATORE", "tempo_salita_90_s"),
    ("ENERGIA", "spinta_rif_N"), ("ENERGIA", "potenza_rif_W"), ("ENERGIA", "esponente"),
    ("RUOTE", "spinta_per_unita_N"), ("RUOTE", "coppia_reazione_rotori_Nm"),
    ("PALE", "numero_pale"), ("PALE", "raggio_mozzo_mm"), ("PALE", "giri_progetto_rpm"),
    ("PALE", "giri_massimi_rpm"), ("PALE", "lunghezza_mm"), ("PALE", "larghezza_mm"), ("PALE", "spessore_mm"),
    ("PALE", "inerzia_rotore_motore_kgm2"),
)
CHIAVI_MOTORE = ("Kv", "R", "I0", "I_max", "inerzia_rotore_kgm2", "duty_max", "ritardo_regolatore_s",
                 "densita_mozzo_kg_m3", "riempimento_mozzo")
F_MIN_FIT_N = 0.1          # spinta minima per ugello del fit della potenza [N]


def nome_dimensionamento(nome):
    """Nome del caso del dimensionamento: la parte di CASO["nome"] prima di "__"."""
    if nome is None:
        raise ValueError("CASO['nome'] è obbligatorio: deve coincidere con un caso di "
                         "Dimensionamento_Sistema_Propulsivo/risultati (da lì si importano i dati; "
                         "un suffisso '__prova' dopo il nome è ammesso).")
    return str(nome).split(SEP_VARIANTE)[0]


def casi_disponibili(radice):
    """Nomi dei casi del dimensionamento (cartelle con 1_spinta/spinta.json)."""
    return sorted(os.path.basename(os.path.dirname(os.path.dirname(f)))
                  for f in glob.glob(os.path.join(radice, "*", "1_spinta", "spinta.json")))


def cartella_caso(nome, radice=None):
    """Cartella del caso del dimensionamento per CASO["nome"]; errore con l'elenco dei casi se manca."""
    radice = radice or RADICE_PREDEFINITA
    caso = nome_dimensionamento(nome)
    if not os.path.isfile(os.path.join(radice, caso, "1_spinta", "spinta.json")):
        elenco = casi_disponibili(radice)
        raise ValueError(f"nessun caso '{caso}' in {radice} (CASO['nome'] = {nome!r}; prima di '__' ci deve essere il "
                         f"nome di un caso del dimensionamento). Casi disponibili: "
                         + (", ".join(elenco) if elenco else "nessuno"))
    return os.path.join(radice, caso)


def _file(cartella, rel):
    f = os.path.join(cartella, *rel.split("/"))
    if not os.path.isfile(f):
        raise ValueError(f"dimensionamento: manca il file {rel} nel caso {os.path.basename(cartella)} "
                         "(il caso è incompleto, ad esempio la ventola non è ancora accettata)")
    return f


def _json(cartella, rel):
    with open(_file(cartella, rel), encoding="utf-8") as fh:
        return json.load(fh)


def _campo(dati, rel, *percorso):
    """Valore dati[percorso[0]][percorso[1]]...; errore con file e campo se manca."""
    x = dati
    for p in percorso:
        try:
            x = x[p]
        except (KeyError, IndexError, TypeError):
            raise ValueError(f"dimensionamento: nel file {rel} manca il campo {'.'.join(map(str, percorso))}") from None
    if x is None:
        raise ValueError(f"dimensionamento: nel file {rel} il campo {'.'.join(map(str, percorso))} è vuoto")
    return x


def _fit_esponente(righe, F_prog, rel):
    """Esponente di P = P_rif (F/F_rif)^n: fit log-log sui punti calcolati (non interpolati) tra F_MIN_FIT_N e la spinta di progetto."""
    F, P = [], []
    for r in righe:
        f, p = r.get("spinta_ugello_N"), r.get("potenza_albero_W")
        if r.get("stato") in ("esatto", "BEMT") and f and p and math.isfinite(f) and math.isfinite(p) \
                and F_MIN_FIT_N <= f <= F_prog * (1 + 1e-9) and p > 0:
            F.append(f)
            P.append(p)
    if len(F) < 3:
        raise ValueError(f"dimensionamento: nel file {rel} servono almeno 3 righe calcolate (esatto o BEMT) tra {F_MIN_FIT_N} N e la "
                         f"spinta di progetto ({F_prog:.3g} N) per ricavare l'esponente della potenza, ne ho {len(F)}")
    return float(np.polyfit(np.log(F), np.log(P), 1)[0])


def _trapezio(y, x):
    return float(np.sum((y[1:] + y[:-1]) * np.diff(x)) / 2)


def _corda_media_mm(cartella, rel):
    with open(_file(cartella, rel), encoding="utf-8", newline="") as fh:
        righe = list(csv.DictReader(fh))
    if not righe or "chord_m" not in righe[0] or "radius_m" not in righe[0]:
        raise ValueError(f"dimensionamento: nel file {rel} servono le colonne radius_m e chord_m")
    r = np.array([float(x["radius_m"]) for x in righe])
    c = np.array([float(x["chord_m"]) for x in righe])
    if len(r) < 2:
        return 1000.0 * float(c.mean())
    return 1000.0 * float(_trapezio(c, r) / (r[-1] - r[0]))        # media sul raggio, non sui nodi


def _motore(cfg):
    m = cfg["MOTORE"]
    mancanti = [k for k in CHIAVI_MOTORE if k not in m]
    if mancanti:
        raise ValueError(f"mancano in MOTORE: {', '.join(mancanti)}")
    return m


def importa(cfg, cartella):
    """Legge il caso del dimensionamento; ritorna (valori, fonti, avvisi).

    valori e fonti sono dizionari {"SEZIONE.chiave": ...}: il valore da usare e il file/campo d'origine.
    Servono cfg["MOTORE"], ENERGIA (tensione, rendimento), RUOTE (squilibrio, vortice residuo) e AMBIENTI.
    """
    v, f, avvisi = {}, {}, []

    def metti(sez, k, valore, fonte):
        v[f"{sez}.{k}"] = valore
        f[f"{sez}.{k}"] = fonte

    mo, en, ru = _motore(cfg), cfg["ENERGIA"], cfg["RUOTE"]
    R_SP, R_VEN = "1_spinta/spinta.json", "3_ventola/00_sintesi/report.json"
    R_CFD, R_CUR = "4_sistema/04_cfd/condotto_con_ventola.json", "4_sistema/00_sintesi/curva_potenza.json"
    R_CAD, R_PALE = "3_ventola/03_cad/CAD_info.json", "3_ventola/00_sintesi/confronto_pale.json"
    R_DES, R_SEZ = "2_venturi/05_convergenza/design.json", "3_ventola/02_excel/sections.csv"

    sp = _json(cartella, R_SP)
    massa = float(_campo(sp, R_SP, "input", "massa"))
    dist = float(_campo(sp, R_SP, "input", "distanza"))
    tempo = float(_campo(sp, R_SP, "input", "tempo"))
    n_ug = int(_campo(sp, R_SP, "input", "n_ugelli"))
    metti("CORPO", "massa_kg", massa, f"{R_SP}: input.massa")
    metti("MANOVRA", "distanza_m", [dist] * 3, f"{R_SP}: input.distanza (uguale sui tre assi)")
    metti("MANOVRA", "tempo_manovra_s", tempo, f"{R_SP}: input.tempo")

    p_amb = float(_campo(_json(cartella, R_DES), R_DES, "case", "p_amb"))
    metti("ATTUATORE", "pressione_progetto_Pa", p_amb, f"{R_DES}: case.p_amb")

    F_ug = float(_campo(_json(cartella, R_CFD), R_CFD, "spinta_con_ventola_N"))
    F_faccia = n_ug * F_ug
    fonte_F = f"{R_CFD}: spinta_con_ventola_N x n_ugelli (input.n_ugelli di {R_SP})"
    metti("ATTUATORE", "spinta_max_positiva_N", [F_faccia] * 3, fonte_F)
    metti("ATTUATORE", "spinta_max_negativa_N", [F_faccia] * 3, fonte_F)
    metti("ENERGIA", "spinta_rif_N", F_faccia, fonte_F)
    metti("RUOTE", "spinta_per_unita_N", F_ug, f"{R_CFD}: spinta_con_ventola_N")

    rep = _json(cartella, R_VEN)
    P_alb = float(_campo(rep, R_VEN, "best", "cases", 0, "shaft_power_W"))
    coppia = float(_campo(rep, R_VEN, "best", "cases", 0, "torque_Nm"))
    rpm = float(_campo(rep, R_VEN, "best", "cases", 0, "rpm"))
    eta = float(en["rendimento_elettrico"])
    metti("ENERGIA", "potenza_rif_W", n_ug * P_alb / eta,
          f"{R_VEN}: best.cases[0].shaft_power_W x n_ugelli / ENERGIA.rendimento_elettrico")
    metti("PALE", "numero_pale", int(_campo(rep, R_VEN, "best", "design", "blade_count")), f"{R_VEN}: best.design.blade_count")
    metti("PALE", "raggio_mozzo_mm", 500.0 * float(_campo(rep, R_VEN, "best", "design", "hub_diameter_m")),
          f"{R_VEN}: best.design.hub_diameter_m / 2")
    metti("PALE", "giri_progetto_rpm", rpm, f"{R_VEN}: best.cases[0].rpm")
    metti("RUOTE", "coppia_reazione_rotori_Nm", ru["squilibrio_coppia"] * ru["vortice_residuo_statore"] * coppia,
          f"{R_VEN}: best.cases[0].torque_Nm x RUOTE.squilibrio_coppia x RUOTE.vortice_residuo_statore")

    cur = _json(cartella, R_CUR)
    righe = _campo(cur, R_CUR, "righe")
    F_prog = float(_campo(cur, R_CUR, "progetto", "spinta_ugello_N"))
    metti("ENERGIA", "esponente", _fit_esponente(righe, F_prog, R_CUR),
          f"{R_CUR}: fit log-log potenza_albero_W / spinta_ugello_N, righe calcolate (non interpolate) da {F_MIN_FIT_N} N alla spinta di progetto")
    pmax = float(_campo(cur, R_CUR, "potenza_max_W"))
    r_max = min((r for r in righe if r.get("potenza_albero_W") is not None and math.isfinite(r["potenza_albero_W"])),
                key=lambda r: abs(r["potenza_albero_W"] - pmax))
    metti("PALE", "giri_massimi_rpm", float(r_max["rpm"]), f"{R_CUR}: rpm della riga di potenza massima")

    cad = _json(cartella, R_CAD)
    d_cad = float(_campo(cad, R_CAD, "diameter_cad_mm"))
    d_hub = float(_campo(cad, R_CAD, "hub_diameter_mm"))
    L_hub = float(_campo(cad, R_CAD, "hub_length_mm"))
    vol = float(_campo(cad, R_CAD, "files", "pala", "volume_mm3"))
    lung = d_cad / 2 - d_hub / 2
    larg = _corda_media_mm(cartella, R_SEZ)
    metti("PALE", "lunghezza_mm", lung, f"{R_CAD}: diameter_cad_mm / 2 - hub_diameter_mm / 2")
    metti("PALE", "larghezza_mm", larg, f"{R_SEZ}: corda media (chord_m, media sul raggio)")
    metti("PALE", "spessore_mm", vol / (lung * larg), f"{R_CAD}: files.pala.volume_mm3 / (lunghezza x larghezza)")
    metti("PALE", "inerzia_rotore_motore_kgm2", float(mo["inerzia_rotore_kgm2"]), "MOTORE.inerzia_rotore_kgm2")

    # tempo di salita: inerzia di pale, mozzo e rotore del motore
    cp = _json(cartella, R_PALE)
    pale = _campo(cp, R_PALE, "pale")
    scelta = _campo(cp, R_PALE, "scelta")
    if scelta not in pale:
        raise ValueError(f"dimensionamento: nel file {R_PALE} la scelta {scelta} non è tra le pale {pale}")
    riga = [r for r in _campo(cp, R_PALE, "righe") if r.get("nome") == "inerzia delle pale [kg m^2]"]
    if not riga:
        raise ValueError(f"dimensionamento: nel file {R_PALE} manca la riga 'inerzia delle pale [kg m^2]'")
    J_pale = float(riga[0]["valori"][pale.index(scelta)])
    r_hub, L = d_hub / 2000, L_hub / 1000
    m_hub = mo["densita_mozzo_kg_m3"] * mo["riempimento_mozzo"] * math.pi * r_hub ** 2 * L
    J_hub = 0.5 * m_hub * r_hub ** 2
    J_tot = J_pale + J_hub + mo["inerzia_rotore_kgm2"]
    motore = types.SimpleNamespace(Kv=mo["Kv"], R=mo["R"], I0=mo["I0"], I_max=mo["I_max"])
    t, _ = DY.tempo_salita(motore, J_tot, rpm, coppia, en["tensione_batteria_V"], duty_max=mo["duty_max"])
    if not math.isfinite(t):
        raise ValueError("tempo di salita infinito: il motore di MOTORE non riesce ad accelerare la ventola a "
                         f"{rpm:.0f} giri/min con {coppia * 1000:.2f} mN·m a {en['tensione_batteria_V']:g} V "
                         "(controlla Kv, R, I0, I_max, duty_max)")
    metti("ATTUATORE", "tempo_salita_90_s", round(t + mo["ritardo_regolatore_s"], 4),
          f"propulsore.tempo_salita (J = pale {J_pale:.3g} + mozzo {J_hub:.3g} + rotore motore "
          f"{mo['inerzia_rotore_kgm2']:.3g} = {J_tot:.3g} kg·m², {coppia * 1000:.2f} mN·m a {rpm:.0f} rpm) "
          f"+ MOTORE.ritardo_regolatore_s; pale e coppia da {R_PALE} e {R_VEN}")
    v["_J"] = {"pale": J_pale, "mozzo": J_hub, "motore": float(mo["inerzia_rotore_kgm2"]), "totale": J_tot,
               "salita_s": t}

    # unico controllo sui dati di input: il bias degli ambienti contro il disturbo con cui si è dimensionata la spinta
    dist_dim = sp["input"].get("disturbo_residuo_g")
    for nome_amb, amb in cfg["AMBIENTI"].items():
        if not amb.get("attivo", True) or dist_dim is None:
            continue
        bias = {**cfg["DISTURBO"], **amb.get("DISTURBO", {})}["bias_g"]
        if bias > dist_dim * (1 + 1e-9):
            avvisi.append(f"AMBIENTI['{nome_amb}'] bias_g = {bias:g} g supera il disturbo residuo con cui il "
                          f"dimensionamento ha calcolato la spinta ({dist_dim:g} g)")
    return v, f, avvisi


def chiavi_vietate(cfg):
    """Chiavi importate scritte in input.py (sezioni di base o AMBIENTI); ritorna l'elenco dei messaggi."""
    err = []
    for sez, k in CHIAVI_IMPORTATE:
        if k in cfg.get(sez, {}):
            err.append(f"{sez}['{k}'] viene dal dimensionamento: toglila da input.py")
        for n, a in cfg.get("AMBIENTI", {}).items():
            if k in a.get(sez, {}):
                err.append(f"AMBIENTI['{n}']['{sez}']['{k}'] viene dal dimensionamento: toglila da input.py")
    return err


def applica(cfg, valori):
    """Scrive i valori importati nelle sezioni di cfg."""
    for chiave, x in valori.items():
        if chiave.startswith("_"):
            continue
        sez, k = chiave.split(".", 1)
        cfg[sez][k] = x
