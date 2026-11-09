"""Excel di confronto: tutto ciò che lo script calcola, con pesi modificabili.

Convenzioni: testo blu = valore modificabile (pesi); nero = valore calcolato
dallo script; sfondo grigio chiaro = formula del foglio.  Il punteggio
totale e la posizione in classifica sono formule: cambiando i pesi nel foglio
Classifica la classifica si aggiorna senza rilanciare lo script.
"""
import math
import os
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as COL
from openpyxl.worksheet.table import Table

FONT = "Arial"
F_TIT = Font(name=FONT, size=14, bold=True)
F_SOT = Font(name=FONT, size=10, italic=True, color="555555")
F_H = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_N = Font(name=FONT, size=10)
F_IN = Font(name=FONT, size=10, color="0000FF", bold=True)
F_B = Font(name=FONT, size=10, bold=True)
FILL_H = PatternFill("solid", fgColor="1F4E79")
FILL_F = PatternFill("solid", fgColor="F2F2F2")
FILL_OK = PatternFill("solid", fgColor="D3F9D8")
FILL_NO = PatternFill("solid", fgColor="FFE3E3")
FILL_IN = PatternFill("solid", fgColor="FFF9DB")
SOTT = Border(bottom=Side(style="thin", color="BBBBBB"))


def _v(x):
    """Valore scrivibile in cella."""
    if x is None:
        return "—"
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    if isinstance(x, float):
        if math.isinf(x) or math.isnan(x):
            return "—"
        return x
    if isinstance(x, (list, tuple)):
        return ", ".join(str(_v(i)) for i in x)
    if isinstance(x, dict):
        return "; ".join(f"{k}: {_v(v)}" for k, v in x.items())
    return x


def _intest(ws, riga, titoli, col0=1):
    for j, t in enumerate(titoli):
        c = ws.cell(riga, col0 + j, t)
        c.font, c.fill = F_H, FILL_H
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.row_dimensions[riga].height = 32


def _titolo(ws, testo, sotto=None):
    ws["A1"] = testo
    ws["A1"].font = F_TIT
    if sotto:
        ws["A2"] = sotto
        ws["A2"].font = F_SOT


def _larghezze(ws, larg):
    for j, w in enumerate(larg, start=1):
        ws.column_dimensions[COL(j)].width = w


def _cella(ws, r, c, val, fmt=None, font=F_N, fill=None):
    cell = ws.cell(r, c, _v(val))
    cell.font = font
    if fmt:
        cell.number_format = fmt
    if fill:
        cell.fill = fill
    return cell


def scrivi(percorso, risultati, cfg, scenari, info, grafici):
    wb = Workbook()
    _leggimi(wb.active, cfg, info)
    _classifica(wb.create_sheet("Classifica"), risultati, cfg)
    _ottimi(wb.create_sheet("Progetto ottimo"), risultati, cfg)
    _fluido(wb.create_sheet("Fluidodinamica"), risultati)
    _perdite(wb.create_sheet("Perdite"), risultati)
    _spazio(wb.create_sheet("Spazio interno"), risultati, cfg)
    _controllo(wb.create_sheet("Controllo e dinamica"), risultati, cfg)
    _struttura(wb.create_sheet("Struttura"), risultati, cfg)
    _massa(wb.create_sheet("Massa"), risultati, cfg)
    _realizz(wb.create_sheet("Realizzabilità"), risultati)
    _ingestione(wb.create_sheet("Ingestione getti"), risultati, cfg)
    _tutti(wb.create_sheet("Tutti i progetti"), risultati)
    _database(wb.create_sheet("Database scenari"), scenari)
    _ipotesi(wb.create_sheet("Ipotesi e fonti"), cfg)
    _grafici(wb.create_sheet("Grafici"), grafici, os.path.dirname(os.path.dirname(percorso)))
    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
        ws.freeze_panes = ws.freeze_panes or None
    wb.save(percorso)


# ----------------------------------------------------------------------------
def _leggimi(ws, cfg, info):
    ws.title = "Leggimi"
    _titolo(ws, "COMPANION — confronto delle configurazioni dei condotti",
            "File generato automaticamente dalle run: non modificare a mano i valori calcolati.")
    righe = [
        ("Esecuzione", info["cartella"]),
        ("Data", info["data"]),
        ("Impronta degli input", info["impronta"]),
        ("Ambiente di progetto", f"{cfg['ambiente_progetto']} — {cfg['ambienti'][cfg['ambiente_progetto']]['descrizione']}"),
        ("Spinta richiesta per asse (N)", round(cfg["missione"]["spinta_per_asse_N"], 3)),
        ("Origine della spinta", cfg["missione"]["origine_spinta"]),
        ("Massa per dimensionare la spinta (kg)", cfg["missione"]["massa_per_spinta_kg"]),
        ("Massa obiettivo (kg)", cfg["missione"]["massa_obiettivo_kg"]),
        ("Massa massima ammessa (kg)", cfg["missione"]["massa_massima_kg"]),
        ("Lato del cubo: intervallo analizzato (mm)",
         f"{cfg['geometria']['lato_cubo_min_mm']:.0f} - {cfg['geometria']['lato_cubo_max_mm']:.0f}, "
         f"passo {cfg['geometria']['lato_cubo_passo_mm']:.0f} ({len(cfg['lati_cubo_mm'])} lati). "
         f"Il lato ottimo di ogni scenario è nel foglio Classifica."),
        ("Tensione del bus (V)", cfg["elettrico"]["tensione_bus_V"]),
        ("", ""),
        ("COME SI LEGGE", ""),
        ("Classifica", "Punteggi per criterio, totale pesato e posizione. I pesi (blu, sfondo giallo) si cambiano qui: totale e posizione sono formule."),
        ("Progetto ottimo", "Tutti i numeri del miglior progetto di ogni scenario, con unità."),
        ("Fluidodinamica / Perdite", "Punto di funzionamento della ventola e ripartizione della potenza."),
        ("Spazio interno", "Volume dei condotti, volume libero, collocazione di batteria, ruote, avionica, ESC."),
        ("Controllo e dinamica", "Forze e momenti disponibili, guasti, salita della spinta, margine di fase, ruote di reazione."),
        ("Struttura", "Frequenze, Campbell, instabilità, sforzi a 1,8 g e 9 g, rigidezza."),
        ("Massa", "Bilancio di massa: guscio, telaio, condotti, staffe, bocche, propulsione, componenti; confronto con obiettivo e massima."),
        ("Realizzabilità", "Parti, curve, attuatori, stampa."),
        ("Ingestione getti", "Indice di riaspirazione per ogni comando su più assi."),
        ("Tutti i progetti", "Ogni combinazione valutata dall'ottimizzatore, anche le scartate."),
        ("Scenari", "Descrizione e parametri degli scenari confrontati (da INPUT.py)."),
        ("Ipotesi e fonti", "Correlazioni usate, campo di validità, valori segnaposto."),
        ("", ""),
        ("LEGENDA", ""),
        ("Testo blu su giallo", "Valore modificabile (pesi della classifica)."),
        ("Sfondo grigio", "Formula del foglio."),
        ("Verde / rosso", "Progetto ammissibile / con violazioni."),
    ]
    for i, (a, b) in enumerate(righe, start=4):
        _cella(ws, i, 1, a, font=F_B if b == "" or a.isupper() else F_N)
        _cella(ws, i, 2, b)
        ws.cell(i, 2).alignment = Alignment(wrap_text=True, vertical="top")
    _larghezze(ws, [30, 110])


