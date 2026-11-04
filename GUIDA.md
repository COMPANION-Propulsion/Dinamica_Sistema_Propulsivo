# GUIDA: come provare l'analisi dei condotti, passo per passo

Questa guida accompagna la prima prova: si modifica un valore in `INPUT.py`, si lancia `RUN.py`, si legge la cartella di output. Va letta insieme a `LEGGIMI.md`, che è la scheda tecnica.

Tre cose da usare, nient'altro:

| Cosa | Dove | A cosa serve |
|---|---|---|
| Input | `INPUT.py` | tutti i valori modificabili e gli scenari |
| Run | `RUN.py` | l'unico script da lanciare |
| Output | `output/` | una cartella nuova per ogni run |

---

## 1. Prima prova (circa 2 minuti)

Vuoi vedere il meccanismo senza aspettare la run completa.

1. In `INPUT.py`, sezione 0, cambia `"modalita": "completa"` in `"modalita": "veloce"`.
2. Da terminale, nella cartella del progetto:

   ```bash
   python RUN.py
   ```

   oppure con il tasto Run di VS Code su `RUN.py`.

3. A fine esecuzione, nel terminale compare il riepilogo. Apri l'ultima cartella in `output/` e il file `excel/Confronto_scenari.xlsx`, foglio **Classifica**.
4. Quando hai finito, rimetti `"modalita": "completa"`. La modalità veloce dimezza diametri, valvole e varianti: i numeri non sono quelli definitivi.

---

## 2. INPUT.py: come si modifica

**Regole di base**

- Si cambia solo il valore a destra dei due punti. Non si toccano i nomi delle chiavi (la parola a sinistra, tra virgolette).
- I numeri si scrivono senza virgolette: `4.0`, non `"4.0"`. Il separatore decimale è il punto.
- Le stringhe vanno tra virgolette: `"completa"`.
- `True` / `False` senza virgolette. `None` (nessun valore) senza virgolette.
- I commenti dopo `#` sono solo note: si possono leggere, non cambiano nulla.
- Dopo ogni modifica si salva e si lancia `RUN.py`. Ogni run copia il file usato in `INPUT_usato.py`: così sai sempre con quali dati è stato prodotto un risultato.

**Il marcatore SEGNAPOSTO** nei commenti indica che il valore è una stima da sostituire con un dato vero (scheda tecnica, misura, schema). Le conclusioni sul peso assoluto dipendono molto da questi valori.

**Le fonti** accanto ai valori: `[PIL]` indicazioni di Pilone, `[COMP]` documentazione COMPASS, `[XLS]` foglio di dimensionamento del team, `[EUG]` ESA User Guide, `[ESA]` regolamento volo parabolico, `[LET]` letteratura.

### Sezione 0 — ESECUZIONE

| Chiave | Cosa fa | Note |
|---|---|---|
| `etichetta` | testo libero nel nome della cartella di output | vuoto = nome automatico |
| `modalita` | `"completa"` o `"veloce"` | veloce: griglia ridotta, per prove |
| `verifiche_fisiche` | `True` esegue prima i 37 controlli del codice | se un controllo fallisce, la run si ferma |
| `risoluzione_voxel_mm` | risoluzione della griglia dello spazio interno | 4 mm per le prove, 2–3 mm per i risultati finali |
| `formato_grafici` | `["svg"]` oppure `["svg", "png"]` | |
| `cartella_output` | cartella dove salvare le run | per default `output` |

### Sezione 1 — MISSIONE E MASSA

| Chiave | Valore attuale | Cosa cambia |
|---|---|---|
| `massa_per_spinta_kg` | 5 | massa con cui si calcola la spinta richiesta; cambiarla cambia la spinta per asse |
| `massa_obiettivo_kg` | 4.0 | sopra questo valore: avviso e punteggio "massa" più basso |
| `massa_massima_kg` | `None` | sopra questo valore il progetto **non è ammissibile**. `None` = uguale a `massa_per_spinta_kg` |
| `massa_vincolante` | `True` | `False`: la massa massima dà solo un avviso |
| `disturbo_residuo_g` | 0.01 | disturbo sugli assi laterali, usato per la spinta |
| `distanza_traslazione_m` | 0.3 | SEGNAPOSTO: distanza della traslazione di riferimento |
| `tempo_traslazione_s` | 3.0 | SEGNAPOSTO: tempo della traslazione |
| `margine_spinta` | 1.2 | fattore di margine sulla spinta |
| `spinta_per_asse_N` | `None` | `None` = calcolata dalle chiavi sopra; se scrivi un numero, quello viene usato |
| `finestra_libera_s` | 5.0 | durata utile della finestra di microgravità per il controllo delle ruote |
| `durata_microgravita_s` | 22.0 | usata nel foglio Excel per l'energia di una parabola |
| `assi_contemporanei_max` | 3 | quanti assi spingono insieme nel calcolo di corrente di picco e ingestione |

