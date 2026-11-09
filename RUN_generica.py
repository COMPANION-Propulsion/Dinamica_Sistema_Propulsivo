"""RUN GENERICA: confronto tra le configurazioni S1, S2 e S3.

    python RUN_generica.py            (oppure il tasto Run dell'editor)
    python RUN_generica.py --veloce   (griglia ridotta, per prove)

Legge i dati da INPUT_generico.py (si modifica solo quello).
Fa verifiche fisiche, ottimizzazione di ogni scenario, grafici di scenario e di confronto, Excel.
Risultati in output/<data-ora>_RUN_xxx_<etichetta>_<impronta>/ (cartella nuova a ogni run, mai sovrascritta).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from condotti import esecuzione                                   # noqa: E402

if __name__ == "__main__":
    esecuzione.main("RUN_generica", "INPUT_generico.py", __doc__)
