"""Generatori parametrici delle disposizioni dei condotti.

Ogni generatore riceve: il dizionario dello scenario (dal database), il
diametro del condotto alla ventola D [mm], il rapporto d'area dell'ugello
sigma e la configurazione generale; restituisce un Layout.

Convenzione di coppia diagonale: per l'asse A i quattro spigoli paralleli
ad A sono individuati dai segni (su, sv) delle coordinate u = A+1, v = A+2.
Le coppie diagonali D1 = {(+,+), (-,-)} e D2 = {(+,-), (-,+)} sono
simmetriche rispetto al centro: due condotti della stessa coppia che
spingono uguale danno forza pura, senza coppia.
"""
import itertools
import math
import numpy as np

from .geometria import Percorso, UnitaGeom, Layout, dist_segmenti

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
def gen_spigoli_pieni(sc, D, sigma, cfg):
    """12 condotti per tutto lo spigolo, scalino (S) vicino ai vertici.

    Nel tratto centrale il condotto sta a filo dei due lati (spigolo vero);
    vicino ai vertici rientra di D_est + gioco con due curve (sfalsamento
    ciclico solo dove serve).  Il tratto d'estremità deve coprire tutta la
    zona d'incrocio: se lo spigolo non basta lo scenario è irrealizzabile.
    Opzione: ugello inclinato di 'angolo_deflessione_deg' verso il centro
    della faccia per allontanare il getto dalle prese vicine (perdita cos).
    """
    L, tw, td, h, Ro, g = _dati_comuni(cfg, D)
    a = h - tw - Ro
    delta = 2 * Ro + g
    De = D * math.sqrt(sigma)
    Lu = _lung_ugello(D, sigma, cfg["elementi"]["semiangolo_ugello_deg"])
    th = math.radians(sc.get("angolo_scalino_deg", 30))
    ell_end = tw + 2 * Ro + delta + 2.0
    ell_s = delta / math.tan(th)
    Rj = sc.get("raggio_scalino_su_D", 1.5) * D
    defl = math.radians(sc.get("angolo_deflessione_deg", 0.0))
    avvisi = []
    medio = L - 2 * (ell_end + ell_s)
    if medio < 0:
        avvisi.append(f"IRREALIZZABILE: le zone d'estremità ({ell_end + ell_s:.0f} mm per lato) superano il mezzo spigolo")
    unita = []
    Lf = cfg["elementi"]["lunghezza_ventola_su_D"] * D
    for A in range(3):
        u, v = (A + 1) % 3, (A + 2) % 3
        for (su, sv) in SEGNI:
            s_D1 = -PARITA[A]
            s_th = s_D1 if su * sv > 0 else -s_D1
            c = np.zeros(3); c[u], c[v] = su * a, sv * a
            ci = c.copy(); ci[v] = sv * (a - delta)
            x1 = h - ell_end
            x2 = max(h - ell_end - ell_s, 0.0)
            pts = []
            for coord, base in [(h, ci), (x1, ci), (x2, c), (-x2, c), (-x1, ci), (-h, ci)]:
                p_ = base.copy(); p_[A] = s_th * coord
                pts.append(p_)
            pts = np.array(pts)
            if medio <= 0:          # degenerazione: niente tratto centrale
                pts = np.delete(pts, 3, axis=0)
            nome = f"{'XYZ'[A]}{'+' if su > 0 else '-'}{'+' if sv > 0 else '-'}"
            perc = Percorso("tronco", pts, [Rj] * (len(pts) - 2), D, De, Lu)
            # ventola nel primo tratto dritto se ci sta, altrimenti nel tratto centrale
            s_v = 0.3 * D
            if ell_end - Rj * math.tan(th / 2) - 0.3 * D < Lf:
                s_v = ell_end + ell_s + 0.5 * D
            getto = _e(A, -s_th) * math.cos(defl)
            # inclinazione verso il centro della faccia (coppia diagonale: si compensa)
            lat = -np.array([0.0, 0.0, 0.0]); lat[u] = -su; lat[v] = -sv
            lat = lat / np.linalg.norm(lat)
            getto = getto + lat * math.sin(defl)
            getto = getto / np.linalg.norm(getto)
            unita.append(UnitaGeom(
                nome=nome, asse=A, verso=_e(A, s_th), tronco=perc, rami=[], s_ventola=s_v,
                ingresso={"pos": pts[0], "normale": _e(A, s_th), "D": D},
                uscite=[{"pos": pts[-1], "getto": getto, "D": De}]))
    return Layout(sc["id"], L, tw, unita, avvisi=avvisi,
                  parametri={"tratto_estremita_mm": ell_end, "scalino_mm": ell_s, "tratto_centrale_mm": medio})