**Attenzione alla spinta.** `spinta_per_asse_N` è `None` e quindi la spinta viene calcolata da `massa_per_spinta_kg`. Se cambi la massa per la spinta, cambia anche la forza richiesta per ogni configurazione.

### Sezione 2 — AMBIENTI

| Chiave | Cosa fa |
|---|---|
| `AMBIENTI` | elenco di ambienti; ognuno ha `p` (pressione in Pa), `T` (temperatura in K) e `descrizione` |
| `AMBIENTE_PROGETTO` | quale ambiente dimensiona la spinta. Deve essere uno dei nomi in `AMBIENTI` |

Per default: `volo_20C` (825 mbar, 20 °C) per il volo; `lab_20C` (1013 mbar) per il banco. Gli altri ambienti (`volo_18C`, `volo_25C`) servono per il grafico di sensibilità alla temperatura.

### Sezione 3 — CUBO

| Chiave | Valore | Cosa fa |
|---|---|---|
| `lato_cubo_min_mm` | 280.0 | **intervallo del lato del cubo**: limite inferiore (mm). Il lato ottimo è un risultato |
| `lato_cubo_max_mm` | 350.0 | limite superiore (mm), sempre incluso nell'analisi |
| `lato_cubo_passo_mm` | 10.0 | passo dell'intervallo: ogni lato in più allunga la run (280–350 con passo 10 = 8 lati) |
| `parete_cubo_mm` | 3.0 | SEGNAPOSTO: spessore della parete (entra nello spazio interno) |
| `parete_condotto_mm` | 1.2 | SEGNAPOSTO: spessore del condotto; minimo 0,6 mm |
| `gioco_tra_condotti_mm` | 5.0 | distanza minima tra condotti: sotto zero i condotti si intersecano |
| `centro_di_massa_mm` | [0,0,0] | **non collegata**: il baricentro usato è `scostamento_baricentro_mm` |
| `scostamento_baricentro_mm` | 5.0 | offset del baricentro per il bilancio dei momenti |
| `ZONE_RISERVATE` | 4 moduli | sensori, aggancio, docking: asse, segno, larghezza, profondità. Le dimensioni sono SEGNAPOSTO |
| `ZONA_CENTRALE_FACCE_MM` | 120.0 | quadrato centrale di ogni faccia dove le bocche non possono stare |
| `FACCIA_SPORTELLINO` | (0, +1) | faccia dove deve toccare la batteria |
| `FACCIA_LIBERA` | (0, -1) | faccia dove le bocche sono ammesse anche al centro |

La convenzione degli assi è nel commento in cima al file: X destra/sinistra, Y fronte/retro, Z alto/basso.

### Sezione 4 — COMPONENTI

| Chiave | Cosa fa |
|---|---|
| `COMPONENTI` | batteria, ruote di reazione, avionica, regolatori ESC: ingombro `dim` in mm, `criterio` di collocazione, `massa_kg` |
| `ESC_4IN1_MM` | ingombro di una scheda ESC, una ogni 4 motori. SEGNAPOSTO |
| `MASSE_FISSE` | masse di moduli e cavi che non occupano volume da collocare. SEGNAPOSTO |

I componenti vengono collocati in ordine: la batteria deve toccare la faccia dello sportellino, gli altri si mettono al centro. Se non entrano, il progetto è scartato per ingombro (lo stop dei diametri scatta in quel caso).

### Sezione 5 — TELAIO (massa della struttura)

Tutti i valori sono SEGNAPOSTO finché non pesi un prototipo.

