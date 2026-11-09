"""Generatori parametrici delle disposizioni dei condotti.

Ogni generatore riceve: il dizionario dello scenario (da INPUT.py), il
diametro del condotto alla ventola D [mm], il rapporto d'area dell'ugello
sigma e la configurazione generale; restituisce un Layout.

Convenzione di coppia diagonale: per l'asse A i quattro spigoli paralleli
ad A sono individuati dai segni (su, sv) delle coordinate u = A+1, v = A+2.
Le coppie diagonali D1 = {(+,+), (-,-)} e D2 = {(+,-), (-,+)} sono
simmetriche rispetto al centro: due condotti della stessa coppia che
spingono uguale danno forza pura, senza coppia.
"""
import math
import numpy as np

from .geometria import Percorso, UnitaGeom, Layout

SEGNI = [(1, 1), (1, -1), (-1, -1), (-1, 1)]


def _e(asse, s=1.0):
    v = np.zeros(3)
    v[asse] = s
    return v


def _lung_ugello(D, sigma, semiangolo):
    De = D * math.sqrt(sigma)
    if abs(D - De) < 1e-6:
        return 0.0
    return max(abs(D - De) / (2 * math.tan(math.radians(semiangolo))), 5.0)


def _dati_comuni(cfg, D):
    g = cfg["geometria"]
    L, tw, td = g["lato_cubo_mm"], g["parete_cubo_mm"], g["parete_condotto_mm"]
    h = L / 2
    Ro = D / 2 + td
    return L, tw, td, h, Ro, g["gioco_tra_condotti_mm"]


# -------------------------------------------------------------------------
def gen_sfalsati(sc, D, sigma, cfg):
    """12 (o 6) condotti dritti per tutto il lato, sfalsamento ciclico.

    Ogni condotto è a filo di una faccia e arretrato dall'altra di D_est + gioco:
    X arretra lungo Z, Y lungo X, Z lungo Y.  Le tre rette che si
    incontrerebbero in ogni vertice diventano sghembe a distanza D_est + gioco.
    """
    L, tw, td, h, Ro, g = _dati_comuni(cfg, D)
    p = h - tw - Ro
    q = p - (2 * Ro + g)
    rev = sc.get("reversibile", False)
    s_D1 = sc.get("verso_coppia_D1", -1)
    De = D if rev else D * math.sqrt(sigma)
    Lu = 0.0 if rev else _lung_ugello(D, sigma, cfg["elementi"]["semiangolo_ugello_deg"])
    unita = []
    for A in range(3):
        u, v = (A + 1) % 3, (A + 2) % 3
        for (su, sv) in SEGNI:
            d1 = su * sv > 0
            if rev and not d1:
                continue
            s_th = s_D1 if d1 else -s_D1
            c = np.zeros(3)
            c[u], c[v] = su * p, sv * q
            I, O = c.copy(), c.copy()
            I[A], O[A] = s_th * h, -s_th * h
            nome = f"{'XYZ'[A]}{'+' if su > 0 else '-'}{'+' if sv > 0 else '-'}"
            perc = Percorso("tronco", np.array([I, O]), [], D, De, Lu)
            frac = 0.5 if rev else sc.get("posizione_ventola_frazione", 0.25)
            unita.append(UnitaGeom(
                nome=nome, asse=A, verso=_e(A, s_th), tronco=perc, rami=[],
                s_ventola=frac * L - cfg["elementi"]["lunghezza_ventola_su_D"] * D / 2,
                ingresso={"pos": I, "normale": _e(A, s_th), "D": D},
                uscite=[{"pos": O, "getto": _e(A, -s_th), "D": De}],
                reversibile=rev, statore=not rev))
    return Layout(sc["id"], L, tw, unita, parametri={"p_mm": p, "q_mm": q})


# -------------------------------------------------------------------------
PARITA = {0: +1, 1: -1, 2: +1}   # vertice d'uscita: X e Z sui vertici pari, Y sui dispari


