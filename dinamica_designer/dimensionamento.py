"""Import dei dati dal dimensionamento della propulsione.

I dati di progetto (massa, manovra, spinta, potenza, giri, pale, tempo di salita) non si scrivono in input.py: si
leggono dal caso di ../Dimensionamento_Sistema_Propulsivo/risultati/<caso>/ che ha lo stesso nome di CASO["nome"]
(il suffisso "__prova1" si toglie: "RUN_6kg__prova1" usa il caso "RUN_6kg").  CASO["nome"] può indicare anche una
variante (Statore, NoStatore) o una serie di casi: trova_catene() lo traduce in una lista di catene, ognuna con la sua
cartella (quella con 2_venturi, 3_ventola, 4_sistema).  Fonti, per ogni catena:

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
import dataclasses
import difflib
import json
import math
import os
import types
from typing import Optional

import numpy as np

from . import propulsore as DY

SEP_VARIANTE = "__"
VARIANTI = ("Statore", "NoStatore")      # sottocartelle del caso con il confronto statore
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


@dataclasses.dataclass
class Catena:
    """Una catena del dimensionamento (venturi -> ventola -> sistema) su cui gira la dinamica."""
    etichetta: str                  # nome nelle uscite: "NoStatore", "massa_4", "massa_4/NoStatore" (/ = sottocartella)
    cartella: str                   # cartella con 2_venturi, 3_ventola, 4_sistema
    spinta_json: str                # 1_spinta/spinta.json della catena, se c'è, altrimenti quello della radice del caso
    radice_caso: str                # cartella del caso (con 1_spinta, 5_confronto_statore, RIEPILOGO_masse.json)
    variante: Optional[str] = None  # "Statore", "NoStatore" oppure None (layout senza confronto statore)


class _NonTrovato(ValueError):
    """Il nome non indica nulla nella radice (si riprova senza il suffisso __xxx)."""


def _sottocartelle(d):
    try:
        return sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)) and n != "__pycache__")
    except OSError:
        return []


def _varianti_di(d):
    return [v for v in VARIANTI if os.path.isdir(os.path.join(d, v))]


def _e_caso(d):
    """Un caso del dimensionamento: ha 1_spinta/spinta.json oppure le cartelle Statore / NoStatore."""
    return os.path.isfile(os.path.join(d, "1_spinta", "spinta.json")) or bool(_varianti_di(d))


def _e_serie(d):
    return not _e_caso(d) and any(_e_caso(os.path.join(d, n)) for n in _sottocartelle(d))


def casi_disponibili(radice):
    """Nomi validi per CASO["nome"]: casi, loro varianti, serie, etichette di serie e le loro varianti.

    Le cartelle che iniziano con "_" (archivio) non sono elencate.
    """
    out = []
    for n in _sottocartelle(radice):
        d = os.path.join(radice, n)
        if n.startswith("_"):
            continue
        if _e_caso(d):
            out.append(n)
            out += [f"{n}/{v}" for v in _varianti_di(d)]
        elif _e_serie(d):
            out.append(n)
            for lab in _sottocartelle(d):
                dl = os.path.join(d, lab)
                if _e_caso(dl):
                    out.append(f"{n}/{lab}")
                    out += [f"{n}/{lab}/{v}" for v in _varianti_di(dl)]
    return sorted(out)


def _vicini(nome, elenco):
    return difflib.get_close_matches(nome, list(elenco), n=3, cutoff=0.5)


def _selezione_varianti(varianti):
    """None = tutte; altrimenti la lista dei nomi richiesti (controllata)."""
    if varianti is None or (isinstance(varianti, str) and varianti.strip().lower() == "tutte"):
        return None
    sel = [varianti] if isinstance(varianti, str) else list(varianti)
    if not sel or any(not isinstance(v, str) for v in sel):
        raise ValueError(f"CASO['varianti'] = {varianti!r}: ci vuole 'tutte' oppure un elenco di nomi, ad esempio "
                         f"['NoStatore'] (nomi validi: {', '.join(VARIANTI)})")
    ignote = [v for v in sel if v not in VARIANTI]
    if ignote:
        raise ValueError(f"CASO['varianti'] contiene {', '.join(map(repr, ignote))}: i nomi validi sono "
                         f"{', '.join(VARIANTI)}")
    return sel


def _catene_di_caso(d, base, resto, sel, in_serie, tutte):
    """Catene di un caso (cartella d). base = nome del caso o etichetta nella serie; resto = parti dopo il nome
    (una variante o niente); tutte = True se il caso è preso in blocco da una serie (i casi senza le varianti
    richieste si saltano)."""
    nv = _varianti_di(d)
    sp_caso = os.path.join(d, "1_spinta", "spinta.json")
    nome_vis = f"serie/{base}" if in_serie else base

    def catena(v):
        et = (f"{base}/{v}" if in_serie else v) if v else base
        cart = os.path.join(d, v) if v else d
        sp = os.path.join(cart, "1_spinta", "spinta.json")
        return Catena(et, cart, sp if os.path.isfile(sp) else sp_caso, d, v)

    if resto:
        v = resto[0]
        if len(resto) > 1 or v not in nv:
            if nv:
                vic = _vicini(v, nv)
                msg = f"le varianti sono {', '.join(nv)}" + (f" (forse {', '.join(vic)}?)" if vic else "")
            else:
                msg = "il caso non ha il confronto statore (niente Statore / NoStatore): il nome è solo il caso"
            raise _NonTrovato(f"nel caso '{nome_vis}' non c'è '{'/'.join(resto)}': {msg}")
        if sel is not None and v not in sel:
            raise ValueError(f"CASO['nome'] indica la variante {v} ma CASO['varianti'] = {sel}: mettili d'accordo")
        return [catena(v)]
    if nv:
        scelte = nv if sel is None else [v for v in nv if v in sel]
        if not scelte:
            if tutte:
                return []
            raise ValueError(f"CASO['varianti'] = {sel} ma il caso '{nome_vis}' ha solo {', '.join(nv)}")
        return [catena(v) for v in scelte]
    if sel is not None:
        if tutte:
            return []
        raise ValueError(f"CASO['varianti'] = {sel} ma il caso '{nome_vis}' non ha il confronto statore (niente "
                         "Statore / NoStatore): metti CASO['varianti'] = 'tutte'")
    return [catena(None)]


def _risolvi(radice, nome, sel):
    parti = [p for p in nome.replace(chr(92), "/").split("/") if p]
    if not parti:
        raise _NonTrovato("nome vuoto")
    d = os.path.join(radice, parti[0])
    if not os.path.isdir(d):
        elenco = casi_disponibili(radice)
        v = _vicini(parti[0], [e for e in elenco if "/" not in e])
        raise _NonTrovato(f"nessun caso né serie '{parti[0]}' in {radice} (CASO['nome'] = {nome!r}). Casi disponibili: "
                          + (", ".join(elenco) if elenco else "nessuno") + (f". Forse: {', '.join(v)}?" if v else ""))
    if _e_caso(d):
        return _catene_di_caso(d, parti[0], parti[1:], sel, False, False)
    if not _e_serie(d):
        raise _NonTrovato(
            f"'{parti[0]}' esiste in {radice} ma non è né un caso del dimensionamento (manca 1_spinta/spinta.json e "
            f"le cartelle Statore / NoStatore) né una serie (nessuna sottocartella è un caso). Contiene: "
            + (", ".join(_sottocartelle(d)) or "nulla") + ". Casi disponibili: "
            + (", ".join(casi_disponibili(radice)) or "nessuno"))
    casi = [n for n in _sottocartelle(d) if _e_caso(os.path.join(d, n))]
    if parti[1:]:
        lab = parti[1]
        if lab not in casi:
            v = _vicini(lab, casi)
            raise _NonTrovato(f"nella serie '{parti[0]}' non c'è il caso '{lab}'. Etichette della serie: {', '.join(casi)}"
                              + (f". Forse: {', '.join(v)}?" if v else ""))
        return _catene_di_caso(os.path.join(d, lab), lab, parti[2:], sel, True, False)
    catene = []
    for lab in casi:
        catene += _catene_di_caso(os.path.join(d, lab), lab, [], sel, True, True)
    if not catene:
        raise ValueError(f"la serie '{parti[0]}' ha i casi {', '.join(casi)} ma nessuno ha le varianti {sel} "
                         "(CASO['varianti'])")
    return catene


def _candidati(nome):
    """Il nome intero, poi senza l'ultimo suffisso "__xxx", e così via (le etichette di serie contengono "__")."""
    out = [nome]
    while SEP_VARIANTE in out[-1]:
        out.append(out[-1].rsplit(SEP_VARIANTE, 1)[0])
    return [c for c in out if c]


