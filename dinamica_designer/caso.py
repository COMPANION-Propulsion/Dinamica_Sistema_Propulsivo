"""
caso.py
=======
Cartella dei risultati di un caso, come in Dimensionamento_Sistema_Propulsivo:

    risultati/
        registro_esecuzioni.csv      una riga per run (storico)
        <nome_caso>/
            caso.json                nome, impronta degli input, data, ambienti, etichette delle catene
            input_usato.py           copia esatta dell'input
            log.txt                  registro della run
            CONFRONTO.md             tabella affiancata degli ambienti
            Pale/                    squilibrio dei rotori (non dipende dall'ambiente, calcolato una volta)
            <ambiente>/              una cartella per ambiente attivo (Volo_Parabolico, ISS, ...)
                00_sintesi/          RISULTATO.md, riepilogo.json
                01_grafici/          grafici
                02_dati/             serie temporali

Il nome è CASO["nome"] dell'input oppure, se è None, un nome automatico con l'impronta degli
input: due casi diversi non finiscono mai nella stessa cartella. Una cartella che contiene un
caso con altri input viene rifiutata, salvo CASO["sovrascrivi"] = True. A ogni run le
cartelle degli ambienti e Pale/ vengono svuotate e riscritte (anche quelle di ambienti non più attivi
e le sottocartelle del vecchio formato senza ambienti): dentro c'è sempre una sola run coerente.
La cartella si prepara una volta sola, all'inizio della run, per tutti gli ambienti.

Con più catene del dimensionamento (Statore / NoStatore, casi di una serie) ogni catena ha la sua sottocartella
risultati/<nome_caso>/<etichetta>/ (la "/" dell'etichetta fa sottocartelle) con la stessa struttura (ambienti, Pale/,
CONFRONTO.md, dati_dimensionamento.json); nella radice del caso restano caso.json, input_usato.py, log.txt e il
confronto fra le catene (CONFRONTO_catene.*).  La pulizia tiene conto anche delle catene della run precedente.
"""
import csv
import datetime as dt
import json
import os
import re
import shutil

SOTTOCARTELLE = ("00_sintesi", "01_grafici", "02_dati")
CASO_PREDEFINITO = {"nome": None, "sovrascrivi": False, "varianti": "tutte"}
# file della radice del caso riscritti a ogni run (o da scrivere solo in certi casi): si tolgono prima
FILE_RADICE = ("CONFRONTO.md", "dati_dimensionamento.json", "CONFRONTO_catene.md", "confronto_catene.xlsx",
               "confronto_catene.svg")
FILE_CATENA = ("CONFRONTO.md", "dati_dimensionamento.json")


def nome_caso(caso, automatico):
    """CASO["nome"] se c'è, altrimenti il nome automatico (già con l'impronta)."""
    nome = caso.get("nome")
    if nome is None:
        return re.sub(r"[^A-Za-z0-9._+-]+", "-", automatico).strip("-")
    nome = str(nome).strip().replace("/", "-").replace(chr(92), "-")        # "serie/massa_4/NoStatore" -> una cartella
    if not nome or any(c in nome for c in '<>:"/\\|?*'):
        raise ValueError(f"CASO['nome'] = {nome!r} non è un nome di cartella valido.")
    return nome


def _pulisci(cartella, ambienti):
    """Toglie da una cartella di uscita ambienti, sottocartelle di sintesi, Pale/ e file di confronto."""
    for x in list(ambienti) + list(SOTTOCARTELLE) + ["Pale"]:
        shutil.rmtree(os.path.join(cartella, x), ignore_errors=True)
    for f in FILE_CATENA:
        try:
            os.remove(os.path.join(cartella, f))
        except OSError:
            pass


def _rimuovi_vuote(cart, rel):
    """Toglie le cartelle vuote lungo il percorso rel (da cart) fino a cart esclusa."""
    parti = rel.split("/")
    while parti:
        d = os.path.join(cart, *parti)
        try:
            os.rmdir(d)
        except OSError:
            break
        parti.pop()


def prepara(base, nome, impronta, sovrascrivi, file_input, ambienti=(), catene=(), catene_da_creare=None):
    """Crea (o svuota) la cartella del caso con una sottocartella per ambiente; ritorna il suo percorso.

    catene = etichette delle catene del dimensionamento che hanno una sottocartella propria (vuoto: struttura piatta,
    gli ambienti stanno nella radice del caso); catene_da_creare = quelle di cui si preparano le cartelle degli
    ambienti (predefinito: tutte; una catena non importabile non ne ha).  Le catene della run precedente (caso.json)
    si puliscono.
    """
    cart = os.path.join(base, nome)
    timbro = os.path.join(cart, "caso.json")
    if os.path.isfile(timbro):
        with open(timbro, encoding="utf-8") as fh:
            vecchia = json.load(fh).get("impronta")
        if vecchia != impronta and not sovrascrivi:
            raise ValueError(
                f"{cart} contiene un caso con altri input (impronta {vecchia}, ora {impronta}). "
                "Cambia CASO['nome'], mettilo a None per un nome automatico, oppure metti "
                "CASO['sovrascrivi'] = True.")
    vecchi, vecchie_catene = [], []
    if os.path.isfile(timbro):
        with open(timbro, encoding="utf-8") as fh:
            vecchio_caso = json.load(fh)
        vecchi, vecchie_catene = vecchio_caso.get("ambienti", []), vecchio_caso.get("catene", [])
    tutti_ambienti = list(vecchi) + list(ambienti)
    _pulisci(cart, tutti_ambienti)
    for f in FILE_RADICE:
        try:
            os.remove(os.path.join(cart, f))
        except OSError:
            pass
    for et in list(vecchie_catene) + list(catene):
        _pulisci(os.path.join(cart, *et.split("/")), tutti_ambienti)
    for et in vecchie_catene:
        if et not in catene:
            _rimuovi_vuote(cart, et)
    da_creare = list(catene if catene_da_creare is None else catene_da_creare)
    for base_amb in ([os.path.join(cart, *et.split("/")) for et in da_creare] if catene else [cart]):
        for amb in ambienti:
            for sotto in SOTTOCARTELLE:
                os.makedirs(os.path.join(base_amb, amb, sotto), exist_ok=True)
    with open(timbro, "w", encoding="utf-8") as fh:
        json.dump({"nome": nome, "impronta": impronta, "data": f"{dt.datetime.now():%d/%m/%Y %H:%M}",
                   "ambienti": list(ambienti), "catene": list(catene)}, fh, indent=1)
    shutil.copyfile(file_input, os.path.join(cart, "input_usato.py"))
    return cart


def registra(base, riga):
    """Aggiunge una riga a risultati/registro_esecuzioni.csv."""
    f = os.path.join(base, "registro_esecuzioni.csv")
    nuovo = not os.path.exists(f)
    with open(f, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(riga.keys()), delimiter=";")
        if nuovo:
            w.writeheader()
        w.writerow(riga)