def gen_spigoli_corti(sc, D, sigma, cfg):
    """12 condotti lunghi mezzo spigolo, presa laterale a metà spigolo.

    Le uscite stanno nei vertici, le prese a metà spigolo su una faccia
    adiacente: presa e ugello restano lontani (circa mezzo lato).
    Con la scelta delle parità (X e Z escono nei vertici pari, Y nei
    dispari) in ogni vertice arrivano al massimo due condotti; i condotti Z
    sono arretrati in Y di D_est + gioco per non toccare gli X.
    """
    L, tw, td, h, Ro, g = _dati_comuni(cfg, D)
    a = h - tw - Ro
    delta = 2 * Ro + g
    De = D * math.sqrt(sigma)
    Lu = _lung_ugello(D, sigma, cfg["elementi"]["semiangolo_ugello_deg"])
    xe_frac = sc.get("posizione_presa_frazione", 0.0)
    Rmax_su_D = sc.get("raggio_curva_presa_max_su_D", 1.5)
    dist_fan = sc.get("distanza_ventola_da_curva_su_D", 1.0) * D
    Lf = cfg["elementi"]["lunghezza_ventola_su_D"] * D
    unita, avvisi = [], []
    for A in range(3):
        u, v = (A + 1) % 3, (A + 2) % 3
        w = v                                    # faccia della presa (ciclica)
        for (su, sv) in SEGNI:
            s_D1 = -PARITA[A]
            s_th = s_D1 if su * sv > 0 else -s_D1
            c = np.zeros(3)
            c[u], c[v] = su * a, sv * a
            if A == 2:
                c[v] = sv * (a - delta)
            sw = 1.0 if c[w] > 0 else -1.0
            K = c.copy(); K[A] = s_th * xe_frac * h
            I = K.copy(); I[w] = sw * h
            O = c.copy(); O[A] = -s_th * h
            spazio = h - abs(c[w])
            Rb = min(spazio, Rmax_su_D * D)
            nome = f"{'XYZ'[A]}{'+' if su > 0 else '-'}{'+' if sv > 0 else '-'}"
            perc = Percorso("tronco", np.array([I, K, O]), [Rb], D, De, Lu)
            s_v = (spazio - Rb) + Rb * math.pi / 2 + dist_fan
            if s_v + Lf > np.linalg.norm(O - K) + (spazio - Rb) + Rb * math.pi / 2 - Lu:
                avvisi.append(f"{nome}: tratto dritto troppo corto per la ventola")
            unita.append(UnitaGeom(
                nome=nome, asse=A, verso=_e(A, s_th), tronco=perc, rami=[], s_ventola=s_v,
                ingresso={"pos": I, "normale": _e(w, sw), "D": D},
                uscite=[{"pos": O, "getto": _e(A, -s_th), "D": De}]))
    return Layout(sc["id"], L, tw, unita, avvisi=avvisi, parametri={"a_mm": a, "delta_mm": delta})