def _ottimi_lista(risultati):
    return [r for r in risultati if r["ottimo"].get("completo")]


def _classifica(ws, risultati, cfg):
    _titolo(ws, "Classifica dei progetti ottimi",
            "Cambia i pesi nelle celle gialle: totale e posizione si ricalcolano. Posizione solo tra gli ammissibili.")
    crit = list(cfg["ottimizzazione"]["pesi"].keys())
    _cella(ws, 4, 1, "Pesi dei criteri", font=F_B)
    for j, c in enumerate(crit):
        _cella(ws, 4, 4 + j, c, font=F_B)
        _cella(ws, 5, 4 + j, cfg["ottimizzazione"]["pesi"][c], "0.00", F_IN, FILL_IN)
    _cella(ws, 5, 1, "← valori da INPUT.py, modificabili qui")
    tit = (["Scenario", "Nome", "Ammissibile"] + [f"punteggio {c}" for c in crit] +
           ["Totale pesato", "Posizione", "Violazioni | avvisi", "D (mm)", "σ ugello", "Tipo di ventola", "Motore",
            "Potenza per asse (W)", "Libero dopo i componenti", "Massa totale stimata (kg)",
            "Lato cubo OTTIMO (mm)"])
    _intest(ws, 7, tit)
    ott = [r for r in risultati]
    r0 = 8
    n = len(ott)
    for i, r in enumerate(ott):
        row = r0 + i
        o = r["ottimo"]
        c = o.get("completo")
        _cella(ws, row, 1, r["scenario"]["id"], font=F_B)
        _cella(ws, row, 2, r["scenario"]["nome"])
        amm = bool(c and c["ammissibile"])
        _cella(ws, row, 3, "sì" if amm else "no", fill=FILL_OK if amm else FILL_NO)
        for j, k in enumerate(crit):
            _cella(ws, row, 4 + j, c["punteggi"][k] if c else 0.0, "0.000")
        jt = 4 + len(crit)
        rng_w = f"${COL(4)}$5:${COL(3 + len(crit))}$5"
        rng_s = f"{COL(4)}{row}:{COL(3 + len(crit))}{row}"
        _cella(ws, row, jt, f"=SUMPRODUCT({rng_w},{rng_s})/SUM({rng_w})", "0.000", F_B, FILL_F)
        colT = COL(jt)
        _cella(ws, row, jt + 1,
               f'=IF(C{row}="sì",1+COUNTIFS($C${r0}:$C${r0 + n - 1},"sì",${colT}${r0}:${colT}${r0 + n - 1},">"&{colT}{row}),"—")',
               "0", F_B, FILL_F)
        testo = "; ".join(c["violazioni"]) if c else "nessun progetto completo"
        if c and c.get("avvisi"):
            testo += (" | " if testo else "") + "Avvisi: " + "; ".join(c["avvisi"])
        _cella(ws, row, jt + 2, testo)
        ws.cell(row, jt + 2).alignment = Alignment(wrap_text=True, vertical="top")
        _cella(ws, row, jt + 3, o["D"], "0")
        if c:
            _cella(ws, row, jt + 4, c["sigma"], "0.00")
            _cella(ws, row, jt + 5, c["tipo_ventola"])
            _cella(ws, row, jt + 6, c["motore"])
            _cella(ws, row, jt + 7, o["aero"]["P_asse_max"], "0.0")
            _cella(ws, row, jt + 9, c["massa_totale_kg"], "0.00")
        _cella(ws, row, jt + 8, o["geometria"]["frazione_libera_dopo"], "0.0%")
        _cella(ws, row, jt + 10, o["L"], "0", F_B)
    _larghezze(ws, [22, 46, 12] + [12] * len(crit) + [12, 10, 50, 8, 8, 22, 14, 12, 12, 12, 14])
    ws.freeze_panes = "B8"
    rnote = r0 + n + 2
    note = ["Come sono costruiti i punteggi (0-1):",
            "spazio: volume libero dopo i componenti, scalato tra i valori di OTTIMIZZAZIONE['scala_volume_libero']; ×0,3 se un componente non entra.",
            "perdite: 70 % potenza elettrica per asse (scala in input) + 30 % quota di potenza utile NON persa nel condotto.",
            "semplicita: punteggio di realizzabilità (parti, curve, attuatori, stampa).",
            "robustezza: forza residua con una ventola guasta / forza richiesta.",
            "dinamica: 40 % tempo di cambio di verso della spinta, 40 % indice d'ingestione, 20 % tempo di desaturazione.",
            "massa: massa totale stimata; 1 all'obiettivo (o sotto), 0 alla massa massima ammessa."]
    for i, t in enumerate(note):
        _cella(ws, rnote + i, 1, t, font=F_B if i == 0 else F_N)


