"""Verifiche automatiche della dinamica di volo contro soluzioni analitiche note.

run_dinamica.py le esegue prima della simulazione (ESECUZIONE["verifiche"]);
da sole:  python -m dinamica_designer.verifiche

Se un test fallisce, i risultati della simulazione non vanno usati finché non si è capito perché.
"""
import math
import sys
import numpy as np

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
