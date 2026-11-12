"""Cartella del caso: nome obbligatorio, rifiuto di input diversi, risultati scritti."""
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dinamica_designer import cli                       # noqa: E402

RADICE = os.path.join(os.path.dirname(__file__), "..")
DIM = os.path.join(os.path.dirname(__file__), "dati", "Dimensionamento_Sistema_Propulsivo", "risultati")   # caso "esempio"


def _sostituisci(testo, chiave, valore):
    """Rimpiazza il valore di "chiave": ... in input.py, qualunque sia quello scritto oggi (solo chiavi di input.py)."""
    nuovo, n = re.subn(rf'("{chiave}":\s*)[^,#\n]+,', lambda m: f"{m.group(1)}{valore!r},", testo, count=1)
    assert n == 1, chiave
    return nuovo


def _input(tmp_path, nome, extra=()):
    testo = open(os.path.join(RADICE, "input.py"), encoding="utf-8").read()
    for chiave, valore in (("cartella_output", str(tmp_path)), ("verifiche", False), ("nome", nome),
                           ("sovrascrivi", False), ("campioni_monte_carlo", 5), ("campioni", 20), *extra):
        testo = _sostituisci(testo, chiave, valore)
    p = tmp_path / f"input_{nome}_{len(extra)}.py"
    p.write_text(testo, encoding="utf-8")
    return str(p)


def _run(tmp_path, nome, extra=()):
    return cli.run(_input(tmp_path, nome, extra), radice_dimensionamento=DIM)


def test_run_scrive_il_caso(tmp_path):
    cart = _run(tmp_path, "esempio__completo")
    assert os.path.basename(cart) == "esempio__completo"
    for f in ("caso.json", "input_usato.py", "log.txt", "CONFRONTO.md", "dati_dimensionamento.json",
              "Pale/PALE.md", "Pale/pale.svg", "Pale/pale.json"):
        assert os.path.isfile(os.path.join(cart, f)), f
    for amb in ("Volo_Parabolico", "ISS"):
        for f in ("00_sintesi/RISULTATO.md", "00_sintesi/riepilogo.json", "01_grafici/01_moto_tre_assi.svg",
                  "01_grafici/02_spazio_massimo.svg", "01_grafici/03_monte_carlo.svg", "02_dati/serie_temporali.csv",
                  "02_dati/monte_carlo.csv"):
            assert os.path.isfile(os.path.join(cart, amb, f)), f"{amb}/{f}"
    assert not os.path.exists(os.path.join(cart, "00_sintesi"))
    confronto = open(os.path.join(cart, "CONFRONTO.md"), encoding="utf-8").read()
    assert "Volo_Parabolico" in confronto and "ISS" in confronto and "corrente di picco" in confronto
    assert "Dati dal dimensionamento (caso `esempio`)" in confronto and "CORPO.massa_kg" in confronto
    with open(os.path.join(cart, "dati_dimensionamento.json"), encoding="utf-8") as fh:
        dati = json.load(fh)
    assert dati["caso"] == "esempio" and dati["valori"]["CORPO.massa_kg"] == 4.5 and "CORPO.massa_kg" in dati["fonti"]
    with open(os.path.join(cart, "ISS", "00_sintesi", "riepilogo.json"), encoding="utf-8") as fh:
        riep = json.load(fh)
    assert riep["ambiente"]["sigma"] == pytest.approx(1.0) and riep["potenza_totale"]["corrente_picco_A"] > 0
    assert len(open(tmp_path / "registro_esecuzioni.csv", encoding="utf-8").read().splitlines()) == 2    # intestazione + 1 run


def test_un_solo_ambiente_attivo_e_pulizia(tmp_path):
    cart = _run(tmp_path, "esempio__uno")
    assert os.path.isdir(os.path.join(cart, "ISS"))
    cart = _run(tmp_path, "esempio__uno", extra=(("attivo", False), ("sovrascrivi", True)))           # spegne Volo_Parabolico
    assert os.path.isdir(os.path.join(cart, "ISS")) and not os.path.exists(os.path.join(cart, "Volo_Parabolico"))
    assert "| grandezza | ISS |" in open(os.path.join(cart, "CONFRONTO.md"), encoding="utf-8").read()


def test_profilo_bang_bang(tmp_path):
    cart = _run(tmp_path, "esempio__bb", extra=(("profilo", "bang_bang"),))
    assert "bang_bang" in open(os.path.join(cart, "ISS", "00_sintesi", "RISULTATO.md"), encoding="utf-8").read()


def test_input_senza_ambienti_o_con_pressione_errata(tmp_path):
    p = _input(tmp_path, "esempio__x")
    testo = open(p, encoding="utf-8").read()
    (tmp_path / "senza.py").write_text(testo.split("AMBIENTI = {")[0], encoding="utf-8")
    with pytest.raises(ValueError, match="AMBIENTI"):
        cli.carica_input(str(tmp_path / "senza.py"), DIM)
    (tmp_path / "errata.py").write_text(testo.replace("82500.0", "-1.0"), encoding="utf-8")
    with pytest.raises(ValueError, match="pressione_Pa"):
        cli.carica_input(str(tmp_path / "errata.py"), DIM)


def test_caso_con_nome_rifiuta_input_diversi(tmp_path):
    _run(tmp_path, "esempio__prova")
    with pytest.raises(ValueError, match="altri input"):
        _run(tmp_path, "esempio__prova", extra=(("tolleranza_posizione_mm", 7.0),))


def test_nome_automatico_non_ammesso(tmp_path):
    with pytest.raises(ValueError, match="obbligatorio"):
        _run(tmp_path, None)
