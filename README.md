# Dinamica di volo del cubo COMPANION

Simula la dinamica di volo del cubo free-flyer (configurazione S4): massa concentrata nel baricentro, tre assi in parallelo, regolatore PD sulla posizione, attuatore del primo ordine, disturbo del volo parabolico.

L'analisi e l'ottimo delle configurazioni dei condotti (scenari S1–S4, lato, diametro, Venturi, ventola, motore, punteggi) sono nella cartella sorella `../Analisi_Configurazioni`. Quella cartella usa il modello del propulsore di qui (`dinamica_designer/propulsore.py`), vedi [Collegamento con l'analisi](#6-collegamento-con-lanalisi-delle-configurazioni).

## 1. Installazione

```bash
pip install -r requirements.txt
```

Dipendenze: `numpy`, `matplotlib` (più `pytest` per i test). La run non ha bisogno di `../Analisi_Configurazioni`.

## 2. Come si usa

Struttura della cartella (stessa impostazione di `Dimensionamento_Sistema_Propulsivo`):

```
Dinamica_Sistema_Propulsivo/
├── input.py                 ← l'unico file da modificare (CASO, sezioni 0 ESECUZIONE … 7 RUOTE)
├── run_dinamica.py          ← la run
├── dinamica_designer/       ← il codice (non va toccato per l'uso normale)
│   ├── cli.py               sequenza della run
│   ├── caso.py              cartella dei risultati del caso
│   ├── volo.py              dinamica di volo: riferimento, disturbo, simulazione di un asse (RK4), indicatori
│   ├── propulsore.py        dinamica del propulsore: salita della spinta, margine di fase, ruote (usato anche dall'analisi)
│   ├── export.py            grafici, serie temporali, RISULTATO.md
│   └── verifiche.py         verifiche contro soluzioni analitiche
├── tests/                   ← pytest: verifiche e struttura del caso
└── risultati/<caso>/        ← un caso per cartella (non sincronizzata con git)
```

```bash
python run_dinamica.py                         # circa 4 secondi
python run_dinamica.py --input altro.py        # usa un altro file di input
python -m pytest tests -q                      # test
python -m dinamica_designer.verifiche          # solo le verifiche, con il dettaglio
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

## 4. Il file di input

| Sezione | Cosa contiene |
|---|---|
| `CASO` | `nome` della cartella in `risultati/` (`None` = automatico, con l'impronta degli input); `sovrascrivi` (`False`: un caso con nome e input diversi viene rifiutato) |
| 0 `ESECUZIONE` | passo di integrazione, formato dei grafici, cartella dei risultati, verifiche sì/no |
| 1 `CORPO` | massa nel baricentro |
| 2 `ATTUATORE` | spinta massima per verso e per asse, tempo di salita al 90 % (dall'analisi) |
| 3 `MANOVRA` | distanza, tempo, finestra simulata, tolleranza, profilo |
| 4 `DISTURBO` | ampiezza, frequenza e fase del disturbo per asse |
| 5 `REGOLATORE` | ωn, ζ, feedforward |
| 6 `ENERGIA` | potenza in funzione della spinta |
| 7 `RUOTE` | dati del bilancio delle ruote di reazione |

Gli elenchi `[X, Y, Z]` seguono sempre questo ordine. Le fonti `[ANL]` indicano valori copiati dall'analisi.

## 5. La cartella risultati

```
risultati/
├── registro_esecuzioni.csv          ← una riga per run: data, caso, impronta, durata
└── <caso>/                          ← per esempio m5.00kg_d0.30m_t3.0s_h06cf3291
    ├── caso.json                    ← nome, impronta, data
    ├── input_usato.py               ← copia esatta dell'input
    ├── log.txt                      ← registro della run
    ├── 00_sintesi/
    │   ├── RISULTATO.md             ← da leggere per primo: input, tabelle per asse, spazio e tempo, ruote
    │   └── riepilogo.json           ← gli stessi numeri, per Python
    ├── 01_grafici/
    │   ├── 01_moto_tre_assi.svg     ← posizione, velocità, spinta, disturbo
    │   └── 02_spazio_massimo.svg    ← spazio percorribile in funzione del tempo della manovra
    └── 02_dati/
        └── serie_temporali.csv      ← serie ogni 0,01 s (separatore ;)
```

- L'**impronta** (8 caratteri) è calcolata dai dati che cambiano i risultati, non dal nome del caso o dal formato dei grafici: stessa impronta = stessi risultati.
- Rilanciare con gli stessi input riscrive lo stesso caso; con input diversi il nome automatico cambia, quindi nessuna run sovrascrive un'altra.
- A ogni run le sottocartelle numerate del caso vengono svuotate e riscritte.

## 6. Collegamento con l'analisi delle configurazioni

- **Dall'analisi alla dinamica (a mano).** Spinta massima per verso, tempo di salita al 90 %, potenza e spinta di riferimento, braccio della coppia, spinta per unità e coppia di reazione si copiano in `input.py` (fonti `[ANL]`) dall'ultima run di S4 di `../Analisi_Configurazioni` (`risultati/<caso>/02_excel/Confronto_scenari.xlsx`, fogli *Controllo e dinamica* e *Fluidodinamica*, oppure `00_sintesi/riepilogo.json`).
- **Dalla dinamica all'analisi (codice).** `../Analisi_Configurazioni/configurazioni_designer/core/ponte_dinamica.py` importa `dinamica_designer/propulsore.py` per valutare ogni progetto (salita della spinta, inversione, margine di fase, ruote). Il modello esiste solo qui: se lo cambi, cambiano anche i risultati dell'analisi. Rinominare questa cartella o il pacchetto, o spostarla da accanto ad `Analisi_Configurazioni`, rompe l'analisi.

## 7. Limiti

- Massa puntiforme, tre assi indipendenti: nessuna rotazione, nessun accoppiamento tra assi.
- Disturbo sinusoidale con ampiezza, frequenza e fase SEGNAPOSTO: serve una registrazione reale di volo.
- Esponente della potenza (1,5) e momento massimo delle ruote SEGNAPOSTO.
- I dati `[ANL]` vanno ricopiati a ogni nuova run dell'analisi: la run non li legge da sola.
