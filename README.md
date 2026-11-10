# Dinamica di volo del cubo COMPANION

Simula la dinamica di volo del cubo free-flyer (configurazione S4): massa concentrata nel baricentro, tre assi in parallelo, regolatore PD sulla posizione, attuatore del primo ordine, disturbo del volo parabolico.

L'analisi e l'ottimo delle configurazioni dei condotti (scenari S1–S4, lato, diametro, Venturi, ventola, motore, punteggi) sono nella cartella sorella `../Analisi_Configurazioni`. Quella cartella usa il modello del propulsore di qui (`dinamica/propulsore.py`), vedi [Collegamento con l'analisi](#5-collegamento-con-lanalisi-delle-configurazioni).

## 1. Installazione

```bash
pip install -r requirements.txt
```

Dipendenze: `numpy`, `matplotlib`. La run non ha bisogno di `../Analisi_Configurazioni`.

## 2. Come si usa

| Cosa | File | A cosa serve |
|---|---|---|
| Input | `INPUT_S4_dinamica.py` | l'unico file da modificare: massa, spinta massima e tempo di salita (copiati dall'ultima run dell'analisi), manovra, disturbo, regolatore, energia, ruote |
| Run | `RUN_S4_dinamica.py` | legge l'input, esegue le verifiche, simula, salva grafici e dati |
| Output | `output/` | una cartella nuova per ogni run (non sincronizzata con git) |

```bash
python RUN_S4_dinamica.py                      # circa 4 secondi
python RUN_S4_dinamica.py --input altro.py     # usa un altro file di input
python -m dinamica.verifiche                   # solo le verifiche
```

Prima della simulazione girano 5 verifiche contro soluzioni analitiche (massa libera con disturbo sinusoidale, sovraelongazione del PD, saturazione, spazio a spinta costante, riferimento da fermo a fermo). Se una fallisce la simulazione non parte. Si disattivano con `ESECUZIONE["verifiche"] = False`.

## 3. Cosa calcola

Per ogni asse, con `m dv/dt = F − m a_d(t)`, `τ dF/dt = F_cmd − F` (τ = t90 / 2,3) e `F_cmd = sat(m [ωn² (x_rif − x) + 2 ζ ωn (v_rif − v)])`:

- spostamento da fermo a fermo in un tempo dato (profilo a minimo jerk o gradino), errore a fine manovra, errore massimo, sovraelongazione, tempo di assestamento;
- spinta massima usata, quota della spinta disponibile, tempo in saturazione;
- energia e potenza di picco, con `P = P_rif (F / F_rif)^esponente`;
- spazio massimo e tempo minimo alla spinta massima, con e senza disturbo;
- margine di fase dell'anello di posizione per le bande in `RUOTE["frequenze_margine_fase_rad_s"]`;
- bilancio delle ruote di reazione nella finestra libera.

## 4. File

```
Dinamica_Sistema_Propulsivo/
├── INPUT_S4_dinamica.py     ← dati (sezioni 0 ESECUZIONE … 7 RUOTE)
├── RUN_S4_dinamica.py       ← run
├── requirements.txt
└── dinamica/
    ├── volo.py              ← dinamica di volo: riferimento, disturbo, simulazione di un asse (RK4), indicatori, spazio e tempo
    ├── propulsore.py        ← dinamica del propulsore: salita della spinta, inversione, margine di fase, ruote di reazione
    ├── esecuzione.py        ← sequenza della run, grafici, log, dati
    └── verifiche.py         ← verifiche contro soluzioni analitiche
```

Cartella di output: `output/<data-ora>_RUN-S4-dinamica_<etichetta>_<impronta>/`

| File | Contenuto |
|---|---|
| `grafici/01_moto_tre_assi.svg` | posizione, velocità, spinta e disturbo per i tre assi |
| `grafici/02_spazio_massimo.svg` | spazio percorribile in funzione del tempo della manovra, alla spinta massima |
| `dati/riepilogo.json` | indicatori per asse, spazio massimo e tempo minimo, margine di fase, ruote |
| `dati/serie_temporali.csv` | serie temporali ogni 0,01 s (separatore `;`) |
| `INPUT_usato.py`, `log.txt` | copia dell'input e registro della run |

`output/registro_esecuzioni.csv` elenca tutte le run, una riga per run. L'**impronta** (8 caratteri) è calcolata dagli input: stessa impronta = stessi dati.

## 5. Collegamento con l'analisi delle configurazioni

- **Dall'analisi alla dinamica (a mano).** Spinta massima per verso, tempo di salita al 90 %, potenza e spinta di riferimento, braccio della coppia, spinta per unità e coppia di reazione si copiano in `INPUT_S4_dinamica.py` (fonti `[ANL]`) dall'ultima run di `../Analisi_Configurazioni` (Excel, fogli *Controllo e dinamica* e *Fluidodinamica*, oppure `dati/riepilogo.json`).
- **Dalla dinamica all'analisi (codice).** `../Analisi_Configurazioni/condotti/ponte_dinamica.py` importa `dinamica/propulsore.py` per valutare ogni progetto (salita della spinta, inversione, margine di fase, ruote). Il modello esiste solo qui: se lo cambi, cambiano anche i risultati dell'analisi. Rinominare questa cartella, o spostarla da accanto ad `Analisi_Configurazioni`, rompe l'analisi.

## 6. Limiti

- Massa puntiforme, tre assi indipendenti: nessuna rotazione, nessun accoppiamento tra assi.
- Disturbo sinusoidale con ampiezza, frequenza e fase SEGNAPOSTO: serve una registrazione reale di volo.
- Esponente della potenza (1,5) e momento massimo delle ruote SEGNAPOSTO.
- I dati `[ANL]` vanno ricopiati a ogni nuova run dell'analisi: la run non li legge da sola.
