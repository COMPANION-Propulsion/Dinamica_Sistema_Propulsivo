"""Controllo contro il dimensionamento: il bias degli ambienti avvisa solo se supera il disturbo residuo; pressione di progetto."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dinamica_designer import cli                       # noqa: E402
from dinamica_designer import confronto_dimensionamento as CF  # noqa: E402

RADICE = os.path.join(os.path.dirname(__file__), "..")


def _dimensionamento(tmp_path, disturbo_g, p_amb):
    caso = tmp_path / "Dimensionamento_Sistema_Propulsivo" / "risultati" / "c"
    (caso / "1_spinta").mkdir(parents=True)
    (caso / "2_venturi" / "05_convergenza").mkdir(parents=True)
    cfg = cli.carica_input(os.path.join(RADICE, "input.py"))
    inp = {"massa": cfg["CORPO"]["massa_kg"], "distanza": 0.2, "tempo": cfg["MANOVRA"]["tempo_manovra_s"],
           "disturbo_residuo_g": disturbo_g}
    (caso / "1_spinta" / "spinta.json").write_text(json.dumps({"input": inp}), encoding="utf-8")
    (caso / "2_venturi" / "05_convergenza" / "design.json").write_text(json.dumps({"case": {"p_amb": p_amb}}), encoding="utf-8")
    return cfg, str(tmp_path / "Dinamica_Sistema_Propulsivo")


def _avvisi(cfg, prog):
    return "\n".join(CF.confronta(cfg, prog)[1])


def test_bias_sotto_il_residuo_non_avvisa(tmp_path):
    cfg, prog = _dimensionamento(tmp_path, 0.02, 101325.0)
    a = _avvisi(cfg, prog)
    assert "bias_g" not in a and "pressione_progetto" not in a


def test_bias_sopra_il_residuo_avvisa(tmp_path):
    cfg, prog = _dimensionamento(tmp_path, 0.005, 101325.0)       # Volo_Parabolico ha bias 0,01 g
    a = _avvisi(cfg, prog)
    assert "Volo_Parabolico" in a and "bias_g" in a and "ISS" not in a


def test_pressione_di_progetto_diversa_avvisa(tmp_path):
    cfg, prog = _dimensionamento(tmp_path, 0.02, 90000.0)
    assert "pressione_progetto_Pa" in _avvisi(cfg, prog)