def _metriche_ottimo(r, cfg):
    o = r["ottimo"]
    g = o["geometria"]
    c = o.get("completo") or {}
    a = o.get("aero") or {}
    cl = max(a["classi"], key=lambda x: x["P_el"]) if a else {}
    rw = c.get("ruote", {})
    car = g["realizzabilita"]
    return [
        ("GEOMETRIA", None, None, None),
        ("Lato del cubo OTTIMO", o["L"], "mm", "0"),
        ("Diametro del condotto alla ventola", o["D"], "mm", "0"),
        ("Variante geometrica", o["variante"] or "—", "", None),
        ("Numero di ventole (unità)", len(g["layout"].unita), "", "0"),
        ("Gioco minimo tra condotti", g["gioco_min_mm"], "mm", "0.0"),
        ("Volume dei condotti", g["frazione_condotti"], "% interno", "0.0%"),
        ("Volume libero prima dei componenti", g["frazione_libera_prima"], "% interno", "0.0%"),
        ("Volume libero dopo i componenti", g["frazione_libera_dopo"], "% interno", "0.0%"),
        ("Componenti tutti collocati", "sì" if g["componenti_tutti"] else "no", "", None),
        ("Lato del più grande cubo libero", g["cubo_libero_mm"], "mm", "0"),
        ("Diametro della più grande sfera libera", g["sfera_libera_mm"], "mm", "0"),
        ("FLUIDODINAMICA (unità più impegnata)", None, None, None),
        ("Tipo di ventola", c.get("tipo_ventola"), "", None),
        ("Motore", c.get("motore"), "", None),
        ("Rapporto d'area dell'ugello σ", c.get("sigma"), "", "0.00"),
        ("Spinta richiesta per unità", cl.get("F_unita"), "N", "0.000"),
        ("Unità per verso", cl.get("n_per_verso"), "", "0"),
        ("Giri di progetto", cl.get("N_req"), "giri/min", "#,##0"),
        ("Giri massimi ammessi", cl.get("N_lim"), "giri/min", "#,##0"),
        ("Portata", (cl.get("Q") or 0) * 1000, "L/s", "0.00"),
        ("Velocità del getto (prima uscita)", (cl.get("v_uscita") or [None])[0], "m/s", "0.0"),
        ("Salto di pressione utile della ventola", cl.get("dp_ventola"), "Pa", "0"),
        ("Coefficiente di flusso φ", cl.get("phi"), "", "0.000"),
        ("Coefficiente di pressione ψ", cl.get("psi"), "", "0.000"),
        ("Rendimento della ventola", cl.get("eta"), "", "0.00"),
        ("Reynolds della pala", cl.get("Re_pala"), "", "#,##0"),
        ("Mach di punta", cl.get("Mach_punta"), "", "0.000"),
        ("Rapporto mozzo/punta", cl.get("nu_mozzo"), "", "0.00"),
        ("Zona di stallo", "sì" if cl.get("stallo") else "no", "", None),
        ("Quota di potenza utile persa nel condotto", cl.get("frazione_perdite"), "", "0.0%"),
        ("Potenza all'albero per unità", cl.get("P_albero"), "W", "0.0"),
        ("Potenza elettrica per unità", cl.get("P_el"), "W", "0.0"),
        ("Corrente per unità", cl.get("I"), "A", "0.00"),
        ("Tensione richiesta al motore", cl.get("V"), "V", "0.0"),
        ("Potenza elettrica per asse (caso peggiore)", a.get("P_asse_max"), "W", "0.0"),
        ("Potenza di picco con 3 assi", a.get("P_picco_3assi"), "W", "0"),
        ("Corrente di picco con 3 assi", a.get("I_picco"), "A", "0.0"),
        ("CONTROLLO E DINAMICA", None, None, None),
        ("Forza pura minima sui 6 versi", min(c["forza_max_N"].values()) if c else None, "N", "0.00"),
        ("Momento puro minimo sui 3 assi", min(c["momento_max_Nm"].values()) if c else None, "N·m", "0.000"),
        ("Forza residua con 1 ventola guasta / richiesta", c.get("tolleranza_guasto"), "", "0.00"),
        ("Indice d'ingestione peggiore", c.get("ingestione_peggiore"), "", "0.000"),
        ("Comandi con ingestione critica", len(c.get("comandi_critici", [])) if c else None, "", "0"),
        ("Tempo di salita al 90 % della spinta", c.get("t_salita_90"), "s", "0.000"),
        ("Tempo di cambio di verso della spinta", c.get("t_cambio_verso"), "s", "0.000"),
        ("Margine di fase a ω_c = 2 rad/s", (c.get("margine_fase") or {}).get(2.0), "°", "0.0"),
        ("Momento accumulato dalle ruote nella finestra", rw.get("H_finestra"), "N·m·s", "0.000"),
        ("Quota della capacità della ruota", rw.get("quota_ruota"), "", "0.0%"),
        ("Tempo per desaturare la ruota", c.get("t_desaturazione"), "s", "0.0"),
        ("STRUTTURA", None, None, None),
        ("1° frequenza del tratto con la ventola", c.get("f1_Hz"), "Hz", "0"),
        ("Risonanze attraversate (Campbell)", c.get("risonanze_campbell") and
         ", ".join(f"{n} a {N:,.0f} giri/min".replace(",", ".") for n, N in c["risonanze_campbell"]) or "nessuna", "", None),
        ("Margine d'instabilità a pressione esterna", c.get("margine_instabilita"), "", "0"),
        ("Sforzo al supporto della ventola a 9 g", c.get("sforzo_9g_MPa"), "MPa", "0.00"),
        ("Rigidezza flessionale portata dai condotti", sum(c["EI_condotti_Nm2"]) if c else None, "N·m²", "0.0"),
        ("Assi a piena spinta sostenibili dal pacco", c.get("assi_pieni_ammessi"), "", "0"),
        ("Avvisi (non bloccanti)", "; ".join(c.get("avvisi", [])) or "nessuno", "", None),
        ("MASSA (stima)", None, None, None),
        ("Massa totale stimata", c.get("massa_totale_kg"), "kg", "0.00"),
        ("di cui dipendente dalla configurazione", c.get("massa_configurazione_kg"), "kg", "0.00"),
        ("Telaio e guscio", (c.get("massa") or {}).get("gruppi", {}).get("telaio e guscio"), "kg", "0.00"),
        ("Condotti e supporti", (c.get("massa") or {}).get("gruppi", {}).get("condotti e supporti"), "kg", "0.00"),
        ("Propulsione (motori, ESC, cavi)", (c.get("massa") or {}).get("gruppi", {}).get("propulsione (motori, ESC, cavi)"), "kg", "0.00"),
        ("Spinta richiesta con la massa stimata", c.get("spinta_richiesta_massa_stimata_N"), "N", "0.000"),
        ("Forza pura disponibile / richiesta con la massa stimata", c.get("margine_spinta_massa_stimata"), "", "0.00"),
        ("REALIZZABILITÀ", None, None, None),
        ("Parti stampate", car["parti"], "", "0"),
        ("Curve", car["curve"], "", "0"),
        ("Raggio di curva minimo / D", car["R_su_D_minimo"], "", "0.00"),
        ("Attuatori (motori)", car["attuatori"], "", "0"),
        ("Lunghezza totale dei condotti", car["lunghezza_condotti_mm"], "mm", "0"),
        ("Condotti più lunghi del piatto di stampa", car["condotti_oltre_piatto"], "", "0"),
        ("Tipi di pezzo diversi", car["tipi_di_pezzo_diversi"], "", "0"),
    ]


