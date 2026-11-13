"""Confronto tra catene: md, xlsx (se openpyxl c'è) e svg da riepiloghi reali; catene fallite non fermano nulla."""
import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dinamica_designer.confronto_catene import (       # noqa: E402
    NOME_MD, NOME_SVG, NOME_XLSX, scrivi_confronto_catene)

RADICE = Path(__file__).resolve().parents[1]
RISULTATI = RADICE / "risultati"
AMBIENTI = ("Volo_Parabolico", "ISS")
HA_OPENPYXL = importlib.util.find_spec("openpyxl") is not None


def _copia_riepiloghi(src, dst):
    for amb in AMBIENTI:
        origine = src / amb / "00_sintesi" / "riepilogo.json"
        if origine.is_file():
            cartella = dst / amb / "00_sintesi"
            cartella.mkdir(parents=True, exist_ok=True)
            shutil.copy(origine, cartella / "riepilogo.json")


def test_confronto_tre_catene(tmp_path):
    src4 = RISULTATI / "Run_20261112_fine_4kg"
    src6 = RISULTATI / "Run_20261112_fine_6kg"
    for s in (src4, src6):
        if not s.is_dir():
            pytest.skip(f"risultati reali mancanti: {s}")
    c4 = tmp_path / "catene" / "massa_4" / "NoStatore"
    c6 = tmp_path / "catene" / "massa_6" / "NoStatore"
    _copia_riepiloghi(src4, c4)
    _copia_riepiloghi(src6, c6)
    catene = [
        {"etichetta": "massa_4/NoStatore", "cartella_out": str(c4), "stato": "ok", "variante": "NoStatore",
         "dati": {"variante": "NoStatore", "L_disk_m": 0.25, "masse": {"cubo": 4.0, "ventole": 0.8}}},
        {"etichetta": "massa_6/NoStatore", "cartella_out": str(c6), "stato": "ok", "variante": "NoStatore",
         "dati": {"variante": "NoStatore", "L_disk_m": 0.25, "masse": {"cubo": 6.0, "ventole": 0.8}}},
        {"etichetta": "massa_4/Statore", "cartella_out": str(tmp_path / "non_esiste"),
         "stato": "errore: 2_venturi mancante", "variante": "Statore", "dati": None},
    ]
    out = tmp_path / "confronto"

    scritti = scrivi_confronto_catene(str(out), catene)

    nomi = {Path(p).name for p in scritti}
    attesi = {NOME_MD, NOME_SVG} | ({NOME_XLSX} if HA_OPENPYXL else set())
    assert attesi <= nomi
    for p in scritti:
        assert Path(p).is_file()
    assert (out / NOME_SVG).stat().st_size > 0

    md = (out / NOME_MD).read_text(encoding="utf-8")
    for c in catene:
        assert c["etichetta"] in md
    assert "errore: 2_venturi mancante" in md
    for amb in AMBIENTI:
        assert f"`{amb}`" in md
    assert "massa_4/NoStatore" in md and "massa_6/NoStatore" in md


def test_catene_rotte_non_sollevano(tmp_path):
    out = tmp_path / "rotto"
    scritti = scrivi_confronto_catene(str(out), [{"etichetta": "a"}, "non_un_dict", {"stato": "boom"}])
    assert (out / NOME_MD).is_file()
    assert (out / NOME_SVG).is_file()
    assert any(Path(p).name == NOME_MD for p in scritti)
    assert "boom" in (out / NOME_MD).read_text(encoding="utf-8")
