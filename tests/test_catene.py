"""Catene del dimensionamento: varianti Statore / NoStatore e serie di casi (trova_catene, coppia residua, --elenca, uscite)."""
import copy
import json
import os
import re
import shutil
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dinamica_designer import cli                       # noqa: E402
from dinamica_designer import dimensionamento as DM     # noqa: E402

RADICE = os.path.join(os.path.dirname(__file__), "..")
DIM = os.path.join(os.path.dirname(__file__), "dati", "Dimensionamento_Sistema_Propulsivo", "risultati")
# fixture: esempio (layout vecchio), esempio_varianti (Statore / NoStatore), serie_esempio (massa_a con varianti, massa_b vecchio)


def _input(tmp_path, nome, varianti="tutte", extra=()):
    """Copia di input.py con nome e varianti scelti, uscite in tmp_path, Monte Carlo e pale ridotti, un solo ambiente."""
    testo = open(os.path.join(RADICE, "input.py"), encoding="utf-8").read()
    for chiave, valore in (("cartella_output", str(tmp_path / "ris")), ("verifiche", False), ("nome", nome),
                           ("varianti", varianti), ("sovrascrivi", False), ("campioni_monte_carlo", 3),
                           ("campioni", 10), *extra):
        testo, n = re.subn(rf'("{chiave}":\s*)[^,#\n]+,', lambda m: f"{m.group(1)}{valore!r},", testo, count=1)
        assert n == 1, chiave
    p = tmp_path / f"input_{abs(hash((nome, str(varianti), extra)))}.py"
    p.write_text(testo, encoding="utf-8")
    return str(p)


def _cfg(tmp_path, nome, radice=DIM, varianti="tutte", indice=0):
    base = cli.leggi_input(_input(tmp_path, nome, varianti))
    return cli.cfg_catena(base, cli.trova_catene(base, radice)[indice])


def _copia(tmp_path):
    """Copia scrivibile della radice dei dati di prova."""
    d = tmp_path / "dim"
    shutil.copytree(DIM, d)
    return str(d)


