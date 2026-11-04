# Analisi dei condotti di COMPANION

Confronta configurazioni di condotti per il cubo free-flyer e cerca, per ognuna, il progetto migliore. Gli obiettivi sono in tensione:

- **più spazio interno** per batteria, ruote di reazione, avionica ed ESC;
- **condotti semplici e con poche perdite di carico**, quindi meno potenza per la stessa spinta;
- **massa intorno ai 4 kg**: ogni configurazione si porta dietro una massa strutturale diversa (condotti, staffe, volumetti d'angolo, telaio).

## Come si usa: due file

| File | Cosa fare |
|---|---|
| `INPUT.py` | **L'unico file da modificare.** Tutti i dati e tutti gli scenari, in sezioni numerate (0 esecuzione … 11 scenari). Ogni valore ha la fonte; `SEGNAPOSTO` = da sostituire con un dato vero. |
| `RUN.py` | **L'unico file da lanciare** (`python RUN.py` o il tasto Run dell'editor). Fa le verifiche fisiche, l'analisi, i grafici e l'Excel. |

```bash
pip install numpy scipy matplotlib openpyxl
python RUN.py
```

- Prove rapide: in `INPUT.py` metti `ESECUZIONE["modalita"] = "veloce"` (circa 1 minuto invece di qualche minuto).
- Escludere uno scenario: `"attivo": False` nel suo blocco in fondo a `INPUT.py`.
- Le verifiche fisiche (37 controlli contro risultati noti) girano prima dell'analisi: se una fallisce l'analisi non parte.

Tutto il resto sta nella cartella `condotti/` e non va toccato per l'uso normale.

## Scenari

| Id | Configurazione | Origine |
|---|---|---|
| S1_SFALSATI_12 | 12 condotti dritti per tutto il lato, sfalsamento ciclico | modello interattivo |
| S2_SPIGOLI_CORTI_12 | 12 condotti lunghi mezzo spigolo, presa a metà spigolo con curva | tua proposta |
| S3_REVERSIBILI_6 | 6 ventole reversibili a coppie sfalsate | Excel del compagno |
| S4_SPIGOLI_CENTRATI_12 | 12 condotti centrati sugli spigoli, accorciati e/o spostati, volumetti tolti ai vertici | tua proposta (foto CAD) |

### Lato del cubo: è un risultato, non un dato

In `INPUT.py`, sezione 3, il lato del cubo non è più un numero: si indica l'**intervallo** da analizzare.

| Chiave | Significato |
|---|---|
| `lato_cubo_min_mm` | limite inferiore (mm) |
| `lato_cubo_max_mm` | limite superiore (mm), sempre incluso |
| `lato_cubo_passo_mm` | passo con cui si scorre l'intervallo |

Per ogni scenario l'ottimizzatore ripete tutta la ricerca (varianti × diametri) a ogni lato dell'intervallo. L'ottimo è il progetto ammissibile con il punteggio più alto; a parità di punteggio vince il condotto più centrato, poi il cubo più piccolo.

Il **lato ottimo di ogni scenario** compare: nel riepilogo del terminale (colonna `L` e blocco "LATO OTTIMO DEL CUBO"), nell'Excel (foglio *Classifica*, ultima colonna; fogli *Progetto ottimo*, *Spazio interno*, *Tutti i progetti*), in `dati/riepilogo.json` (`L_mm`), in `dati/progetti.csv` (colonna `L_mm`), nei titoli dei grafici di scenario e nel grafico `13_lato_cubo`.

Se il lato ottimo coincide con un limite dell'intervallo, il terminale lo segnala: l'ottimo vero potrebbe stare fuori, quindi conviene allargare l'intervallo.

Ogni lato in più allunga la run: tempo ≈ numero di lati × tempo di una run a lato fisso.

### S4, spigoli centrati: come funziona

Base: ogni spigolo ha un condotto dritto, tangente alle due facce che lo formano. Nel vertice le tre rette dei condotti si incontrerebbero. Per eliminare l'intersezione si fanno due cose, combinabili:

- **accorciare** il condotto, lasciandolo centrato sulla mezzeria dello spigolo (3 piani di simmetria);
- **spostarlo** lungo lo spigolo, rompendo la simmetria.

Ai vertici si toglie un volumetto d'angolo, dalle estremità dei condotti alla faccia interna: il vertice è aperto e i condotti sboccano lì.

| Parametro in INPUT.py | Significato |
|---|---|
| `lunghezza_frazione` | lunghezza del condotto / lunghezza massima consentita (1 = arriva fino al limite) |
| `spostamento_frazione` | spostamento lungo lo spigolo, in frazione del margine disponibile; `0` = centrato, negativo/positivo = verso i due vertici |
| `varianti_geometria` | i valori da provare (prodotto cartesiano): l'ottimizzatore prova tutte le combinazioni |

Il limite delle estremità, da cui dipendono sia accorciamento sia spostamento, è c = a − (2·Ro + gioco), con a la distanza dell'asse dal centro e Ro il raggio esterno del condotto. Lo spostamento non può superare il margine che tiene il condotto a cavallo della mezzeria e dentro il limite c.

## Massa

`condotti/massa.py` stima la massa del cubo per ogni progetto. Voci:

- **guscio**, a spessore equivalente;
- **telaio**: longheroni sugli spigoli, meno i tratti tolti ai vertici;
- **condotti, alloggiamenti delle ventole, staffe**: una staffa ogni 100 mm di condotto, più una per curva;
- **flange e griglie delle bocche**;
- **motori, ESC, cavi, viteria**;
- **componenti fissi**, da `COMPONENTI` e `MASSE_FISSE`.