# -------------------------------------------------------------------------
def gen_spigoli_centrati(sc, D, sigma, cfg):
    """12 condotti dritti centrati sugli spigoli, accorciati e/o spostati; volumetti tolti ai vertici.

    Configurazione di base: ogni spigolo ha un condotto parallelo a sé, tangente alle due facce
    che lo formano (asse a distanza a = hi - Ro dal centro del lato).  Le tre rette di un vertice
    si incontrerebbero nel vertice.  Per eliminare l'intersezione:
      - l'estremità di ogni condotto resta a distanza <= c = a - (2 Ro + g) dal piano del vertice
        (c è il limite di gioco con i due condotti che arrivano nello stesso vertice);
      - il volumetto d'angolo, tolto al vertice, comincia dalle estremità dei condotti e arriva
        alla faccia interna: attraverso di lui i condotti aspirano e soffiano verso l'esterno.
    Due parametri (sezione 11 di INPUT.py):
      lunghezza_frazione     lunghezza del condotto / lunghezza massima 2c (1 = arriva al limite)
      spostamento_frazione   spostamento lungo lo spigolo, in frazione del margine disponibile;
                             0 = centrato, con i tre piani di simmetria
    Ogni condotto è spinto nel verso del suo asse; le coppie diagonali (come in S1) danno forza pura.
    Gli spostamenti sono uguali per tutti gli spigoli nel verso del loro asse: si conserva la simmetria
    ruotata di 120° attorno alla diagonale.
    """
    L, tw, td, h, Ro, g = _dati_comuni(cfg, D)
    hi = h - tw                               # faccia interna
    a = hi - Ro                               # asse del condotto: tangente alle due facce dello spigolo
    c = a - (2 * Ro + g)                      # distanza massima delle estremità dal piano del vertice
    De = D * math.sqrt(sigma)
    Lu = _lung_ugello(D, sigma, cfg["elementi"]["semiangolo_ugello_deg"])
    Lf = cfg["elementi"]["lunghezza_ventola_su_D"] * D
    avvisi = []
    if c <= 0:
        avvisi.append("IRREALIZZABILE: spigolo troppo piccolo per due condotti con il gioco richiesto")
        return Layout(sc["id"], L, tw, [], avvisi=avvisi)
    fr_L = min(max(sc.get("lunghezza_frazione", 0.8), 0.0), 1.0)
    ell = fr_L * 2 * c
    # lo spostamento è limitato: il condotto deve restare a cavallo del centro e non superare c
    margine = min(c - ell / 2, ell / 2)
    delta = min(max(sc.get("spostamento_frazione", 0.0), -1.0), 1.0) * margine
    if ell < Lf + Lu + 0.6 * D:
        avvisi.append(f"IRREALIZZABILE: condotto di {ell:.0f} mm troppo corto per ventola e ugello")
    s_D1 = sc.get("verso_coppia_D1", -1)
    frac_v = sc.get("posizione_ventola_frazione", 0.3)
    s_v = min(max(frac_v * ell - Lf / 2, 0.3 * D), max(ell - Lu - Lf - 0.1 * D, 0.0))
    unita = []
    for A in range(3):
        u, v = (A + 1) % 3, (A + 2) % 3
        for (su, sv) in SEGNI:
            s_th = s_D1 if su * sv > 0 else -s_D1
            c0 = np.zeros(3)
            c0[u], c0[v] = su * a, sv * a
            I, O = c0.copy(), c0.copy()
            I[A] = delta + s_th * ell / 2          # presa: estremità dal lato della spinta
            O[A] = delta - s_th * ell / 2          # uscita: estremità opposta, il getto va in -s_th
            nome = f"{'XYZ'[A]}{'+' if su > 0 else '-'}{'+' if sv > 0 else '-'}"
            unita.append(UnitaGeom(
                nome=nome, asse=A, verso=_e(A, s_th),
                tronco=Percorso("tronco", np.array([I, O]), [], D, De, Lu), rami=[], s_ventola=s_v,
                ingresso={"pos": I, "normale": _e(A, s_th), "D": D},
                uscite=[{"pos": O, "getto": _e(A, -s_th), "D": De}]))
    # volumetti d'angolo: da ciascuna estremità alla faccia interna (sul lato di ogni vertice)
    e_piu, e_meno = ell / 2 + delta, ell / 2 - delta
    volumetti = []
    for sx in (1, -1):
        for sy in (1, -1):
            for sz in (1, -1):
                mn, mx = np.zeros(3), np.zeros(3)
                for j, sg in enumerate((sx, sy, sz)):
                    e = e_piu if sg > 0 else e_meno
                    if sg > 0:
                        mn[j], mx[j] = e, hi
                    else:
                        mn[j], mx[j] = -hi, -e
                volumetti.append((mn, mx))
    # struttura portante (opzionale): pareti piene dietro le 6 facce e una trave attorno a ogni condotto.
    # La trave è un prisma di sezione quadrata (raggio esterno del condotto + spessore), che arriva fino alle
    # due facce dello spigolo e va da un'estremità all'altra del condotto; i fori dei condotti restano vuoti.
    solidi, par_str = [], {}
    t_f, t_c = sc.get("spessore_parete_faccia_mm"), sc.get("spessore_attorno_condotto_mm")
    if t_f is not None and t_c is not None:
        sp_extra = max(float(t_f) - tw, 0.0)           # la parete esterna (tw) è già fuori dalla griglia
        for A in range(3):
            for sg in (1, -1):
                mn, mx = np.full(3, -hi), np.full(3, hi)
                if (A, sg) == tuple(cfg.get("faccia_sportellino", ())):
                    continue                                   # lo sportellino della batteria resta aperto (solo pelle)
                if sg > 0:
                    mn[A] = hi - sp_extra
                else:
                    mx[A] = -hi + sp_extra
                if sp_extra > 0:
                    solidi.append((mn, mx))
        w = Ro + float(t_c)
        for A in range(3):
            u, v = (A + 1) % 3, (A + 2) % 3
            for (su, sv) in SEGNI:
                mn, mx = np.zeros(3), np.zeros(3)
                mn[A], mx[A] = delta - ell / 2, delta + ell / 2
                for j, sg in ((u, su), (v, sv)):
                    centro = sg * a
                    mn[j], mx[j] = max(centro - w, -hi), min(centro + w, hi)
                solidi.append((mn, mx))
        par_str = {"spessore_parete_faccia_mm": float(t_f), "spessore_attorno_condotto_mm": float(t_c),
                   "riempimento": float(sc.get("riempimento", 1.0))}
    return Layout(sc["id"], L, tw, unita, tacche=volumetti, solidi=solidi, avvisi=avvisi,
                  parametri={"lunghezza_condotto_mm": ell, "spostamento_mm": delta, "asse_condotto_mm": a,
                             "estremita_max_mm": c, **par_str})


GENERATORI = {
    "sfalsati": gen_sfalsati,
    "spigoli_corti": gen_spigoli_corti,
    "spigoli_centrati": gen_spigoli_centrati,
}


def genera_layout(sc, D, sigma, cfg):
    """Layout dello scenario (sc già unito alla variante geometrica)."""
    return GENERATORI[sc["topologia"]](sc, D, sigma, cfg)
