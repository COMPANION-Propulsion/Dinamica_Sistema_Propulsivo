"""Verifiche automatiche della dinamica di volo contro soluzioni analitiche note.

run_dinamica.py le esegue prima della simulazione (ESECUZIONE["verifiche"]);
da sole:  python -m dinamica_designer.verifiche

Se un test fallisce, i risultati della simulazione non vanno usati finché non si è capito perché.
"""
import math
import sys
import numpy as np

from . import cli as CLI
from . import pale as PA
from . import propulsore as DY
from . import volo as VO

RISULTATI = []
_STAMPA = [print]


def verifica(nome, condizione, dettaglio=""):
    RISULTATI.append((nome, bool(condizione), dettaglio))
    _STAMPA[0](f"   [{'OK ' if condizione else 'NO '}] {nome}  {dettaglio}")


def test_volo():
    """Dinamica di volo: soluzioni analitiche note."""
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


def test_disturbo():
    """Disturbo del volo parabolico: bias, velocità iniziale, rumore in banda, azione integrale."""
    g = VO.G0
    # massa libera, bias costante e velocità iniziale: x(t) = v0 t - a t^2 / 2 (RK4 esatto sui polinomi)
    a, v0, t_f = 0.01 * g, 0.01, 3.0
    s = VO.simula_asse(5.0, 1.0, 0.1, 0.0, 0.0, 0.0, 1.0, lambda t: a + 0 * t, t_f, 1e-3, v0=v0)
    atteso = v0 * t_f - 0.5 * a * t_f ** 2
    verifica("disturbo: massa libera con bias e v0, x = v0 t - a t^2 / 2", abs(s["x"][-1] - atteso) < 1e-9,
             f"{s['x'][-1] * 1000:.3f} mm contro {atteso * 1000:.3f} mm")
    # rumore in banda: deviazione standard e nessuna potenza sopra la banda
    rng = np.random.default_rng(0)
    dt, n = 1e-3, 200_001
    r = VO.rumore_in_banda(n, dt, 0.002 * g, 1.0, rng, 4)
    sd = float(np.std(r)) / (0.002 * g)
    spettro = np.abs(np.fft.rfft(r, axis=-1)) ** 2
    f = np.fft.rfftfreq(n, dt)
    fuori = float(spettro[:, f > 1.0].sum() / spettro.sum())
    verifica("disturbo: rumore in banda, deviazione standard = sigma", abs(sd - 1) < 0.05, f"{sd:.3f} sigma")
    verifica("disturbo: rumore in banda, niente potenza sopra la banda", fuori < 1e-12, f"quota {fuori:.1e}")
    # PD con bias costante: errore fisso a / wn^2;  PID: errore che va a zero
    wn, z = 2.0, 0.8
    s = VO.simula_asse(5.0, 1e6, 1e-3, wn, z, 0.0, 1.0, lambda t: a + 0 * t, 20.0, 1e-3)
    verifica("disturbo: PD con bias, errore fisso a / wn^2", abs(-s["x"][-1] - a / wn ** 2) < 1e-3 * a / wn ** 2,
             f"{-s['x'][-1] * 1000:.2f} mm contro {a / wn ** 2 * 1000:.2f} mm")
    s = VO.simula_asse(5.0, 1e6, 1e-3, wn, z, 0.0, 1.0, lambda t: a + 0 * t, 30.0, 1e-3, alfa_integrale=0.5)
    verifica("disturbo: PID con bias, errore che va a zero", abs(s["x"][-1]) < 1e-3 * a / wn ** 2,
             f"{abs(s['x'][-1]) * 1e6:.3f} µm")
    # N campioni insieme = N simulazioni separate
    ad = np.array([[a] * 2001, [-a] * 2001])
    insieme = VO.simula_asse(5.0, 1.0, 0.1, wn, z, 0.3, 1.0, ad, 2.0, 1e-3, v0=[0.01, -0.01], alfa_integrale=0.5)
    ok = all(np.allclose(VO.simula_asse(5.0, 1.0, 0.1, wn, z, 0.3, 1.0, ad[j], 2.0, 1e-3, v0=[0.01, -0.01][j],
                                        alfa_integrale=0.5)["x"], insieme["x"][j], atol=1e-12) for j in range(2))
    verifica("disturbo: simulazione di N campioni insieme uguale alle singole", ok)


