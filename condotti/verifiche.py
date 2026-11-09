"""Verifiche fisiche automatiche del pacchetto 'condotti'.

le run le eseguono prima dell'analisi (ESECUZIONE["verifiche_fisiche"]);
da sole:  python -m condotti.verifiche

Ogni test confronta il codice con un risultato noto (formula analitica,
conservazione, legge di scala, simmetria).  Se un test fallisce, i
risultati dell'analisi non vanno usati finché non si è capito perché.
"""
import math
import sys
import numpy as np

from .aria import crea_aria
from . import perdite as P
from . import rete as R
from .ventole import TipoVentola, Ventola
from .geometria import dist_segmenti, dist_segmenti_vett, gioco_minimo, Griglia3D, tubi_unita
from . import prestazioni as PR
from . import massa as MA
from .scenari import gen_spigoli_centrati
from .config import lati_del_cubo, cfg_con_lato

ARIA = crea_aria("prova", 82500.0, 293.15)
TIPO = TipoVentola("prova", phi_d=0.5, psi_d=0.25, psi_0_su_psi_d=1.4, eta_max=0.7, Re_rif=2e5,
                   larghezza_eta=0.6, nu_min=0.35, Z=5, corda_su_D=0.2)
RISULTATI = []
_STAMPA = [print]


def verifica(nome, condizione, dettaglio=""):
    RISULTATI.append((nome, bool(condizione), dettaglio))
    _STAMPA[0](f"   [{'OK ' if condizione else 'NO '}] {nome}  {dettaglio}")


def unita_dritta(D=0.045, sigma=0.85, griglie=True):
    De = D * math.sqrt(sigma)
    v = Ventola(TIPO, D, 0.4, 0.3e-3)
    tronco = []
    if griglie:
        tronco.append(R.Griglia("g", D=D, porosita=0.6))
    tronco += [R.Imbocco("i", D=D, r_su_D=0.1), R.Tratto("t1", L=0.06, D1=D),
               R.ElementoVentola("v", L=0.03, ventola=v), R.Tratto("t2", L=0.17, D1=D),
               R.Ugello("u", L=0.05, D1=D, D2=De, semiangolo=8)]
    return R.UnitaRete("u", tronco, [R.Ramo("r", [], R.Uscita("o", D=De, direzione_getto=(-1, 0, 0)))], v)


def test_attrito_laminare():
    for Re in (100, 800, 2000):
        verifica(f"attrito laminare 64/Re a Re={Re}", abs(P.fattore_attrito(Re) - 64 / Re) < 1e-12)


def test_attrito_turbolento():
    # Colebrook a Re = 1e5, tubo liscio: lambda = 0.01799
    lam = P.fattore_attrito(1e5, 0.0)
    verifica("attrito turbolento (Haaland vs Colebrook, liscio, Re 1e5)", abs(lam - 0.01799) / 0.01799 < 0.02,
             f"lambda = {lam:.5f}")


def test_tubo_poiseuille():
    # tratto laminare: Dp = 128 mu L Q / (pi D^4)
    D, L, Q = 0.01, 0.5, 2e-6
    t = R.Tratto("t", L=L, D1=D, rugosita=0.0)
    dp = t.dp(Q, ARIA, {})
    dp_an = 128 * ARIA.mu * L * Q / (math.pi * D ** 4)
    verifica("tratto laminare = Hagen-Poiseuille", abs(dp - dp_an) / dp_an < 1e-9, f"{dp:.4f} vs {dp_an:.4f} Pa")


def test_bilancio_energia_e_spinta():
    u = unita_dritta()
    u.imposta_N(18000)
    sol = R.risolvi([u], ARIA)["u"]
    b = R.bilancio_unita(u, sol, ARIA)
    resid = b["P_utile_ventola"] - b["P_getto"] - b["P_perdite"]
    verifica("bilancio di potenza: utile ventola = getto + perdite", abs(resid) / b["P_utile_ventola"] < 1e-6,
             f"residuo {resid:.2e} W")
    A = R.area(u.rami[0].uscita.D)
    v = sol["Q"] / A
    F = 1.02 * ARIA.rho * A * v * v
    verifica("spinta = beta rho A v^2", abs(F - b["spinta"]) / F < 1e-9)
    st = b["stato_ventola"]
    verifica("potenza all'albero >= potenza utile", st["P_albero"] >= b["P_utile_ventola"])


