"""File di uscita del caso: per ogni ambiente grafici (01_grafici), serie temporali (02_dati), sintesi (00_sintesi);
al livello del caso Pale/ (squilibrio dei rotori) e CONFRONTO.md (tabella affiancata degli ambienti)."""
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


def descrivi_regolatore(rg):
    alfa = rg.get("polo_integrale_su_wn", 0.0)
    kp, kd, ki = VO.guadagni(rg["frequenza_propria_rad_s"], rg["smorzamento"], alfa)
    tipo = f"PID (terzo polo in -{alfa:g} wn)" if alfa else "PD"
    return (f"regolatore {tipo}: wn = {rg['frequenza_propria_rad_s']:g} rad/s, zeta = {rg['smorzamento']:g}, "
            f"kp = {kp:.3g} 1/s², kd = {kd:.3g} 1/s, ki = {ki:.3g} 1/s³"
            + (", con feedforward" if rg["feedforward_riferimento"] else ", senza feedforward"))


def descrivi_disturbo(di):
    sin = ""
    if any(di["sinusoide_ampiezza_g"]):
        sin = (f" + sinusoide {di['sinusoide_ampiezza_g']} g a {di['sinusoide_frequenza_Hz']} Hz")
    return (f"bias {di['bias_g']:g} g + rumore gaussiano sigma {di['rumore_sigma_g']:g} g in banda "
            f"{di['rumore_banda_Hz']:g} Hz{sin}; velocità iniziale {di['velocita_iniziale_m_s']:g} m/s; "
            f"Monte Carlo {di['campioni_monte_carlo']} campioni (seme {di['seme']})")


def _salva(fig, percorso, formati):
    out = []
    for f in formati:
        p = f"{percorso}.{f}"
        fig.savefig(p, bbox_inches="tight")
        out.append(p)
    plt.close(fig)
    return out


# ---------------------------------------------------------------- 01_grafici
def grafico_moto(serie, cfg, potenza, percorso, formati):
    """Posizione, velocità, spinta e disturbo sui tre assi; in basso la potenza elettrica (per asse e totale)."""
    ma, at = cfg["MANOVRA"], cfg["ATTUATORE"]
    P_assi, P_tot = potenza
    fig = plt.figure(figsize=(13, 12))
    gs = fig.add_gridspec(5, 3)
    ax = np.empty((4, 3), dtype=object)
    for r in range(4):
        for c in range(3):
            ax[r, c] = fig.add_subplot(gs[r, c], sharex=ax[0, 0] if (r or c) else None)
    for r in range(3):
        for c in range(3):
            plt.setp(ax[r, c].get_xticklabels(), visible=False)
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
    pw = fig.add_subplot(gs[4, :], sharex=ax[0, 0])
    for i, P in enumerate(P_assi):
        pw.plot(serie[0]["t"], P, color=COL[i], lw=0.9, label=f"asse {ASSI[i]}")
    pw.plot(serie[0]["t"], P_tot, "k", lw=1.5, label="totale")
    pw.axvline(ma["tempo_manovra_s"], color="#868e96", lw=0.6, ls=":")
    pw.set_ylabel("potenza elettrica (W)"); pw.set_xlabel("t (s)"); pw.legend(fontsize=7, ncol=4)
    tipo = "PID" if cfg["REGOLATORE"].get("polo_integrale_su_wn", 0.0) else "PD"
    fig.suptitle(f"{cfg['AMBIENTE']['nome']} — caso peggiore sui tre assi: posizione, velocità, spinta, disturbo, potenza "
                 f"(massa puntiforme, {tipo})")
    fig.tight_layout()
    return _salva(fig, percorso, formati)