def trova_catene(radice, nome, varianti="tutte"):
    """Catene del dimensionamento indicate da CASO["nome"] e CASO["varianti"].

    Formati di nome (sempre con l'eventuale suffisso __vN in fondo, che si toglie):
        <caso>                       un caso: Statore e NoStatore se ci sono, altrimenti la catena unica
        <caso>/<variante>            una variante (Statore o NoStatore)
        <serie>                      tutti i casi della serie
        <serie>/<etichetta>          un caso della serie
        <serie>/<etichetta>/<variante>
    varianti: "tutte" o un elenco (["NoStatore"]); nelle serie i casi senza la variante richiesta si saltano.
    Ritorna list[Catena]; ValueError con cosa è stato trovato e i nomi validi.
    """
    radice = radice or RADICE_PREDEFINITA
    if nome is None or not str(nome).strip():
        raise ValueError("CASO['nome'] è obbligatorio: deve coincidere con un caso di "
                         "Dimensionamento_Sistema_Propulsivo/risultati (da lì si importano i dati; "
                         "un suffisso '__prova' dopo il nome è ammesso).")
    sel = _selezione_varianti(varianti)
    ultimo = None
    for c in _candidati(str(nome).strip()):
        try:
            return _risolvi(radice, c, sel)
        except _NonTrovato as e:
            ultimo = e
    raise ValueError(str(ultimo))