| Chiave | Cosa fa |
|---|---|
| `materiale_guscio` | uno dei materiali della sezione 9 |
| `spessore_equivalente_guscio_mm` | spessore equivalente del guscio |
| `massa_longherone_g_per_m` | massa per metro dei longheroni sugli spigoli |
| `massa_nodo_g` | massa di un nodo d'angolo (8 vertici) |
| `passo_staffe_mm` | una staffa ogni questo passo di condotto |
| `massa_staffa_g_a_D30`, `massa_statore_g_a_D30` | masse scalate con il diametro |
| `spessore_alloggiamento_ventola_mm` | anello attorno al rotore |
| `larghezza_flangia_bocca_mm`, `spessore_flangia_bocca_mm` | rinforzo attorno ai fori nel guscio |
| `densita_rete_griglia_g_m2` | massa delle griglie di protezione |
| `massa_esc_4in1_g`, `massa_cablaggio_per_motore_g` | massa di ESC e cablaggi |
| `frazione_viteria_colla` | percentuale in più su viteria e colla |

Queste voci compongono il bilancio di massa per configurazione (foglio Excel **Massa**).

### Sezione 6 — ELEMENTI DEL CONDOTTO

| Chiave | Cosa fa |
|---|---|
| `griglia_ingresso`, `griglia_uscita` | presenza delle griglie di protezione |
| `porosita_griglia_ingresso`, `porosita_griglia_uscita` | SEGNAPOSTO: porosità delle griglie, incide sulle perdite |
| `diametro_filo_griglia_mm` | diametro del filo della griglia |
| `raggio_imbocco_su_D` | raggio dell'imbocco, in frazione del diametro. Più grande = meno perdite |
| `lunghezza_ventola_su_D` | lunghezza della ventola (rotore + statore + motore) in diametri |
| `gioco_punta_mm` | gioco tra pale e parete del condotto |
| `spessore_mozzo_mm` | spessore del mozzo |
| `statore` | `True` = con statore; senza statore il vortice si perde |
| `k_gioco_eta`, `k_gioco_psi` | effetto del gioco sulle prestazioni della ventola |
| `penalita_reversibile` | perdita di rendimento delle pale simmetriche |
| `frazione_vortice_residuo` | quota di vortice residuo con statore |
| `semiangolo_ugello_deg` | semiangolo del Venturi di uscita |
| `alfa_getto`, `beta_getto` | coefficienti del getto (energia e quantità di moto) |
| `rugosita_parete_um` | rugosità della parete |
| `rendimento_esc` | rendimento del regolatore |

Il **Venturi** (rapporto d'area dell'uscita) non si cambia qui: si provano i valori in `OTTIMIZZAZIONE["sigma"]` (sezione 10).

### Sezione 7 — VENTOLE, MOTORI, BATTERIA

| Chiave | Cosa fa |
|---|---|
| `TIPI_VENTOLA` | tre tipi di ventola con coefficienti adimensionali. SEGNAPOSTO: da sostituire con la curva misurata |
| `MOTORI` | cinque motori brushless con `Kv`, `R`, `I0`, `I_max`, massa, diametro, inerzia. SEGNAPOSTO |
| `ELETTRICO` | `tensione_bus_V` (24 V), `duty_massimo`, `corrente_max_pacco_A` (15 A) |
| `ROTORE` | massa del rotore e inerzia |

I motori vengono scelti per ogni geometria: la combinazione con la potenza minima per asse, ammissibile per tensione, corrente e Mach. Se aggiungi un motore, rispetta le chiavi degli altri.

**Non collegata:** `capacita_Wh` (72 Wh) è letta ma non usata dal calcolo.

### Sezione 8 — LIMITI

| Chiave | Valore | Cosa fa |
|---|---|---|
| `mach_punta_max` | 0.30 | sopra questo Mach le formule incomprimibili non valgono: progetto non ammissibile |
| `velocita_punta_max_m_s` | 150 | SEGNAPOSTO: velocità massima della punta della pala |
| `indice_ingestione_attenzione` | 0.05 | soglia di avviso per la riaspirazione dei getti |
| `indice_ingestione_critico` | 0.20 | soglia critica |
| `momento_ruote_max_Nms` | 0.15 | capacità di una ruota di reazione. SEGNAPOSTO |
| `differenza_spinta_coppia` | 0.05 | squilibrio ammesso tra due ventole di una coppia |