def _ottimi(ws, risultati, cfg):
    _titolo(ws, "Progetto ottimo di ogni scenario", "Una colonna per scenario. Le righe in grigio sono formule.")
    _intest(ws, 4, ["Grandezza", "Unità"] + [r["scenario"]["id"] for r in risultati])
    tabelle = [_metriche_ottimo(r, cfg) for r in risultati]
    riga_idx = {}
    for i, voce in enumerate(tabelle[0]):
        row = 5 + i
        nome, _, unita, fmt = voce
        if unita is None:
            _cella(ws, row, 1, nome, font=F_B)
            continue
        _cella(ws, row, 1, nome)
        _cella(ws, row, 2, unita)
        riga_idx[nome] = row
        for j, t in enumerate(tabelle):
            _cella(ws, row, 3 + j, t[i][1], fmt)
    row = 5 + len(tabelle[0]) + 1
    _cella(ws, row, 1, "GRANDEZZE DERIVATE (formule)", font=F_B)
    F = cfg["missione"]["spinta_per_asse_N"]
    rP = riga_idx["Potenza elettrica per asse (caso peggiore)"]
    rQ = riga_idx["Potenza utile per asse"] if "Potenza utile per asse" in riga_idx else None
    _cella(ws, row + 1, 1, "Spinta per asse / potenza elettrica per asse")
    _cella(ws, row + 1, 2, "N/kW")
    _cella(ws, row + 2, 1, "Energia per una parabola con 3 assi pieni (22 s)")
    _cella(ws, row + 2, 2, "Wh")
    rpk = riga_idx["Potenza di picco con 3 assi"]
    for j in range(len(tabelle)):
        cl = COL(3 + j)
        _cella(ws, row + 1, 3 + j, f'=IFERROR({F:.6f}/{cl}{rP}*1000,"—")', "0.0", fill=FILL_F)
        _cella(ws, row + 2, 3 + j, f'=IFERROR({cl}{rpk}*{cfg["missione"]["durata_microgravita_s"]}/3600,"—")',
               "0.00", fill=FILL_F)
    _larghezze(ws, [48, 12] + [20] * len(tabelle))
    ws.freeze_panes = "C5"


def _fluido(ws, risultati):
    _titolo(ws, "Punto di funzionamento per classe di unità (progetto ottimo)",
            "Una classe = unità con condotto geometricamente uguale (per simmetria hanno le stesse prestazioni).")
    tit = ["Scenario", "Unità della classe", "Asse", "Spinta per unità (N)", "Giri (giri/min)", "Giri max",
           "Limite giri da tensione", "Limite da Mach", "Limite da velocità di punta", "Portata (L/s)",
           "Velocità getto (m/s)", "Δp ventola (Pa)", "φ", "ψ", "η ventola", "Re pala", "Mach punta",
           "Mozzo/punta", "Stallo", "P albero (W)", "P getto (W)", "P perdite (W)", "Quota perdite",
           "P elettrica (W)", "Corrente (A)", "Tensione (V)", "Duty", "η motore", "Coppia rotore (N·m)",
           "Coppia sul corpo (N·m)"]
    _intest(ws, 4, tit)
    row = 5
    for r in _ottimi_lista(risultati):
        for c in r["ottimo"]["aero"]["classi"]:
            vals = [r["scenario"]["id"], " ".join(c["unita"]), "XYZ"[c["asse"]], c["F_unita"], c["N_req"], c["N_lim"],
                    c["limiti_N"]["tensione"], c["limiti_N"]["mach"], c["limiti_N"]["velocita_punta"], c["Q"] * 1000,
                    c["v_uscita"][0], c["dp_ventola"], c["phi"], c["psi"], c["eta"], c["Re_pala"], c["Mach_punta"],
                    c["nu_mozzo"], "sì" if c["stallo"] else "no", c["P_albero"], c["P_getto"], c["P_perdite"],
                    c["frazione_perdite"], c["P_el"], c["I"], c["V"], c["duty"], c["eta_motore"],
                    c["coppia_rotore"], c["coppia_corpo"]]
            fmts = [None, None, None, "0.000", "#,##0", "#,##0", "#,##0", "#,##0", "#,##0", "0.00", "0.0", "0",
                    "0.000", "0.000", "0.00", "#,##0", "0.000", "0.00", None, "0.0", "0.0", "0.0", "0.0%", "0.0",
                    "0.00", "0.0", "0.00", "0.00", "0.0000", "0.0000"]
            for j, (v, f) in enumerate(zip(vals, fmts)):
                _cella(ws, row, 1 + j, v, f)
            row += 1
    _larghezze(ws, [20, 40] + [11] * (len(tit) - 2))
    ws.freeze_panes = "C5"