def test_affinita():
    u = unita_dritta(griglie=False)
    out = {}
    for N in (12000, 24000):
        u.imposta_N(N)
        sol = R.risolvi([u], ARIA)["u"]
        out[N] = (sol["Q"], R.bilancio_unita(u, sol, ARIA)["spinta"])
    rq = out[24000][0] / out[12000][0]
    rf = out[24000][1] / out[12000][1]
    verifica("affinità: Q proporzionale a N (entro 5 %)", abs(rq - 2) / 2 < 0.05, f"Q2/Q1 = {rq:.3f}")
    verifica("affinità: spinta proporzionale a N^2 (entro 8 %)", abs(rf - 4) / 4 < 0.08, f"F2/F1 = {rf:.3f}")


def test_densita():
    u = unita_dritta(griglie=False)
    u.imposta_N(20000)
    F = []
    for p in (82500, 101325):
        aria = crea_aria("x", p, 293.15)
        sol = R.risolvi([u], aria)["u"]
        F.append(R.bilancio_unita(u, sol, aria)["spinta"])
    r = F[1] / F[0]
    verifica("a giri fissi la spinta segue la densità (entro 3 %)", abs(r - 101325 / 82500) / r < 0.03,
             f"F_lab/F_volo = {r:.3f} vs rho = {101325 / 82500:.3f}")


def test_curve_e_diffusore():
    ks = [P.k_curva(rd, 90, 1e5)[0] for rd in (0.6, 1.0, 2.0, 4.0)]
    verifica("perdita in curva decrescente con R/D", all(a > b for a, b in zip(ks, ks[1:])),
             ", ".join(f"{k:.3f}" for k in ks))
    _, av = P.k_ugello(1.5, 10)
    verifica("diffusore a 20° totali segnalato", len(av) == 1)
    k_conv = P.k_ugello(0.7, 8)[0]
    verifica("convergente: perdita piccola (< 0,1 della pressione dinamica d'uscita)", k_conv < 0.1)


def test_vortice_senza_statore():
    v1 = Ventola(TIPO, 0.045, 0.4, 0.3e-3, statore=True)
    v2 = Ventola(TIPO, 0.045, 0.4, 0.3e-3, statore=False)
    s1, s2 = v1.stato(0.02, 20000, ARIA), v2.stato(0.02, 20000, ARIA)
    verifica("senza statore: meno pressione utile", s2["dp_utile"] < s1["dp_utile"])
    verifica("senza statore: coppia sul corpo = coppia del rotore", abs(s2["coppia_corpo"] - s2["coppia"]) < 1e-12)


def test_distanze_segmenti():
    rng = np.random.default_rng(0)
    err = 0.0
    for _ in range(500):
        p1, q1, p2, q2 = [rng.normal(size=3) * 50 for _ in range(4)]
        err = max(err, abs(dist_segmenti(p1, q1, p2, q2) - dist_segmenti_vett(p1[None], q1[None], p2[None], q2[None])[0]))
    verifica("distanza tra segmenti: versione vettoriale = scalare", err < 1e-9, f"errore {err:.1e}")
    d = dist_segmenti(np.array([0., 0, 0]), np.array([10., 0, 0]), np.array([5., -5, 3]), np.array([5., 5, 3]))
    verifica("distanza tra rette sghembe perpendicolari = 3", abs(d - 3) < 1e-12)