# -------------------------------------------------------------------------
def _profondita_modulo(cfg, A, s_f):
    """Profondità del modulo riservato dietro la faccia (A, s_f), 0 se non c'è."""
    for (ax, sg, wu, wv, dep) in cfg["zone_riservate"].values():
        if ax == A and sg == s_f:
            return dep
    return 0.0


def gen_y6_plenum(sc, D, sigma, cfg, segni_giunzione=None, diagonali_assi=None):
    """6 ventole unidirezionali, una per verso, condotto sdoppiato a Y.

    La ventola del verso +X spinge l'aria fuori dalla faccia -X attraverso
    due ugelli simmetrici rispetto al centro (margini opposti della faccia o
    angoli opposti se 'ugelli_diagonali').  La giunzione sta sul piano
    bisettore dei due ugelli, così i due rami sono lunghi uguali.
    Forma 'spaziale': stelo perpendicolare alla faccia, rami obliqui verso gli ugelli.
    Forma 'piatta': stelo e rami in uno strato parallelo alla faccia, più profondo
      del modulo riservato; i rami piegano di 90° solo sotto gli ugelli (giunzione a T).
    Aspirazione: dal volume interno (plenum), alimentato da una griglia
    sulla faccia libera (-X).  Le valvole sui rami parzializzano un ugello
    per creare coppia e desaturare le ruote di reazione.
    """
    L, tw, td, h, Ro, g = _dati_comuni(cfg, D)
    kappa = sc.get("rapporto_area_rami", 1.0)
    Db = D * math.sqrt(kappa / 2.0)
    De = Db * math.sqrt(sigma)
    Rob = Db / 2 + td
    Lu = _lung_ugello(Db, sigma, cfg["elementi"]["semiangolo_ugello_deg"])
    forma = sc.get("forma_y", "spaziale")
    margine = sc.get("margine_ugello_mm", 4.0)
    e_off = h - tw - Rob - margine
    r_j = sc.get("raggio_giunzione_frazione", 0.55) * h
    d_j0 = sc.get("profondita_giunzione_frazione", 0.45) * h
    Lf = cfg["elementi"]["lunghezza_ventola_su_D"] * D
    stelo = sc.get("lunghezza_stelo_su_D", 0.4) * D + Lf + sc.get("distanza_ventola_giunzione_su_D", 1.0) * D
    Rb = sc.get("raggio_curva_ramo_su_D", 1.0) * Db
    n_valv = sc.get("valvole_per_unita", 2)
    unita, avvisi = [], []
    facce = [(A, s) for A in range(3) for s in (1, -1)]
    if segni_giunzione is None:
        segni_giunzione = [1, -1, 1, -1, 1, -1]
    if diagonali_assi is None:
        diagonali_assi = [1, 1, 1]
    for k, (A, s_f) in enumerate(facce):
        t, w = (A + 2) % 3, (A + 1) % 3
        if sc.get("ugelli_diagonali", False):
            dg = diagonali_assi[A]
            n1, n2 = np.array([e_off, dg * e_off]), np.array([-e_off, -dg * e_off])
            bis = np.array([-dg * 1.0, 1.0]) / math.sqrt(2)
        else:
            n1, n2 = np.array([e_off, 0.0]), np.array([-e_off, 0.0])
            bis = np.array([0.0, 1.0])

        def P(depth, tw_):
            p_ = np.zeros(3)
            p_[A] = s_f * (h - depth)
            p_[t], p_[w] = tw_[0], tw_[1]
            return p_

        if forma == "piatta":
            d_j = max(d_j0, _profondita_modulo(cfg, A, s_f) + Rob + 6.0, Rb + Lu + 5.0)
            jtw = np.zeros(2)
            S_in = P(d_j, jtw + segni_giunzione[k] * stelo * bis)
            J = P(d_j, jtw)
            rami = []
            for i, nk in enumerate((n1, n2)):
                pts = np.array([J, P(d_j, nk), P(0.0, nk)])
                rami.append(Percorso(f"ramo{i + 1}", pts, [Rb], Db, De, Lu))
        else:
            d_j = d_j0
            jtw = segni_giunzione[k] * r_j * bis
            ang_ramo = math.degrees(math.atan2(np.linalg.norm(n1 - jtw), max(d_j - (Lu + Rb + 5), 1.0)))
            d_b = Lu + Rb * math.tan(math.radians(ang_ramo) / 2) + 5.0
            if d_j <= d_b + 5:
                avvisi.append(f"faccia {'+' if s_f > 0 else '-'}{'XYZ'[A]}: giunzione troppo vicina alla faccia")
            S_in, J = P(d_j + stelo, jtw), P(d_j, jtw)
            rami = []
            for i, nk in enumerate((n1, n2)):
                pts = np.array([J, P(d_b, nk), P(0.0, nk)])
                rami.append(Percorso(f"ramo{i + 1}", pts, [Rb], Db, De, Lu))
        tronco = Percorso("stelo", np.array([S_in, J]), [], D)
        valv = [{"ramo": i, "nome": f"valvola{i + 1}"} for i in range(n_valv)]
        segno = "+" if -s_f > 0 else "-"
        unita.append(UnitaGeom(
            nome=f"Y{segno}{'XYZ'[A]}", asse=A, verso=_e(A, -s_f), tronco=tronco, rami=rami,
            s_ventola=sc.get("lunghezza_stelo_su_D", 0.4) * D,
            ingresso=None,
            uscite=[{"pos": rami[0].punti[-1], "getto": _e(A, s_f), "D": De},
                    {"pos": rami[1].punti[-1], "getto": _e(A, s_f), "D": De}],
            valvole=valv, da_plenum=True))
    A_g = sc.get("area_griglia_plenum_mm2", None)
    lay = Layout(sc["id"], L, tw, unita, avvisi=avvisi,
                 parametri={"D_ramo_mm": Db, "r_giunzione_mm": r_j, "forma_y": forma})
    lay.plenum = {"faccia": (0, -1), "pos": np.array([-h, 0.0, 0.0]), "normale": np.array([-1.0, 0, 0]),
                  "area_mm2": A_g}
    return lay


