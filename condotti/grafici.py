"""Grafici in SVG (e PNG a richiesta) per ogni scenario e per il confronto."""
import copy
import math
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, Rectangle

from . import rete as R
from . import dinamica as DY
from . import struttura as ST
from .geometria import tubi_unita, box_dietro_faccia
from .aria import crea_aria

plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3, "figure.dpi": 110,
                     "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
COLORI = ["#1f5bd8", "#e8590c", "#2b8a3e", "#ae3ec9", "#c92a2a", "#0b7285", "#5c940d", "#f59f00"]
CAT_COL = {"griglie": "#868e96", "imbocco": "#74c0fc", "attrito": "#1971c2", "curve": "#f08c00",
           "effetto di sistema": "#e8590c", "ugello": "#2f9e44", "energia del getto": "#ffd43b"}


def _salva(fig, percorso, formati):
    os.makedirs(os.path.dirname(percorso), exist_ok=True)
    out = []
    for f in formati:
        p = f"{percorso}.{f}"
        fig.savefig(p, bbox_inches="tight")
        out.append(p)
    plt.close(fig)
    return out


def _solve(un, aria, N, ctx=None):
    un.imposta_N(N)
    sol = R.risolvi([un], aria, ctx or {})[un.nome]
    return sol, R.bilancio_unita(un, sol, aria, ctx or {})


# ======================================================================= profili
def _disegna_profili(axs, un, aria, N, colore, etichetta, ctx=None, confini=True):
    sol, _ = _solve(un, aria, N, ctx)
    prf = R.profili_unita(un, sol, aria, ctx or {})
    pezzi = [prf["tronco"]] + prf["rami"]
    for k, p in enumerate(pezzi):
        ls = "-"
        lab = etichetta if k == 0 else None
        if k >= 1:          # la coda d'uscita parte dalla fine del tronco
            s = np.concatenate([[prf["tronco"]["s"][-1]], p["s"]])
            v = np.concatenate([[prf["tronco"]["v"][-1]], p["v"]])
            pp = np.concatenate([[prf["tronco"]["p"][-1]], p["p"]])
            p0 = np.concatenate([[prf["tronco"]["p0"][-1]], p["p0"]])
        else:
            s, v, pp, p0 = p["s"], p["v"], p["p"], p["p0"]
        axs[0].plot(s * 1000, v, ls, color=colore, lw=1.4, label=lab)
        axs[1].plot(s * 1000, pp, ls, color=colore, lw=1.4)
        axs[2].plot(s * 1000, p0, ls, color=colore, lw=1.4)
    if confini:
        for (s0, nome, cat) in prf["tronco"]["confini"]:
            for a in axs:
                a.axvline(s0 * 1000, color="#adb5bd", lw=0.5, zorder=0)
            axs[0].text(s0 * 1000, 1.0, " " + nome, transform=axs[0].get_xaxis_transform(), rotation=90,
                        va="top", ha="left", fontsize=6, color="#495057")
    return sol


def grafico_profili(un, arie, N_lista, ambiente_rif, titolo, percorso, formati, ctx=None):
    fig, axs = plt.subplots(3, 1, figsize=(9, 8.5), sharex=True)
    for i, N in enumerate(N_lista):
        _disegna_profili(axs, un, arie[ambiente_rif], N, COLORI[i % 8], f"{N:,.0f} giri/min".replace(",", "."),
                         ctx, confini=(i == 0))
    _finisci_profili(fig, axs, titolo + f" — ambiente {ambiente_rif}")
    return _salva(fig, percorso, formati)


def grafico_profili_ambienti(un, arie, N, titolo, percorso, formati):
    fig, axs = plt.subplots(3, 1, figsize=(9, 8.5), sharex=True)
    for i, (nome, aria) in enumerate(arie.items()):
        _disegna_profili(axs, un, aria, N, COLORI[i % 8], f"{nome} (ρ = {aria.rho:.3f} kg/m³)", confini=(i == 0))
    _finisci_profili(fig, axs, titolo + f" — {N:,.0f} giri/min".replace(",", "."))
    return _salva(fig, percorso, formati)


def _finisci_profili(fig, axs, titolo):
    axs[0].set_ylabel("velocità media v (m/s)")
    axs[1].set_ylabel("pressione statica p − p_amb (Pa)")
    axs[2].set_ylabel("pressione totale p₀ − p_amb (Pa)")
    axs[2].set_xlabel("coordinata curvilinea lungo l'asse del condotto s (mm)")
    axs[0].legend(fontsize=7, loc="lower right")
    axs[1].axhline(0, color="k", lw=0.6)
    axs[2].axhline(0, color="k", lw=0.6)
    fig.suptitle(titolo, fontsize=10)
    fig.tight_layout()


