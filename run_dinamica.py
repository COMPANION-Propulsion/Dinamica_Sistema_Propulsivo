"""Dinamica di volo del cubo S4: legge input.py, scrive risultati/<caso>/.

    python run_dinamica.py                  (oppure il tasto Run dell'editor)
    python run_dinamica.py --input altro.py

Calcola, per i tre assi insieme: spostamento da fermo a fermo in un tempo dato, errore di posizione
con il disturbo (0,01 g a 1 Hz di base), uso della spinta e saturazione, energia, spazio massimo e
tempo minimo alla spinta massima, margine di fase dell'attuatore, budget delle ruote di reazione.
Sintesi in risultati/<caso>/00_sintesi/RISULTATO.md.
"""
import sys

from dinamica_designer.cli import main

if __name__ == "__main__":
    sys.exit(main(descrizione=__doc__))
