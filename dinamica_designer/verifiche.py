"""Verifiche automatiche della dinamica di volo contro soluzioni analitiche note.

run_dinamica.py le esegue prima della simulazione (ESECUZIONE["verifiche"]);
da sole:  python -m dinamica_designer.verifiche

Se un test fallisce, i risultati della simulazione non vanno usati finché non si è capito perché.
"""
import math
import sys
import numpy as np

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
