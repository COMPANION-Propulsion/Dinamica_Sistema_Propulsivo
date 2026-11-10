"""RUN S4 DINAMICA: dinamica di volo del cubo S4 (massa nel baricentro, tre assi, regolatore PD, disturbo del volo parabolico).

    python RUN_S4_dinamica.py            (oppure il tasto Run dell'editor)

Legge i dati da INPUT_S4_dinamica.py (si modifica solo quello); non dipende dall'analisi delle configurazioni (../Analisi_Configurazioni).
Calcola, per i tre assi insieme: spostamento da fermo a fermo in un tempo dato, errore di posizione con il disturbo
(0,01 g a 1 Hz di base), uso della spinta e saturazione, energia, spazio massimo e tempo minimo alla spinta massima,
tempo di salita e margine di fase dell'attuatore, budget delle ruote di reazione.
Risultati in output/<data-ora>_RUN-S4-dinamica_<etichetta>_<impronta>/ (cartella nuova a ogni run, mai sovrascritta).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dinamica import esecuzione                                   # noqa: E402

if __name__ == "__main__":
    esecuzione.main("RUN_S4_dinamica", "INPUT_S4_dinamica.py", __doc__)