def test_pale():
    """Squilibrio dei rotori: casi con risultato noto."""
    r = 0.016
    U = max(float(PA.squilibrio([1e-4] * Z, r)) for Z in (2, 3, 5, 7))
    verifica("pale: pale uguali, squilibrio nullo", U < 1e-18, f"{U:.1e} kg m")
    # caso peggiore: confronto con tutte le 2^Z combinazioni di pale al minimo e al massimo
    ok = True
    for Z in (2, 3, 4, 5, 6, 7):
        tutte = np.array([[(s >> k) & 1 for k in range(Z)] for s in range(2 ** Z)], float)
        ok &= abs(float(np.max(PA.squilibrio(tutte, 1.0))) - PA.fattore_peggiore(Z)) < 1e-12
    verifica("pale: fattore del caso peggiore uguale al massimo su tutte le combinazioni (Z = 2..7)", ok)
    dm = 1e-5
    U = float(PA.squilibrio([1e-4 + dm, 1e-4, 1e-4], r))
    verifica("pale: una pala più pesante di dm, U = dm r_cg", abs(U - dm * r) < 1e-15, f"{U:.3e} contro {dm * r:.3e} kg m")
    # caso peggiore = una pala al massimo, le altre al minimo: nessun campione casuale lo supera
    pa = dict(numero_pale=3, lunghezza_mm=10.0, larghezza_mm=10.0, spessore_mm=1.0, raggio_mozzo_mm=10.0,
              densita_min_kg_m3=1000.0, densita_max_kg_m3=1200.0, giri_progetto_rpm=30000.0, giri_massimi_rpm=30000.0,
              inerzia_rotore_motore_kgm2=0.0, ventole_fuori_asse=1, campioni=5000, seme=0)
    ris = PA.analizza(pa, 5.0)
    atteso = 200 * 1e-7 * 0.015 * 1e6                     # (rho_max - rho_min) V r_cg in g mm
    verifica("pale: caso peggiore (rho_max - rho_min) V r_cg, mai superato",
             abs(ris["caso_peggiore"]["squilibrio_g_mm"] - atteso) < 1e-9 and ris["monte_carlo"]["squilibrio_g_mm"]["max"] <= atteso,
             f"{ris['caso_peggiore']['squilibrio_g_mm']:.4f} g·mm")
    # oscillazione della massa libera: x = U / M per una forza U w^2 sin(w t) a regime
    verifica("pale: oscillazione del cubo = U / M", abs(ris["caso_peggiore"]["spostamento_cubo_um"] - atteso * 1e-6 / 5.0 * 1e6) < 1e-12)


def test_margine_fase():
    """Margine di fase dell'anello: PD senza ritardo (formula analitica) e caso dell'input."""
    # PD senza ritardo: w_c^2 = wn^2 (2 z^2 + sqrt(4 z^4 + 1)), PM = atan(2 z w_c / wn)
    wn, z = 2.0, 0.8
    kp, kd, ki = VO.guadagni(wn, z, 0.0)
    wc, pm = DY.margine_fase_anello(kp, kd, ki, 0.0)
    wc_a = wn * math.sqrt(2 * z * z + math.sqrt(4 * z ** 4 + 1))
    pm_a = math.degrees(math.atan(2 * z * wc_a / wn))
    verifica("margine: PD senza ritardo, taglio e margine analitici",
             abs(wc - wc_a) < 1e-6 * wc_a and abs(pm - pm_a) < 1e-6, f"{wc:.4f} rad/s, {pm:.3f}° contro {wc_a:.4f} rad/s, {pm_a:.3f}°")
    # PID con ritardo: |L| = 1 e fase coerenti con il calcolo diretto della funzione d'anello complessa
    tau = 0.2856 / 2.3
    kp, kd, ki = VO.guadagni(2.0, 0.8, 1.0)
    wc, pm = DY.margine_fase_anello(kp, kd, ki, tau)
    s = 1j * wc
    L = (kp + kd * s + ki / s) / s ** 2 / (1 + tau * s)
    pm_c = 180.0 + math.degrees(np.angle(L))
    verifica("margine: |L(j wc)| = 1 e margine uguale a 180° + arg L", abs(abs(L) - 1) < 1e-9 and abs(pm - pm_c) < 1e-6,
             f"|L| = {abs(L):.9f}, {pm:.3f}° contro {pm_c:.3f}°")
    verifica("margine: caso dell'input (wn 2, zeta 0,8, alfa 1, t90 0,2856 s) circa 4,6 rad/s e 35°",
             abs(wc - 4.6) < 0.3 and abs(pm - 35.0) < 2.0, f"{wc:.2f} rad/s, {pm:.1f}°")


