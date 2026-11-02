# Analisi dei condotti di COMPANION

Confronta configurazioni di condotti per il cubo free-flyer e cerca, per ognuna, il progetto migliore. I due obiettivi sono in tensione:

- **più spazio interno** per batteria, ruote di reazione, avionica ed ESC;
- **condotti semplici e con poche perdite di carico**, quindi meno potenza per la stessa spinta.

## Avvio

```bash
pip install numpy scipy matplotlib openpyxl
python test_fisica.py          # 27 verifiche fisiche: devono passare tutte
python run_analisi.py          # analisi completa (2-3 minuti)
python run_analisi.py --veloce # griglia ridotta per prove (circa 1 minuto)
```

## File

| File | A cosa serve |
|---|---|
| `input.py` | **Unico file da modificare** per i dati: missione, ambienti, geometria, zone riservate, componenti, elementi, ventole, motori, limiti, pesi. Ogni valore ha la fonte; `SEGNAPOSTO` = da sostituire. |
| `database_scenari.py` | Gli scenari confrontati. Per aggiungerne uno si copia un blocco e si cambiano id e parametri. |
| `run_analisi.py` | Esegue tutto e crea la cartella di output. |
| `test_fisica.py` | Confronta il codice con risultati noti (Poiseuille, Colebrook, bilancio di energia, affinità, densità, Y simmetrica, valvola, plenum, allocazione). |
| `condotti/` | Il pacchetto di calcolo (vedi sotto). |

## Scenari nel database

| Id | Configurazione | Origine |
|---|---|---|
| S1_SFALSATI_12 | 12 condotti dritti per tutto il lato, sfalsamento ciclico | modello interattivo |
| S2_SPIGOLI_CORTI_12 | 12 condotti lunghi mezzo spigolo, presa a metà spigolo con curva | tua proposta |
| S3_SPIGOLI_PIENI_12 | 12 condotti per tutto lo spigolo, scalino a S ai vertici, ugelli inclinati | tua proposta |
| S4_Y6_MARGINI | 6 ventole, condotto a Y, ugelli ai margini, valvole per desaturare, presa dal plenum interno | Excel (conversazione) |
| S5_REVERSIBILI_6 | 6 ventole reversibili a coppie sfalsate | Excel del compagno |
| S6_Y6_DIAGONALI | come S4 con ugelli negli angoli opposti | variante |

Le Y6 vengono provate in due forme («spaziale» e «piatta») e con più posizioni della giunzione.

## Output

Ogni esecuzione crea una cartella nuova, mai sovrascritta:

```
output/AAAAMMGG-HHMMSS_<etichetta>_<impronta>/
    grafici/<scenario>/   01 viste del layout (3 proiezioni + 3D)
                          02 profili v(s), p(s), p0(s) lungo l'asse a vari giri
                          03 gli stessi profili nei vari ambienti (volo 18-25 °C, laboratorio)
                          04 mappa della ventola con curve del sistema e punto di progetto
                          05 spinta-giri, spinta-salto di pressione, potenza-spinta
                          06 ripartizione della potenza (perdite ed energia del getto)
                          07 salita della spinta con limite di corrente
                          08 diagramma di Campbell
                          09 indice di riaspirazione dei getti per comando
                          10-11 (Y6) valvola: portate e momento, profili con valvola chiusa
    grafici/confronto/    punteggi, radar, Pareto spazio-potenza, sensibilità al diametro,
                          perdite per categoria, spazio, margine di fase, ruote di reazione,
                          autorità e guasti, struttura, effetto dell'ambiente
    excel/Confronto_scenari.xlsx
    dati/riepilogo.json, dati/progetti.csv
    input_usato.py, database_usato.py, log.txt
output/registro_esecuzioni.csv   (una riga per esecuzione)
```

- **Etichetta**: quella scritta in `ESECUZIONE["etichetta"]`, altrimenti automatica (spinta, lato, ambiente, numero di scenari).
- **Impronta**: calcolata dagli input; due cartelle con la stessa impronta hanno usato gli stessi dati.

Nell'Excel i pesi della classifica si cambiano direttamente nel foglio *Classifica*: totale e posizione sono formule.

## Cosa calcola, in ordine

1. **Geometria e spazio**:
   - condotti come tubi a voxel;
   - gioco minimo tra condotti, sovrapposizioni con i moduli dietro le facce (sensori, docking, aggancio), bocche nelle zone centrali;
   - collocazione automatica di batteria (deve toccare la faccia dello sportellino), ruote, avionica ed ESC;
   - volume libero e cubo libero più grande.
2. **Fluidodinamica**:
   - rete 1D per ogni unità: griglia, imbocco, tratti, curve, effetto di sistema, ventola con statore, giunzione, valvola, ugello di Venturi, griglia d'uscita;
   - risoluzione simultanea delle unità che condividono un plenum;
   - giri per la spinta richiesta, potenza elettrica dal modello del motore.
3. **Controllo**:
   - forza e momento puri disponibili (programmazione lineare);
   - forza residua con una ventola guasta;
   - indice di riaspirazione per tutte le 26 combinazioni di comandi su più assi.
4. **Dinamica**:
   - salita della spinta col limite di corrente e tempo d'inversione per le reversibili;
   - margine di fase dell'anello di posizione;
   - bilancio delle ruote di reazione nella finestra di 5 s e tempo di desaturazione.
5. **Struttura**:
   - frequenza del tratto con la ventola e incroci di Campbell;
   - instabilità a pressione esterna;
   - sforzi a 1,8 g e 9 g;
   - rigidezza portata dai condotti;
   - massa della propulsione.
6. **Realizzabilità e punteggi**:
   - parti stampate (i condotti più lunghi del piatto si dividono), curve, giunzioni, attuatori, stampa;
   - punteggio pesato.

L'**ottimizzatore** prova, per ogni scenario, varianti geometriche × diametro. Per ogni geometria sceglie poi Venturi, tipo di ventola e motore a minima potenza. Si comporta così perché ventola, ugello e condotto si influenzano a vicenda: la ventola migliore cambia da una configurazione all'altra.

## Limiti da tenere presenti

- Le **curve delle ventole sono forme generiche**. Appena scelta la ventola, inserire la curva misurata (`TIPI_VENTOLA`, chiave `tabella` con `phi`, `psi`, `eta`).
- Anche i **motori** sono valori tipici: vanno sostituiti con le schede tecniche.
- **Effetto di sistema**, **perdita del passaggio nel plenum** e **indice d'ingestione** sono stime di screening. Vanno confermati con CFD o al banco prima di decidere su quei punti.
- Ruote di reazione (inviluppo 130³ mm) e moduli dei sensori hanno ingombri **segnaposto**.
- Il modello è 1D: non vede distacchi di vena locali, disuniformità del getto, interazioni tra getti vicini oltre l'indice.

## Per estendere

- **Nuovo scenario con una topologia esistente**: aggiungere un blocco in `database_scenari.py`.
- **Nuova topologia**: scrivere un generatore in `condotti/scenari.py`, che restituisce un `Layout` con percorsi e bocche, e registrarlo in `GENERATORI`.
- **Nuovo elemento** (per esempio un filtro): una classe in `condotti/rete.py` con `dp()` e la velocità di riferimento dichiarata, da inserire in `condotti/costruttore.py`.
- **Nuova correlazione**: in `condotti/perdite.py`, con fonte, velocità di riferimento e campo di validità. Poi aggiungere un test in `test_fisica.py`.