Come entra nell'analisi:

- **Obiettivo** (`massa_obiettivo_kg`, 4 kg): sopra dà un avviso e un punteggio "massa" più basso.
- **Massima** (`massa_massima_kg`): sopra il progetto **non è ammissibile**. Il valore predefinito è la massa usata per la spinta: oltre quella, la spinta di progetto non basta più.
- **Spinta**: viene ricontrollata con la massa stimata (riga "forza pura disponibile / richiesta").

Tutti i parametri di `TELAIO` e le masse dei componenti sono **SEGNAPOSTO**. Il valore assoluto della massa dipende soprattutto da loro. Le **differenze tra scenari** sono la parte affidabile: mostrano quanto costa, in massa, ogni configurazione di condotti.

## Output

Ogni esecuzione crea una cartella nuova, mai sovrascritta:

```
output/AAAAMMGG-HHMMSS_<etichetta>_<impronta>/
    grafici/<scenario>/   01 viste del layout (3 proiezioni + 3D; tratteggio: volumetti d'angolo), al lato ottimo
                          02 profili v(s), p(s), p0(s) lungo l'asse a vari giri
                          03 gli stessi profili nei vari ambienti
                          04 mappa della ventola con curve del sistema e punto di progetto
                          05 spinta-giri, spinta-salto di pressione, potenza-spinta
                          06 ripartizione della potenza (perdite ed energia del getto)
                          07 salita della spinta con limite di corrente
                          08 diagramma di Campbell
                          09 indice di riaspirazione dei getti per comando
    grafici/confronto/    01-11 punteggi, radar, Pareto, sensibilità, perdite, spazio, stabilità,
                          ruote, autorità, struttura, ambiente; 12 bilancio di massa;
                          13 lato del cubo (punteggio e massa per ogni lato, stella = ottimo)
    excel/Confronto_scenari.xlsx   (foglio "Massa" con voci, totale, scarto dall'obiettivo)
    dati/riepilogo.json, dati/progetti.csv
    INPUT_usato.py, log.txt
output/registro_esecuzioni.csv   (una riga per esecuzione)
```

Nell'Excel i pesi della classifica si cambiano direttamente nel foglio *Classifica*: totale e posizione sono formule.

## Cosa calcola, in ordine

1. **Geometria e spazio**: condotti a voxel, volumetti d'angolo, gioco tra condotti, moduli riservati, bocche nelle zone centrali, collocazione automatica dei componenti, volume libero.
2. **Fluidodinamica**: rete 1D per ogni unità (griglia, imbocco, tratti, curve, effetto di sistema, ventola con statore, ugello, griglia d'uscita); giri per la spinta richiesta; potenza elettrica dal modello del motore.
3. **Controllo**: forza e momento puri disponibili, forza residua con una ventola guasta, indice di riaspirazione per le 26 combinazioni di comandi.
4. **Dinamica**: salita della spinta, inversione per le reversibili, margine di fase, ruote di reazione nella finestra di 5 s.
5. **Struttura**: frequenza del tratto con la ventola e Campbell, instabilità a pressione esterna, sforzi a 1,8 g e 9 g, rigidezza portata dai condotti.
6. **Massa**: bilancio completo, confronto con obiettivo e massima, spinta ricontrollata.
7. **Realizzabilità e punteggi**: parti, curve, attuatori, stampa; punteggio pesato su spazio, perdite, semplicità, robustezza, dinamica, massa.

L'**ottimizzatore** prova, per ogni scenario, lato del cubo × varianti geometriche × diametro. Per ogni geometria sceglie poi Venturi, tipo di ventola e motore a minima potenza.

## Diametri: regola di potatura

Per ogni lato del cubo e per ogni variante geometrica si sale con il diametro D. Il diametro massimo con soluzione ammissibile è **Xi**, riportato nel log per lato.

Si smette di salire solo quando l'**ingombro** non regge: condotti che si intersecano, moduli riservati, bocche nelle zone centrali, componenti che non entrano. L'ingombro peggiora con D, quindi i diametri successivi non vengono analizzati.

Motore, Mach, potenza e massa **non** attivano lo stop: per ora tutti i diametri della lista vengono analizzati, anche quando il progetto non è ammissibile per quei motivi.

## Limiti da tenere presenti

- Le **curve delle ventole sono forme generiche**. Appena scelta la ventola, inserire la curva misurata (`TIPI_VENTOLA`, chiave `tabella`).
- **Motori**, **masse dei componenti** e **parametri del telaio** sono valori tipici o stime: vanno sostituiti con schede tecniche e pesate.
- **Effetto di sistema** e **indice d'ingestione** sono stime di screening, da confermare con CFD o al banco.
- Nei volumetti d'angolo i condotti sboccano in aria libera: la perdita di sbocco e l'eventuale riaspirazione dei getti sono stimate, non misurate.
- Il modello è 1D: non vede distacchi di vena locali, disuniformità del getto, interazioni tra getti vicini oltre l'indice.

## Per estendere

- **Nuovo scenario con una topologia esistente**: copiare un blocco nella sezione 11 di `INPUT.py`.
- **Nuova topologia**: scrivere un generatore in `condotti/scenari.py` che restituisce un `Layout`, poi registrarlo in `GENERATORI`.
- **Nuovo elemento** (per esempio un filtro): una classe in `condotti/rete.py` con `dp()` e la velocità di riferimento dichiarata, da inserire in `condotti/costruttore.py`.
- **Nuova correlazione**: in `condotti/perdite.py`, con fonte, velocità di riferimento e campo di validità, più un test in `condotti/verifiche.py`.
