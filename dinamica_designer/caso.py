"""
caso.py
=======
Cartella dei risultati di un caso, come in Dimensionamento_Sistema_Propulsivo:

    risultati/
        registro_esecuzioni.csv      una riga per run (storico)
        <nome_caso>/
            caso.json                nome, impronta degli input, data
            input_usato.py           copia esatta dell'input
            log.txt                  registro della run
            00_sintesi/              RISULTATO.md, riepilogo.json
            01_grafici/              grafici
            02_dati/                 serie temporali

Il nome è CASO["nome"] dell'input oppure, se è None, un nome automatico con l'impronta degli
input: due casi diversi non finiscono mai nella stessa cartella. Una cartella che contiene un
caso con altri input viene rifiutata, salvo CASO["sovrascrivi"] = True. A ogni run le
sottocartelle del caso vengono svuotate e riscritte: dentro c'è sempre una sola run coerente.
"""
import csv
import datetime as dt
import json
import os
import re
import shutil

SOTTOCARTELLE = ("00_sintesi", "01_grafici", "02_dati")
CASO_PREDEFINITO = {"nome": None, "sovrascrivi": False}


def nome_caso(caso, automatico):
    """CASO["nome"] se c'è, altrimenti il nome automatico (già con l'impronta)."""
    nome = caso.get("nome")
    if nome is None:
        return re.sub(r"[^A-Za-z0-9._+-]+", "-", automatico).strip("-")
    nome = str(nome).strip()
    if not nome or any(c in nome for c in '<>:"/\\|?*'):
        raise ValueError(f"CASO['nome'] = {nome!r} non è un nome di cartella valido.")
    return nome


def prepara(base, nome, impronta, sovrascrivi, file_input):
    """Crea (o svuota) la cartella del caso; ritorna il suo percorso."""
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
    for sotto in SOTTOCARTELLE:
        shutil.rmtree(os.path.join(cart, sotto), ignore_errors=True)
        os.makedirs(os.path.join(cart, sotto))
    with open(timbro, "w", encoding="utf-8") as fh:
        json.dump({"nome": nome, "impronta": impronta, "data": f"{dt.datetime.now():%d/%m/%Y %H:%M}"},
                  fh, indent=1)
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