def grafico_monte_carlo(mc, cfg, percorso, formati):
    """Errore di posizione nel tempo (mediana, 5-95 %, inviluppo) e istogramma dell'errore a fine finestra."""
    ma = cfg["MANOVRA"]
    tol = ma["tolleranza_posizione_mm"]
    inv = mc["inviluppo"]
    fig, ax = plt.subplots(2, 3, figsize=(13, 7))
    for i, a in enumerate(ASSI):
        e = inv[a]
        g = ax[0, i]
        g.fill_between(inv["t"], e["min"], e["max"], color=COL[i], alpha=0.15, lw=0, label="min-max")
        g.fill_between(inv["t"], e["p5"], e["p95"], color=COL[i], alpha=0.35, lw=0, label="5-95 %")
        g.plot(inv["t"], e["p50"], color=COL[i], label="mediana")
        g.axhspan(-tol, tol, color="#adb5bd", alpha=0.3)
        g.axvline(ma["tempo_manovra_s"], color="#868e96", lw=0.6, ls=":")
        g.set_title(f"asse {a}"); g.set_xlabel("t (s)"); g.set_ylabel("x_rif - x (mm)"); g.legend(fontsize=7)
        h = ax[1, i]
        h.hist(e["finale"], bins=30, color=COL[i], alpha=0.8)
        for s in (-tol, tol):
            h.axvline(s, color="#c92a2a", lw=0.8, ls=":")
        h.set_xlabel(f"errore a t = {ma['finestra_s']:g} s (mm)"); h.set_ylabel("campioni")
    fig.suptitle(f"{cfg['AMBIENTE']['nome']}, Monte Carlo del disturbo: {mc['campioni']} campioni, assestati su tutti gli assi "
                 f"{mc['quota_tutti_assestati']:.0%} (banda grigia: tolleranza ±{tol:g} mm)")
    fig.tight_layout()
    return _salva(fig, percorso, formati)


def grafico_pale(pale, cfg, percorso, formati):
    """Squilibrio dei rotori nel Monte Carlo e forza rotante in funzione dei giri."""
    pa = cfg["PALE"]
    U = pale["U_campioni_g_mm"]
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    ax[0].hist(U, bins=40, color=COL[0], alpha=0.8)
    ax[0].axvline(pale["caso_peggiore"]["squilibrio_g_mm"], color="#c92a2a", ls=":", label="caso peggiore")
    ax[0].set_xlabel("squilibrio di un rotore (g·mm)"); ax[0].set_ylabel("rotori")
    ax[0].set_title(f"{pale['campioni']} rotori, densità {pa['densita_min_kg_m3']:g}-{pa['densita_max_kg_m3']:g} kg/m³")
    ax[0].legend(fontsize=7)
    giri = np.linspace(0, pa["giri_massimi_rpm"], 200)
    w2 = (giri * 2 * np.pi / 60) ** 2
    for chiave, nome, col in (("media", "media", COL[0]), ("p95", "95 %", COL[1])):
        ax[1].plot(giri, pale["monte_carlo"]["squilibrio_g_mm"][chiave] * 1e-6 * w2, color=col, label=nome)
    ax[1].plot(giri, pale["caso_peggiore"]["squilibrio_g_mm"] * 1e-6 * w2, color="#c92a2a", ls=":", label="caso peggiore")
    ax[1].axhline(pale["forza_peggiore_su_spinta"] and pale["caso_peggiore"]["forza_N"] / pale["forza_peggiore_su_spinta"],
                  color="k", lw=0.8, ls="--", label="spinta massima di un asse")
    ax[1].axvline(pa["giri_progetto_rpm"], color="#868e96", lw=0.6, ls=":")
    ax[1].set_xlabel("giri/min"); ax[1].set_ylabel("forza rotante di una ventola (N)")
    ax[1].set_title(f"F = U ω²; il cubo oscilla di U / M = {pale['caso_peggiore']['spostamento_cubo_um']:.3f} µm al massimo")
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    return _salva(fig, percorso, formati)


