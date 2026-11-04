"""Cartelle di output: una per esecuzione, mai sovrascritte, sempre riconoscibili.

Nome:  AAAAMMGG-HHMMSS_<etichetta>_<impronta degli input>
  etichetta  testo libero da INPUT.py, oppure automatica (spinta, lato, ambiente, scenari)
  impronta   8 caratteri calcolati dagli input: stessa impronta = stessi dati
Il file registro_esecuzioni.csv nella cartella principale elenca tutte le
esecuzioni con data, cartella, impronta e scenario vincente.
"""
import csv
import datetime as dt
import os
import re
import shutil


def _pulisci(testo):
    return re.sub(r"[^A-Za-z0-9.+-]+", "-", testo).strip("-")


def crea_cartella(cfg, scenari, impronta, base):
    m, g = cfg["missione"], cfg["geometria"]
    et = cfg["esecuzione"].get("etichetta") or (
        f"F{m['spinta_per_asse_N']:.2f}N_L{g['lato_cubo_min_mm']:.0f}-{g['lato_cubo_max_mm']:.0f}"
        f"_{cfg['ambiente_progetto']}_{len(scenari)}scenari")
    nome = f"{dt.datetime.now():%Y%m%d-%H%M%S}_{_pulisci(et)}_{impronta}"
    percorso = os.path.join(base, nome)
    k = 2
    while os.path.exists(percorso):
        percorso = os.path.join(base, f"{nome}_{k}")
        k += 1
    for sotto in ("grafici", "grafici/confronto", "dati", "excel"):
        os.makedirs(os.path.join(percorso, sotto), exist_ok=True)
    return percorso


def copia_input(percorso, file_input):
    shutil.copy(file_input, os.path.join(percorso, "INPUT_usato.py"))


def registra(base, riga):
    f = os.path.join(base, "registro_esecuzioni.csv")
    nuovo = not os.path.exists(f)
    with open(f, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(riga.keys()), delimiter=";")
        if nuovo:
            w.writeheader()
        w.writerow(riga)