# ======================================================================= mappa ventola
def grafico_mappa_ventola(un, arie, ambiente_rif, N_req, N_lim, titolo, percorso, formati):
    v = un.ventola
    aria0 = arie[ambiente_rif]
    fig, ax = plt.subplots(figsize=(8, 5.5))
    N_lista = [f * N_lim for f in (0.4, 0.6, 0.8, 1.0)]
    for i, N in enumerate(N_lista):
        Q = np.linspace(0, v.Q_max(N), 80)
        dp = [v.stato(q, N, aria0)["dp_utile"] for q in Q]
        ax.plot(Q * 1000, dp, color="#495057", lw=1, alpha=0.4 + 0.15 * i)
        ax.text(Q[len(Q) // 3] * 1000, dp[len(Q) // 3], f" {N:,.0f}".replace(",", "."), fontsize=7, color="#495057")
    for k, (nome, aria) in enumerate(arie.items()):
        Ns = np.linspace(0.15, 1.0, 14) * N_lim
        pts = []
        for N in Ns:
            sol, b = _solve(un, aria, N)
            pts.append((sol["Q"] * 1000, b["dp_ventola"]))
        pts = np.array(pts)
        ax.plot(pts[:, 0], pts[:, 1], "-o", ms=2.5, color=COLORI[k % 8], label=f"curva del sistema, {nome}")
    sol, b = _solve(un, aria0, N_req)
    ax.plot(sol["Q"] * 1000, b["dp_ventola"], "*", ms=14, color="#c92a2a", label="punto di progetto", zorder=5)
    ax.set_xlabel("portata Q (L/s)")
    ax.set_ylabel("salto di pressione totale utile della ventola (Pa)")
    ax.set_title(titolo + "\ncurve della ventola (grigio, giri/min indicati) e curve del sistema")
    ax.legend(fontsize=7)
    ax.set_ylim(bottom=0)
    return _salva(fig, percorso, formati)


# ======================================================================= spinta / potenza
def grafico_spinta_giri(un, arie, motore, cfg, N_req, N_lim, F_req, titolo, percorso, formati):
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.3))
    Ns = np.linspace(0.1, 1.0, 25) * N_lim
    V_bus = cfg["elettrico"]["tensione_bus_V"]
    for k, (nome, aria) in enumerate(arie.items()):
        F, dp, P, FP = [], [], [], []
        for N in Ns:
            sol, b = _solve(un, aria, N)
            st = b["stato_ventola"]
            mp = motore.punto(st["coppia"], N, V_bus, cfg["elementi"]["rendimento_esc"])
            F.append(b["spinta"]); dp.append(b["dp_ventola"]); P.append(mp["P_el"])
            FP.append(b["spinta"] / max(mp["P_el"], 1e-9) * 1000)
        c = COLORI[k % 8]
        axs[0].plot(Ns, F, color=c, label=nome)
        axs[1].plot(dp, F, color=c, label=nome)
        axs[2].plot(F, P, color=c, label=nome)
    axs[0].axhline(F_req, color="#c92a2a", ls="--", lw=0.8, label="spinta richiesta per unità")
    axs[0].axvline(N_req, color="#c92a2a", ls=":", lw=0.8)
    axs[0].set_xlabel("giri del rotore (giri/min)"); axs[0].set_ylabel("spinta dell'unità (N)")
    axs[1].set_xlabel("salto di pressione utile della ventola (Pa)"); axs[1].set_ylabel("spinta dell'unità (N)")
    axs[2].set_xlabel("spinta dell'unità (N)"); axs[2].set_ylabel("potenza elettrica dell'unità (W)")
    axs[2].axvline(F_req, color="#c92a2a", ls="--", lw=0.8)
    for a in axs:
        a.legend(fontsize=7)
    fig.suptitle(titolo)
    fig.tight_layout()
    return _salva(fig, percorso, formati)


def grafico_perdite_unita(classe, titolo, percorso, formati):
    fig, ax = plt.subplots(figsize=(8, 3.2))
    cats = dict(classe["perdite_W"])
    cats["energia del getto"] = classe["P_getto"]
    tot = sum(cats.values())
    x0 = 0.0
    for k, v in sorted(cats.items(), key=lambda kv: -kv[1]):
        ax.barh(0, v, left=x0, color=CAT_COL.get(k, "#adb5bd"), edgecolor="white")
        if v / tot > 0.04:
            ax.text(x0 + v / 2, 0, f"{k}\n{v:.1f} W", ha="center", va="center", fontsize=7)
        x0 += v
    ax.set_yticks([])
    ax.set_xlabel("potenza utile della ventola ripartita (W) — il getto è la parte che produce spinta")
    ax.set_title(titolo + f"\nperdite = {classe['frazione_perdite']:.0%} della potenza utile; "
                 f"rendimento ventola {classe['eta']:.2f}")
    return _salva(fig, percorso, formati)