def _perdite(ws, risultati):
    _titolo(ws, "Ripartizione della potenza utile delle ventole, per asse (progetto ottimo)",
            "Potenze in W; le percentuali sono formule.  Energia del getto = parte che produce spinta.")
    cats = ["griglie", "imbocco", "attrito", "curve", "effetto di sistema", "ugello", "energia del getto"]
    _intest(ws, 4, ["Scenario"] + [f"{c} (W)" for c in cats] + ["Totale (W)"] + [f"{c} (%)" for c in cats])
    row = 5
    for r in _ottimi_lista(risultati):
        c0 = max(r["ottimo"]["aero"]["classi"], key=lambda x: x["P_el"])
        n = c0["n_per_verso"]
        _cella(ws, row, 1, r["scenario"]["id"], font=F_B)
        for j, k in enumerate(cats):
            v = c0["P_getto"] * n if k == "energia del getto" else c0["perdite_W"].get(k, 0.0) * n
            _cella(ws, row, 2 + j, v, "0.00")
        jt = 2 + len(cats)
        _cella(ws, row, jt, f"=SUM({COL(2)}{row}:{COL(jt - 1)}{row})", "0.0", F_B, FILL_F)
        for j in range(len(cats)):
            _cella(ws, row, jt + 1 + j, f"=IFERROR({COL(2 + j)}{row}/{COL(jt)}{row},0)", "0.0%", fill=FILL_F)
        row += 1
    _larghezze(ws, [22] + [12] * (2 * len(cats) + 1))


def _spazio(ws, risultati, cfg):
    _titolo(ws, "Spazio interno e collocazione dei componenti (progetto ottimo)",
            "Coordinate in mm rispetto al centro del cubo (X destra, Y fronte, Z alto).")
    _intest(ws, 4, ["Scenario", "Lato cubo (mm)", "D (mm)", "Condotti", "Volumetti tolti ai vertici", "Libero prima", "Libero dopo",
                    "Cubo libero (mm)", "Sfera libera (mm)", "Gioco minimo (mm)", "Coppia più vicina",
                    "Sovrapposizioni con moduli (cm³)", "Bocche in zone centrali"])
    row = 5
    for r in risultati:
        g = r["ottimo"]["geometria"]
        vals = [r["scenario"]["id"], g["layout"].L, g["D"], g["frazione_condotti"], g["frazione_extra"], g["frazione_libera_prima"],
                g["frazione_libera_dopo"], g["cubo_libero_mm"], g["sfera_libera_mm"], g["gioco_min_mm"],
                g["coppia_critica"], g["sovrapposizioni_zone_cm3"] or "nessuna", g["bocche_in_zone_centrali"] or "nessuna"]
        fm = [None, "0", "0", "0.0%", "0.0%", "0.0%", "0.0%", "0", "0", "0.0", None, None, None]
        for j, (v, f) in enumerate(zip(vals, fm)):
            _cella(ws, row, 1 + j, v, f)
        row += 1
    row += 2
    _cella(ws, row, 1, "Collocazione dei componenti", font=F_B)
    row += 1
    _intest(ws, row, ["Scenario", "Componente", "Dimensioni (mm)", "Collocato", "min X", "min Y", "min Z",
                      "max X", "max Y", "max Z"])
    row += 1
    for r in risultati:
        g = r["ottimo"]["geometria"]
        for nome, box in g["componenti"].items():
            dims = cfg["componenti"][nome]["dim"] if cfg["componenti"][nome]["dim"] else "dal numero di motori"
            vals = [r["scenario"]["id"], nome, dims, "sì" if box is not None else "NO"]
            vals += list(box[0]) + list(box[1]) if box is not None else ["—"] * 6
            for j, v in enumerate(vals):
                _cella(ws, row, 1 + j, v, "0" if j >= 4 else None,
                       fill=(FILL_NO if box is None and j == 3 else None))
            row += 1
    _larghezze(ws, [22, 34, 18, 12, 10, 10, 10, 10, 10, 10, 34, 34, 20])


