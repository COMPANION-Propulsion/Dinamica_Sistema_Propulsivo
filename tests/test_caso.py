"""Cartella del caso: nome automatico con l'impronta, rifiuto di input diversi, risultati scritti."""
import json
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


def _input(tmp_path, nome, massa, extra=()):
    testo = open(os.path.join(RADICE, "input.py"), encoding="utf-8").read()
    for chiave, valore in (("cartella_output", str(tmp_path)), ("verifiche", False), ("nome", nome),
                           ("sovrascrivi", False), ("massa_kg", massa), ("campioni_monte_carlo", 5), ("campioni", 20), *extra):
        testo = _sostituisci(testo, chiave, valore)
    p = tmp_path / f"input_{nome}_{massa}.py"
    p.write_text(testo, encoding="utf-8")
    return str(p)


def test_run_scrive_il_caso(tmp_path):
    cart = cli.run(_input(tmp_path, None, 5))
    assert re.match(r"m5\.00kg_d\d+\.\d{2}m_t\d+\.\ds_h[0-9a-f]{8}$", os.path.basename(cart)), os.path.basename(cart)
    for f in ("caso.json", "input_usato.py", "log.txt", "CONFRONTO.md", "Pale/PALE.md", "Pale/pale.svg", "Pale/pale.json"):
        assert os.path.isfile(os.path.join(cart, f)), f
    for amb in ("Volo_Parabolico", "ISS"):
        for f in ("00_sintesi/RISULTATO.md", "00_sintesi/riepilogo.json", "01_grafici/01_moto_tre_assi.svg",
                  "01_grafici/02_spazio_massimo.svg", "01_grafici/03_monte_carlo.svg", "02_dati/serie_temporali.csv",
                  "02_dati/monte_carlo.csv"):
            assert os.path.isfile(os.path.join(cart, amb, f)), f"{amb}/{f}"
    assert not os.path.exists(os.path.join(cart, "00_sintesi"))
    confronto = open(os.path.join(cart, "CONFRONTO.md"), encoding="utf-8").read()
    assert "Volo_Parabolico" in confronto and "ISS" in confronto and "corrente di picco" in confronto
    with open(os.path.join(cart, "ISS", "00_sintesi", "riepilogo.json"), encoding="utf-8") as fh:
        riep = json.load(fh)
    assert riep["ambiente"]["sigma"] == pytest.approx(1.0) and riep["potenza_totale"]["corrente_picco_A"] > 0
    assert len(open(tmp_path / "registro_esecuzioni.csv", encoding="utf-8").read().splitlines()) == 2    # intestazione + 1 run


def test_un_solo_ambiente_attivo_e_pulizia(tmp_path):
    cart = cli.run(_input(tmp_path, "uno", 5))
    assert os.path.isdir(os.path.join(cart, "ISS"))
    cart = cli.run(_input(tmp_path, "uno", 5, extra=(("attivo", False), ("sovrascrivi", True))))           # spegne Volo_Parabolico
    assert os.path.isdir(os.path.join(cart, "ISS")) and not os.path.exists(os.path.join(cart, "Volo_Parabolico"))
    assert "| grandezza | ISS |" in open(os.path.join(cart, "CONFRONTO.md"), encoding="utf-8").read()


def test_profilo_bang_bang(tmp_path):
    cart = cli.run(_input(tmp_path, "bb", 5, extra=(("profilo", "bang_bang"),)))
    assert "bang_bang" in open(os.path.join(cart, "ISS", "00_sintesi", "RISULTATO.md"), encoding="utf-8").read()


def test_input_senza_ambienti_o_con_pressione_errata(tmp_path):
    p = _input(tmp_path, "x", 5)
    testo = open(p, encoding="utf-8").read()
    (tmp_path / "senza.py").write_text(testo.split("AMBIENTI = {")[0], encoding="utf-8")
    with pytest.raises(ValueError, match="AMBIENTI"):
        cli.carica_input(str(tmp_path / "senza.py"))
    (tmp_path / "errata.py").write_text(testo.replace("82500.0", "-1.0"), encoding="utf-8")
    with pytest.raises(ValueError, match="pressione_Pa"):
        cli.carica_input(str(tmp_path / "errata.py"))


def test_caso_con_nome_rifiuta_input_diversi(tmp_path):
    cli.run(_input(tmp_path, "prova", 5))
    with pytest.raises(ValueError, match="altri input"):
        cli.run(_input(tmp_path, "prova", 6))