# ======================================================================= dinamica e struttura
def grafico_salita(storia, N_req, t90, titolo, percorso, formati, t_inv=None):
    fig, ax = plt.subplots(figsize=(7, 4))
    st = np.array(storia)
    w_req = N_req * 2 * math.pi / 60
    ax.plot(st[:, 0] * 1000, (st[:, 1] / w_req) ** 2 * 100, color="#1f5bd8")
    ax.axhline(90, color="#adb5bd", ls="--", lw=0.8)
    ax.axvline(t90 * 1000, color="#c92a2a", ls=":", lw=0.8)
    ax.text(t90 * 1000, 50, f"  t₉₀ = {t90 * 1000:.0f} ms", color="#c92a2a")
    if t_inv:
        ax.text(0.98, 0.1, f"inversione completa (ventola reversibile): {t_inv * 1000:.0f} ms",
                transform=ax.transAxes, ha="right", fontsize=8)
    ax.set_xlabel("tempo (ms)"); ax.set_ylabel("spinta (% della spinta di progetto)")
    ax.set_title(titolo + "\nsalita della spinta con limite di corrente del regolatore")
    return _salva(fig, percorso, formati)


def grafico_campbell(f1, Z, N_req, N_lim, titolo, percorso, formati):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    N = np.linspace(0, N_lim * 1.1, 200)
    for k, lab, c in ((1, "1 × giro (sbilanciamento)", "#495057"), (Z, f"{Z} × giro (passaggio pale)", "#d9480f"),
                      (2 * Z, f"{2 * Z} × giro", "#e8590c")):
        ax.plot(N, k * N / 60, color=c, label=lab)
    ax.axhline(f1, color="#1f5bd8", lw=2, label=f"1° modo flessionale del condotto: {f1:.0f} Hz")
    ax.axvspan(0.3 * N_req, N_lim, color="#d0ebff", alpha=0.5, label="campo di giri di esercizio")
    ax.axvline(N_req, color="#c92a2a", ls=":", label="giri di progetto")
    ax.set_ylim(0, max(f1 * 1.6, 2 * Z * N_req / 60 * 1.1))
    ax.set_xlabel("giri del rotore (giri/min)"); ax.set_ylabel("frequenza (Hz)")
    ax.set_title(titolo + "\ndiagramma di Campbell (incroci = risonanze da attraversare)")
    ax.legend(fontsize=7)
    return _salva(fig, percorso, formati)


def grafico_ingestione(ing, cfg, titolo, percorso, formati):
    items = sorted(ing.items(), key=lambda kv: -kv[1]["indice"])
    fig, ax = plt.subplots(figsize=(9, 4))
    nomi = [k for k, _ in items]
    vals = [v["indice"] for _, v in items]
    lim = cfg["limiti"]
    col = ["#c92a2a" if v > lim["indice_ingestione_critico"] else "#f08c00"
           if v > lim["indice_ingestione_attenzione"] else "#2f9e44" for v in vals]
    ax.bar(range(len(vals)), vals, color=col)
    ax.axhline(lim["indice_ingestione_attenzione"], color="#f08c00", ls="--", lw=0.8, label="attenzione")
    ax.axhline(lim["indice_ingestione_critico"], color="#c92a2a", ls="--", lw=0.8, label="critico")
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(nomi, rotation=90, fontsize=6)
    ax.set_ylabel("indice d'ingestione (aspirazione / getto)")
    ax.set_title(titolo + "\nriaspirazione dei getti per ogni comando su più assi (screening, non CFD)")
    ax.legend(fontsize=7)
    return _salva(fig, percorso, formati)


# ======================================================================= viste del layout
def _rett_proiettato(p, q, r, piano):
    a, b = piano
    P = np.array([p[a], p[b]]); Q = np.array([q[a], q[b]])
    d = Q - P
    n = np.linalg.norm(d)
    if n < 1e-6:
        return None
    t = d / n
    nn = np.array([-t[1], t[0]]) * r
    return np.array([P + nn, Q + nn, Q - nn, P - nn])