def _controllo(ws, risultati, cfg):
    _titolo(ws, "Autorità di controllo, guasti, dinamica, ruote di reazione (progetto ottimo)")
    dirs = ["+X", "-X", "+Y", "-Y", "+Z", "-Z"]
    tit = (["Scenario"] + [f"Forza {d} (N)" for d in dirs] + ["Mx (N·m)", "My (N·m)", "Mz (N·m)",
           "Forza residua con guasto / richiesta", "Guasto peggiore", "t salita 90 % (s)", "t inversione (s)",
           "t cambio verso (s)", "PM ω=1 (°)", "PM ω=2 (°)", "PM ω=4 (°)", "Braccio della spinta (m)",
           "Coppia baricentro (N·m)", "Coppia squilibrio (N·m)", "Coppia reazione rotori (N·m)",
           "Momento rotori in avvio (N·m·s)", "Momento in finestra (N·m·s)", "Quota ruota",
           "Coppia di desaturazione (N·m)", "t desaturazione (s)", "Inerzia rotore (kg·m²)"])
    _intest(ws, 4, tit)
    row = 5
    for r in _ottimi_lista(risultati):
        c = r["ottimo"]["completo"]
        rw = c["ruote"]
        vals = ([r["scenario"]["id"]] + [c["forza_max_N"][d] for d in dirs] +
                [c["momento_max_Nm"][k] for k in ("Mx", "My", "Mz")] +
                [c["tolleranza_guasto"], c["guasto_peggiore"], c["t_salita_90"], c["t_inversione"], c["t_cambio_verso"],
                 c["margine_fase"][1.0], c["margine_fase"][2.0], c["margine_fase"][4.0], c["braccio_spinta_m"],
                 rw["coppia_baricentro"], rw["coppia_squilibrio"], rw["coppia_reazione"], rw["H_rotori"],
                 rw["H_finestra"], rw["quota_ruota"], c["coppia_desaturazione"], c["t_desaturazione"], c["J_rotore"]])
        for j, v in enumerate(vals):
            f = "0.0%" if tit[j] == "Quota ruota" else ("0.00E+00" if "Inerzia" in tit[j] else "0.000")
            _cella(ws, row, 1 + j, v, f if j > 0 and not isinstance(_v(v), str) else None)
        row += 1
    _larghezze(ws, [22] + [12] * (len(tit) - 1))
    ws.freeze_panes = "B5"


def _struttura(ws, risultati, cfg):
    _titolo(ws, "Struttura dei condotti (progetto ottimo)",
            f"Materiale: {cfg['materiale_condotto']}; parete {cfg['geometria']['parete_condotto_mm']} mm.")
    tit = ["Scenario", "Campata con ventola (mm)", "1° frequenza (Hz)", "Risonanze attraversate", "Margine Campbell",
           "p critica (Pa)", "Suzione max (Pa)", "Margine instabilità", "Sforzo 1,8 g (MPa)", "Sforzo 9 g (MPa)",
           "Margine sforzo 9 g", "EI asse X (N·m²)", "EI asse Y (N·m²)", "EI asse Z (N·m²)"]
    _intest(ws, 4, tit)
    row = 5
    for r in _ottimi_lista(risultati):
        c = r["ottimo"]["completo"]
        vals = [r["scenario"]["id"], c["campata_ventola_mm"], c["f1_Hz"],
                ", ".join(f"{n} a {N:,.0f}".replace(",", ".") for n, N in c["risonanze_campbell"]) or "nessuna",
                c["margine_campbell"], c["p_critica_Pa"], c["suzione_max_Pa"], c["margine_instabilita"],
                c["sforzo_1_8g_MPa"], c["sforzo_9g_MPa"], c["margine_sforzo_9g"]] + list(c["EI_condotti_Nm2"])
        fm = [None, "0", "0", None, "0.00", "#,##0", "0", "0", "0.000", "0.000", "0", "0.0", "0.0", "0.0"]
        for j, (v, f) in enumerate(zip(vals, fm)):
            _cella(ws, row, 1 + j, v, f)
        row += 1
    _larghezze(ws, [22, 12, 12, 40] + [12] * 10)


def _massa(ws, risultati, cfg):
    mis = cfg["missione"]
    _titolo(ws, "Bilancio di massa (progetto ottimo)",
            f"Obiettivo {mis['massa_obiettivo_kg']:.2f} kg, massima ammessa {mis['massa_massima_kg']:.2f} kg. "
            "Stime parametriche: parametri nella sezione TELAIO di INPUT.py. Le righe in grigio sono formule.")
    ott = _ottimi_lista(risultati)
    if not ott:
        return
    _intest(ws, 4, ["Voce", "Unità"] + [r["scenario"]["id"] for r in ott])
    voci = list(ott[0]["ottimo"]["completo"]["massa"]["voci"].keys())
    for i, k in enumerate(voci):
        row = 5 + i
        _cella(ws, row, 1, k)
        _cella(ws, row, 2, "kg")
        for j, r in enumerate(ott):
            _cella(ws, row, 3 + j, r["ottimo"]["completo"]["massa"]["voci"][k], "0.000")
    r_tot = 5 + len(voci)
    r_ob, r_mx = r_tot + 1, r_tot + 2
    _cella(ws, r_tot, 1, "TOTALE", font=F_B)
    _cella(ws, r_ob, 1, "Scarto dall'obiettivo")
    _cella(ws, r_mx, 1, "Margine sulla massima ammessa")
    for rr in (r_tot, r_ob, r_mx):
        _cella(ws, rr, 2, "kg")
    for j in range(len(ott)):
        cl = COL(3 + j)
        _cella(ws, r_tot, 3 + j, f"=SUM({cl}5:{cl}{r_tot - 1})", "0.000", F_B, FILL_F)
        _cella(ws, r_ob, 3 + j, f"={cl}{r_tot}-{mis['massa_obiettivo_kg']}", "+0.000;-0.000", fill=FILL_F)
        _cella(ws, r_mx, 3 + j, f"={mis['massa_massima_kg']}-{cl}{r_tot}", "+0.000;-0.000", fill=FILL_F)
    row = r_mx + 2
    _cella(ws, row, 1, "Dettagli", font=F_B)
    det = list(ott[0]["ottimo"]["completo"]["massa"]["dettagli"].keys())
    for i, k in enumerate(det):
        _cella(ws, row + 1 + i, 1, k.replace("_", " "))
        for j, r in enumerate(ott):
            _cella(ws, row + 1 + i, 3 + j, r["ottimo"]["completo"]["massa"]["dettagli"][k], "0.00")
    row = row + len(det) + 3
    _cella(ws, row, 1, "Componenti fissi (uguali per tutti gli scenari)", font=F_B)
    for i, (k, v) in enumerate(ott[0]["ottimo"]["completo"]["massa"]["componenti"].items()):
        _cella(ws, row + 1 + i, 1, k)
        _cella(ws, row + 1 + i, 2, "kg")
        _cella(ws, row + 1 + i, 3, v, "0.000")
    _larghezze(ws, [44, 8] + [20] * len(ott))
    ws.freeze_panes = "C5"