def cartella_uscita(cart_caso, catena, piatto):
    """Cartella delle uscite di una catena: il caso stesso se piatto, altrimenti le sottocartelle dell'etichetta."""
    return cart_caso if piatto else os.path.join(cart_caso, *catena.etichetta.split("/"))


# ---------------------------------------------------------------- coppia residua e dati informativi
def _json_se_c_e(*parti):
    f = os.path.join(*parti)
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _flag_statore(catena, rep):
    """True / False: la catena ha lo statore (dal nome della variante, dall'input della ventola o dal report)."""
    if catena.variante:
        return catena.variante == "Statore"
    inp = _json_se_c_e(catena.radice_caso, "input_ventola.json")
    try:
        return bool(inp["stator"]["enabled"])
    except (TypeError, KeyError):
        pass
    try:
        return bool(rep["best"]["cases"][0]["stator_enabled"])
    except (TypeError, KeyError, IndexError):
        return None


def coppia_residua(catena, rep, coppia_rotore, ru):
    """Coppia netta sul veicolo di una coppia di rotori [N m] e la fonte; ritorna (valore, fonte, avvisi).

    La coppia netta è quella vera del dimensionamento (nell'ordine: 5_confronto_statore del caso, net_torque_Nm del report.json
    della catena, il confronto a rotore fisso di 4_sistema della catena); il valore usato è squilibrio_coppia x coppia netta.
    Solo se nessuna c'è si ripiega su RUOTE.vortice_residuo_statore x coppia del rotore, con un avviso.
    """
    sq = ru["squilibrio_coppia"]
    flag = _flag_statore(catena, rep)
    R_C5 = "5_confronto_statore/confronto_statore.json"
    c5 = _json_se_c_e(catena.radice_caso, "5_confronto_statore", "confronto_statore.json")
    if c5 and catena.variante:
        v = (c5.get("varianti") or {}).get(catena.variante) or {}
        m = (v.get("ventola") or {}).get("coppia_netta_mNm") if v.get("presente", True) else None
        if m is not None:
            return (sq * abs(float(m)) / 1000.0,
                    f"{R_C5} (caso): varianti.{catena.variante}.ventola.coppia_netta_mNm x RUOTE.squilibrio_coppia", [])
    R_REP = "3_ventola/00_sintesi/report.json"
    try:
        net = rep["best"]["cases"][0]["net_torque_Nm"]
    except (TypeError, KeyError, IndexError):
        net = None
    if net is not None:
        return sq * abs(float(net)), f"{R_REP}: best.cases[0].net_torque_Nm x RUOTE.squilibrio_coppia", []
    R_C4 = "4_sistema/00_sintesi/confronto_statore.json"
    c4 = _json_se_c_e(catena.cartella, "4_sistema", "00_sintesi", "confronto_statore.json")
    if c4:
        righe = [r for r in (c4.get("varianti") or []) if "errore" not in r and r.get("coppia_netta_Nm") is not None]
        scelte = [r for r in righe if bool(r.get("statore")) == (True if flag is None else flag)]
        if scelte:
            return (sq * abs(float(scelte[0]["coppia_netta_Nm"])),
                    f"{R_C4}: varianti[statore={'true' if scelte[0].get('statore') else 'false'}].coppia_netta_Nm "
                    "x RUOTE.squilibrio_coppia (confronto a rotore fisso)", [])
    return (sq * ru["vortice_residuo_statore"] * coppia_rotore,
            f"{R_REP}: best.cases[0].torque_Nm x RUOTE.squilibrio_coppia x RUOTE.vortice_residuo_statore (RIPIEGO)",
            ["coppia residua dei rotori: nel dimensionamento non c'è la coppia netta (né 5_confronto_statore, né "
             "net_torque_Nm nel report, né 4_sistema/00_sintesi/confronto_statore.json): uso il parametro "
             "RUOTE['vortice_residuo_statore'], che è una stima"])