def grafico_viste(gm, cfg, titolo, percorso, formati):
    lay = gm["layout"]
    h = lay.L / 2
    td = cfg["geometria"]["parete_condotto_mm"]
    fig = plt.figure(figsize=(13, 10))
    piani = [((0, 1), "vista dall'alto (X–Y)", 2), ((0, 2), "vista dal fronte (X–Z)", 1), ((1, 2), "vista di lato (Y–Z)", 0)]
    for k, (piano, nome, normale) in enumerate(piani):
        ax = fig.add_subplot(2, 2, k + 1)
        ax.add_patch(Rectangle((-h, -h), 2 * h, 2 * h, fill=False, lw=1.5, color="k"))
        hi = h - lay.parete
        ax.add_patch(Rectangle((-hi, -hi), 2 * hi, 2 * hi, fill=False, lw=0.5, color="#868e96", ls=":"))
        for nome_z, (axz, sg, wu, wv, dep) in cfg["zone_riservate"].items():
            mn, mx = box_dietro_faccia(lay.L, lay.parete, axz, sg, wu, wv, dep)
            ax.add_patch(Rectangle((mn[piano[0]], mn[piano[1]]), mx[piano[0]] - mn[piano[0]], mx[piano[1]] - mn[piano[1]],
                                   fill=True, alpha=0.12, color="#495057", ls="--"))
        for nome_c, box in gm["componenti"].items():
            if box is None:
                continue
            mn, mx = box
            ax.add_patch(Rectangle((mn[piano[0]], mn[piano[1]]), mx[piano[0]] - mn[piano[0]], mx[piano[1]] - mn[piano[1]],
                                   fill=True, alpha=0.18, color="#f59f00", lw=0.8))
        for mn, mx in lay.tacche:
            ax.add_patch(Rectangle((mn[piano[0]], mn[piano[1]]), mx[piano[0]] - mn[piano[0]], mx[piano[1]] - mn[piano[1]],
                                   fill=False, hatch="////", lw=0.4, color="#868e96"))
        for u in lay.unita:
            for p, q, r, _ in u.canali:
                poly = _rett_proiettato(p, q, r, piano)
                if poly is not None:
                    ax.add_patch(Polygon(poly, closed=True, fill=False, lw=0.8, ls="--", color=COLORI[u.asse]))
            for p, q, r, _ in tubi_unita(u, td):
                poly = _rett_proiettato(p, q, r, piano)
                c = COLORI[u.asse]
                if poly is None:
                    ax.add_patch(Circle((p[piano[0]], p[piano[1]]), r, alpha=0.45, color=c))
                else:
                    ax.add_patch(Polygon(poly, closed=True, alpha=0.45, color=c, lw=0))
        ax.set_xlim(-h * 1.08, h * 1.08); ax.set_ylim(-h * 1.08, h * 1.08)
        ax.set_aspect("equal")
        ax.set_xlabel(f"{'XYZ'[piano[0]]} (mm)"); ax.set_ylabel(f"{'XYZ'[piano[1]]} (mm)")
        ax.set_title(nome, fontsize=9)
    ax3 = fig.add_subplot(2, 2, 4, projection="3d")
    for u in lay.unita:
        for perc in [u.tronco] + list(u.rami):
            P = perc.punti
            ax3.plot(P[:, 0], P[:, 1], P[:, 2], color=COLORI[u.asse], lw=max(perc.D / 8, 1))
    for nome_c, box in gm["componenti"].items():
        if box is None:
            continue
        mn, mx = box
        for (x0, y0, z0), (x1, y1, z1) in _spigoli_box(mn, mx):
            ax3.plot([x0, x1], [y0, y1], [z0, z1], color="#f59f00", lw=0.8)
    for (x0, y0, z0), (x1, y1, z1) in _spigoli_box(np.array([-h] * 3), np.array([h] * 3)):
        ax3.plot([x0, x1], [y0, y1], [z0, z1], color="k", lw=0.6)
    ax3.set_box_aspect((1, 1, 1))
    ax3.set_xlabel("X"); ax3.set_ylabel("Y"); ax3.set_zlabel("Z")
    ax3.set_title("vista 3D (blu X, arancio Y, verde Z; giallo: componenti)", fontsize=9)
    extra = "; tratteggio: volumetti tolti ai vertici" if lay.tacche else ""
    fig.suptitle(titolo + f"\nD = {gm['D']:.0f} mm — libero dopo i componenti {gm['frazione_libera_dopo']:.0%}, "
                 f"condotti {gm['frazione_condotti']:.0%} del volume interno; grigio: moduli riservati{extra}")
    fig.tight_layout()
    return _salva(fig, percorso, formati)