def _realizz(ws, risultati):
    _titolo(ws, "Realizzabilità (progetto ottimo)")
    keys = ["parti", "curve", "R_su_D_minimo", "lunghezza_condotti_mm", "condotti_oltre_piatto",
            "pezzi_con_supporti", "tipi_di_pezzo_diversi", "motori", "attuatori", "prese", "uscite"]
    sub = ["parti", "curve", "attuatori", "stampa"]
    _intest(ws, 4, ["Scenario"] + keys + [f"sotto-punteggio {s}" for s in sub] + ["Punteggio realizzabilità"])
    row = 5
    for r in risultati:
        car = r["ottimo"]["geometria"]["realizzabilita"]
        c = r["ottimo"].get("completo")
        _cella(ws, row, 1, r["scenario"]["id"], font=F_B)
        for j, k in enumerate(keys):
            _cella(ws, row, 2 + j, car[k], "0.00" if k == "R_su_D_minimo" else "0")
        if c:
            for j, s in enumerate(sub):
                _cella(ws, row, 2 + len(keys) + j, c["sotto_realizzabilita"][s], "0.00")
            _cella(ws, row, 2 + len(keys) + len(sub), c["punteggi"]["semplicita"], "0.000", F_B)
        row += 1
    _larghezze(ws, [22] + [11] * (len(keys) + len(sub) + 1))


def _ingestione(ws, risultati, cfg):
    lim = cfg["limiti"]
    _titolo(ws, "Indice d'ingestione per comando (progetto ottimo)",
            f"Screening: < {lim['indice_ingestione_attenzione']} trascurabile, > {lim['indice_ingestione_critico']} probabile ingestione.")
    ott = _ottimi_lista(risultati)
    _intest(ws, 4, ["Comando"] + [r["scenario"]["id"] for r in ott] + ["coppia peggiore (getto → presa)"] * len(ott))
    if not ott:
        return
    comandi = list(ott[0]["ottimo"]["completo"]["ingestione_per_comando"].keys())
    for i, cmd in enumerate(comandi):
        row = 5 + i
        _cella(ws, row, 1, cmd)
        for j, r in enumerate(ott):
            d = r["ottimo"]["completo"]["ingestione_per_comando"].get(cmd, {"indice": 0, "coppia": None})
            v = d["indice"]
            fill = FILL_NO if v > lim["indice_ingestione_critico"] else (FILL_IN if v > lim["indice_ingestione_attenzione"] else None)
            _cella(ws, row, 2 + j, v, "0.000", fill=fill)
            _cella(ws, row, 2 + len(ott) + j, " → ".join(d["coppia"]) if d["coppia"] else "—")
    _larghezze(ws, [14] + [14] * len(ott) + [24] * len(ott))


def _tutti(ws, risultati):
    _titolo(ws, "Tutti i progetti valutati dall'ottimizzatore")
    tit = ["Scenario", "Variante", "Lato cubo (mm)", "D (mm)", "Geometria ammissibile", "Completo", "Ammissibile", "Punteggio",
           "σ", "Ventola", "Motore", "P asse (W)", "Picco 3 assi (W)", "Condotti", "Libero dopo", "Gioco (mm)",
           "Componenti tutti", "Violazioni"]
    _intest(ws, 4, tit)
    row = 5
    for r in risultati:
        for p in r["progetti"]:
            g = p["geometria"]
            c = p.get("completo")
            a = p.get("aero")
            vals = [r["scenario"]["id"], p["variante"] or "—", p["L"], p["D"], "sì" if p["geometria_ammissibile"] else "no",
                    "sì" if c else "no", ("sì" if c["ammissibile"] else "no") if c else "—",
                    c["punteggio_totale"] if c else None, c["sigma"] if c else None,
                    c["tipo_ventola"] if c else None, c["motore"] if c else None,
                    a["P_asse_max"] if a else None, a["P_picco_3assi"] if a else None,
                    g["frazione_condotti"], g["frazione_libera_dopo"], g["gioco_min_mm"],
                    "sì" if g["componenti_tutti"] else "no",
                    "; ".join(c["violazioni"]) if c else _viol_geom(g)]
            fm = [None, None, "0", "0", None, None, None, "0.000", "0.00", None, None, "0.0", "0", "0.0%", "0.0%", "0.0",
                  None, None]
            for j, (v, f) in enumerate(zip(vals, fm)):
                _cella(ws, row, 1 + j, v, f)
            row += 1
    _larghezze(ws, [22, 40, 10, 8, 12, 10, 12, 10, 8, 22, 14, 10, 10, 10, 10, 10, 12, 70])
    ws.freeze_panes = "E5"
    ws.auto_filter.ref = f"A4:{COL(len(tit))}{row - 1}"


def _viol_geom(g):
    v = []
    if g["irrealizzabile"]:
        v.append("irrealizzabile")
    if g["gioco_min_mm"] < 0:
        v.append(f"intersezione {g['gioco_min_mm']:.0f} mm")
    if g["sovrapposizioni_zone_cm3"]:
        v.append("dentro moduli riservati")
    if g["bocche_in_zone_centrali"]:
        v.append("bocche in zone centrali")
    return "; ".join(v) or "spinta non raggiunta con gli elementi in libreria"