**Non collegata:** `tempo_salita_spinta_max_s` (0,5 s). Il tempo di salita è valutato nel punteggio "dinamica" con `OTTIMIZZAZIONE["scala_tempo_salita_s"]`.

### Sezione 9 — MATERIALI E CARICHI

| Chiave | Cosa fa |
|---|---|
| `MATERIALI` | quattro materiali con modulo elastico, Poisson, densità, snervamento, dimensione massima di stampa |
| `MATERIALE_CONDOTTO` | materiale dei condotti (scelto da `MATERIALI`) |
| `CARICHI` | ipergravità 1,8 g e atterraggio d'emergenza 9 g: servono per gli sforzi |

### Sezione 10 — OTTIMIZZAZIONE E CLASSIFICA

| Chiave | Cosa fa |
|---|---|
| `diametri_mm` | lista dei diametri del condotto alla ventola da provare, in ordine crescente |
| `sigma` | rapporti d'area dell'uscita da provare (Venturi) |
| `pesi` | peso di ciascun criterio nel punteggio: spazio, perdite, semplicità, robustezza, dinamica, massa |
| `scala_volume_libero`, `scala_potenza_asse_W`, `scala_tempo_salita_s` | soglie che trasformano una misura in punteggio da 0 a 1 |

I pesi si possono cambiare anche nell'Excel (foglio **Classifica**, celle gialle): il punteggio totale e la posizione sono formule.

**Come agisce la lista dei diametri.** Per ogni variante geometrica si sale con il diametro. Il primo diametro che rende lo spazio non ammissibile (condotti che si intersecano, moduli riservati, bocche nelle zone centrali, componenti che non entrano) ferma la salita per quella variante: i diametri successivi non vengono analizzati. Motore, Mach e massa **non** fermano la salita: per ora si analizzano tutti i diametri della lista.

### Sezione 11 — SCENARI

Ogni scenario è un blocco `{...}` nella lista `SCENARI`.

| Chiave | Cosa fa |
|---|---|
| `id` | nome breve che compare in tutte le tabelle e nei grafici |
| `attivo` | `True` = analizzato, `False` = escluso dalla run |
| `nome`, `origine`, `descrizione`, `pregi_attesi`, `difetti_attesi` | testi: appaiono nell'Excel |
| `topologia` | uno tra `sfalsati`, `spigoli_corti`, `spigoli_centrati` |
| `varianti_geometria` | liste di valori: l'ottimizzatore prova tutte le combinazioni |

**Lo scenario S4 (`S4_SPIGOLI_CENTRATI_12`)** è quello della tua foto. Ha tre parametri che puoi cambiare:

- `lunghezza_frazione` (default 0.8): lunghezza del condotto in frazione del massimo consentito. Con 1 il condotto arriva al limite, con valori piccoli si accorcia.
- `spostamento_frazione` (default 0.0): spostamento lungo lo spigolo. Con 0 il condotto è centrato e il pezzo conserva i tre piani di simmetria. Valori negativi o positivi lo spostano verso i due vertici e rompono la simmetria.
- `posizione_ventola_frazione` (default 0.3): posizione della ventola lungo il condotto, dalla presa.

La griglia `varianti_geometria` provata di default è: lunghezza `[0.7, 0.8, 0.9, 1.0]` × spostamento `[-0.5, 0.0, 0.5]`, cioè 12 varianti. Per cambiarle modifica le due liste.

Il limite fisico dello spostamento è dentro il codice: il condotto deve restare a cavallo della mezzeria dello spigolo e non superare la distanza c dal vertice. Un valore troppo grande viene riportato automaticamente al limite.

**Per escludere uno scenario**: cambia `"attivo": True` in `"attivo": False` nel suo blocco. I dati restano nel file.

---

## 3. RUN.py: cosa fa

Il file ha un solo scopo: eseguire le analisi e salvare i risultati. Non si modifica.

**Comandi**

```bash
python RUN.py                     # usa INPUT.py con i valori di ESECUZIONE
python RUN.py --veloce            # come modalita = "veloce", senza toccare il file
python RUN.py --input altro.py    # usa un altro file di input
```

**Cosa fa in ordine**