def test_bang_bang():
    """Riferimento bang-bang: da fermo a fermo, accelerazione 4 d / T^2 per T/2 e poi l'opposta."""
    d, T = 0.3, 3.0
    t = np.linspace(0.0, 2 * T, 60001)
    x, v, a = VO.riferimento_bang_bang(t, d, T)
    verifica("bang-bang: x(0) = 0, x(T) = d, v(0) = v(T) = 0 e fermo in d dopo T",
             abs(x[0]) < 1e-12 and abs(x[30000] - d) < 1e-12 and abs(v[0]) < 1e-12 and abs(v[30000]) < 1e-12
             and np.all(x[30000:] == d) and np.all(v[30000:] == 0.0))
    verifica("bang-bang: picco di accelerazione 4 d / T^2", abs(np.max(np.abs(a)) - 4 * d / T ** 2) < 1e-12,
             f"{np.max(np.abs(a)):.5f} contro {4 * d / T ** 2:.5f} m/s^2")
    e = 1e-9
    xm, vm, _ = VO.riferimento_bang_bang(np.array([T / 2 - e, T / 2 + e]), d, T)
    verifica("bang-bang: x e v continue a T/2 (x = d/2, v = 2 d / T)",
             abs(xm[0] - xm[1]) < 1e-8 and abs(vm[0] - vm[1]) < 1e-8 and abs(xm[0] - d / 2) < 1e-8
             and abs(vm[0] - 2 * d / T) < 1e-8)
    dt = t[1] - t[0]
    verifica("bang-bang: velocità e posizione coerenti con l'accelerazione (integrale)",
             abs(np.trapezoid(a, t)) < 1e-3 and abs(np.max(np.abs(np.diff(x) / dt - v[:-1]))) < 1e-3 * 4 * d / T)