def _database(ws, scenari):
    ws.title = "Scenari"
    _titolo(ws, "Scenari confrontati", "Da INPUT.py, sezione 11 (SCENARI).")
    tit = ["Id", "Nome", "Topologia", "Origine", "Descrizione", "Pregi attesi", "Difetti attesi", "Parametri"]
    _intest(ws, 4, tit)
    for i, s in enumerate(scenari):
        row = 5 + i
        par = {k: v for k, v in s.items() if k not in ("id", "attivo", "nome", "topologia", "origine", "descrizione",
                                                     "pregi_attesi", "difetti_attesi")}
        for j, v in enumerate([s["id"], s["nome"], s["topologia"], s.get("origine", ""), s["descrizione"],
                               s.get("pregi_attesi", ""), s.get("difetti_attesi", ""), str(par)]):
            c = _cella(ws, row, 1 + j, v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row].height = 120
    _larghezze(ws, [20, 30, 14, 30, 70, 40, 40, 50])


def _ipotesi(ws, cfg):
    _titolo(ws, "Ipotesi, correlazioni e fonti")
    righe = [
        ("Flusso", "Incomprimibile (Mach di punta < 0,3 verificato); aria secca, gas perfetto; viscosità di Sutherland."),
        ("Bilancio", "p0 lungo il condotto = p_ambiente − perdite + Δp ventola; uscita a pressione ambiente; aria aspirata da ferma."),
        ("Spinta", "Flusso di quantità di moto del getto: β ρ A v² (β = 1,02); nessun termine di pressione."),
        ("Perdite", "Sommate come potenza (Q·Δp) per la ripartizione per categoria."),
        ("Attrito", "Laminare 64/Re; turbolento Haaland (≈ Colebrook); transizione interpolata 2300-4000."),
        ("Griglie", "Idelchik, fili tondi: K = k_Re [1,3(1−f) + (1/f − 1)²], riferito alla velocità a monte."),
        ("Imbocco", "Idelchik / ASHRAE, bordo raggiato: K da 0,5 (spigolo vivo) a 0,03 (r/D ≥ 0,2)."),
        ("Curve", "Idelchik: K = A1(angolo) B1(R/D) k_Re; sotto R/D = 0,5 gomito a spigolo vivo."),
        ("Ugello / diffusore", "Convergente: K piccolo sull'uscita; diffusore di Gibson con avviso oltre 12° totali."),
        ("Effetto di sistema", "Ispirato ad AMCA 201: curva entro 2,5 D dalla ventola. VALORI INDICATIVI, da verificare."),
        ("Ventola", "Mappe adimensionali generiche (SEGNAPOSTO); gioco di punta; Moody (esponente 0,2) per Reynolds; statore o vortice perso."),
        ("Motore", "Kv, R, I0 tipici di catalogo (SEGNAPOSTO)."),
        ("Ingestione", "Indice di screening (pozzo emisferico contro getto tondo): NON è una previsione CFD."),
        ("Dinamica", "Salita con limite di corrente; PD con zero a ω_c/3; attuatore del primo ordine τ = t90/2,3."),
        ("Struttura", "Tubo appoggiato + massa (Dunkerley); p_cr = 2E/(1−ν²)(t/D)³; flessione della massa a n g."),
        ("Lato del cubo", "Intervallo e passo in INPUT.py (GEOMETRIA). Per ogni lato si ripete tutta l'ottimizzazione; l'ottimo è il progetto ammissibile con il punteggio più alto (a parità: condotto più centrato, poi cubo più piccolo). La spinta richiesta non dipende dal lato: dipende dalla massa di progetto."),
        ("Spazio", f"Voxel da {cfg['esecuzione']['risoluzione_voxel_mm']} mm; tubi come capsule (prudente sulle curve); componenti come scatole; volumetti d'angolo tolti ai vertici."),
        ("Spigoli centrati", "Condotto dritto per ogni spigolo, tangente alle due facce, centrato sulla mezzeria. Accorciato (lunghezza_frazione) e/o spostato lungo lo spigolo (spostamento_frazione) fino a che le estremità restano a distanza c = a − (2 Ro + gioco) dal vertice. Ai vertici si toglie un volumetto d'angolo dalle estremità alla faccia interna: il vertice è aperto e i condotti sboccano lì."),
        ("Massa", "Stima parametrica (condotti/massa.py, parametri TELAIO in INPUT.py): guscio a spessore equivalente, longheroni e nodi, pareti dei condotti, alloggiamenti, staffe, flange e griglie, fori di vertice, motori, ESC, cavi, viteria; componenti da COMPONENTI e MASSE_FISSE. SEGNAPOSTO finché non si pesa un prototipo."),
        ("Componenti", "Batteria NiMH 150×100×80, avionica 200×150×50 (COMPASS); inviluppo ruote 130³ SEGNAPOSTO."),
        ("Fonti", "Idelchik, Handbook of Hydraulic Resistance; Miller, Internal Flow Systems; AMCA 201; Pereira 2008; Graf 2005; Akturk & Camci 2011; Brandt & Selig 2011; ESA EUG cap. 5; ESDP; SPFC."),
    ]
    _intest(ws, 4, ["Argomento", "Ipotesi o correlazione"])
    for i, (a, b) in enumerate(righe, start=5):
        _cella(ws, i, 1, a, font=F_B)
        c = _cella(ws, i, 2, b)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    _larghezze(ws, [30, 120])


def _grafici(ws, grafici, base):
    _titolo(ws, "Grafici generati (SVG)", "Percorsi relativi alla cartella dell'esecuzione.")
    _intest(ws, 4, ["Gruppo", "File"])
    for i, (gruppo, p) in enumerate(grafici, start=5):
        _cella(ws, i, 1, gruppo)
        rel = os.path.relpath(p, base)
        c = _cella(ws, i, 2, rel)
        c.hyperlink = os.path.join("..", rel)
        c.font = Font(name=FONT, size=10, color="1F5BD8", underline="single")
    _larghezze(ws, [26, 90])