1. **Verifiche fisiche.** Esegue 37 controlli del codice contro risultati noti (attrito, bilancio di potenza, affinità delle ventole, simmetria dei condotti, rotazione a 120°, massa di un tubo). Se uno fallisce, la run si ferma: non vanno usati risultati di un codice che non passa i controlli.
2. **Analisi per ogni scenario attivo.** Per ogni variante geometrica e per ogni diametro: geometria, componenti, ventola, motore, dinamica, struttura, massa, punteggio. Il progetto migliore dello scenario è quello ammissibile con il punteggio più alto. Se nessuno è ammissibile, viene riportato il meno peggio con le violazioni.
3. **Grafici** per scenario e di confronto.
4. **Excel** con tutti i fogli.
5. **Riepilogo** nella cartella e a schermo.

**Tempi.** Il tempo è circa il numero di lati dell'intervallo per il tempo di una run a lato fisso. Con 8 lati la run completa dura molto di più di prima (diverse decine di minuti, ore con griglie di varianti fitte). Per le prove usa `"modalita": "veloce"`, che analizza un lato su due, o riduci l'intervallo o aumenta il passo.

**Come leggere il log (righe nel terminale).**

| Riga | Significato |
|---|---|
| `verifiche superate` | i 37 controlli passano: si può andare avanti |
| `L 315 · D  34 (...): punteggio 0.649` | progetto con lato del cubo L e diametro D, ammissibile, con punteggio |
| `L 315 · D  34 (...): punteggio 0.649 con violazioni` | progetto analizzato ma non ammissibile (motore, Mach, massa, ecc.) |
| `L 315 · D  42 (...): spinta non raggiunta` | la ventola non riesce a dare la spinta richiesta con questo diametro |
| `spazio/geometria non ammissibile; diametri successivi ... non analizzati` | lo stop per ingombro (anche componenti che non entrano): si passa alla variante successiva |
| `>> lato 315 mm (2/8): miglior punteggio ...` | riepilogo di ogni lato del cubo con il suo miglior progetto: serve a seguire l'avanzamento di una run lunga |
| `massimo diametro ammissibile (Xi) tra le varianti, per lato: ...` | per ogni lato l'intervallo dei diametri massimi ammissibili (solo informativo) |
| `-> ottimo: lato L = 315 mm, D = 34 mm (...)` | il progetto migliore dello scenario, con il suo lato del cubo |
| `ATTENZIONE: il lato ottimo è al limite ...` | l'ottimo coincide con un estremo dell'intervallo del lato: conviene allargarlo |
| `avviso:` | aspetto da tenere d'occhio che non blocca il progetto (risonanze, massa sopra obiettivo, assi pieni contemporanei) |

Il riepilogo finale elenca gli scenari dal migliore, con punteggio, lato L, diametro, potenza per asse, spazio libero, massa e stato. Segue il blocco **LATO OTTIMO DEL CUBO**, con il lato di ogni scenario.

---

## 4. La cartella output

Ogni run crea una cartella nuova, mai sovrascritta:

```
output/AAAAMMGG-HHMMSS_<etichetta>_<impronta>/
```

- **data e ora** della run;
- **etichetta**: quella scritta in `ESECUZIONE["etichetta"]`, altrimenti automatica (spinta, lato, ambiente, numero di scenari);
- **impronta**: 8 caratteri ricavati dagli input. Due cartelle con la stessa impronta sono state prodotte con gli stessi dati.

Per le tue prove la cartella da guardare è l'ultima per data. Le run precedenti restano lì.

### Contenuto

```
output/AAAAMMGG-HHMMSS_…/
├── excel/
│   └── Confronto_scenari.xlsx         ← il file principale
├── grafici/
│   ├── S1_SFALSATI_12/                ← 9 grafici per scenario
│   ├── S2_SPIGOLI_CORTI_12/
│   ├── S3_REVERSIBILI_6/
│   ├── S4_SPIGOLI_CENTRATI_12/
│   └── confronto/                     ← 13 grafici che mettono a confronto gli scenari
├── dati/
│   ├── riepilogo.json                 ← risultati principali per scenario
│   └── progetti.csv                   ← ogni progetto valutato (separatore ;)
├── INPUT_usato.py                     ← copia esatta degli input della run
└── log.txt                            ← registro completo della run
```

Nella cartella `output/` c'è anche **`registro_esecuzioni.csv`**: una riga per run, con data, cartella, impronta, numero di scenari e scenario vincente.

### Excel: i 15 fogli

