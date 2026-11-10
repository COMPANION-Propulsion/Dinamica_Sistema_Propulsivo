"""File di uscita del caso: grafici (01_grafici), serie temporali (02_dati), sintesi (00_sintesi)."""
import csv
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402

from . import volo as VO                                           # noqa: E402

ASSI = "XYZ"
COL = ["#1f5bd8", "#e8590c", "#2b8a3e"]
CAMPI_SERIE = ("x", "x_rif", "v", "F", "F_cmd", "a_dist")
NOMI_SERIE = ("x_m", "x_rif_m", "v_m_s", "F_N", "F_cmd_N", "a_dist_m_s2")


def _salva(fig, percorso, formati):
    out = []
    for f in formati:
        p = f"{percorso}.{f}"
        fig.savefig(p, bbox_inches="tight")
        out.append(p)
    plt.close(fig)
    return out


# ---------------------------------------------------------------- 01_grafici
def grafico_moto(serie, cfg, percorso, formati):
    """Posizione, velocità, spinta e disturbo sui tre assi."""
    ma, at = cfg["MANOVRA"], cfg["ATTUATORE"]
    fig, ax = plt.subplots(4, 3, figsize=(13, 10), sharex=True)
    for i, s in enumerate(serie):
        t = s["t"]
        a = ax[0, i]
        a.plot(t, s["x_rif"] * 1000, "k--", lw=1, label="riferimento")
        a.plot(t, s["x"] * 1000, color=COL[i], label="posizione")
        tol = ma["tolleranza_posizione_mm"]
        a.axhspan(ma["distanza_m"][i] * 1000 - tol, ma["distanza_m"][i] * 1000 + tol, color="#adb5bd", alpha=0.3)
        a.set_title(f"asse {ASSI[i]}"); a.set_ylabel("x (mm)"); a.legend(fontsize=7)
        ax[1, i].plot(t, s["v"] * 1000, color=COL[i]); ax[1, i].plot(t, s["v_rif"] * 1000, "k--", lw=1)
        ax[1, i].set_ylabel("v (mm/s)")
        ax[2, i].plot(t, s["F_cmd"], color="#adb5bd", label="comando")
        ax[2, i].plot(t, s["F"], color=COL[i], label="spinta")
        for F in (at["spinta_max_positiva_N"][i], -at["spinta_max_negativa_N"][i]):
            ax[2, i].axhline(F, color="#c92a2a", lw=0.8, ls=":")
        ax[2, i].set_ylabel("F (N)"); ax[2, i].legend(fontsize=7)
        ax[3, i].plot(t, s["a_dist"] / VO.G0 * 1000, color="#868e96")
        ax[3, i].set_ylabel("disturbo (mg)"); ax[3, i].set_xlabel("t (s)")
        for r in range(4):
            ax[r, i].axvline(ma["tempo_manovra_s"], color="#868e96", lw=0.6, ls=":")
    fig.suptitle("S4 — moto sui tre assi: posizione, velocità, spinta, disturbo (massa puntiforme, PD)")
    return _salva(fig, percorso, formati)


def grafico_spazio_massimo(cfg, percorso, formati):
    """Spazio percorribile da fermo a fermo in funzione del tempo, alla spinta massima."""
    m = cfg["CORPO"]["massa_kg"]
    ma, at, di = cfg["MANOVRA"], cfg["ATTUATORE"], cfg["DISTURBO"]
    t = np.linspace(0.5, ma["finestra_s"], 100)
    fig, ax = plt.subplots(figsize=(8, 5))
    for i in range(3):
        F = min(at["spinta_max_positiva_N"][i], at["spinta_max_negativa_N"][i])
        a_d = di["ampiezza_g"][i] * VO.G0
        d0, d1 = VO.spazio_massimo(m, F, a_d, t)
        ax.plot(t, d0, color=COL[i], label=f"{ASSI[i]} senza disturbo")
        ax.plot(t, d1, color=COL[i], ls="--", label=f"{ASSI[i]} disturbo nel caso peggiore")
    ax.axhline(ma["distanza_m"][0], color="k", lw=0.8, ls=":")
    ax.axvline(ma["tempo_manovra_s"], color="k", lw=0.8, ls=":")
    ax.set_xlabel("tempo della manovra (s)"); ax.set_ylabel("spazio massimo da fermo a fermo (m)")
    ax.set_title("Spazio percorribile in un tempo dato alla spinta massima (accelera t/2, frena t/2)")
    ax.legend(fontsize=7)
    return _salva(fig, percorso, formati)


# ---------------------------------------------------------------- 02_dati
def scrivi_serie(serie, passo_integrazione_s, percorso):
    """Serie temporali dei tre assi ogni 0,01 s (separatore ;)."""
    with open(percorso, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["t_s"] + [f"{c}_{a}" for a in ASSI for c in NOMI_SERIE])
        passo = max(1, int(round(0.01 / passo_integrazione_s)))
        for k in range(0, len(serie[0]["t"]), passo):
            riga = [round(float(serie[0]["t"][k]), 6)]
            for s in serie:
                riga += [round(float(s[c][k]), 6) for c in CAMPI_SERIE]
            w.writerow(riga)
    return percorso