def grafico_spazio_massimo(cfg, percorso, formati):
    """Spazio percorribile da fermo a fermo in funzione del tempo, alla spinta massima."""
    m = cfg["CORPO"]["massa_kg"]
    ma, at, di = cfg["MANOVRA"], cfg["ATTUATORE"], cfg["DISTURBO"]
    t = np.linspace(0.5, ma["finestra_s"], 100)
    fig, ax = plt.subplots(figsize=(8, 5))
    for i in range(3):
        F = min(at["spinta_max_positiva_N"][i], at["spinta_max_negativa_N"][i])
        a_d = (di["bias_g"] + di["sinusoide_ampiezza_g"][i]) * VO.G0
        d0, d1 = VO.spazio_massimo(m, F, a_d, t)
        ax.plot(t, d0, color=COL[i], label=f"{ASSI[i]} senza disturbo")
        ax.plot(t, d1, color=COL[i], ls="--", label=f"{ASSI[i]} disturbo nel caso peggiore")
    ax.axhline(ma["distanza_m"][0], color="k", lw=0.8, ls=":")
    ax.axvline(ma["tempo_manovra_s"], color="k", lw=0.8, ls=":")
    ax.set_xlabel("tempo della manovra (s)"); ax.set_ylabel("spazio massimo da fermo a fermo (m)")
    ax.set_title(f"{cfg['AMBIENTE']['nome']}: spazio percorribile in un tempo dato alla spinta massima (accelera t/2, frena t/2)")
    ax.legend(fontsize=7)
    return _salva(fig, percorso, formati)


# ---------------------------------------------------------------- 02_dati
def scrivi_serie(serie, P_assi, P_tot, passo_integrazione_s, percorso):
    """Serie temporali dei tre assi, potenza per asse e totale, ogni 0,01 s (separatore ;)."""
    with open(percorso, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["t_s"] + [f"{c}_{a}" for a in ASSI for c in NOMI_SERIE] + [f"P_{a}_W" for a in ASSI] + ["P_tot_W"])
        passo = max(1, int(round(0.01 / passo_integrazione_s)))
        for k in range(0, len(serie[0]["t"]), passo):
            riga = [round(float(serie[0]["t"][k]), 6)]
            for s in serie:
                riga += [round(float(s[c][k]), 6) for c in CAMPI_SERIE]
            riga += [round(float(P[k]), 6) for P in P_assi] + [round(float(P_tot[k]), 6)]
            w.writerow(riga)
    return percorso


def scrivi_monte_carlo(mc, percorso):
    """Una riga per campione: disturbo estratto e indicatori per asse (separatore ;)."""
    with open(percorso, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(mc["righe"][0]), delimiter=";")
        w.writeheader()
        for r in mc["righe"]:
            w.writerow({k: (round(v, 6) if isinstance(v, float) else ("" if v is None else v)) for k, v in r.items()})
    return percorso


# ---------------------------------------------------------------- 00_sintesi
def scrivi_riepilogo(riep, percorso):
    with open(percorso, "w", encoding="utf-8") as fh:
        json.dump(riep, fh, indent=2, ensure_ascii=False, default=float)
    return percorso