| Foglio | Cosa contiene | Quando guardarlo |
|---|---|---|
| **Leggimi** | come si legge il file, dati di missione e massa | prima di tutto |
| **Classifica** | punteggi per criterio, totale pesato, posizione. Pesi modificabili nelle celle gialle | per capire chi vince e perché |
| **Progetto ottimo** | tutti i numeri del progetto migliore di ogni scenario, con unità | per leggere un progetto nel dettaglio |
| **Fluidodinamica** | punto di lavoro della ventola: giri, portata, pressione, rendimento, potenza | per verificare che la ventola lavori in una zona sensata |
| **Perdite** | ripartizione della potenza tra griglie, imbocco, attrito, curve, ugello, energia del getto | per capire dove si perde potenza |
| **Spazio interno** | volumi, cubo libero, posizione dei componenti | per capire dove stanno batteria, ruote, avionica |
| **Controllo e dinamica** | forze e momenti, forza residua con una ventola guasta, salita della spinta, margine di fase, ruote di reazione | per il controllo di assetto |
| **Struttura** | frequenza del condotto, Campbell, instabilità, sforzi | per la resistenza |
| **Massa** | bilancio voce per voce, totale, scarto dall'obiettivo e margine sulla massima | per il vincolo dei 4 kg |
| **Realizzabilità** | parti stampate, curve, attuatori, punteggio di realizzabilità | per la stampabilità |
| **Ingestione getti** | indice di riaspirazione per ogni comando su più assi | per la sicurezza dei getti |
| **Tutti i progetti** | ogni combinazione provata, anche le scartate, con il motivo | per vedere le alternative |
| **Scenari** | descrizione e parametri di ogni scenario | per ricordare cosa è stato provato |
| **Ipotesi e fonti** | correlazioni usate, campo di validità, segnaposto | per sapere cosa è stima |
| **Grafici** | elenco di tutti i file grafici con collegamento | per aprire i grafici dall'Excel |

Nota: nel terminale di Windows i nomi con accenti possono comparire storti (per esempio `Realizzabilit�`). È un problema della console, il file è corretto.

### Grafici per scenario (`grafici/<scenario>/`)

| File | Cosa mostra |
|---|---|
| `01_viste_layout.svg` | vista dall'alto, di fronte, di lato e 3D del layout. Tratteggio: volumetti tolti ai vertici |
| `02_profili_giri.svg` | velocità, pressione statica e totale lungo il condotto, a più giri |
| `03_profili_ambienti.svg` | gli stessi profili negli ambienti di volo e di laboratorio |
| `04_mappa_ventola.svg` | curve della ventola e del sistema, con il punto di progetto |
| `05_spinta_giri_potenza.svg` | spinta in funzione dei giri, della pressione e della potenza elettrica |
| `06_perdite.svg` | ripartizione della potenza utile della ventola |
| `07_salita_spinta.svg` | tempo per raggiungere il 90 % della spinta, con il limite di corrente |
| `08_campbell.svg` | diagramma di Campbell: risonanze che il condotto attraversa |
| `09_ingestione.svg` | indice di riaspirazione per ogni comando su più assi |

### Grafici di confronto (`grafici/confronto/`)

| File | Cosa mostra |
|---|---|
| `01_punteggi.svg` | punteggi per criterio e totale, per scenario |
| `02_radar.svg` | profilo dei punteggi di ogni scenario |
| `03_pareto_spazio_potenza.svg` | spazio libero contro potenza per asse, un punto per diametro |
| `04_sensibilita_diametro.svg` | come cambiano volume, spazio e potenza al variare del diametro |
| `05_perdite_per_categoria.svg` | ripartizione delle perdite a confronto |
| `06_spazio_interno.svg` | spazio interno dei progetti migliori |
| `07_stabilita_margine_fase.svg` | margine di fase dell'anello di posizione |
| `08_ruote_di_reazione.svg` | momento accumulato dalle ruote nella finestra di 5 s |
| `09_autorita_guasti.svg` | forza e momento disponibili, tolleranza a una ventola guasta |
| `10_struttura.svg` | frequenza, instabilità e rigidezza dei condotti |
| `11_effetto_ambiente.svg` | come la spinta cambia con la pressione a giri fissi |
| `12_bilancio_massa.svg` | massa totale per scenario, con obiettivo e massima; a destra le voci che cambiano |
| `13_lato_cubo.svg` | punteggio e massa del miglior progetto per ogni lato del cubo; la stella è il lato ottimo di ogni scenario |