# ---------------------------------------------------------------- 00_sintesi
def scrivi_riepilogo(riep, percorso):
    with open(percorso, "w", encoding="utf-8") as fh:
        json.dump(riep, fh, indent=2, ensure_ascii=False, default=float)
    return percorso


def scrivi_risultato(riep, cfg, nome_caso, file_scritti, percorso):
    """RISULTATO.md: i numeri del caso su una pagina."""
    ma, at, di, rg, ru = cfg["MANOVRA"], cfg["ATTUATORE"], cfg["DISTURBO"], cfg["REGOLATORE"], cfg["RUOTE"]
    rw = riep["ruote"]
    L = [f"# Dinamica di volo, caso `{nome_caso}`", "",
         f"Run del {riep['data']}, impronta degli input `{riep['impronta']}`.", "",
         "## Input", "",
         f"- massa {riep['massa_kg']:g} kg nel baricentro; manovra {ma['distanza_m']} m in {ma['tempo_manovra_s']:g} s "
         f"(profilo `{ma['profilo']}`), finestra simulata {ma['finestra_s']:g} s, tolleranza {ma['tolleranza_posizione_mm']:g} mm",
         f"- spinta massima [X, Y, Z]: {at['spinta_max_positiva_N']} N (+), {at['spinta_max_negativa_N']} N (−); "
         f"tempo di salita al 90 % {at['tempo_salita_90_s']:g} s",
         f"- regolatore PD: ωn = {rg['frequenza_propria_rad_s']:g} rad/s, ζ = {rg['smorzamento']:g}"
         f"{', con feedforward' if rg['feedforward_riferimento'] else ', senza feedforward'}",
         f"- disturbo: {di['ampiezza_g']} g a {di['frequenza_Hz']} Hz, fasi {di['fase_gradi']} gradi", "",
         "## Risultati per asse", "",
         "| asse | errore a fine manovra [mm] | errore max [mm] | sovraelongazione [mm] | assestamento [s] "
         "| spinta max usata [N] | quota della massima | in saturazione [s] | energia [J] | potenza di picco [W] |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for a, x in riep["assi"].items():
        ass = f"{x['tempo_assestamento_s']:.2f}" if x["tempo_assestamento_s"] is not None else "oltre la finestra"
        L.append(f"| {a} | {x['errore_a_T_mm']:.1f} | {x['errore_max_mm']:.1f} | {x['sovraelongazione_mm']:.1f} | {ass} "
                 f"| {x['spinta_max_usata_N']:.3f} | {x['spinta_su_massima']:.0%} | {x['tempo_in_saturazione_s']:.2f} "
                 f"| {x['energia_J']:.0f} | {x['potenza_picco_W']:.0f} |")
    L += ["", "## Spazio massimo e tempo minimo (spinta massima, da fermo a fermo)", "",
          f"| asse | spinta [N] | spazio in {ma['tempo_manovra_s']:g} s [m] | con disturbo [m] "
          "| tempo minimo [s] | con disturbo [s] | disturbo / spinta |",
          "|---|---|---|---|---|---|---|"]
    for s in riep["spazio_massimo"]:
        t1 = f"{s['tempo_min_con_disturbo_s']:.2f}" if s["tempo_min_con_disturbo_s"] else "impossibile"
        L.append(f"| {s['asse']} | {s['spinta_N']:.3f} | {s['spazio_max_senza_disturbo_m']:.3f} "
                 f"| {s['spazio_max_con_disturbo_m']:.3f} | {s['tempo_min_senza_disturbo_s']:.2f} | {t1} "
                 f"| {s['disturbo_sulla_spinta']:.0%} |")
    L += ["", "## Attuatore e ruote di reazione", "",
          f"- margine di fase: " + ", ".join(f"{p:.0f}° a {wc} rad/s" for wc, p in riep["margine_fase_gradi"].items()),
          f"- momento accumulato dalle ruote nella finestra: {rw['H_finestra']:.3f} N·m·s = "
          f"**{rw['quota_ruota']:.0%} della capacità** ({ru['momento_ruote_max_Nms']} N·m·s)"
          + (" → **le ruote SATURANO**" if rw["quota_ruota"] > 1 else ""),
          f"- coppie: baricentro {rw['coppia_baricentro']:.2e} N·m, squilibrio {rw['coppia_squilibrio']:.2e} N·m, "
          f"reazione dei rotori {rw['coppia_reazione']:.2e} N·m; momento dei rotori in avvio {rw['H_rotori']:.2e} N·m·s", "",
          "## File", ""]
    L += [f"- `{p}`" for p in file_scritti]
    L.append("")
    with open(percorso, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return percorso