def scrivi_risultato(riep, cfg, nome_caso, file_scritti, percorso):
    """RISULTATO.md di un ambiente: i numeri su una pagina."""
    ma, at, di, rg, ru = cfg["MANOVRA"], cfg["ATTUATORE"], cfg["DISTURBO"], cfg["REGOLATORE"], cfg["RUOTE"]
    rw, amb, pot = riep["ruote"], riep["ambiente"], riep["potenza_totale"]
    en = cfg["ENERGIA"]
    L = [f"# Dinamica di volo, caso `{nome_caso}`, ambiente `{amb['nome']}`", "",
         f"Run del {riep['data']}, impronta degli input `{riep['impronta']}`. Confronto tra gli ambienti: `../CONFRONTO.md`; "
         "squilibrio delle pale (uguale per tutti gli ambienti): `../Pale/PALE.md`.", "",
         "## Ambiente", "",
         f"- pressione {amb['pressione_Pa']:g} Pa, sigma = pressione / pressione di progetto ({at['pressione_progetto_Pa']:g} Pa) = "
         f"**{amb['sigma']:.4f}**",
         f"- spinta massima = spinta di progetto {amb['spinta_max_progetto_N']} N x sigma = {at['spinta_max_positiva_N']} N (+), "
         f"{at['spinta_max_negativa_N']} N (−)",
         f"- fattore di potenza 1 / sqrt(sigma) = **{amb['fattore_potenza']:.4f}**: potenza per una spinta F = "
         f"P_rif (F / F_rif)^{en['esponente']:g} x {amb['fattore_potenza']:.4f}, con P_rif = {en['potenza_rif_W']:g} W a "
         f"F_rif = {en['spinta_rif_N']:g} N", "",
         "## Input", "",
         f"- massa {riep['massa_kg']:g} kg nel baricentro; manovra {ma['distanza_m']} m in {ma['tempo_manovra_s']:g} s "
         f"(profilo `{ma['profilo']}`), finestra simulata {ma['finestra_s']:g} s, tolleranza {ma['tolleranza_posizione_mm']:g} mm",
         f"- tempo di salita al 90 % {at['tempo_salita_90_s']:g} s",
         f"- {descrivi_regolatore(rg)}",
         f"- disturbo: {descrivi_disturbo(di)}", "",
         "## Risultati per asse, caso peggiore", "",
         f"Bias {di['bias_g']:g} g e velocità iniziale {di['velocita_iniziale_m_s']:g} m/s col modulo pieno su ogni asse, "
         "contro il moto, senza rumore.", "",
         "| asse | errore a fine manovra [mm] | errore max [mm] | sovraelongazione [mm] | assestamento [s] "
         "| spinta max usata [N] | quota della massima | in saturazione [s] | energia [J] | potenza di picco [W] |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for a, x in riep["assi"].items():
        ass = f"{x['tempo_assestamento_s']:.2f}" if x["tempo_assestamento_s"] is not None else "oltre la finestra"
        L.append(f"| {a} | {x['errore_a_T_mm']:.2f} | {x['errore_max_mm']:.2f} | {x['sovraelongazione_mm']:.2f} | {ass} "
                 f"| {x['spinta_max_usata_N']:.3f} | {x['spinta_su_massima']:.0%} | {x['tempo_in_saturazione_s']:.2f} "
                 f"| {x['energia_J']:.1f} | {x['potenza_picco_W']:.2f} |")
    L += ["", f"**Potenza elettrica totale** (somma dei tre assi, batteria {en['tensione_batteria_V']:g} V), caso peggiore: "
          f"picco {pot['potenza_picco_W']:.2f} W, energia nella finestra {pot['energia_J']:.1f} J, potenza media "
          f"{pot['potenza_media_W']:.2f} W, corrente di picco {pot['corrente_picco_A']:.3f} A."]
    mc = riep.get("monte_carlo")
    if mc:
        L += ["", f"## Monte Carlo ({mc['campioni']} campioni, seme {mc['seme']})", "",
              "Bias e velocità iniziale in direzione casuale, rumore gaussiano in banda, fasi della sinusoide casuali. "
              "Valori assoluti: media / 95° percentile / massimo.", "",
              "| asse | errore a fine manovra [mm] | errore a fine finestra [mm] | errore max [mm] "
              "| quota della spinta massima | assestamento [s] | assestati | in tolleranza a fine manovra |",
              "|---|---|---|---|---|---|---|---|"]

        def f3(s, fmt="{:.1f}"):
            return " / ".join("—" if s[k] is None else fmt.format(s[k]) for k in ("media", "p95", "max"))
        for a, x in mc["assi"].items():
            st = x["statistiche"]
            L.append(f"| {a} | {f3(st['errore_a_T_mm'])} | {f3(st['errore_finale_mm'])} | {f3(st['errore_max_mm'])} "
                     f"| {f3(st['spinta_su_massima'], '{:.0%}')} | {f3(st['tempo_assestamento_s'], '{:.2f}')} "
                     f"| {x['quota_assestati']:.0%} | {x['quota_in_tolleranza_a_T']:.0%} |")
        L += ["", f"Assestati su tutti e tre gli assi entro la finestra: **{mc['quota_tutti_assestati']:.0%}** dei campioni "
              "(— = qualche campione non si assesta nella finestra).", "",
              "Potenza elettrica totale (somma dei tre assi), media / 95° percentile / massimo:", "",
              "| picco [W] | energia [J] | potenza media [W] | corrente di picco [A] |", "|---|---|---|---|",
              "| " + " | ".join(f3(mc["potenza_totale"][k], f) for k, f in (
                  ("potenza_picco_W", "{:.2f}"), ("energia_J", "{:.1f}"), ("potenza_media_W", "{:.2f}"),
                  ("corrente_picco_A", "{:.3f}"))) + " |"]
    if not rg.get("polo_integrale_su_wn", 0.0) and di["bias_g"]:
        e_inf = di["bias_g"] * VO.G0 / rg["frequenza_propria_rad_s"] ** 2 * 1000
        L += ["", f"Con il PD un bias costante lascia un errore fisso bias / ωn² = **{e_inf:.1f} mm** "
              f"(tolleranza {ma['tolleranza_posizione_mm']:g} mm): serve l'azione integrale "
              "(`REGOLATORE['polo_integrale_su_wn']` > 0) o una banda più alta."]
    L += ["", "## Spazio massimo e tempo minimo (spinta massima, da fermo a fermo)", "",
          f"| asse | spinta [N] | spazio in {ma['tempo_manovra_s']:g} s [m] | con disturbo [m] "
          "| tempo minimo [s] | con disturbo [s] | disturbo / spinta |",
          "|---|---|---|---|---|---|---|"]
    for s in riep["spazio_massimo"]:
        t1 = f"{s['tempo_min_con_disturbo_s']:.2f}" if s["tempo_min_con_disturbo_s"] else "impossibile"
        L.append(f"| {s['asse']} | {s['spinta_N']:.3f} | {s['spazio_max_senza_disturbo_m']:.3f} "
                 f"| {s['spazio_max_con_disturbo_m']:.3f} | {s['tempo_min_senza_disturbo_s']:.2f} | {t1} "
                 f"| {s['disturbo_sulla_spinta']:.0%} |")
    an = riep["margine_fase_anello"]
    L += ["", "## Attuatore e ruote di reazione", "",
          f"- margine di fase dell'anello simulato ({'PID' if rg.get('polo_integrale_su_wn', 0.0) else 'PD'} + attuatore del "
          f"primo ordine, massa pura): **{an['margine_gradi']:.1f}°** alla pulsazione di taglio {an['pulsazione_taglio_rad_s']:.2f} rad/s"
          + ("" if an["margine_gradi"] >= 45.0 else
             f" → **ATTENZIONE: margine sotto 45°**, il ritardo dell'attuatore è troppo alto per questa banda"),
          "- per confronto, regolatore PD di riferimento con zero a wc/3 (non è l'anello simulato): "
          + ", ".join(f"{p:.0f}° a {wc} rad/s" for wc, p in riep["margine_fase_gradi"].items()),
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


# ---------------------------------------------------------------- livello del caso: Pale/ e CONFRONTO.md
def scrivi_pale(pale, cfg, cartella, formati):
    """Cartella Pale/: grafico, pale.json e PALE.md.  Lo squilibrio non dipende dall'ambiente: si scrive una volta."""
    os.makedirs(cartella, exist_ok=True)
    grafico_pale(pale, cfg, os.path.join(cartella, "pale"), formati)
    with open(os.path.join(cartella, "pale.json"), "w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in pale.items() if k != "U_campioni_g_mm"}, fh, indent=2, ensure_ascii=False, default=float)
    pa, pl = cfg["PALE"], pale
    pg, pm = pl["caso_peggiore"], pl["monte_carlo"]
    L = ["# Pale: squilibrio dei rotori", "",
         "Calcolo unico per tutti gli ambienti (geometria e giri di progetto); la quota sulla spinta massima è riferita alla "
         "spinta di progetto.", "",
         f"{pa['numero_pale']} pale per rotore, ognuna un parallelepipedo {pa['lunghezza_mm']:g} x {pa['larghezza_mm']:g} x "
         f"{pa['spessore_mm']:g} mm (lunghezza x larghezza x spessore) dal mozzo di raggio {pa['raggio_mozzo_mm']:g} mm; "
         f"densità di ogni pala a caso tra {pa['densita_min_kg_m3']:g} e {pa['densita_max_kg_m3']:g} kg/m³, "
         f"quindi massa tra {pl['massa_pala_g']['min']:.3f} e {pl['massa_pala_g']['max']:.3f} g. "
         f"Giri di progetto {pa['giri_progetto_rpm']:g} giri/min ({pl['frequenza_Hz']:.0f} Hz).", "",
         "| grandezza (una ventola) | media | 95 % | caso peggiore |", "|---|---|---|---|"]
    for k, nome, fmt in (("squilibrio_g_mm", "squilibrio [g·mm]", "{:.3f}"), ("forza_N", "forza rotante [N]", "{:.2f}"),
                         ("accelerazione_cubo_g", "accelerazione del cubo [g]", "{:.3f}"),
                         ("spostamento_cubo_um", "oscillazione del cubo [µm]", "{:.3f}"),
                         ("velocita_cubo_mm_s", "velocità di vibrazione del cubo [mm/s]", "{:.3f}")):
        L.append(f"| {nome} | {fmt.format(pm[k]['media'])} | {fmt.format(pm[k]['p95'])} | {fmt.format(pg[k])} |")
    L += ["",
          f"Nel caso peggiore la forza di una ventola è il **{pl['forza_peggiore_su_spinta']:.0%} della spinta massima**, "
          f"ma gira a {pl['frequenza_Hz']:.0f} Hz e il cubo si sposta solo di {pg['spostamento_cubo_um']:.3f} µm "
          f"({pl['spostamento_peggiore_su_un_asse_um']:.3f} µm con {pl['ventole_fuori_asse']} ventole in fase): "
          "sulla traiettoria non pesa. Pesa sulle vibrazioni (cuscinetti, struttura, sensori inerziali): i rotori vanno equilibrati.",
          f"- momento angolare di un rotore: {pl['momento_angolare_rotore_Nms']:.2e} N·m·s; residuo di una coppia "
          f"controrotante con pale di densità diversa: {pl['residuo_coppia_Nms']['p95']:.1e} N·m·s al 95 %, "
          f"{pl['residuo_coppia_Nms']['peggiore']:.1e} N·m·s nel caso peggiore (va alle ruote di reazione).", "",
          "File: `pale.svg`, `pale.json`.", ""]
    percorso = os.path.join(cartella, "PALE.md")
    with open(percorso, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return percorso


def formatta_valore(x):
    """Valore importato in una riga di testo (numeri a 5 cifre, elenchi con lo stesso formato)."""
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(formatta_valore(y) for y in x) + "]"
    return f"{x:.6g}" if isinstance(x, float) else str(x)


def scrivi_confronto(riepiloghi, cfgs, nome_caso, data, dimensionamento, percorso):
    """CONFRONTO.md: tabella affiancata degli ambienti con le grandezze principali."""
    nomi = list(riepiloghi)

    def peggiore(r, k):
        return max(abs(x[k]) for x in r["assi"].values())

    def mc_pot(r, k, fmt):
        if not r["monte_carlo"]:
            return "—"
        s = r["monte_carlo"]["potenza_totale"][k]
        return " / ".join(fmt.format(s[c]) for c in ("media", "p95", "max"))

    def mc_err(r):
        if not r["monte_carlo"]:
            return "—"
        return f"{max(a['statistiche']['errore_a_T_mm']['p95'] for a in r['monte_carlo']['assi'].values()):.2f}"

    def mc_quota(r):
        return f"{r['monte_carlo']['quota_tutti_assestati']:.0%}" if r["monte_carlo"] else "—"

    def sezione(titolo):
        return (f"**{titolo}**",) + ("",) * len(nomi)

    c0, r0 = cfgs[nomi[0]], riepiloghi[nomi[0]]
    righe = [
        sezione("Ambiente"),
        ("pressione [Pa]", lambda r: f"{r['ambiente']['pressione_Pa']:g}"),
        ("sigma = pressione / pressione di progetto", lambda r: f"{r['ambiente']['sigma']:.4f}"),
        ("spinta massima per asse X / Y / Z, verso + [N] (progetto x sigma)",
         lambda r: " / ".join(f"{f:.3f}" for f in r["spinta_max_N"]["positiva"])),
        ("spinta massima per asse X / Y / Z, verso − [N]",
         lambda r: " / ".join(f"{f:.3f}" for f in r["spinta_max_N"]["negativa"])),
        ("fattore di potenza 1 / sqrt(sigma)", lambda r: f"{r['ambiente']['fattore_potenza']:.4f}"),
        sezione("Disturbo e finestra"),
        ("bias [g]", lambda r: f"{r['disturbo']['bias_g']:g}"),
        (f"rumore, sigma [g] (banda {c0['DISTURBO']['rumore_banda_Hz']:g} Hz)", lambda r: f"{r['disturbo']['rumore_sigma_g']:g}"),
        ("velocità iniziale [m/s]", lambda r: f"{r['disturbo']['velocita_iniziale_m_s']:g}"),
        (f"finestra simulata [s] (manovra {r0['tempo_manovra_s']:g} s)", lambda r: f"{r['finestra_s']:g}"),
        sezione("Caso peggiore (valore peggiore dei tre assi)"),
        ("errore a fine manovra [mm]", lambda r: f"{peggiore(r, 'errore_a_T_mm'):.2f}"),
        ("errore massimo [mm]", lambda r: f"{peggiore(r, 'errore_max_mm'):.2f}"),
        ("spinta massima usata [N]", lambda r: f"{peggiore(r, 'spinta_max_usata_N'):.3f}"),
        ("quota della spinta massima", lambda r: f"{peggiore(r, 'spinta_su_massima'):.0%}"),
        ("tempo in saturazione [s]", lambda r: f"{peggiore(r, 'tempo_in_saturazione_s'):.2f}"),
        sezione("Monte Carlo"),
        ("errore a fine manovra, 95° percentile [mm] (asse peggiore)", mc_err),
        ("manovre assestate su tutti gli assi", mc_quota),
        sezione("Potenza elettrica totale (3 assi), caso peggiore"),
        ("potenza di picco [W]", lambda r: f"{r['potenza_totale']['potenza_picco_W']:.2f}"),
        ("energia nella finestra [J]", lambda r: f"{r['potenza_totale']['energia_J']:.1f}"),
        ("potenza media [W]", lambda r: f"{r['potenza_totale']['potenza_media_W']:.2f}"),
        ("corrente di picco [A]", lambda r: f"{r['potenza_totale']['corrente_picco_A']:.3f}"),
        sezione("Potenza elettrica totale, Monte Carlo (media / 95° / massimo)"),
        ("potenza di picco [W]", lambda r: mc_pot(r, "potenza_picco_W", "{:.2f}")),
        ("energia nella finestra [J]", lambda r: mc_pot(r, "energia_J", "{:.1f}")),
        ("corrente di picco [A]", lambda r: mc_pot(r, "corrente_picco_A", "{:.3f}")),
        sezione("Anello di controllo"),
        ("margine di fase [°] (non dipende dall'ambiente)", lambda r: f"{r['margine_fase_anello']['margine_gradi']:.1f}"),
    ]
    L = [f"# Confronto tra gli ambienti, caso `{nome_caso}`", "",
         f"Run del {data}. Un ambiente per colonna; i dettagli sono in `<ambiente>/00_sintesi/RISULTATO.md`.", "",
         f"Spinta massima e potenza seguono la pressione: sigma = pressione / {c0['ATTUATORE']['pressione_progetto_Pa']:g} Pa; "
         "spinta massima = spinta di progetto x sigma; potenza per una spinta F = P_rif (F / F_rif)^esponente / sqrt(sigma). "
         f"Batteria {c0['ENERGIA']['tensione_batteria_V']:g} V. Squilibrio delle pale (uguale per tutti): `Pale/PALE.md`.", "",
         "| grandezza | " + " | ".join(nomi) + " |", "|---|" + "---|" * len(nomi)]
    for r in righe:
        if not callable(r[1]):                            # riga di sezione
            L.append("| " + " | ".join(r) + " |")
        else:
            L.append(f"| {r[0]} | " + " | ".join(r[1](riepiloghi[n]) for n in nomi) + " |")
    L += ["", f"Dati dal dimensionamento (caso `{dimensionamento['caso']}`)", "",
          "| chiave | valore | fonte |", "|---|---|---|"]
    L += [f"| {k} | {formatta_valore(x)} | {dimensionamento['fonti'][k]} |"
          for k, x in dimensionamento["valori"].items() if not k.startswith("_")]
    L += [""] + [f"- ATTENZIONE: {a}" for a in dimensionamento["avvisi"]]
    L.append("")
    with open(percorso, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return percorso
