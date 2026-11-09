"""RUN S4 INTERAZIONE: configurazione S4 (spigoli centrati), parte sulla non interazione tra i condotti.

    python RUN_S4_interazione.py            (oppure il tasto Run dell'editor)
    python RUN_S4_interazione.py --completa   (griglia ridotta, per prove)

Legge i dati da INPUT_S4.py (si modifica solo quello).
Solo S4, quindi nessun grafico di confronto. Grafici di scenario: viste del layout, sezioni della struttura, profili di velocità e pressione,
perdite, indice di riaspirazione dei getti (ingestione). Excel completo.
Risultati in output/<data-ora>_RUN_xxx_<etichetta>_<impronta>/ (cartella nuova a ogni run, mai sovrascritta).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from condotti import esecuzione                                   # noqa: E402

# Grafici di scenario prodotti da questa run (gli altri gruppi sono in RUN_S4_dinamica.py)
GRUPPI = {"viste", "sezioni", "profili", "perdite", "ingestione"}

if __name__ == "__main__":
    esecuzione.main("RUN_S4_interazione", "INPUT_S4.py", __doc__, gruppi=GRUPPI, con_confronto=False)