### Dati

- **`dati/riepilogo.json`**: per ogni scenario il progetto migliore, con diametro, variante, punteggi, violazioni, avvisi e voci di massa. Si legge con un editor di testo o con Python.
- **`dati/progetti.csv`**: una riga per ogni progetto valutato, con lato del cubo (`L_mm`), diametro, variante, ammissibilità, punteggio, potenza e massa. Separatore `;`, si apre direttamente con Excel in italiano.

---

## 5. Come leggere un risultato

Ordine consigliato, per non perdere il filo:

1. **Terminale**: il riepilogo finale. Vedi chi è ammissibile e chi no, e perché.
2. **Excel, Classifica**: punteggi e vincitore. Qui cambi i pesi per vedere se la classifica si rovescia.
3. **Excel, Massa**: il vincolo dei 4 kg. Dove si perde massa e quanto manca.
4. **Excel, Progetto ottimo**: i numeri del progetto vincente.
5. **Excel, Spazio interno** e **grafico `01_viste_layout.svg`**: verifica che la geometria sia quella che hai in mente.
6. **Excel, Perdite** e **grafico `06_perdite.svg`**: dove va la potenza.
7. **Excel, Controllo e dinamica** e **grafico `09_autorita_guasti.svg`**: assetto e guasti.
8. **Excel, Struttura** e **grafico `08_campbell.svg`**: risonanze.
9. **Excel, Ingestione getti**: sicurezza dei getti.
10. **Excel, Tutti i progetti**: le alternative scartate e il motivo.

Il punteggio totale viene per ultimo: dipende dai pesi, che sono una scelta del team, non un risultato della fisica.

---

## 6. Come confrontare due run

Ogni cartella di output contiene `INPUT_usato.py`: il file esatto usato per quella run.

- Per confrontare due run, apri i due `INPUT_usato.py` e cerca le differenze.
- Il file `output/registro_esecuzioni.csv` elenca le run in ordine di data. Due righe con la stessa impronta hanno usato gli stessi dati.
- Dalla ricerca sul lato del cubo il nome della cartella contiene l'intervallo (per esempio `L280-350`) invece di un lato solo: le run precedenti (`L320`) hanno un lato fisso e non sono confrontabili con quelle nuove.
- La run `20261103-163031_…` usava una regola di stop più aggressiva: si fermava anche per motore e massa. Ha quindi meno diametri analizzati. Non confrontarla con la run più recente sui diametri.

---

## 7. Cosa non fidarsi ancora

- **Valori SEGNAPOSTO**: motori, curve delle ventole, masse dei componenti, parametri del telaio, dimensioni dei moduli. Il peso assoluto della massa dipende soprattutto da questi.
- **Stime di screening**: effetto di sistema, indice di riaspirazione, perdita dei volumetti d'angolo. Vanno confermate con CFD o al banco.
- **Ipotesi sullo stop dei diametri**: per l'ingombro è dimostrata (cresce con D). Per motore, Mach e massa non si applica lo stop.
- **Massa di S4**: 4,56 kg, sopra l'obiettivo di 4 kg. Il margine dipende dalle stime sopra.
- **Chiavi non collegate**: `centro_di_massa_mm`, `tempo_salita_spinta_max_s`, `capacita_Wh`. Non cambiano nessun risultato.

---

## 8. Checklist della prima prova

- [ ] `INPUT.py`: `modalita` su `"veloce"`, `verifiche_fisiche` su `True`
- [ ] `python RUN.py` finisce con `Finito in … s`
- [ ] Nel terminale: `37/37 verifiche superate`
- [ ] Ultima cartella in `output/` presente, con `excel/Confronto_scenari.xlsx`
- [ ] Excel: foglio **Classifica** aperto, vincitore letto
- [ ] Excel: foglio **Massa** aperto, totale di S4 letto
- [ ] Grafico `grafici/S4_SPIGOLI_CENTRATI_12/01_viste_layout.svg` aperto
- [ ] Modifica di prova: `lunghezza_frazione` in S4 da `0.8` a `0.9`, nuova run, confronto di `Classifica`
- [ ] `modalita` riportata su `"completa"` prima della run definitiva
