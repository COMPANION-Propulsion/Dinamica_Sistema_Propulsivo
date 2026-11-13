"""Confronto tra catene della dinamica (varianti Statore/NoStatore o casi di una serie).

Una catena è una cartella di uscita della dinamica; per ogni ambiente contiene
<ambiente>/00_sintesi/riepilogo.json. Nella radice del confronto la funzione scrive:
CONFRONTO_catene.md, confronto_catene.xlsx (solo se openpyxl è installato) e confronto_catene.svg.
Catene fallite o file mancanti non sollevano eccezioni: compaiono con il loro stato o con "-".
"""
import datetime
import json
import os
import re
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.patches import Patch                  # noqa: E402

NOME_MD = "CONFRONTO_catene.md"
NOME_XLSX = "confronto_catene.xlsx"
NOME_SVG = "confronto_catene.svg"
MANCANTE = "-"
COLORI = ["#1f5bd8", "#e8590c", "#2b8a3e", "#9c36b5", "#f59f00", "#0c8599", "#c92a2a", "#495057"]

# (chiave interna, intestazione, formato, verso migliore: "max" o "min")
METRICHE = [
    ("spazio_m", "Spazio max con disturbo [m]", "{:.3f}", "max"),
    ("tempo_min_s", "Tempo minimo con disturbo [s]", "{:.2f}", "min"),
    ("errore_mm", "Errore a fine manovra, peggior asse [mm]", "{:.2f}", "min"),
    ("energia_J", "Energia nella finestra [J]", "{:.1f}", "min"),
    ("corrente_A", "Corrente di picco [A]", "{:.3f}", "min"),
    ("potenza_W", "Potenza di picco [W]", "{:.2f}", "min"),
    ("H_finestra", "Momento ruote nella finestra [N·m·s]", "{:.3f}", "min"),
    ("quota_ruote", "Quota della capacità ruote", "{:.0%}", "min"),
    ("coppia_squilibrio", "Coppia di squilibrio [N·m]", "{:.2e}", "min"),
    ("coppia_reazione", "Coppia di reazione rotori [N·m]", "{:.2e}", "min"),
    ("margine_fase", "Margine di fase anello [°]", "{:.1f}", "max"),
    ("quota_assestati", "Manovre assestate (Monte Carlo)", "{:.1%}", "max"),
]
# grandezze del grafico SVG (sottoinsieme di METRICHE, con intestazioni corte)
SVG_GRANDEZZE = [
    ("spazio_m", "Spazio [m]", "{:.3f}"),
    ("tempo_min_s", "Tempo min [s]", "{:.2f}"),
    ("errore_mm", "Errore [mm]", "{:.2f}"),
    ("energia_J", "Energia [J]", "{:.1f}"),
    ("corrente_A", "Corrente [A]", "{:.3f}"),
    ("quota_ruote", "Quota ruote", "{:.0%}"),
]


