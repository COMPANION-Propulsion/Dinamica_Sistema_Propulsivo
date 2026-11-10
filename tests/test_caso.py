"""Cartella del caso: nome automatico con l'impronta, rifiuto di input diversi, risultati scritti."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dinamica_designer import cli                       # noqa: E402

RADICE = os.path.join(os.path.dirname(__file__), "..")


def _input(tmp_path, nome, massa):
    testo = open(os.path.join(RADICE, "input.py"), encoding="utf-8").read()
    testo = testo.replace('"cartella_output": "risultati"', f'"cartella_output": {str(tmp_path)!r}')
    testo = testo.replace('"verifiche": True', '"verifiche": False')
    testo = testo.replace('"nome": None', f'"nome": {nome!r}')
    testo = testo.replace('"massa_kg": 5,', f'"massa_kg": {massa},')
    p = tmp_path / f"input_{nome}_{massa}.py"
    p.write_text(testo, encoding="utf-8")
    return str(p)


def test_run_scrive_il_caso(tmp_path):
    cart = cli.run(_input(tmp_path, None, 5))
    assert os.path.basename(cart).startswith("m5.00kg_d0.30m_t3.0s_h")
    for f in ("caso.json", "input_usato.py", "log.txt", "00_sintesi/RISULTATO.md", "00_sintesi/riepilogo.json",
              "01_grafici/01_moto_tre_assi.svg", "01_grafici/02_spazio_massimo.svg", "02_dati/serie_temporali.csv"):
        assert os.path.isfile(os.path.join(cart, f)), f
    assert os.path.isfile(tmp_path / "registro_esecuzioni.csv")


def test_caso_con_nome_rifiuta_input_diversi(tmp_path):
    cli.run(_input(tmp_path, "prova", 5))
    with pytest.raises(ValueError, match="altri input"):
        cli.run(_input(tmp_path, "prova", 6))