def test_allocazione():
    # 4 propulsori simmetrici: forza pura uguale nei due versi
    modi = []
    for k, (y, sgn) in enumerate(((0.1, 1), (-0.1, 1), (0.1, -1), (-0.1, -1))):
        F = np.array([sgn * 1.0, 0, 0])
        r = np.array([0, y, 0.0])
        modi.append({"unita": f"u{k}", "w": np.concatenate([F, np.cross(r, F)])})
    f, m, _ = PR.autorita(modi)
    verifica("allocazione: forza pura +X = 2 N con due propulsori", abs(f["+X"] - 2) < 1e-6)
    verifica("allocazione: forza pura -X = 2 N", abs(f["-X"] - 2) < 1e-6)
    verifica("allocazione: nessuna forza in Y", f["+Y"] < 1e-9)


def _cfg_geometria():
    return {"geometria": {"lato_cubo_mm": 320.0, "parete_cubo_mm": 3.0, "parete_condotto_mm": 1.2,
                          "gioco_tra_condotti_mm": 5.0},
            "elementi": {"semiangolo_ugello_deg": 8.0, "lunghezza_ventola_su_D": 0.7}}


def _chiavi_condotti(lay):
    """Insieme dei condotti come segmenti non orientati (per confrontare simmetrie)."""
    out = set()
    for u in lay.unita:
        P_ = u.tronco.punti
        out.add(frozenset([tuple(np.round(P_[0], 6)), tuple(np.round(P_[-1], 6))]))
    return out


def _specchio(chiavi, asse):
    return {frozenset(tuple(np.round(np.where(np.arange(3) == asse, -np.array(p), np.array(p)), 6))
                      for p in k) for k in chiavi}


def test_spigoli_centrati():
    cfg = _cfg_geometria()
    g_min = cfg["geometria"]["gioco_tra_condotti_mm"]
    lay = gen_spigoli_centrati({"id": "prova", "lunghezza_frazione": 0.8, "spostamento_frazione": 0.0}, 30.0, 0.8, cfg)
    verifica("spigoli centrati: 12 condotti, nessuno irrealizzabile",
             len(lay.unita) == 12 and not any("IRREALIZZABILE" in a for a in lay.avvisi))
    verifica("spigoli centrati: 8 volumetti d'angolo", len(lay.tacche) == 8)
    chiavi = _chiavi_condotti(lay)
    for asse in range(3):
        verifica(f"spigoli centrati: piano di simmetria {'XYZ'[asse]}=0 (centrato)",
                 _specchio(chiavi, asse) == chiavi)
    lay2 = gen_spigoli_centrati({"id": "prova", "lunghezza_frazione": 0.8, "spostamento_frazione": 0.5}, 30.0, 0.8, cfg)
    verifica("spigoli spostati: rompono la simmetria lungo X",
             _specchio(_chiavi_condotti(lay2), 0) != _chiavi_condotti(lay2))
    # gioco minimo su tutta la griglia dei parametri: nessuna intersezione
    peggio = math.inf
    for fl in (0.6, 0.7, 0.8, 0.9, 1.0):
        for fs in (-1.0, -0.5, 0.0, 0.5, 1.0):
            lay_g = gen_spigoli_centrati({"id": "p", "lunghezza_frazione": fl, "spostamento_frazione": fs},
                                         34.0, 0.8, cfg)
            if any("IRREALIZZABILE" in a for a in lay_g.avvisi):
                continue
            peggio = min(peggio, gioco_minimo(lay_g, cfg["geometria"]["parete_condotto_mm"])[0])
    verifica("spigoli centrati: gioco minimo >= gioco richiesto su tutta la griglia",
             peggio >= g_min - 1e-6, f"gioco minimo {peggio:.2f} mm")
    # forza pura: le coppie diagonali si annullano per ogni verso
    M_max = 0.0
    for A in range(3):
        for sg in (1, -1):
            M = np.zeros(3)
            for u in lay2.unita:
                if u.asse == A and u.verso[A] * sg > 0:
                    M += np.cross(u.uscite[0]["pos"], u.verso)
            M_max = max(M_max, float(np.linalg.norm(M)))
    verifica("spigoli spostati: coppie diagonali danno ancora forza pura", M_max < 1e-9, f"|M| max {M_max:.1e}")
    # tre assi equivalenti (solo centrati): rotazione di 120 gradi attorno alla diagonale
    def firma(u, perm):
        return frozenset([tuple(np.round(u.tronco.punti[0][perm], 6)), tuple(np.round(u.tronco.punti[-1][perm], 6))])
    base = {firma(u, [0, 1, 2]) for u in lay.unita}
    ruotato = {firma(u, [2, 0, 1]) for u in lay.unita}
    verifica("spigoli centrati: invarianti per rotazione di 120 gradi", base == ruotato)


