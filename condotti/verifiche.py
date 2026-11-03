"""Verifiche fisiche automatiche del pacchetto 'condotti'.

    python test_fisica.py

Ogni test confronta il codice con un risultato noto (formula analitica,
conservazione, legge di scala).  Se un test fallisce, i risultati
dell'analisi non vanno usati finché non si è capito perché.
"""
import math
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from condotti.aria import crea_aria                                    # noqa: E402
from condotti import perdite as P                                      # noqa: E402
from condotti import rete as R                                         # noqa: E402
from condotti.ventole import TipoVentola, Ventola                      # noqa: E402
from condotti.geometria import dist_segmenti, dist_segmenti_vett       # noqa: E402
from condotti import prestazioni as PR                                 # noqa: E402

ARIA = crea_aria("prova", 82500.0, 293.15)
TIPO = TipoVentola("prova", phi_d=0.5, psi_d=0.25, psi_0_su_psi_d=1.4, eta_max=0.7, Re_rif=2e5,
                   larghezza_eta=0.6, nu_min=0.35, Z=5, corda_su_D=0.2)
RISULTATI = []


def verifica(nome, condizione, dettaglio=""):
    RISULTATI.append((nome, bool(condizione), dettaglio))
    print(f"[{'OK ' if condizione else 'NO '}] {nome}  {dettaglio}")


def unita_dritta(D=0.045, sigma=0.85, griglie=True, Q_plenum=False):
    De = D * math.sqrt(sigma)
    v = Ventola(TIPO, D, 0.4, 0.3e-3)
    tronco = []
    if griglie:
        tronco.append(R.Griglia("g", D=D, porosita=0.6))
    tronco += [R.Imbocco("i", D=D, r_su_D=0.1), R.Tratto("t1", L=0.06, D1=D),
               R.ElementoVentola("v", L=0.03, ventola=v), R.Tratto("t2", L=0.17, D1=D),
               R.Ugello("u", L=0.05, D1=D, D2=De, semiangolo=8)]
    return R.UnitaRete("u", tronco, [R.Ramo("r", [], R.Uscita("o", D=De, direzione_getto=(-1, 0, 0)))], v,
                       da_plenum=Q_plenum)


def unita_y(D=0.045, alfa=40.0):
    Db = D / math.sqrt(2)
    v = Ventola(TIPO, D, 0.4, 0.3e-3)
    tronco = [R.Imbocco("i", D=D, r_su_D=0.15), R.ElementoVentola("v", L=0.03, ventola=v), R.Tratto("t", L=0.05, D1=D)]
    rami = []
    for k, y in enumerate((0.1, -0.1)):
        el = [R.Giunzione(f"g{k}", D_tronco=D, D_ramo=Db, alfa=alfa), R.Valvola(f"valvola{k + 1}", D=Db),
              R.Tratto(f"r{k}", L=0.1, D1=Db), R.Curva(f"c{k}", L=Db * math.pi / 2, D=Db, R=Db, angolo=alfa)]
        rami.append(R.Ramo(f"ramo{k}", el, R.Uscita(f"o{k}", D=Db, direzione_getto=(-1, 0, 0), posizione=(0.1, y, 0))))
    return R.UnitaRete("y", tronco, rami, v, da_plenum=True)


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


def test_y_simmetrica_e_valvola():
    u = unita_y()
    u.imposta_N(20000)
    sol = R.risolvi([u], ARIA)["y"]
    q1, q2 = sol["Q_rami"]
    verifica("Y simmetrica: portate uguali nei due rami", abs(q1 - q2) / q1 < 1e-6)
    b = R.bilancio_unita(u, sol, ARIA)
    verifica("Y simmetrica: momento nullo", np.linalg.norm(b["momento"]) < 1e-9)
    ctx = {"aperture": {"valvola1": 0.3}}
    sol2 = R.risolvi([u], ARIA, None, ctx)["y"]
    b2 = R.bilancio_unita(u, sol2, ARIA, ctx)
    verifica("valvola chiusa al 30 %: portata spostata sull'altro ramo",
             sol2["Q_rami"][0] < q1 and sol2["Q_rami"][1] > q2)
    verifica("valvola chiusa: portata totale minore", sol2["Q"] < sol["Q"])
    verifica("valvola chiusa: nasce un momento (desaturazione)", np.linalg.norm(b2["momento"]) > 1e-4,
             f"{np.linalg.norm(b2['momento']):.4f} N m")


def test_plenum_accoppiato():
    g = R.Griglia("gp", D=0.1, porosita=0.6, A_frontale=0.004)
    pl = R.Plenum(griglia=g, K_interno=1.0, A_griglia=0.004)
    u1, u2 = unita_dritta(griglie=False, Q_plenum=True), unita_dritta(griglie=False, Q_plenum=True)
    u2.nome = "u2"
    for u in (u1, u2):
        u.imposta_N(20000)
    s1 = R.risolvi([u1], ARIA, pl)
    s2 = R.risolvi([u1, u2], ARIA, pl)
    verifica("plenum condiviso: con due ventole ognuna porta meno aria", s2["u"]["Q"] < s1["u"]["Q"],
             f"{s1['u']['Q'] * 1000:.2f} -> {s2['u']['Q'] * 1000:.2f} L/s")


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


def main():
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
    ko = [r for r in RISULTATI if not r[1]]
    print(f"\n{len(RISULTATI) - len(ko)}/{len(RISULTATI)} verifiche superate")
    return 0 if not ko else 1


if __name__ == "__main__":
    sys.exit(main())
