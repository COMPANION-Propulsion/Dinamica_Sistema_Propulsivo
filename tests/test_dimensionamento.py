"""Import dei dati dal dimensionamento: valori, nome con suffisso, errori, avviso sul bias."""
import copy
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dinamica_designer import cli                       # noqa: E402
from dinamica_designer import dimensionamento as DM     # noqa: E402

RADICE = os.path.join(os.path.dirname(__file__), "..")
DIM = os.path.join(os.path.dirname(__file__), "dati", "Dimensionamento_Sistema_Propulsivo", "risultati")   # caso "esempio"


def _input(tmp_path, nome="esempio", aggiunte=""):
    """Copia di input.py con CASO["nome"] cambiato e, se serve, righe in più in fondo (es. una chiave doppia)."""
    testo = open(os.path.join(RADICE, "input.py"), encoding="utf-8").read()
    testo = testo.replace('"nome": "RUN_POST_FIX_11-11__v2"', f'"nome": {nome!r}', 1)
    p = tmp_path / "input_prova.py"
    p.write_text(testo + aggiunte, encoding="utf-8")
    return str(p)


def _carica(tmp_path, **kw):
    return cli.carica_input(_input(tmp_path, **kw), DIM)


def test_valori_importati(tmp_path):
    cfg = _carica(tmp_path)
    d = cfg["DIMENSIONAMENTO"]
    assert d["caso"] == "esempio" and d["avvisi"] == []
    assert cfg["CORPO"]["massa_kg"] == 4.5
    assert cfg["MANOVRA"]["distanza_m"] == [0.2] * 3 and cfg["MANOVRA"]["tempo_manovra_s"] == 5
    at, en, ru, pa = cfg["ATTUATORE"], cfg["ENERGIA"], cfg["RUOTE"], cfg["PALE"]
    assert at["pressione_progetto_Pa"] == pytest.approx(101325.0)
    assert at["spinta_max_positiva_N"] == pytest.approx([1.974] * 3, abs=1e-3)
    assert at["spinta_max_negativa_N"] == pytest.approx([1.974] * 3, abs=1e-3)
    assert en["spinta_rif_N"] == pytest.approx(1.974, abs=1e-3)
    assert en["potenza_rif_W"] == pytest.approx(31.43, abs=0.01)
    assert en["esponente"] == pytest.approx(1.37, abs=0.01)
    assert ru["spinta_per_unita_N"] == pytest.approx(0.987, abs=1e-3)
    assert ru["coppia_reazione_rotori_Nm"] == pytest.approx(1.5e-5, rel=0.03)
    assert pa["numero_pale"] == 3
    assert pa["raggio_mozzo_mm"] == pytest.approx(13.07, abs=0.01)
    assert pa["lunghezza_mm"] == pytest.approx(15.47, abs=0.01)
    assert pa["larghezza_mm"] == pytest.approx(15.4, abs=0.1)
    assert pa["spessore_mm"] == pytest.approx(1.46, abs=0.01)
    assert pa["giri_progetto_rpm"] == pytest.approx(18515, abs=1)
    assert pa["giri_massimi_rpm"] == pytest.approx(23349, abs=1)
    assert pa["inerzia_rotore_motore_kgm2"] == cfg["MOTORE"]["inerzia_rotore_kgm2"]
    assert set(d["fonti"]) == {k for k in d["valori"] if not k.startswith("_")}


def test_tempo_di_salita_automatico(tmp_path):
    cfg = _carica(tmp_path)
    t90, J = cfg["ATTUATORE"]["tempo_salita_90_s"], cfg["DIMENSIONAMENTO"]["valori"]["_J"]
    assert 0.05 < J["salita_s"] < 0.3
    assert t90 == pytest.approx(J["salita_s"] + cfg["MOTORE"]["ritardo_regolatore_s"])
    assert J["totale"] == pytest.approx(J["pale"] + J["mozzo"] + J["motore"])


def test_suffisso_della_variante(tmp_path):
    assert DM.nome_dimensionamento("esempio__prova1") == "esempio"
    a = _carica(tmp_path, nome="esempio__prova1")
    b = _carica(tmp_path, nome="esempio")
    assert a["DIMENSIONAMENTO"]["valori"] == b["DIMENSIONAMENTO"]["valori"]
    assert cli.impronta(a) == cli.impronta(b)


def test_caso_mancante_elenca_i_disponibili(tmp_path):
    with pytest.raises(ValueError, match="esempio") as e:
        _carica(tmp_path, nome="non_esiste__x")
    assert "non_esiste" in str(e.value) and "Casi disponibili" in str(e.value)


def test_nome_none_e_errore(tmp_path):
    p = _input(tmp_path)
    testo = open(p, encoding="utf-8").read().replace('"nome": \'esempio\'', '"nome": None', 1)
    open(p, "w", encoding="utf-8").write(testo)
    with pytest.raises(ValueError, match="obbligatorio"):
        cli.carica_input(p, DIM)


def test_chiave_importata_in_input_e_errore(tmp_path):
    with pytest.raises(ValueError, match="viene dal dimensionamento"):
        cli.carica_input(_input(tmp_path, aggiunte='\nCORPO["massa_kg"] = 6.0\n'), DIM)


def test_chiave_importata_in_ambienti_e_errore(tmp_path):
    with pytest.raises(ValueError, match=r"AMBIENTI\['ISS'\].*viene dal dimensionamento"):
        cli.carica_input(_input(tmp_path, aggiunte='\nAMBIENTI["ISS"]["CORPO"] = {"massa_kg": 6.0}\n'), DIM)


def test_campo_mancante_nomina_file_e_campo(tmp_path):
    radice = tmp_path / "risultati"
    shutil.copytree(os.path.join(DIM, "esempio"), radice / "esempio")
    (radice / "esempio" / "3_ventola" / "03_cad" / "CAD_info.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match=r"CAD_info\.json.*diameter_cad_mm"):
        cli.carica_input(_input(tmp_path), str(radice))
    (radice / "esempio" / "3_ventola" / "00_sintesi" / "report.json").unlink()
    with pytest.raises(ValueError, match=r"manca il file 3_ventola/00_sintesi/report\.json"):
        cli.carica_input(_input(tmp_path), str(radice))


def test_bias_sopra_il_residuo_avvisa(tmp_path):
    # nel caso "esempio" il disturbo residuo è 0,02 g: Volo_Parabolico a 0,03 g lo supera, ISS no
    aggiunte = '\nAMBIENTI["Volo_Parabolico"]["DISTURBO"]["bias_g"] = 0.03\n'
    a = "\n".join(cli.carica_input(_input(tmp_path, aggiunte=aggiunte), DIM)["DIMENSIONAMENTO"]["avvisi"])
    assert "Volo_Parabolico" in a and "bias_g" in a and "ISS" not in a


def test_bias_sotto_il_residuo_non_avvisa(tmp_path):
    assert _carica(tmp_path)["DIMENSIONAMENTO"]["avvisi"] == []


def test_impronta_cambia_se_cambia_un_valore_importato(tmp_path):
    cfg = _carica(tmp_path)
    altro = copy.deepcopy(cfg)
    altro["CORPO"]["massa_kg"] = 6.0
    assert cli.impronta(cfg) != cli.impronta(altro)