def test_ambiente():
    """Ambiente: sigma = 1 come prima, spinta massima ~ sigma, potenza a spinta fissata ~ 1/sqrt(sigma), potenza totale."""
    m, F_max, t90, wn, z, d, T, dt = 4.5, 1.17, 0.15, 2.0, 0.8, 0.2, 5.0, 1e-3
    P_rif, F_rif, esp = 16.5, 1.17, 1.5
    s = VO.simula_asse(m, F_max, t90, wn, z, d, T, lambda t: 0.01 * VO.G0 + 0 * t, 5.0, dt, True,
                       VO.riferimento_minjerk, v0=0.01, alfa_integrale=1.0)
    ind = VO.indicatori(s, d, T, 0.005, F_max, P_rif, F_rif, esp, dt)
    P_vecchia = P_rif * (np.abs(s["F"]) / F_rif) ** esp
    verifica("ambiente: sigma = 1 riproduce esattamente gli indicatori di prima",
             ind == VO.indicatori(s, d, T, 0.005, F_max, P_rif, F_rif, esp, dt, sigma=1.0)
             and ind["energia_J"] == float(np.trapezoid(P_vecchia, s["t"])) and ind["potenza_picco_W"] == float(np.max(P_vecchia)),
             f"{ind['energia_J']:.6f} J")
    # spinta massima dell'ambiente = spinta di progetto x sigma (sul cfg dell'ambiente costruito da cli)
    base = {sez: {} for sez in CLI.SEZ_AMBIENTE}
    base["ATTUATORE"] = {"spinta_max_positiva_N": [1.17, 1.0, 0.5], "spinta_max_negativa_N": [1.17, 1.0, 0.5],
                         "pressione_progetto_Pa": 100000.0}
    base["AMBIENTI"] = {"a": {"pressione_Pa": 82500.0}, "b": {"pressione_Pa": 100000.0}, "c": {"pressione_Pa": 50000.0}}
    ok = True
    for n, sg in (("a", 0.825), ("b", 1.0), ("c", 0.5)):
        c = CLI.cfg_ambiente(base, n)
        ok &= abs(c["AMBIENTE"]["sigma"] - sg) < 1e-12
        ok &= all(abs(f - f0 * sg) < 1e-12 for f, f0 in zip(c["ATTUATORE"]["spinta_max_positiva_N"], [1.17, 1.0, 0.5]))
        ok &= all(abs(f - f0 * sg) < 1e-12 for f, f0 in zip(c["ATTUATORE"]["spinta_max_negativa_N"], [1.17, 1.0, 0.5]))
        ok &= abs(c["AMBIENTE"]["fattore_potenza"] - 1 / math.sqrt(sg)) < 1e-12
    ok &= base["ATTUATORE"]["spinta_max_positiva_N"] == [1.17, 1.0, 0.5]            # la base non cambia
    verifica("ambiente: la spinta massima scala con sigma (e l'input di base non cambia)", ok)
    # potenza a spinta fissata: P(sigma) = P(1) / sqrt(sigma)
    F = np.array([0.2, 0.6, 1.17])
    r = [VO.potenza_elettrica(F, P_rif, F_rif, esp, sg) * math.sqrt(sg) / VO.potenza_elettrica(F, P_rif, F_rif, esp) for sg in (0.5, 0.825, 2.0)]
    verifica("ambiente: la potenza a spinta fissata scala con 1 / sqrt(sigma)", np.allclose(r, 1.0, atol=1e-14, rtol=0)
             and abs(VO.potenza_elettrica(1.17, 16.5, 1.17, 1.5, 0.25) - 33.0) < 1e-12,
             "sigma 0,25: 16,5 W -> 33 W")
    # energia nel tempo: stesso andamento di F, energia ~ 1 / sqrt(sigma)
    e1 = VO.indicatori(s, d, T, 0.005, F_max, P_rif, F_rif, esp, dt, sigma=1.0)["energia_J"]
    e2 = VO.indicatori(s, d, T, 0.005, F_max, P_rif, F_rif, esp, dt, sigma=0.64)["energia_J"]
    verifica("ambiente: energia a parità di spinta nel tempo ~ 1 / sqrt(sigma)", abs(e2 / e1 - 1 / 0.8) < 1e-12)
    # potenza totale = somma dei tre assi: serie, energia (trapezi lineari), picco, corrente
    serie = [VO.simula_asse(m, F_max, t90, wn, z, dd, T, lambda t, a=a: a * VO.G0 + 0 * t, 5.0, dt, True,
                            VO.riferimento_minjerk, v0=0.01, alfa_integrale=1.0) for dd, a in ((0.2, 0.01), (0.1, 0.002), (-0.15, 0.005))]
    P = [VO.potenza_elettrica(x["F"], P_rif, F_rif, esp, 0.825) for x in serie]
    tot = VO.potenza_totale(P, serie[0]["t"], 24.0)
    E = sum(VO.indicatori(x, dd, T, 0.005, F_max, P_rif, F_rif, esp, dt, sigma=0.825)["energia_J"]
            for x, dd in zip(serie, (0.2, 0.1, -0.15)))
    verifica("potenza totale: somma dei tre assi nel tempo, energia = somma delle energie, corrente = picco / tensione",
             np.array_equal(tot["P_tot"], P[0] + P[1] + P[2]) and abs(tot["energia_J"] - E) < 1e-9 * E
             and tot["potenza_picco_W"] == float(np.max(P[0] + P[1] + P[2])) and tot["potenza_picco_W"] <= sum(float(np.max(x)) for x in P) + 1e-12
             and abs(tot["corrente_picco_A"] - tot["potenza_picco_W"] / 24.0) < 1e-15
             and abs(tot["potenza_media_W"] - E / 5.0) < 1e-9 * E, f"energia {E:.2f} J")


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