def _info_catena(catena):
    """Dati solo informativi: variante, L_disk finale della fascia, masse dei pezzi (None se mancano)."""
    L_disk = None
    fascia = _json_se_c_e(catena.cartella, "fascia.json")
    if isinstance(fascia, list):
        ok = [r for r in fascia if isinstance(r, dict) and "errore" not in r and r.get("L_disk_m") is not None]
        if ok:
            L_disk = float(ok[-1]["L_disk_m"])
    masse = None
    rm = _json_se_c_e(catena.radice_caso, "RIEPILOGO_masse.json")
    cat = ((rm or {}).get("catene") or {}).get(catena.variante or "catena")
    if isinstance(cat, dict):
        masse = {k: (cat.get(k) or {}).get("massa_g") for k in ("tubo", "rotore", "statore", "totale")}
    return {"etichetta": catena.etichetta, "variante": catena.variante, "L_disk_m": L_disk, "masse_g": masse}


def _nome_cartella(cartella):
    b = os.path.basename(os.path.normpath(cartella))
    return f"{os.path.basename(os.path.dirname(os.path.normpath(cartella)))}/{b}" if b in VARIANTI else b


def _file(cartella, rel):
    f = os.path.join(cartella, *rel.split("/"))
    if not os.path.isfile(f):
        raise ValueError(f"dimensionamento: manca il file {rel} nel caso {_nome_cartella(cartella)} "
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


def importa(cfg, catena):
    """Legge una catena del dimensionamento (Catena, o la cartella di un caso senza varianti); ritorna (valori, fonti, avvisi).

    valori e fonti sono dizionari {"SEZIONE.chiave": ...}: il valore da usare e il file/campo d'origine.
    valori["_J"] e valori["_info"] sono informativi (inerzie; etichetta, variante, L_disk_m, masse dei pezzi) e non
    finiscono nelle sezioni.  Servono cfg["MOTORE"], ENERGIA (tensione, rendimento), RUOTE (squilibrio, vortice
    residuo come ripiego) e AMBIENTI.
    """
    if not isinstance(catena, Catena):
        c = str(catena)
        catena = Catena(os.path.basename(os.path.normpath(c)), c, os.path.join(c, "1_spinta", "spinta.json"), c, None)
    cartella = catena.cartella
    v, f, avvisi = {}, {}, []

    def metti(sez, k, valore, fonte):
        v[f"{sez}.{k}"] = valore
        f[f"{sez}.{k}"] = fonte

    mo, en, ru = _motore(cfg), cfg["ENERGIA"], cfg["RUOTE"]
    R_SP, R_VEN = "1_spinta/spinta.json", "3_ventola/00_sintesi/report.json"
    R_CFD, R_CUR = "4_sistema/04_cfd/condotto_con_ventola.json", "4_sistema/00_sintesi/curva_potenza.json"
    R_CAD, R_PALE = "3_ventola/03_cad/CAD_info.json", "3_ventola/00_sintesi/confronto_pale.json"
    R_DES, R_SEZ = "2_venturi/05_convergenza/design.json", "3_ventola/02_excel/sections.csv"

    if not os.path.isfile(catena.spinta_json):
        raise ValueError(f"dimensionamento: manca il file {R_SP} nel caso {_nome_cartella(catena.radice_caso)} "
                         "(il caso è incompleto, ad esempio la ventola non è ancora accettata)")
    with open(catena.spinta_json, encoding="utf-8") as fh:
        sp = json.load(fh)
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
    c_res, fonte_c, av_c = coppia_residua(catena, rep, coppia, ru)
    metti("RUOTE", "coppia_reazione_rotori_Nm", c_res, fonte_c)
    avvisi += av_c

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
    v["_info"] = {**_info_catena(catena), "fonte_coppia_residua": fonte_c}

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
