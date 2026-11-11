"""Cartella del caso: nome automatico con l'impronta, rifiuto di input diversi, risultati scritti."""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dinamica_designer import cli                       # noqa: E402

RADICE = os.path.join(os.path.dirname(__file__), "..")


def _sostituisci(testo, chiave, valore):
    """Rimpiazza il valore di "chiave": ... in input.py, qualunque sia quello scritto oggi."""
    nuovo, n = re.subn(rf'("{chiave}":\s*)[^,#\n]+,', lambda m: f"{m.group(1)}{valore!r},", testo, count=1)
    assert n == 1, chiave
    return nuovo


def _input(tmp_path, nome, massa):
    testo = open(os.path.join(RADICE, "input.py"), encoding="utf-8").read()
    for chiave, valore in (("cartella_output", str(tmp_path)), ("verifiche", False), ("nome", nome),
                           ("sovrascrivi", False), ("massa_kg", massa)):
        testo = _sostituisci(testo, chiave, valore)
    p = tmp_path / f"input_{nome}_{massa}.py"
    p.write_text(testo, encoding="utf-8")
    return str(p)


def test_run_scrive_il_caso(tmp_path):
    cart = cli.run(_input(tmp_path, None, 5))
    assert re.match(r"m5\.00kg_d\d+\.\d{2}m_t\d+\.\ds_h[0-9a-f]{8}$", os.path.basename(cart)), os.path.basename(cart)
    for f in ("caso.json", "input_usato.py", "log.txt", "00_sintesi/RISULTATO.md", "00_sintesi/riepilogo.json",
              "01_grafici/01_moto_tre_assi.svg", "01_grafici/02_spazio_massimo.svg", "01_grafici/03_monte_carlo.svg",
              "01_grafici/04_pale.svg", "02_dati/serie_temporali.csv", "02_dati/monte_carlo.csv"):
        assert os.path.isfile(os.path.join(cart, f)), f
    assert os.path.isfile(tmp_path / "registro_esecuzioni.csv")


def test_caso_con_nome_rifiuta_input_diversi(tmp_path):
    cli.run(_input(tmp_path, "prova", 5))
    with pytest.raises(ValueError, match="altri input"):
        cli.run(_input(tmp_path, "prova", 6))