# ---------------------------------------------------------------- lettura dei riepiloghi
def _valore_numerico(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _fmt(v, fmt):
    if v is None:
        return MANCANTE
    if isinstance(v, (bool, str)):
        return str(v)
    try:
        return fmt.format(v)
    except (TypeError, ValueError):
        return str(v)


def _sez(r, *chiavi):
    x = r
    for k in chiavi:
        if not isinstance(x, dict):
            return None
        x = x.get(k)
    return x


def _estremo(valori, f):
    ok = [v for v in valori if v is not None]
    return f(ok) if ok else None


def _tempo_min(valori):
    """Tempo minimo nel caso peggiore; 'impossibile' se su un asse la spinta non basta (come in export.py)."""
    if not valori:
        return None
    if any(not v for v in valori):
        return "impossibile"
    return _estremo([_valore_numerico(v) for v in valori], max)


def _grandezze(r):
    """Grandezze principali di un riepilogo, None dove manca. Sui tre assi prende il caso peggiore."""
    if not isinstance(r, dict):
        return {}
    assi_d = r.get("assi")
    assi = [a for a in assi_d.values() if isinstance(a, dict)] if isinstance(assi_d, dict) else []
    spazi_l = r.get("spazio_massimo")
    spazi = [s for s in spazi_l if isinstance(s, dict)] if isinstance(spazi_l, list) else []
    return {
        "spazio_m": _estremo([_valore_numerico(s.get("spazio_max_con_disturbo_m")) for s in spazi], min),
        "tempo_min_s": _tempo_min([s.get("tempo_min_con_disturbo_s") for s in spazi]),
        "errore_mm": _estremo([_valore_numerico(a.get("errore_a_T_mm")) for a in assi], max),
        "energia_J": _sez(r, "potenza_totale", "energia_J"),
        "potenza_W": _sez(r, "potenza_totale", "potenza_picco_W"),
        "corrente_A": _sez(r, "potenza_totale", "corrente_picco_A"),
        "H_finestra": _sez(r, "ruote", "H_finestra"),
        "quota_ruote": _sez(r, "ruote", "quota_ruota"),
        "coppia_squilibrio": _sez(r, "ruote", "coppia_squilibrio"),
        "coppia_reazione": _sez(r, "ruote", "coppia_reazione"),
        "margine_fase": _sez(r, "margine_fase_anello", "margine_gradi"),
        "quota_assestati": _sez(r, "monte_carlo", "quota_tutti_assestati"),
    }


def _appiattisci(x, prefisso=""):
    """Dizionario piatto di scalari: dizionari con punto, liste con indice o con l'asse ([X], [0])."""
    out = {}
    if isinstance(x, dict):
        for k, v in x.items():
            if str(k).startswith("_"):
                continue
            nuovo = f"{prefisso}.{k}" if prefisso else str(k)
            out.update(_appiattisci(v, nuovo))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            etichetta = v["asse"] if isinstance(v, dict) and "asse" in v else i
            out.update(_appiattisci(v, f"{prefisso}[{etichetta}]"))
    else:
        out[prefisso] = x
    return out


def _unione(liste):
    out = {}
    for d in liste:
        for k in d:
            out.setdefault(k, None)
    return list(out)


def _ambienti_con_riepilogo(cartella):
    try:
        nomi = sorted(os.listdir(cartella))
    except OSError:
        return []
    return [n for n in nomi if os.path.isfile(os.path.join(cartella, n, "00_sintesi", "riepilogo.json"))]


def _leggi_riepilogo(cartella, amb):
    try:
        with open(os.path.join(cartella, amb, "00_sintesi", "riepilogo.json"), encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _raccogli(catene):
    """Una voce per catena: etichetta, cartella, stato, variante, dati e riepiloghi per ambiente (solo se ok)."""
    info = []
    for i, c in enumerate(catene or []):
        if not isinstance(c, dict):
            c = {}
        stato = str(c.get("stato") or "ok")
        cartella = str(c["cartella_out"]) if c.get("cartella_out") else None
        riep = {}
        if cartella and stato == "ok":
            for amb in _ambienti_con_riepilogo(cartella):
                r = _leggi_riepilogo(cartella, amb)
                if r is not None:
                    riep[amb] = r
        dati = c.get("dati") if isinstance(c.get("dati"), dict) else None
        variante = c.get("variante") or (dati or {}).get("variante") or MANCANTE
        info.append({"etichetta": str(c.get("etichetta") or f"catena_{i + 1}"), "cartella": cartella,
                     "stato": stato, "variante": str(variante), "dati": dati, "riep": riep})
    return info


def _ambienti(info):
    out = []
    for c in info:
        for amb in c["riep"]:
            if amb not in out:
                out.append(amb)
    return out


def _stato_catena(c):
    if c["stato"] != "ok":
        return c["stato"]
    return "ok" if c["riep"] else "ok, nessun riepilogo.json"


def _stato_amb(c, amb):
    if c["stato"] != "ok":
        return c["stato"]
    return "ok" if c["riep"].get(amb) is not None else "ok, riepilogo mancante"


def _cella(s):
    return str(s).replace("|", "/").replace("\n", " ")


def _valore_testo(v):
    if v is None:
        return MANCANTE
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


# ---------------------------------------------------------------- Markdown
def _letture(info, amb):
    gr = [(c["etichetta"], _grandezze(c["riep"][amb])) for c in info if c["riep"].get(amb) is not None]
    if len(gr) < 2:
        return ["- Meno di due catene con dati per questo ambiente: nessun confronto."]
    righe = []
    for k, nome, fmt, verso in METRICHE:
        vals = []
        for et, g in gr:
            v = _valore_numerico(g.get(k))
            if v is not None:
                vals.append((et, v))
        if len(vals) < 2:
            continue
        if len({round(abs(v), 12) for _, v in vals}) == 1:
            righe.append(f"- {nome}: uguale in tutte le catene.")
            continue
        scelta = max if verso == "max" else min
        mig_et, mig = scelta(vals, key=lambda t: abs(t[1]))
        altre = []
        for et, v in vals:
            if et == mig_et:
                continue
            scarto = "-" if mig == 0 else f"{(abs(v) - abs(mig)) / abs(mig) * 100:+.1f}%"
            altre.append(f"`{et}` {scarto}")
        righe.append(f"- {nome}: migliore `{mig_et}` ({_fmt(mig, fmt)})"
                     + (f"; scarto delle altre: {', '.join(altre)}" if altre else ""))
    return righe or ["- Nessuna grandezza confrontabile."]


def _tabella_dimensionamento(info):
    masse = sorted({k for c in info if c["dati"] for k in _appiattisci(c["dati"])
                    if "mass" in k.lower() and k != "variante"})
    intest = ["catena", "stato", "variante", "L_disk_m"] + masse
    L = ["| " + " | ".join(intest) + " |", "|" + "---|" * len(intest)]
    for c in info:
        dd = _appiattisci(c["dati"]) if c["dati"] else {}
        cols = [c["etichetta"], _stato_catena(c), c["variante"], _valore_testo(dd.get("L_disk_m"))]
        cols += [_valore_testo(dd.get(m)) for m in masse]
        L.append("| " + " | ".join(_cella(x) for x in cols) + " |")
    return L


def _md(percorso, info, ambienti, data, file_scritti):
    L = ["# Confronto tra catene della dinamica", "",
         f"Generato il {data}. Ogni catena è una cartella di uscita della dinamica (una variante Statore/NoStatore "
         "o un caso della serie); i valori vengono dal suo `<ambiente>/00_sintesi/riepilogo.json`. "
         f"`{MANCANTE}` = grandezza assente. Le catene fallite non hanno valori: compare il loro stato.", "",
         "## Catene", "", "| catena | stato | cartella di uscita |", "|---|---|---|"]
    for c in info:
        L.append(f"| {_cella(c['etichetta'])} | {_cella(_stato_catena(c))} | {_cella(c['cartella'] or MANCANTE)} |")
    intest = [nome for _, nome, _, _ in METRICHE]
    for amb in ambienti:
        L += ["", f"## Ambiente `{amb}`", "",
              "| catena | stato | " + " | ".join(intest) + " |", "|---|---|" + "---|" * len(intest)]
        for c in info:
            r = c["riep"].get(amb)
            g = _grandezze(r) if r is not None else {}
            vals = [_fmt(g.get(k), f) if r is not None else MANCANTE for k, _, f, _ in METRICHE]
            L.append("| " + " | ".join([_cella(c["etichetta"]), _cella(_stato_amb(c, amb))] + vals) + " |")
    L += ["", "## Dati del dimensionamento", ""] + _tabella_dimensionamento(info)
    L += ["", "## Letture", "",
          "Per ogni grandezza: catena migliore (il massimo per spazio, margine di fase e manovre assestate, "
          "il minimo per le altre; confronto sui valori assoluti) e scarto in % delle altre rispetto a lei "
          "((valore - migliore) / |migliore|)."]
    if not ambienti:
        L += ["", "- Nessun ambiente con riepilogo: nessun confronto."]
    for amb in ambienti:
        L += ["", f"**{amb}**", ""] + _letture(info, amb)
    L += ["", "## File", ""] + [f"- `{os.path.basename(p)}`" for p in file_scritti] + [""]
    with open(percorso, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return percorso


# ---------------------------------------------------------------- Excel
def _cella_xlsx(v):
    if v is None:
        return MANCANTE
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float, str)):
        return v
    return str(v)


def _nome_foglio(nome, usati):
    base = re.sub(r"[\[\]:*?/\\]", "_", str(nome))[:31] or "foglio"
    cand, n = base, 2
    while cand.lower() in usati:
        suff = f"_{n}"
        cand = base[:31 - len(suff)] + suff
        n += 1
    usati.add(cand.lower())
    return cand


def _scrivi_foglio(ws, intest, righe, n_fissi):
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter
    ws.append(intest)
    for cella in ws[1]:
        cella.font = Font(bold=True)
    for r in righe:
        ws.append(r)
    ws.freeze_panes = f"{get_column_letter(n_fissi + 1)}2"
    for idx, nome in enumerate(intest, start=1):
        lung = max([len(str(nome))] + [len(str(r[idx - 1])) for r in righe if idx - 1 < len(r)])
        ws.column_dimensions[get_column_letter(idx)].width = min(max(10, lung + 2), 60)


def _scrivi_xlsx(percorso, info, ambienti, data):
    try:
        from openpyxl import Workbook
    except ImportError:
        warnings.warn("openpyxl non installato: confronto_catene.xlsx non scritto (pip install openpyxl).")
        return None
    wb = Workbook()
    wb.remove(wb.active)
    usati = set()
    for amb in ambienti:
        chiavi = _unione([_appiattisci(c["riep"][amb]) for c in info if c["riep"].get(amb) is not None])
        righe = []
        for c in info:
            r = c["riep"].get(amb)
            piatto = _appiattisci(r) if r is not None else {}
            cols = [c["etichetta"], _stato_amb(c, amb)]
            cols += [_cella_xlsx(piatto.get(k)) if r is not None else MANCANTE for k in chiavi]
            righe.append(cols)
        _scrivi_foglio(wb.create_sheet(_nome_foglio(amb, usati)), ["etichetta", "stato"] + chiavi, righe, 2)
    chiavi_dati = _unione([_appiattisci(c["dati"]) for c in info if c["dati"]])
    chiavi_dati = [k for k in chiavi_dati if k != "variante"]
    righe = []
    for c in info:
        dd = _appiattisci(c["dati"]) if c["dati"] else {}
        cols = [c["etichetta"], _stato_catena(c), c["cartella"] or MANCANTE, c["variante"]]
        cols += [_cella_xlsx(dd.get(k)) if c["dati"] else MANCANTE for k in chiavi_dati]
        righe.append(cols)
    _scrivi_foglio(wb.create_sheet(_nome_foglio("Dimensionamento", usati)),
                   ["etichetta", "stato", "cartella_out", "variante"] + chiavi_dati, righe, 4)
    ws = wb.create_sheet(_nome_foglio("Note", usati))
    testo = ["Confronto tra catene della dinamica", f"Generato il {data}", "",
             "Una riga per catena. La colonna stato è ok oppure il motivo del fallimento.",
             "Fogli per ambiente: tutte le chiavi scalari di <ambiente>/00_sintesi/riepilogo.json, appiattite "
             "(dizionari con punto, liste con indice o con l'asse, es. spazio_massimo[X].tempo_min_con_disturbo_s).",
             "Foglio Dimensionamento: dati importati dal dimensionamento per catena (variante, L_disk, masse).",
             f"{MANCANTE} = grandezza assente nel riepilogo, o catena senza valori.", "", "Catene:"]
    testo += [f"- {c['etichetta']}: {_stato_catena(c)} ({c['cartella'] or MANCANTE})" for c in info]
    from openpyxl.styles import Font
    for i, t in enumerate(testo, start=1):
        ws.cell(row=i, column=1, value=t)
    ws["A1"].font = Font(bold=True)
    ws.column_dimensions["A"].width = 110
    wb.save(percorso)
    return percorso


# ---------------------------------------------------------------- SVG
def _svg(percorso, info, ambienti, data):
    n = max(1, len(ambienti))
    fig, righe_assi = plt.subplots(n, 1, figsize=(11, 4.2 * n + 1.3), squeeze=False)
    assi = [a[0] for a in righe_assi]
    larg = 0.8 / max(1, len(info))
    for ax, amb in zip(assi, ambienti or [None]):
        if amb is None:
            ax.text(0.5, 0.5, "Nessun riepilogo disponibile", ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            continue
        gr = {j: _grandezze(c["riep"][amb]) for j, c in enumerate(info) if c["riep"].get(amb) is not None}
        rif = {}
        for k, _, _ in SVG_GRANDEZZE:
            for j in gr:
                v = _valore_numerico(gr[j].get(k))
                if v:
                    rif[k] = v
                    break
        ymax = 1.0
        for j in gr:
            for i, (k, _, fmt) in enumerate(SVG_GRANDEZZE):
                raw = gr[j].get(k)
                x = i - 0.4 + (j + 0.5) * larg
                colore = COLORI[j % len(COLORI)]
                if isinstance(raw, str):
                    ax.text(x, 0.02, raw, rotation=90, fontsize=6, ha="center", va="bottom", color="#495057")
                    continue
                v = _valore_numerico(raw)
                if v is None or k not in rif:
                    continue
                rapp = v / rif[k]
                ax.bar(x, rapp, width=larg * 0.95, color=colore)
                ax.text(x, rapp, _fmt(v, fmt), rotation=90, fontsize=6, ha="center", va="bottom")
                ymax = max(ymax, rapp)
        ax.axhline(1.0, color="#868e96", lw=0.8, ls="--")
        ax.set_ylim(0, ymax * 1.6)
        ax.set_xlim(-0.6, len(SVG_GRANDEZZE) - 0.4)
        ax.set_xticks(range(len(SVG_GRANDEZZE)))
        ax.set_xticklabels([nome for _, nome, _ in SVG_GRANDEZZE], fontsize=8)
        ax.set_ylabel("rapporto sulla prima catena", fontsize=8)
        ax.set_title(f"Ambiente {amb}", fontsize=10)
        handles = [Patch(color=COLORI[j % len(COLORI)], label=info[j]["etichetta"]) for j in gr]
        if handles:
            ax.legend(handles=handles, fontsize=7, loc="upper right")
    fallite = [f"{c['etichetta']}: {c['stato']}" for c in info if c["stato"] != "ok"]
    fig.suptitle(f"Confronto tra catene, {data}. Barre = valore / valore della prima catena con il dato (linea a 1). "
                 "Per errore, tempo, energia, corrente e ruote è meglio il valore più basso.", fontsize=9)
    if fallite:
        fig.text(0.01, 0.005, "Non confrontate: " + "; ".join(fallite), fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(percorso, format="svg", bbox_inches="tight")
    plt.close(fig)
    return percorso


# ---------------------------------------------------------------- funzione pubblica
def scrivi_confronto_catene(radice_out, catene):
    """Scrive CONFRONTO_catene.md, confronto_catene.xlsx e confronto_catene.svg in radice_out.

    catene: lista di dict con etichetta, cartella_out, stato ("ok" o motivo), variante, dati (o None).
    Restituisce i percorsi dei file scritti (l'xlsx manca se openpyxl non è installato).
    """
    os.makedirs(radice_out, exist_ok=True)
    data = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    info = _raccogli(catene)
    ambienti = _ambienti(info)
    scritti = []
    p_xlsx = _scrivi_xlsx(os.path.join(radice_out, NOME_XLSX), info, ambienti, data)
    if p_xlsx:
        scritti.append(p_xlsx)
    scritti.append(_svg(os.path.join(radice_out, NOME_SVG), info, ambienti, data))
    scritti.insert(0, _md(os.path.join(radice_out, NOME_MD), info, ambienti, data,
                          [p for p in scritti]))
    return scritti