def _leggi(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _scrivi(p, dati):
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(dati, fh)


# ---------------------------------------------------------------- trova_catene
def test_caso_senza_varianti():
    for nome in ("esempio", "esempio__v2", "esempio__prova1"):
        c, = DM.trova_catene(DIM, nome)
        assert (c.etichetta, c.variante) == ("esempio", None)
        assert c.cartella == c.radice_caso == os.path.join(DIM, "esempio")
        assert c.spinta_json == os.path.join(DIM, "esempio", "1_spinta", "spinta.json")


def test_caso_con_varianti():
    s, n = DM.trova_catene(DIM, "esempio_varianti")
    assert [x.etichetta for x in (s, n)] == ["Statore", "NoStatore"] and [x.variante for x in (s, n)] == ["Statore", "NoStatore"]
    radice = os.path.join(DIM, "esempio_varianti")
    assert s.cartella == os.path.join(radice, "Statore") and s.radice_caso == radice
    assert s.spinta_json == os.path.join(radice, "Statore", "1_spinta", "spinta.json")       # copia nella catena


def test_spinta_dalla_radice_se_la_catena_non_ha_la_copia(tmp_path):
    radice = _copia(tmp_path)
    shutil.rmtree(os.path.join(radice, "esempio_varianti", "NoStatore", "1_spinta"))
    n = DM.trova_catene(radice, "esempio_varianti/NoStatore")[0]
    assert n.spinta_json == os.path.join(radice, "esempio_varianti", "1_spinta", "spinta.json")
    assert os.path.isfile(n.spinta_json)


def test_una_variante():
    for nome in ("esempio_varianti/NoStatore", "esempio_varianti/NoStatore__v3"):
        c, = DM.trova_catene(DIM, nome)
        assert (c.etichetta, c.variante) == ("NoStatore", "NoStatore")


def test_serie():
    cs = DM.trova_catene(DIM, "serie_esempio")
    assert [c.etichetta for c in cs] == ["massa_a/Statore", "massa_a/NoStatore", "massa_b"]
    assert [c.variante for c in cs] == ["Statore", "NoStatore", None]
    assert cs[0].radice_caso == os.path.join(DIM, "serie_esempio", "massa_a")
    assert cs[2].cartella == os.path.join(DIM, "serie_esempio", "massa_b")
    assert [c.etichetta for c in DM.trova_catene(DIM, "serie_esempio__v2")] == [c.etichetta for c in cs]


def test_etichetta_e_variante_di_una_serie():
    assert [c.etichetta for c in DM.trova_catene(DIM, "serie_esempio/massa_a")] == ["massa_a/Statore", "massa_a/NoStatore"]
    c, = DM.trova_catene(DIM, "serie_esempio/massa_b")
    assert (c.etichetta, c.variante) == ("massa_b", None)
    c, = DM.trova_catene(DIM, "serie_esempio/massa_a/NoStatore__v1")
    assert (c.etichetta, c.variante) == ("massa_a/NoStatore", "NoStatore")


def test_elenco_varianti_scelte():
    assert [c.etichetta for c in DM.trova_catene(DIM, "esempio_varianti", ["NoStatore"])] == ["NoStatore"]
    assert [c.etichetta for c in DM.trova_catene(DIM, "esempio_varianti", ("Statore", "NoStatore"))] == ["Statore", "NoStatore"]
    assert [c.etichetta for c in DM.trova_catene(DIM, "esempio_varianti", "tutte")] == ["Statore", "NoStatore"]
    # in una serie i casi senza la variante (massa_b, layout vecchio) si saltano
    assert [c.etichetta for c in DM.trova_catene(DIM, "serie_esempio", ["NoStatore"])] == ["massa_a/NoStatore"]


def test_etichetta_con_doppio_trattino_basso(tmp_path):
    radice = _copia(tmp_path)
    shutil.move(os.path.join(radice, "serie_esempio", "massa_b"), os.path.join(radice, "serie_esempio", "massa_b__D_0.07"))
    assert [c.etichetta for c in DM.trova_catene(radice, "serie_esempio/massa_b__D_0.07")] == ["massa_b__D_0.07"]
    assert [c.etichetta for c in DM.trova_catene(radice, "serie_esempio/massa_b__D_0.07__v2")] == ["massa_b__D_0.07"]


def test_casi_disponibili():
    d = DM.casi_disponibili(DIM)
    for n in ("esempio", "esempio_varianti", "esempio_varianti/Statore", "esempio_varianti/NoStatore", "serie_esempio",
              "serie_esempio/massa_a", "serie_esempio/massa_a/NoStatore", "serie_esempio/massa_b"):
        assert n in d, n
    assert "esempio/Statore" not in d and "serie_esempio/massa_b/Statore" not in d


# ---------------------------------------------------------------- errori
def test_errore_nome_inesistente():
    with pytest.raises(ValueError) as e:
        DM.trova_catene(DIM, "esempio_variant")
    t = str(e.value)
    assert "esempio_variant" in t and "Casi disponibili" in t and "esempio_varianti/NoStatore" in t and "Forse" in t


def test_errore_variante_sbagliata():
    with pytest.raises(ValueError, match=r"le varianti sono Statore, NoStatore.*forse Statore"):
        DM.trova_catene(DIM, "esempio_varianti/Statoree")
    with pytest.raises(ValueError, match="non ha il confronto statore"):
        DM.trova_catene(DIM, "esempio/Statore")
    with pytest.raises(ValueError, match="non ha il confronto statore"):
        DM.trova_catene(DIM, "serie_esempio/massa_b/NoStatore")


def test_errore_etichetta_di_serie_sbagliata():
    with pytest.raises(ValueError, match=r"nella serie 'serie_esempio' non c'è il caso 'massa_z'.*massa_a, massa_b"):
        DM.trova_catene(DIM, "serie_esempio/massa_z")


def test_errore_varianti_incoerenti():
    with pytest.raises(ValueError, match="mettili d'accordo"):
        DM.trova_catene(DIM, "esempio_varianti/NoStatore", ["Statore"])
    with pytest.raises(ValueError, match="nomi validi sono Statore, NoStatore"):
        DM.trova_catene(DIM, "esempio_varianti", ["Foo"])
    with pytest.raises(ValueError, match="non ha il confronto statore"):
        DM.trova_catene(DIM, "esempio", ["NoStatore"])


def test_errore_serie_senza_le_varianti_richieste(tmp_path):
    shutil.copytree(os.path.join(DIM, "esempio"), tmp_path / "s" / "uno")
    shutil.copytree(os.path.join(DIM, "esempio"), tmp_path / "s" / "due")
    assert [c.etichetta for c in DM.trova_catene(str(tmp_path), "s")] == ["due", "uno"]
    with pytest.raises(ValueError, match="nessuno ha le varianti"):
        DM.trova_catene(str(tmp_path), "s", ["NoStatore"])


def test_errore_cartella_che_non_e_un_caso(tmp_path):
    (tmp_path / "vuota" / "x").mkdir(parents=True)
    (tmp_path / "vuota" / "x" / "file.txt").write_text("a")
    with pytest.raises(ValueError, match=r"non è né un caso del dimensionamento.*né una serie"):
        DM.trova_catene(str(tmp_path), "vuota")


def test_errore_nome_assente():
    with pytest.raises(ValueError, match="obbligatorio"):
        DM.trova_catene(DIM, None)


# ---------------------------------------------------------------- coppia residua e dati informativi
def test_coppia_dal_confronto_del_caso(tmp_path):
    s = _cfg(tmp_path, "esempio_varianti", indice=0)
    n = _cfg(tmp_path, "esempio_varianti", indice=1)
    sq = s["RUOTE"]["squilibrio_coppia"]
    assert s["RUOTE"]["coppia_reazione_rotori_Nm"] == 0.0
    assert n["RUOTE"]["coppia_reazione_rotori_Nm"] == pytest.approx(sq * 5.4e-3)
    for c in (s, n):
        assert c["DIMENSIONAMENTO"]["avvisi"] == []
        assert "5_confronto_statore/confronto_statore.json" in c["DIMENSIONAMENTO"]["fonti"]["RUOTE.coppia_reazione_rotori_Nm"]


def test_coppia_dal_confronto_della_catena(tmp_path):
    radice = _copia(tmp_path)
    caso = os.path.join(radice, "esempio_varianti")
    shutil.rmtree(os.path.join(caso, "5_confronto_statore"))
    f = os.path.join(caso, "NoStatore", "4_sistema", "00_sintesi", "confronto_statore.json")
    d = _leggi(f)
    d["varianti"][1]["coppia_netta_Nm"] = 0.001
    _scrivi(f, d)
    n = _cfg(tmp_path, "esempio_varianti/NoStatore", radice)
    assert n["RUOTE"]["coppia_reazione_rotori_Nm"] == pytest.approx(n["RUOTE"]["squilibrio_coppia"] * 0.001)
    assert "4_sistema/00_sintesi/confronto_statore.json" in n["DIMENSIONAMENTO"]["fonti"]["RUOTE.coppia_reazione_rotori_Nm"]
    assert n["DIMENSIONAMENTO"]["avvisi"] == []
    s = _cfg(tmp_path, "esempio_varianti/Statore", radice)
    assert s["RUOTE"]["coppia_reazione_rotori_Nm"] == 0.0


def test_coppia_layout_vecchio_segue_lo_statore_dell_input(tmp_path):
    radice = _copia(tmp_path)
    caso = os.path.join(radice, "esempio")
    _scrivi(os.path.join(caso, "4_sistema", "00_sintesi", "confronto_statore.json"), {"varianti": [
        {"statore": True, "coppia_netta_Nm": 0.0}, {"statore": False, "coppia_netta_Nm": 0.004}]})
    c = _cfg(tmp_path, "esempio", radice)                                        # senza input_ventola: riga con statore
    assert c["RUOTE"]["coppia_reazione_rotori_Nm"] == 0.0
    _scrivi(os.path.join(caso, "input_ventola.json"), {"stator": {"enabled": False}})
    c = _cfg(tmp_path, "esempio", radice)
    assert c["RUOTE"]["coppia_reazione_rotori_Nm"] == pytest.approx(c["RUOTE"]["squilibrio_coppia"] * 0.004)
    assert c["DIMENSIONAMENTO"]["avvisi"] == []


def test_report_della_catena_prima_del_confronto_a_rotore_fisso(tmp_path):
    radice = _copia(tmp_path)
    caso = os.path.join(radice, "esempio_varianti")
    shutil.rmtree(os.path.join(caso, "5_confronto_statore"))
    f = os.path.join(caso, "NoStatore", "3_ventola", "00_sintesi", "report.json")
    rep = _leggi(f)
    rep["best"]["cases"][0]["net_torque_Nm"] = 0.002           # il confronto a rotore fisso della catena dice 0,0054
    _scrivi(f, rep)
    n = _cfg(tmp_path, "esempio_varianti/NoStatore", radice)
    assert n["RUOTE"]["coppia_reazione_rotori_Nm"] == pytest.approx(n["RUOTE"]["squilibrio_coppia"] * 0.002)
    assert "net_torque_Nm" in n["DIMENSIONAMENTO"]["fonti"]["RUOTE.coppia_reazione_rotori_Nm"]


def test_coppia_dal_report_e_ripiego_con_avviso(tmp_path):
    radice = _copia(tmp_path)
    caso = os.path.join(radice, "esempio_varianti")
    shutil.rmtree(os.path.join(caso, "5_confronto_statore"))
    os.remove(os.path.join(caso, "NoStatore", "4_sistema", "00_sintesi", "confronto_statore.json"))
    f = os.path.join(caso, "NoStatore", "3_ventola", "00_sintesi", "report.json")
    rep = _leggi(f)
    coppia_rotore = rep["best"]["cases"][0]["torque_Nm"]
    rep["best"]["cases"][0]["net_torque_Nm"] = 0.002
    _scrivi(f, rep)
    n = _cfg(tmp_path, "esempio_varianti/NoStatore", radice)
    assert n["RUOTE"]["coppia_reazione_rotori_Nm"] == pytest.approx(n["RUOTE"]["squilibrio_coppia"] * 0.002)
    assert "net_torque_Nm" in n["DIMENSIONAMENTO"]["fonti"]["RUOTE.coppia_reazione_rotori_Nm"] and n["DIMENSIONAMENTO"]["avvisi"] == []
    del rep["best"]["cases"][0]["net_torque_Nm"]
    _scrivi(f, rep)
    n = _cfg(tmp_path, "esempio_varianti/NoStatore", radice)
    ru = n["RUOTE"]
    assert ru["coppia_reazione_rotori_Nm"] == pytest.approx(ru["squilibrio_coppia"] * ru["vortice_residuo_statore"] * coppia_rotore)
    av = n["DIMENSIONAMENTO"]["avvisi"]
    assert len(av) == 1 and "vortice_residuo_statore" in av[0] and "RIPIEGO" in n["DIMENSIONAMENTO"]["fonti"]["RUOTE.coppia_reazione_rotori_Nm"]


def test_dati_informativi(tmp_path):
    s = _cfg(tmp_path, "esempio_varianti", indice=0)["DIMENSIONAMENTO"]
    n = _cfg(tmp_path, "esempio_varianti", indice=1)["DIMENSIONAMENTO"]
    assert (s["variante"], n["variante"]) == ("Statore", "NoStatore")
    assert s["valori"]["_info"]["L_disk_m"] == pytest.approx(0.0285) and n["valori"]["_info"]["L_disk_m"] == pytest.approx(0.026)
    assert s["valori"]["_info"]["masse_g"] == {"tubo": 10.0, "rotore": 3.0, "statore": 2.0, "totale": 15.0}
    assert n["valori"]["_info"]["masse_g"]["totale"] == 12.0
    dati = cli.dati_dimensionamento(n)
    assert dati["variante"] == "NoStatore" and dati["L_disk_m"] == pytest.approx(0.026) and dati["masse_g"]["tubo"] == 9.0
    assert set(n["fonti"]) == {k for k in n["valori"] if not k.startswith("_")}          # le aggiunte non sono grandezze importate
    v = _cfg(tmp_path, "esempio")["DIMENSIONAMENTO"]
    assert v["variante"] is None and v["valori"]["_info"]["L_disk_m"] is None and v["valori"]["_info"]["masse_g"] is None


def test_catene_danno_gli_stessi_dati_di_progetto(tmp_path):
    e = _cfg(tmp_path, "esempio")
    s = _cfg(tmp_path, "esempio_varianti", indice=0)
    assert s["CORPO"]["massa_kg"] == e["CORPO"]["massa_kg"] and s["ATTUATORE"]["tempo_salita_90_s"] == e["ATTUATORE"]["tempo_salita_90_s"]


# ---------------------------------------------------------------- --elenca
def test_elenca(tmp_path, capsys):
    p = _input(tmp_path, "serie_esempio__v1")
    assert cli.main(["--input", p, "--radice-dimensionamento", DIM, "--elenca"]) == 0
    out = capsys.readouterr().out
    assert "Catene trovate: 3" in out
    for et in ("massa_a/Statore", "massa_a/NoStatore", "massa_b"):
        assert et in out
    ris = tmp_path / "ris" / "serie_esempio__v1"
    assert os.path.join(str(ris), "massa_a", "NoStatore") in out and os.path.join(str(ris), "massa_b") in out
    assert not (tmp_path / "ris").exists()                                      # non simula e non scrive nulla


def test_elenca_caso_senza_varianti_e_piatto(tmp_path, capsys):
    cli.main(["--input", _input(tmp_path, "esempio__x"), "--radice-dimensionamento", DIM, "--elenca"])
    out = capsys.readouterr().out
    assert "Catene trovate: 1" in out and "struttura piatta" in out and os.path.join(str(tmp_path / "ris"), "esempio__x") in out


def test_elenca_nome_con_serie_e_slash(tmp_path, capsys):
    cli.main(["--input", _input(tmp_path, "serie_esempio/massa_a/NoStatore"), "--radice-dimensionamento", DIM, "--elenca"])
    out = capsys.readouterr().out
    assert "Catene trovate: 1" in out and os.path.join(str(tmp_path / "ris"), "serie_esempio-massa_a-NoStatore", "massa_a", "NoStatore") in out


def test_elenca_errore_chiaro(tmp_path, capsys):
    assert cli.main(["--input", _input(tmp_path, "non_esiste"), "--radice-dimensionamento", DIM, "--elenca"]) == 1
    assert "Casi disponibili" in capsys.readouterr().out


# ---------------------------------------------------------------- uscite con più catene
def test_pianificazione_cartelle(tmp_path):
    base = cli.leggi_input(_input(tmp_path, "serie_esempio__v1"))
    _, nome, piatto, piano = cli.pianifica(base, cli.trova_catene(base, DIM))
    assert nome == "serie_esempio__v1" and not piatto
    cart = str(tmp_path / "ris" / "serie_esempio__v1")
    assert [out for _, out in piano] == [os.path.join(cart, "massa_a", "Statore"), os.path.join(cart, "massa_a", "NoStatore"),
                                         os.path.join(cart, "massa_b")]
    base = cli.leggi_input(_input(tmp_path, "esempio__x"))
    assert cli.pianifica(base, cli.trova_catene(base, DIM))[2] is True


def test_run_con_due_catene(tmp_path, monkeypatch):
    chiamate = []

    def finto(radice_out, catene):
        chiamate.append((radice_out, copy.deepcopy(catene)))
        return []

    monkeypatch.setitem(sys.modules, "dinamica_designer.confronto_catene", types.SimpleNamespace(scrivi_confronto_catene=finto))
    p = _input(tmp_path, "esempio_varianti__v1", extra=(("attivo", False),))       # solo ISS
    cart = cli.run(p, radice_dimensionamento=DIM)
    assert os.path.basename(cart) == "esempio_varianti__v1"
    for v in ("Statore", "NoStatore"):
        for f in ("CONFRONTO.md", "dati_dimensionamento.json", "Pale/PALE.md", "ISS/00_sintesi/riepilogo.json",
                  "ISS/00_sintesi/RISULTATO.md", "ISS/02_dati/serie_temporali.csv"):
            assert os.path.isfile(os.path.join(cart, v, f)), f"{v}/{f}"
    for f in ("caso.json", "input_usato.py", "log.txt"):
        assert os.path.isfile(os.path.join(cart, f))
    assert not os.path.exists(os.path.join(cart, "ISS")) and not os.path.exists(os.path.join(cart, "Pale"))
    assert _leggi(os.path.join(cart, "caso.json"))["catene"] == ["Statore", "NoStatore"]
    dati = _leggi(os.path.join(cart, "NoStatore", "dati_dimensionamento.json"))
    assert dati["variante"] == "NoStatore" and dati["etichetta"] == "NoStatore" and dati["L_disk_m"] == pytest.approx(0.026)
    assert dati["masse_g"]["totale"] == 12.0 and "valori" in dati and "fonti" in dati
    # contratto con il confronto fra le catene
    (radice_out, catene), = chiamate
    assert radice_out == cart and [c["etichetta"] for c in catene] == ["Statore", "NoStatore"]
    assert [c["stato"] for c in catene] == ["ok", "ok"] and [c["variante"] for c in catene] == ["Statore", "NoStatore"]
    assert catene[1]["cartella_out"] == os.path.join(cart, "NoStatore") and catene[1]["dati"]["variante"] == "NoStatore"
    assert os.path.isfile(os.path.join(catene[0]["cartella_out"], "ISS", "00_sintesi", "riepilogo.json"))
    # la coppia residua dei rotori è quella vera: nulla con lo statore, maggiore senza
    c_s = _leggi(os.path.join(cart, "Statore", "ISS", "00_sintesi", "riepilogo.json"))["ruote"]
    c_n = _leggi(os.path.join(cart, "NoStatore", "ISS", "00_sintesi", "riepilogo.json"))["ruote"]
    assert c_s != c_n


def test_catena_che_fallisce_non_ferma_le_altre(tmp_path, monkeypatch):
    radice = _copia(tmp_path)
    os.remove(os.path.join(radice, "esempio_varianti", "NoStatore", "3_ventola", "00_sintesi", "report.json"))
    chiamate = []
    monkeypatch.setitem(sys.modules, "dinamica_designer.confronto_catene",
                        types.SimpleNamespace(scrivi_confronto_catene=lambda r, c: chiamate.append(c) or []))
    cart = cli.run(_input(tmp_path, "esempio_varianti__f", extra=(("attivo", False),)), radice_dimensionamento=radice)
    assert os.path.isfile(os.path.join(cart, "Statore", "ISS", "00_sintesi", "riepilogo.json"))
    assert not os.path.exists(os.path.join(cart, "NoStatore", "ISS", "00_sintesi", "riepilogo.json"))
    s, n = chiamate[0]
    assert s["stato"] == "ok" and n["stato"].startswith("importazione fallita") and "report.json" in n["stato"] and n["dati"] is None
    assert "catena NoStatore: importazione fallita" in open(os.path.join(cart, "log.txt"), encoding="utf-8").read()


def test_confronto_catene_assente_avvisa_e_non_ferma(tmp_path, monkeypatch):
    def rotto(*a):
        raise RuntimeError("prova")

    monkeypatch.setitem(sys.modules, "dinamica_designer.confronto_catene", types.SimpleNamespace(scrivi_confronto_catene=rotto))
    cart = cli.run(_input(tmp_path, "esempio_varianti__w", extra=(("attivo", False),)), radice_dimensionamento=DIM)
    assert "confronto tra le catene non scritto" in open(os.path.join(cart, "log.txt"), encoding="utf-8").read()


def test_pulizia_passando_da_due_catene_a_una(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "dinamica_designer.confronto_catene", types.SimpleNamespace(scrivi_confronto_catene=lambda r, c: []))
    cart = cli.run(_input(tmp_path, "esempio_varianti__p", extra=(("attivo", False),)), radice_dimensionamento=DIM)
    assert os.path.isdir(os.path.join(cart, "Statore", "ISS")) and os.path.isdir(os.path.join(cart, "NoStatore", "ISS"))
    with pytest.raises(ValueError, match="altri input"):                     # l'insieme delle catene cambia l'impronta
        cli.run(_input(tmp_path, "esempio_varianti__p", ["NoStatore"], extra=(("attivo", False),)), radice_dimensionamento=DIM)
    cart = cli.run(_input(tmp_path, "esempio_varianti__p", ["NoStatore"], extra=(("attivo", False), ("sovrascrivi", True))),
                   radice_dimensionamento=DIM)
    assert os.path.isfile(os.path.join(cart, "NoStatore", "ISS", "00_sintesi", "riepilogo.json"))
    assert not os.path.exists(os.path.join(cart, "Statore"))
    assert _leggi(os.path.join(cart, "caso.json"))["catene"] == ["NoStatore"]


def test_caso_senza_varianti_resta_piatto(tmp_path):
    cart = cli.run(_input(tmp_path, "esempio__piatto", extra=(("attivo", False),)), radice_dimensionamento=DIM)
    assert os.path.isfile(os.path.join(cart, "ISS", "00_sintesi", "riepilogo.json")) and os.path.isfile(os.path.join(cart, "CONFRONTO.md"))
    assert _leggi(os.path.join(cart, "caso.json"))["catene"] == []
    assert _leggi(os.path.join(cart, "dati_dimensionamento.json"))["caso"] == "esempio"