def gen_y6_ottimizza_segni(sc, D, sigma, cfg, parete_condotto):
    """Sceglie lato della giunzione (e diagonale, se ugelli diagonali) col gioco migliore."""
    from .geometria import gioco_minimo
    migliore, gm, scelta = None, -math.inf, None
    diag_opz = list(itertools.product([1, -1], repeat=3)) if sc.get("ugelli_diagonali", False) else [(1, 1, 1)]
    for dg in diag_opz:
        for tre in itertools.product([1, -1], repeat=3):
            segni = [tre[0], -tre[0], tre[1], -tre[1], tre[2], -tre[2]]
            lay = gen_y6_plenum(sc, D, sigma, cfg, segni, list(dg))
            g_, _ = gioco_minimo(lay, parete_condotto)
            if g_ > gm:
                gm, migliore, scelta = g_, lay, (segni, list(dg))
    migliore.parametri["segni_giunzione"] = scelta
    return migliore


GENERATORI = {
    "sfalsati": gen_sfalsati,
    "spigoli_corti": gen_spigoli_corti,
    "spigoli_pieni": gen_spigoli_pieni,
    "y6_plenum": gen_y6_plenum,
}


def genera_layout(sc, D, sigma, cfg, segni=None):
    """Layout dello scenario; per le Y6 'segni' riusa i lati di giunzione già scelti."""
    topo = sc["topologia"]
    if topo == "y6_plenum":
        if segni is not None:
            lay = gen_y6_plenum(sc, D, sigma, cfg, list(segni[0]), list(segni[1]))
            lay.parametri["segni_giunzione"] = segni
            return lay
        if sc.get("cerca_lato_giunzione", True):
            return gen_y6_ottimizza_segni(sc, D, sigma, cfg, cfg["geometria"]["parete_condotto_mm"])
    return GENERATORI[topo](sc, D, sigma, cfg)