def test_struttura_portante():
    """Pareti piene e travi attorno ai condotti (S4 con spessori)."""
    cfg = _cfg_geometria()
    sc = {"id": "p", "lunghezza_frazione": 0.8, "spostamento_frazione": 0.0,
          "spessore_parete_faccia_mm": 10.0, "spessore_attorno_condotto_mm": 6.0, "riempimento": 0.2}
    lay = gen_spigoli_centrati(sc, 30.0, 1.0, cfg)
    verifica("struttura portante: 12 travi + 6 pareti piene", len(lay.solidi) == 18, f"{len(lay.solidi)} solidi")
    lay0 = gen_spigoli_centrati({"id": "p", "lunghezza_frazione": 0.8}, 30.0, 1.0, cfg)
    verifica("senza spessori la struttura portante non c'è", len(lay0.solidi) == 0 and "riempimento" not in lay0.parametri)
    # il foro del condotto resta vuoto: nella griglia l'asse di ogni condotto è un condotto, non struttura
    gr = Griglia3D(lay.L, lay.parete, 2.0)
    for u in lay.unita:
        for p, q, r, _ in tubi_unita(u, cfg["geometria"]["parete_condotto_mm"]):
            gr.capsula(p, q, r, 1)
    for mn, mx in lay.solidi:
        gr.box(mn, mx, 5)
    centro_foro = [gr.occ[tuple(gr.indice((u.tronco.punti[0] + u.tronco.punti[-1]) / 2))] for u in lay.unita]
    verifica("struttura portante: il foro di ogni condotto resta libero dalla struttura",
             all(c == 1 for c in centro_foro))
    verifica("struttura portante: c'è materiale pieno attorno ai condotti", int((gr.occ == 5).sum()) > 0)


def test_lati_del_cubo():
    g = {"lato_cubo_min_mm": 280.0, "lato_cubo_max_mm": 350.0, "lato_cubo_passo_mm": 10.0}
    verifica("lati del cubo: 280-350 passo 10 = 8 valori con gli estremi",
             lati_del_cubo(g) == [280.0, 290.0, 300.0, 310.0, 320.0, 330.0, 340.0, 350.0])
    g2 = dict(g, lato_cubo_passo_mm=25.0)
    verifica("lati del cubo: il massimo è sempre incluso anche se il passo non lo raggiunge",
             lati_del_cubo(g2) == [280.0, 305.0, 330.0, 350.0])
    verifica("lati del cubo: min = max dà un solo lato",
             lati_del_cubo(dict(g, lato_cubo_max_mm=280.0)) == [280.0])
    cfg = _cfg_geometria()
    c2 = cfg_con_lato(cfg, 300.0)
    verifica("cfg_con_lato: cambia solo la copia", c2["geometria"]["lato_cubo_mm"] == 300.0
             and cfg["geometria"]["lato_cubo_mm"] == 320.0)


def test_effetto_del_lato_sugli_spigoli_centrati():
    cfg = _cfg_geometria()
    sc = {"id": "p", "lunghezza_frazione": 0.8, "spostamento_frazione": 0.0}
    c = [gen_spigoli_centrati(sc, 34.0, 0.8, cfg_con_lato(cfg, L)).parametri["estremita_max_mm"]
         for L in (280.0, 320.0, 350.0)]
    verifica("lato del cubo maggiore = più spazio lungo lo spigolo per i condotti",
             c[0] < c[1] < c[2], f"limite estremità {c[0]:.0f}, {c[1]:.0f}, {c[2]:.0f} mm")
    # il limite è mezzo lato meno parete, raggio e gioco: variazione di L/2 per mm di lato
    verifica("il limite delle estremità cresce di mezzo millimetro per ogni millimetro di lato",
             abs((c[2] - c[0]) - 35.0) < 1e-6)