def _spigoli_box(mn, mx):
    c = [np.array([x, y, z]) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
    out = []
    for i in range(8):
        for j in range(i + 1, 8):
            if np.sum(np.abs(c[i] - c[j]) > 1e-9) == 1:
                out.append((c[i], c[j]))
    return out


# ======================================================================= confronto
def confronto(risultati, cfg, cartella, formati):
    out = []
    ott = [r for r in risultati if r["ottimo"].get("completo")]
    nomi = [r["scenario"]["id"] for r in ott]
    col = {n: COLORI[i % 8] for i, n in enumerate([r["scenario"]["id"] for r in risultati])}
    # punteggi
    crit = list(cfg["ottimizzazione"]["pesi"].keys())
    fig, ax = plt.subplots(figsize=(11, 4.5))
    w = 0.8 / (len(crit) + 1)
    for j, c in enumerate(crit + ["totale"]):
        vals = [r["ottimo"]["completo"]["punteggi"][c] if c != "totale" else r["ottimo"]["completo"]["punteggio_totale"]
                for r in ott]
        ax.bar(np.arange(len(ott)) + j * w, vals, w, label=c, color=(COLORI[j] if c != "totale" else "k"))
    for i, r in enumerate(ott):
        if not r["ottimo"]["completo"]["ammissibile"]:
            ax.text(i + 0.4, 1.02, "non ammissibile", ha="center", color="#c92a2a", fontsize=7)
    ax.set_xticks(np.arange(len(ott)) + 0.4); ax.set_xticklabels(nomi, fontsize=7)
    ax.set_ylim(0, 1.1); ax.set_ylabel("punteggio (0-1)"); ax.legend(fontsize=7, ncol=6)
    ax.set_title("Confronto dei progetti ottimi: punteggi per criterio e totale pesato")
    out += _salva(fig, os.path.join(cartella, "01_punteggi"), formati)
    # radar
    ang = np.linspace(0, 2 * np.pi, len(crit), endpoint=False).tolist()
    fig = plt.figure(figsize=(7, 7)); ax = fig.add_subplot(111, polar=True)
    for r in ott:
        v = [r["ottimo"]["completo"]["punteggi"][c] for c in crit]
        ax.plot(ang + ang[:1], v + v[:1], color=col[r["scenario"]["id"]], label=r["scenario"]["id"])
        ax.fill(ang + ang[:1], v + v[:1], color=col[r["scenario"]["id"]], alpha=0.06)
    ax.set_xticks(ang); ax.set_xticklabels(crit); ax.set_ylim(0, 1)
    ax.legend(fontsize=7, loc="upper right", bbox_to_anchor=(1.35, 1.1))
    ax.set_title("Profilo dei punteggi")
    out += _salva(fig, os.path.join(cartella, "02_radar"), formati)
    # pareto spazio-potenza
    fig, ax = plt.subplots(figsize=(9, 6))
    for r in risultati:
        sid = r["scenario"]["id"]
        for p in r["progetti"]:
            if not p.get("completo") or p["L"] != r["ottimo"]["L"]:
                continue
            x = p["geometria"]["frazione_libera_dopo"] * 100
            y = p["aero"]["P_asse_max"]
            amm = p["completo"]["ammissibile"]
            if not p["geometria"]["componenti_tutti"]:
                ax.scatter(x, y, s=34, marker="x", color=col[sid])
            else:
                ax.scatter(x, y, s=28, facecolors=col[sid] if amm else "none", edgecolors=col[sid])
            ax.annotate(f"{p['D']:.0f}", (x, y), fontsize=6, xytext=(2, 2), textcoords="offset points")
        o = r["ottimo"]
        if o.get("completo"):
            amm = o["completo"]["ammissibile"]
            ax.scatter(o["geometria"]["frazione_libera_dopo"] * 100, o["aero"]["P_asse_max"], s=170, marker="*",
                       facecolors=col[sid] if amm else "white", edgecolors=col[sid] if not amm else "k",
                       linewidths=1.5, label=f"{sid} ({'ottimo' if amm else 'migliore, NON ammissibile'})", zorder=5)
    ax.set_xlabel("volume interno libero dopo batteria, ruote, avionica, ESC (%)\n"
                  "(× = qualche componente non entra: il suo volume è comunque sottratto)")
    ax.set_ylabel("potenza elettrica per asse alla spinta richiesta (W)")
    ax.set_title("Spazio contro potenza al lato ottimo di ogni scenario: un punto per diametro (mm indicati); "
                 "vuoto = non ammissibile", fontsize=9)
    ax.legend(fontsize=7)
    out += _salva(fig, os.path.join(cartella, "03_pareto_spazio_potenza"), formati)
    # sensibilità al diametro
    fig, axs = plt.subplots(1, 3, figsize=(14, 4))
    for r in risultati:
        sid = r["scenario"]["id"]
        best_D = {}
        for p in r["progetti"]:
            if p["L"] != r["ottimo"]["L"]:
                continue
            g = p["geometria"]
            k = p["D"]
            val = (g["frazione_condotti"], g["frazione_libera_dopo"],
                   p["aero"]["P_asse_max"] if p.get("aero") else np.nan)
            if k not in best_D or (not np.isnan(val[2]) and (np.isnan(best_D[k][2]) or val[2] < best_D[k][2])):
                best_D[k] = val
        Ds = sorted(best_D)
        axs[0].plot(Ds, [best_D[d][0] * 100 for d in Ds], "-o", ms=3, color=col[sid], label=sid)
        axs[1].plot(Ds, [best_D[d][1] * 100 for d in Ds], "-o", ms=3, color=col[sid])
        axs[2].plot(Ds, [best_D[d][2] for d in Ds], "-o", ms=3, color=col[sid])
    axs[0].set_ylabel("volume dei condotti (% interno)"); axs[1].set_ylabel("volume libero dopo i componenti (%)")
    axs[2].set_ylabel("potenza per asse (W)")
    for a in axs:
        a.set_xlabel("diametro del condotto alla ventola D (mm)")
    axs[0].legend(fontsize=7)
    fig.suptitle("Sensibilità al diametro, al lato ottimo di ogni scenario (con più varianti: la migliore per diametro)")
    fig.tight_layout()
    out += _salva(fig, os.path.join(cartella, "04_sensibilita_diametro"), formati)
    # perdite a confronto (per asse)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for i, r in enumerate(ott):
        a = r["ottimo"]["aero"]
        c0 = max(a["classi"], key=lambda c: c["P_el"])
        n = c0["n_per_verso"]
        cats = {k: v * n for k, v in c0["perdite_W"].items()}
        cats["energia del getto"] = c0["P_getto"] * n
        x0 = 0
        for k in CAT_COL:
            v = cats.get(k, 0.0)
            ax.bar(i, v, bottom=x0, color=CAT_COL[k], label=k if i == 0 else None, edgecolor="white")
            x0 += v
    ax.set_xticks(range(len(ott))); ax.set_xticklabels(nomi, fontsize=7)
    ax.set_ylabel("potenza utile per asse ripartita (W)")
    ax.set_title("Dove va la potenza delle ventole: perdite per categoria ed energia del getto (per asse)")
    ax.legend(fontsize=7, ncol=3)
    out += _salva(fig, os.path.join(cartella, "05_perdite_per_categoria"), formati)
    # spazio
    fig, ax = plt.subplots(figsize=(10, 4))
    x = np.arange(len(ott))
    g = [r["ottimo"]["geometria"] for r in ott]
    ax.bar(x - 0.27, [gg["frazione_condotti"] * 100 for gg in g], 0.27, label="condotti", color="#1f5bd8")
    ax.bar(x, [gg["frazione_libera_prima"] * 100 for gg in g], 0.27, label="libero prima dei componenti", color="#74c0fc")
    ax.bar(x + 0.27, [gg["frazione_libera_dopo"] * 100 for gg in g], 0.27, label="libero dopo i componenti", color="#2f9e44")
    for i, gg in enumerate(g):
        ax.text(i + 0.27, gg["frazione_libera_dopo"] * 100 + 1, f"cubo libero\n{gg['cubo_libero_mm']:.0f} mm",
                ha="center", fontsize=6)
    ax.set_xticks(x); ax.set_xticklabels(nomi, fontsize=7); ax.set_ylabel("% del volume interno")
    ax.legend(fontsize=7); ax.set_title("Spazio interno dei progetti ottimi")
    out += _salva(fig, os.path.join(cartella, "06_spazio_interno"), formati)
    # stabilità: margine di fase
    fig, ax = plt.subplots(figsize=(8, 5))
    tau = np.linspace(0.005, 1.0, 200)
    for wc, c in ((1.0, "#2f9e44"), (2.0, "#1f5bd8"), (4.0, "#c92a2a")):
        ax.plot(tau * 1000, [DY.margine_fase(t * 2.3, wc) for t in tau], color=c, label=f"banda ω_c = {wc:.0f} rad/s")
    for r in ott:
        cc = r["ottimo"]["completo"]
        ta = cc["t_cambio_verso"] / 2.3
        ax.scatter(ta * 1000, DY.margine_fase(cc["t_cambio_verso"], 2.0), color=col[r["scenario"]["id"]],
                   s=50, zorder=5, label=r["scenario"]["id"])
    ax.axhline(45, color="k", ls="--", lw=0.8)
    ax.text(5, 46, "margine minimo consigliato 45°", fontsize=7)
    ax.set_xlabel("costante di tempo del propulsore τ_a = t_cambio_verso / 2,3 (ms)")
    ax.set_ylabel("margine di fase dell'anello di posizione (°)")
    ax.set_title("Stabilità del controllo di traslazione (regolatore PD, punti a ω_c = 2 rad/s)")
    ax.legend(fontsize=7)
    out += _salva(fig, os.path.join(cartella, "07_stabilita_margine_fase"), formati)
    # ruote di reazione
    fig, ax = plt.subplots(figsize=(10, 4.5))
    lim = cfg["limiti"]["momento_ruote_max_Nms"]
    t_f = cfg["missione"]["finestra_libera_s"]
    for i, r in enumerate(ott):
        rw = r["ottimo"]["completo"]["ruote"]
        parti = [("baricentro fuori asse", rw["coppia_baricentro"] * t_f, "#1f5bd8"),
                 ("squilibrio tra ventole", rw["coppia_squilibrio"] * t_f, "#74c0fc"),
                 ("coppia di reazione dei rotori", rw["coppia_reazione"] * t_f, "#f08c00"),
                 ("momento dei rotori in avvio", rw["H_rotori"], "#c92a2a")]
        b0 = 0
        for nome, v, c in parti:
            ax.bar(i, v, bottom=b0, color=c, label=nome if i == 0 else None)
            b0 += v
    ax.axhline(lim, color="k", ls="--", lw=0.8, label="capacità della ruota (input)")
    ax.set_xticks(range(len(ott))); ax.set_xticklabels(nomi, fontsize=7)
    ax.set_ylabel(f"momento angolare accumulato in {t_f:.0f} s (N·m·s)")
    ax.set_title("Bilancio delle ruote di reazione nella finestra libera")
    ax.legend(fontsize=7)
    out += _salva(fig, os.path.join(cartella, "08_ruote_di_reazione"), formati)
    # autorità e guasti
    fig, axs = plt.subplots(1, 3, figsize=(14, 4))
    F_req = cfg["missione"]["spinta_per_asse_N"]
    for i, r in enumerate(ott):
        cc = r["ottimo"]["completo"]
        c = col[r["scenario"]["id"]]
        axs[0].bar(i, min(cc["forza_max_N"].values()), color=c)
        axs[1].bar(i, min(cc["momento_max_Nm"].values()), color=c)
        axs[2].bar(i, cc["tolleranza_guasto"], color=c)
    axs[0].axhline(F_req, color="#c92a2a", ls="--", lw=0.8)
    axs[2].axhline(1.0, color="#c92a2a", ls="--", lw=0.8)
    axs[0].set_ylabel("forza pura minima sui 6 versi (N)")
    axs[1].set_ylabel("momento puro minimo sui 3 assi (N·m)")
    axs[2].set_ylabel("forza residua / richiesta con 1 ventola guasta")
    for a in axs:
        a.set_xticks(range(len(ott))); a.set_xticklabels(nomi, fontsize=6, rotation=20)
    fig.suptitle("Autorità di controllo (alla massima spinta) e tolleranza ai guasti")
    fig.tight_layout()
    out += _salva(fig, os.path.join(cartella, "09_autorita_guasti"), formati)
    # struttura
    fig, axs = plt.subplots(1, 3, figsize=(14, 4))
    for i, r in enumerate(ott):
        cc = r["ottimo"]["completo"]
        c = col[r["scenario"]["id"]]
        axs[0].bar(i, cc["f1_Hz"], color=c)
        axs[1].bar(i, cc["margine_instabilita"], color=c)
        axs[2].bar(i, sum(cc["EI_condotti_Nm2"]), color=c)
    axs[0].set_ylabel("1° frequenza del tratto con la ventola (Hz)")
    axs[1].set_ylabel("p_critica / suzione massima"); axs[1].set_yscale("log")
    axs[2].set_ylabel("rigidezza flessionale portata dai condotti (N·m²)")
    for a in axs:
        a.set_xticks(range(len(ott))); a.set_xticklabels(nomi, fontsize=6, rotation=20)
    fig.suptitle("Rigidezza e verifiche strutturali dei condotti")
    fig.tight_layout()
    out += _salva(fig, os.path.join(cartella, "10_struttura"), formati)
    # sensibilità all'ambiente
    fig, ax = plt.subplots(figsize=(8, 4.5))
    p_lista = np.linspace(70000, 103000, 12)
    T0 = cfg["aria_progetto"].T
    for r in ott:
        a = r["ottimo"]["aero"]
        c0 = max(a["classi"], key=lambda c: c["P_el"])
        un = copy.deepcopy(c0["unita_rete"])
        F = []
        for p in p_lista:
            _, b = _solve(un, crea_aria("x", p, T0), c0["N_req"])
            F.append(b["spinta"] / c0["F_unita"])
        ax.plot(p_lista / 100, F, color=col[r["scenario"]["id"]], label=r["scenario"]["id"])
    ax.axvline(825, color="#adb5bd", ls="--"); ax.text(826, ax.get_ylim()[0], " cabina 825 mbar", fontsize=7)
    ax.set_xlabel("pressione dell'aria (mbar)"); ax.set_ylabel("spinta / spinta di progetto (stessi giri)")
    ax.set_title("Effetto dell'ambiente: a giri fissi la spinta segue la densità")
    ax.legend(fontsize=7)
    out += _salva(fig, os.path.join(cartella, "11_effetto_ambiente"), formati)
    out += grafico_massa(ott, cfg, os.path.join(cartella, "12_bilancio_massa"), formati)
    out += grafico_lato(risultati, cfg, os.path.join(cartella, "13_lato_cubo"), formati)
    return out


def grafico_lato(risultati, cfg, percorso, formati):
    """Per ogni lato del cubo, il miglior progetto di ogni scenario: punteggio e massa. Stella = lato ottimo."""
    mis = cfg["missione"]
    fig, axs = plt.subplots(1, 2, figsize=(14, 5))
    for k, r in enumerate(risultati):
        sid = r["scenario"]["id"]
        c = COLORI[k % 8]
        per_L = {}
        for p in r["progetti"]:
            cp = p.get("completo")
            if not cp:
                continue
            chiave = (cp["ammissibile"], round(cp["punteggio_totale"], 4))
            if p["L"] not in per_L or chiave > per_L[p["L"]][0]:
                per_L[p["L"]] = (chiave, p)
        if not per_L:
            continue
        Ls = sorted(per_L)
        punt = [per_L[L][1]["completo"]["punteggio_totale"] for L in Ls]
        mass = [per_L[L][1]["completo"]["massa_totale_kg"] for L in Ls]
        amm = [per_L[L][0][0] for L in Ls]
        axs[0].plot(Ls, punt, "-", color=c, lw=1, label=sid)
        axs[1].plot(Ls, mass, "-", color=c, lw=1, label=sid)
        for L, p_, m_, a_ in zip(Ls, punt, mass, amm):
            for ax_, y_ in ((axs[0], p_), (axs[1], m_)):
                ax_.scatter(L, y_, s=26, facecolors=c if a_ else "white", edgecolors=c, zorder=3)
        co = r["ottimo"].get("completo")
        if co:
            Lo = r["ottimo"]["L"]
            axs[0].scatter(Lo, co["punteggio_totale"], marker="*", s=220, facecolors=c, edgecolors="k", zorder=5)
            axs[1].scatter(Lo, co["massa_totale_kg"], marker="*", s=220, facecolors=c, edgecolors="k", zorder=5)
    axs[1].axhline(mis["massa_obiettivo_kg"], color="#2f9e44", ls="--", lw=1, label="massa obiettivo")
    axs[1].axhline(mis["massa_massima_kg"], color="#c92a2a", ls="--", lw=1, label="massa massima ammessa")
    g = cfg["geometria"]
    for ax_ in axs:
        ax_.axvspan(g["lato_cubo_min_mm"], g["lato_cubo_max_mm"], color="#e7f5ff", alpha=0.35, zorder=0)
        ax_.set_xlabel("lato del cubo L (mm)")
    axs[0].set_ylabel("punteggio totale del miglior progetto")
    axs[1].set_ylabel("massa stimata del miglior progetto (kg)")
    axs[0].legend(fontsize=7)
    axs[1].legend(fontsize=7)
    fig.suptitle("Lato del cubo: per ogni L il miglior progetto di ogni scenario (stella = lato ottimo; "
                 "vuoto = non ammissibile). Banda azzurra = intervallo analizzato", fontsize=10)
    fig.tight_layout()
    return _salva(fig, percorso, formati)


# ======================================================================= massa
COL_MASSA = {"componenti fissi": "#ced4da", "telaio e guscio": "#1f5bd8", "condotti e supporti": "#e8590c",
             "propulsione (motori, ESC, cavi)": "#2b8a3e"}


def grafico_massa(ott, cfg, percorso, formati):
    """Massa totale stimata per scenario, divisa per gruppi, con obiettivo e massima."""
    if not ott:
        return []
    mis = cfg["missione"]
    fig, axs = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axs[0]
    nomi = [r["scenario"]["id"] for r in ott]
    for i, r in enumerate(ott):
        mb = r["ottimo"]["completo"]["massa"]
        b0 = 0.0
        for g, c in COL_MASSA.items():
            v = mb["gruppi"][g]
            ax.bar(i, v, bottom=b0, color=c, label=g if i == 0 else None, edgecolor="white")
            if v > 0.12:
                ax.text(i, b0 + v / 2, f"{v:.2f}", ha="center", va="center", fontsize=7)
            b0 += v
        ax.text(i, b0 + 0.04, f"{b0:.2f} kg", ha="center", fontsize=8, fontweight="bold")
    ax.axhline(mis["massa_obiettivo_kg"], color="#2f9e44", ls="--", lw=1,
               label=f"obiettivo {mis['massa_obiettivo_kg']:.1f} kg")
    ax.axhline(mis["massa_massima_kg"], color="#c92a2a", ls="--", lw=1,
               label=f"massima ammessa {mis['massa_massima_kg']:.1f} kg")
    ax.set_xticks(range(len(ott)))
    ax.set_xticklabels(nomi, fontsize=7, rotation=15)
    ax.set_ylabel("massa stimata del cubo (kg)")
    ax.set_ylim(0, max(ax.get_ylim()[1], mis["massa_massima_kg"]) * 1.3)
    ax.set_title("Massa totale stimata (progetto ottimo di ogni scenario)")
    ax.legend(fontsize=7, loc="upper left", ncol=3)
    # dettaglio delle voci che dipendono dalla configurazione
    ax = axs[1]
    voci = [k for k in ott[0]["ottimo"]["completo"]["massa"]["voci"] if k != "componenti fissi"]
    w = 0.8 / len(ott)
    for i, r in enumerate(ott):
        mb = r["ottimo"]["completo"]["massa"]["voci"]
        ax.barh(np.arange(len(voci)) + i * w, [mb[k] * 1000 for k in voci], w, color=COLORI[i % 8],
                label=r["scenario"]["id"])
    ax.set_yticks(np.arange(len(voci)) + 0.4 - w / 2)
    ax.set_yticklabels(voci, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("massa (g)")
    ax.set_title("Voci che cambiano con la configurazione (stime parametriche: TELAIO in INPUT.py)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    return _salva(fig, percorso, formati)