def test_massa_tubo():
    # tubo PETG D 30 mm, parete 1,2 mm, 100 mm: rho * pi * (D + t) * t * L
    m = MA._tubo(1270.0, 30.0, 1.2, 100.0)
    atteso = 1270.0 * math.pi * (32.4e-3 ** 2 - 30e-3 ** 2) / 4 * 0.1
    verifica("massa del tubo = rho * area dell'anello * lunghezza", abs(m - atteso) / atteso < 1e-9, f"{m * 1000:.2f} g")


def test_volo():
    """Dinamica di volo: soluzioni analitiche note."""
    from . import volo as VO
    g = VO.G0
    # massa libera con disturbo sinusoidale, da ferma: con fase 90 gradi x(t) = (a/w^2)(cos wt - 1), picco 2a/w^2
    a_amp, f_Hz = 0.01, 1.0
    s = VO.simula_asse(1.0, 1.0, 2e-3, 0.0, 0.0, 0.0, 1.0,
                       lambda t: VO.disturbo_sinusoidale(t, a_amp, f_Hz, 90.0), 2.0, 1e-4)
    atteso = 2 * a_amp * g / (2 * math.pi * f_Hz) ** 2
    verifica("volo: massa libera con disturbo, picco 2 a / w^2", abs(np.max(np.abs(s["x"])) - atteso) < 0.01 * atteso,
             f"{np.max(np.abs(s['x'])) * 1000:.3f} mm contro {atteso * 1000:.3f} mm")
    # PD senza disturbo e senza ritardo: sovraelongazione del secondo ordine exp(-pi z / sqrt(1 - z^2))
    z = 0.5
    s = VO.simula_asse(1.0, 1e6, 2e-3, 4.0, z, 0.1, 0.0, lambda t: 0 * t, 5.0, 1e-4, riferimento=VO.riferimento_gradino)
    sov = (np.max(s["x"]) - 0.1) / 0.1
    atteso = math.exp(-math.pi * z / math.sqrt(1 - z * z))
    verifica("volo: PD, sovraelongazione del secondo ordine", abs(sov - atteso) < 0.01, f"{sov:.3f} contro {atteso:.3f}")
    # saturazione: la spinta non supera il massimo
    s = VO.simula_asse(2.0, 0.5, 0.1, 5.0, 0.8, 1.0, 1.0, lambda t: 0 * t, 3.0, 1e-3)
    verifica("volo: la spinta resta entro il massimo", float(np.max(np.abs(s["F"]))) <= 0.5 + 1e-9)
    # spostamento da fermo a fermo a spinta costante: d = F t^2 / (4 m)
    d0, _ = VO.spazio_massimo(2.0, 1.0, 0.0, 3.0)
    verifica("volo: spazio da fermo a fermo = F t^2 / (4 m)", abs(float(d0) - 1.0 * 9 / 8) < 1e-12)
    # riferimento a minimo jerk: parte e arriva da fermo
    x, v, ac = VO.riferimento_minjerk(np.array([0.0, 3.0]), 0.3, 3.0)
    verifica("volo: riferimento da fermo a fermo", abs(x[0]) < 1e-12 and abs(x[1] - 0.3) < 1e-12 and abs(v[0]) < 1e-12 and abs(v[1]) < 1e-12)


def esegui(stampa=print):
    """Esegue tutte le verifiche; ritorna (superate, totali)."""
    RISULTATI.clear()
    _STAMPA[0] = stampa
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
    ko = [r for r in RISULTATI if not r[1]]
    return len(RISULTATI) - len(ko), len(RISULTATI)


def main():
    ok, tot = esegui()
    print(f"\n{ok}/{tot} verifiche superate")
    return 0 if ok == tot else 1


if __name__ == "__main__":
    sys.exit(main())
