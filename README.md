# Dinamica di volo del cubo COMPANION

Questa cartella risponde a una domanda pratica: durante una parabola, il cubo riesce a spostarsi di quanto
vogliamo, nel tempo che abbiamo, e a fermarsi dove deve? Per rispondere simula il moto del cubo (configurazione S4)
con i suoi propulsori, il regolatore di posizione e i disturbi che troverà in volo: l'aereo che non è mai a 0 g
perfetti, il rilascio che lascia il cubo con un po' di velocità, le pale stampate che non pesano tutte uguali.

Il dimensionamento dei condotti, della ventola e del motore non si fa qui ma nella cartella accanto,
`../Dimensionamento_Sistema_Propulsivo`. Da lì si copiano a mano in `input.py` i numeri che servono (spinta di una
faccia, potenza, giri, pale), fonte `[DIM]`. Il collegamento è spiegato più sotto.


## Come si lancia

Una volta sola:

```bash
pip install -r requirements.txt
```

Servono solo `numpy` e `matplotlib`, più `pytest` per i test.

Poi, ogni volta:

```bash
python run_dinamica.py
```

La run dura qualche secondo. Prima di simulare controlla il codice con 28 verifiche contro soluzioni note (una volta
sola); se una non torna, si ferma e non scrive risultati. La run produce una soluzione per ogni ambiente attivo (volo
parabolico, ISS) e un confronto. Alla fine dice dove ha messo i file: il primo da aprire è
`risultati/<caso>/CONFRONTO.md`, poi `risultati/<caso>/<ambiente>/00_sintesi/RISULTATO.md`.

Altri comandi utili:

```bash
python run_dinamica.py --input altro_input.py   # usa un altro file di input
python -m dinamica_designer.verifiche           # solo le verifiche, con il dettaglio di ognuna
python -m pytest tests -q                       # i test automatici
```

Per cambiare qualcosa si modifica soltanto `input.py`. Il codice in `dinamica_designer/` non va toccato per l'uso
normale.


## Cosa c'è nella cartella

```
Dinamica_Sistema_Propulsivo/
├── input.py               l'unico file da modificare
├── run_dinamica.py        lancia la run
├── dinamica_designer/     il codice
│   ├── cli.py             la sequenza della run: legge l'input, verifica, simula, scrive
│   ├── volo.py            il moto di un asse: riferimento, disturbo, regolatore, integrazione nel tempo
│   ├── pale.py            lo squilibrio dei rotori dovuto alle pale stampate
│   ├── propulsore.py      salita della spinta, margine di fase, ruote di reazione
│   ├── export.py          grafici, tabelle, RISULTATO.md
│   ├── caso.py            nome e cartella del caso (una cartella per ambiente)
│   ├── confronto_dimensionamento.py  controllo dei dati [DIM] contro il caso del dimensionamento
│   └── verifiche.py       i controlli contro soluzioni analitiche
├── tests/                 test pytest
└── risultati/             un caso per cartella (non va su git)
```


## Il modello, un pezzo alla volta

### Il cubo

Il cubo è trattato come un punto con tutta la massa nel baricentro (4,5 kg oggi, la massa di missione, la stessa del dimensionamento). Si muove lungo X, Y e Z nello
stesso momento, ma i tre assi non si parlano: quello che succede su X non cambia Y. Le rotazioni non ci sono. È una
semplificazione forte, ma per capire se la spinta basta e quanto bene si ferma il cubo è sufficiente.

Su ogni asse vale la seconda legge di Newton:

```
m dv/dt = F - m a_d(t)
```

dove `F` è la spinta dei propulsori su quell'asse e `a_d` è l'accelerazione di disturbo (più avanti). Il segno meno
vuol dire che un disturbo positivo frena un moto positivo.

### I propulsori

La spinta non arriva subito: la ventola deve prendere giri. Lo modelliamo come un ritardo del primo ordine,

```
tau dF/dt = F_cmd - F,     tau = t90 / 2,3
```

dove `t90` è il tempo che la spinta impiega ad arrivare al 90 % del valore chiesto (0,16 s oggi: 0,11 s di salita dei giri più 0,05 s di ritardo del regolatore, una stima). Le ventole sono reversibili e per
cambiare verso impiegano di più: questo il modello non lo vede.
La spinta chiesta non può superare la spinta massima per verso; se la supera, viene tagliata (saturazione).

### Gli ambienti

La stessa manovra si simula in due ambienti, ognuno con la sua pressione e il suo disturbo (sezione `AMBIENTI` di
`input.py`):

| ambiente | pressione | disturbo | finestra |
|---|---|---|---|
| `Volo_Parabolico` | 82 500 Pa (cabina durante le parabole, rho 0,98 kg/m³) | bias 0,01 g, rumore 0,002 g, v0 0,01 m/s | 5 s |
| `ISS` | 101 325 Pa | bias 4e-5 g, rumore 1e-5 g, v0 0,005 m/s [STIMA, da sostituire] | 10 s (si osserva anche l'assestamento) |

Ogni ambiente ha `attivo` (True/False), `pressione_Pa` e le chiavi di `DISTURBO` e `MANOVRA` (o di altre sezioni) che
cambiano: si fondono sulle sezioni di base, che restano i valori comuni. Se un solo ambiente è attivo la run funziona
lo stesso, con una sola cartella.

Spinta e potenza dipendono dall'aria. I dati dell'attuatore in `input.py` sono quelli di progetto, validi alla
pressione `ATTUATORE["pressione_progetto_Pa"]` (101 325 Pa, la `p_amb` del dimensionamento). In un ambiente con
`sigma = pressione / pressione di progetto`, stessa temperatura, ventole a geometria e giri fissati (leggi di
similitudine):

```
spinta massima dell'ambiente  = spinta massima di progetto x sigma          (agli stessi giri massimi)
potenza per erogare F         = P_rif (F / F_rif)^esponente / sqrt(sigma)   (per la stessa spinta in aria meno densa
                                                                              servono più giri)
```

Con `sigma = 1` tutto torna uguale a prima (c'è una verifica). Nel volo parabolico sigma vale 0,814: spinta massima
0,953 N per asse e potenza maggiorata del 10,8 %. Sigma, spinta massima e fattore di potenza sono nel log, in
`RISULTATO.md`, in `riepilogo.json` e in `CONFRONTO.md`.

### Il regolatore

Il cubo deve seguire un riferimento: parte fermo, si sposta di una distanza d in un tempo T e si ferma. Il profilo
predefinito è "a minimo jerk" (`minimo_jerk`), un polinomio di quinto grado che parte e arriva con velocità e
accelerazione nulle, quindi senza strattoni. Si può scegliere anche `gradino` e `bang_bang`: accelerazione costante
4 d / T² per T/2 e poi l'opposta, da fermo a fermo, poi riferimento fermo in d. Il bang-bang è il profilo con cui il
dimensionamento calcola la spinta, ma con il ritardo dell'attuatore non è inseguibile esattamente agli istanti di
commutazione: serve come confronto.

Il regolatore confronta posizione e velocità vere con quelle del riferimento e calcola la spinta:

```
F_cmd = m [ kp (x_rif - x) + kd (v_rif - v) + ki * integrale di (x_rif - x) ]
```

I tre guadagni non si scelgono a mano: si danno la banda `wn`, lo smorzamento `zeta` e la posizione del terzo polo
`alfa`, e il codice li ricava mettendo i poli in `(s + alfa wn)(s^2 + 2 zeta wn s + wn^2)`:

```
kp = (1 + 2 zeta alfa) wn^2      kd = (2 zeta + alfa) wn      ki = alfa wn^3
```

Con `alfa = 0` il termine integrale sparisce e resta un PD. Con `alfa > 0` diventa un PID. Quando la spinta è in
saturazione l'integrale si ferma, altrimenti continuerebbe a crescere e farebbe sovraelongare il cubo.

Perché l'integrale conta: con un disturbo costante (il bias, sotto) il PD si ferma in una posizione sbagliata di

```
errore = bias / wn^2
```

Con 0,01 g e `wn` = 2 rad/s sono 24,5 mm, cinque volte la tolleranza di 5 mm. Il PID invece porta l'errore a zero.
Il feedforward (`feedforward_riferimento`) aggiunge al comando la spinta che servirebbe per seguire il riferimento
senza disturbi; senza, il regolatore insegue sempre in ritardo e l'integrale si carica di quel ritardo.

### Il disturbo del volo parabolico

In una parabola l'aereo non sta mai a 0 g esatti. Il cubo, che galleggia libero nella cabina, vede l'aereo muoversi
attorno a sé, ed è come se su di lui agisse una piccola accelerazione. La modelliamo come somma di tre pezzi più una
condizione iniziale, seguendo le proposte uscite nella chat del team:

| pezzo | cosa rappresenta | valore di default |
|---|---|---|
| bias costante | la deriva lenta del livello di gravità | 0,01 g, direzione casuale |
| rumore gaussiano a media nulla | le correzioni del pilota e le vibrazioni, tagliato sopra 1 Hz | sigma 0,002 g |
| sinusoide (facoltativa) | un'oscillazione lenta, se la si vuole vedere a parte | spenta |
| velocità iniziale | il rilascio non è mai perfetto | 0,01 m/s, direzione casuale |

Da dove vengono i numeri. Il report ERMES (ESA Fly Your Thesis 2022, nella cartella Documentazione del progetto)
riporta alla Fig. 6.3.2 l'accelerometro di Novespace durante una parabola vera (volo 302, 26 ottobre 2022).
Nei 22 s di microgravità le tre componenti stanno sotto 0,02 g. Si vedono due cose:

- una parte lenta di circa ±0,01 g: Gz oscilla con un periodo di 6-7 s, Gx scivola da +0,015 a -0,02 g;
- un rumore veloce di circa ±0,003 g sopra la parte lenta.

Su una finestra di 5 s la parte lenta è quasi costante, per questo la trattiamo come un bias di 0,01 g (lo stesso
valore proposto da Mattia). Il rumore veloce di ±0,003 g corrisponde a una sigma di circa 0,002 g. Per la velocità
al rilascio ERMES chiedeva al suo meccanismo 0,005 ± 0,001 m/s per asse sul bersaglio (requisito P.4.2) e scrive che
con il rilascio a mano una piccola velocità residua era "quasi inevitabile": 0,01 m/s in modulo è una stima prudente.

Il modulo ESA per le proposte (lo si trova nel Deploy! Proposal, §6.3.2) parla di g-jitter di ±0,05 g attorno a 1 Hz.
È un valore da manuale, circa dieci volte quello che si vede nella registrazione. Lo teniamo come prova di robustezza:
basta mettere `rumore_sigma_g` attorno a 0,025.

Il rumore viene generato così: si prende rumore bianco gaussiano, se ne tolgono in frequenza tutte le componenti sopra
la banda, e lo si riscala perché la deviazione standard sia esattamente quella dell'input.

### Caso peggiore e Monte Carlo

Il disturbo ha direzioni casuali, quindi un'unica simulazione non basta. La run ne fa due tipi.

Il caso peggiore mette bias e velocità iniziale col modulo pieno su tutti e tre gli assi insieme, nel verso che si
oppone al moto, senza rumore. È pessimista apposta: il bias vero ha modulo 0,01 g in tutto, non su ogni asse. Da qui
vengono il grafico del moto e la tabella per asse.

Tutto questo si ripete in ogni ambiente. Il Monte Carlo estrae 200 volte (il numero si cambia) una direzione a caso per il bias, una per la velocità iniziale,
un rumore diverso e, se c'è, una fase della sinusoide. Per ogni asse riporta media, 95° percentile e massimo degli
errori, e la quota di campioni che si assestano dentro la tolleranza entro la finestra. Il seme è fisso, quindi la
stessa run dà sempre gli stessi numeri. Le 200 simulazioni girano tutte insieme come vettori, per questo la run resta
veloce.

### Le pale

Le pale delle ventole saranno stampate in 3D, e due pale stampate non pesano mai uguale: la densità cambia un po' con
i vuoti tra le linee di deposizione, l'umidità del filamento, la posizione sul piatto. Se le pale di un rotore hanno
masse diverse, il baricentro del rotore non sta più sull'asse e il rotore, girando, tira il cubo in una direzione che
gira con lui.

Ogni pala è un parallelepipedo con lunghezza (radiale), larghezza (la corda) e spessore dati in input, attaccato al
mozzo. Il suo baricentro sta a metà della lunghezza:

```
r_cg = raggio_mozzo + lunghezza / 2
massa della pala = densità x lunghezza x larghezza x spessore
```

La densità di ogni pala viene estratta a caso nel range dell'input. Con Z pale equispaziate lo squilibrio è

```
U = r_cg | somma delle masse m_k per exp(i 2 pi k / Z) |
```

e a velocità angolare `omega` la forza rotante vale `F = U omega^2`.

Facciamo i conti a mano con i numeri della ventola del dimensionamento. Pala equivalente di 15,47 x 15,4 x 1,46 mm:
volume 348 mm³. In PLA tra 1150 e 1250 kg/m³ pesa tra 0,400 e 0,435 g, quindi la differenza massima fra due pale è
0,035 g. Il baricentro è a 20,8 mm dall'asse. Lo squilibrio peggiore con 3 pale è una pala pesante e due leggere:
0,035 g x 20,8 mm = 0,72 g·mm. A 18 515 giri/min (309 Hz, omega = 1939 rad/s) la forza è 0,72e-6 x 1939² = 2,7 N,
più di una volta e mezzo la spinta di una faccia (1,974 N).

Sembra molto, ma gira a 309 Hz. Il regolatore lavora sotto 1 Hz e non la vede nemmeno; il cubo si comporta come una
massa libera spinta avanti e indietro, e una massa libera spinta da una forza `U omega^2 sin(omega t)` oscilla di

```
x = U / M
```

che non dipende dai giri: 0,72 g·mm / 4,5 kg = 0,16 µm. Anche con quattro ventole in fase sono 0,64 µm. Sulla
traiettoria le pale non contano. Contano invece sulle vibrazioni: 2,7 N a 309 Hz passano per i cuscinetti e la
struttura e arrivano ai sensori inerziali. Il messaggio pratico è che i rotori vanno equilibrati dopo la stampa.

Per questo motivo lo squilibrio non entra nella simulazione nel tempo: per seguire 309 Hz servirebbe un passo di
integrazione sotto 0,2 ms, e il risultato sarebbe comunque `U / M`. I conti sono in forma chiusa in `pale.py`.

Con più di tre pale il caso peggiore non è più una sola pala pesante: conviene che siano pesanti più pale vicine.
Il codice usa la formula generale (`fattore_peggiore`), verificata contro tutte le combinazioni possibili.

C'è anche un secondo effetto, piccolo. Ogni rotore ha un momento angolare `H = (I_pale + J_motore) omega`, circa
1e-3 N·m·s. Le due ventole di una coppia girano in versi opposti e i loro H si annullano, ma solo se le pale pesano
uguale. Il residuo, al 95 % circa 2e-5 N·m·s, finisce sulle ruote di reazione, che ne reggono 0,15.

### Potenza e corrente totali

Per ogni asse la potenza elettrica nel tempo segue la spinta (formula sopra, con il fattore dell'ambiente). Si somma
sui tre assi: potenza totale nel tempo, il suo picco, l'energia nella finestra (integrale), la potenza media (energia /
finestra) e la corrente di picco, cioè potenza di picco / `ENERGIA["tensione_batteria_V"]` (24 V, pacco NiMH 20S).
Sono riportate per il caso peggiore e, nel Monte Carlo, come media / 95° percentile / massimo. La curva è anche nel
grafico del moto (riga in basso). Il picco del totale non è la somma dei picchi dei singoli assi: non coincidono nel
tempo.

### Spazio massimo, tempo minimo, ruote

Oltre alla simulazione, la run calcola a spinta massima quanto spazio si può fare nel tempo della manovra (accelerando
per metà del tempo e frenando per l'altra metà) e il tempo minimo per la distanza richiesta, con e senza bias. Infine
fa il margine di fase dell'anello di posizione realmente simulato (regolatore PD/PID dell'input, massa pura, attuatore del
primo ordine con τ = t90/2,3; pulsazione di taglio e margine calcolati numericamente, avviso sotto 45°; la tabella alle
frequenze fisse è solo un regolatore PD di riferimento con zero a ωc/3) e il bilancio del momento angolare delle
ruote di reazione nella finestra (modelli in `propulsore.py`).


## Il file di input, sezione per sezione

Tutti gli elenchi a tre valori seguono l'ordine [X, Y, Z]. Accanto a ogni numero c'è un commento con la fonte:
`[DIM]` viene dal dimensionamento della propulsione (caso RUN_POST_FIX_11-11), `[ERM]` dal report ERMES, `[XLS]` dal foglio di dimensionamento,
`[team]` dalla chat del team. `SEGNAPOSTO` vuol dire che il valore è provvisorio e va sostituito appena c'è un dato vero.

| sezione | cosa si imposta |
|---|---|
| `CASO` | il nome della cartella dei risultati (`None` = automatico) e se si può sovrascrivere un caso con input diversi |
| 0 `ESECUZIONE` | passo di integrazione, formato dei grafici, cartella di uscita, verifiche sì o no |
| 1 `CORPO` | la massa del cubo |
| 2 `ATTUATORE` | spinta massima di progetto per verso e per asse, tempo di salita al 90 %, pressione di progetto |
| 3 `MANOVRA` | distanza, tempo della manovra, durata della finestra simulata, tolleranza, profilo del riferimento (`minimo_jerk`, `gradino`, `bang_bang`): valori comuni, ogni ambiente può cambiarli |
| 4 `DISTURBO` | bias, sigma e banda del rumore, velocità iniziale, sinusoide facoltativa, campioni del Monte Carlo, seme: valori comuni, ogni ambiente può cambiarli |
| 5 `REGOLATORE` | banda `wn`, smorzamento `zeta`, terzo polo `polo_integrale_su_wn` (0 = PD), feedforward sì o no |
| 6 `ENERGIA` | potenza in funzione della spinta, `P = P_rif (F / F_rif)^esponente` (alla pressione di progetto), tensione della batteria |
| 7 `RUOTE` | dati per il bilancio delle ruote di reazione |
| 8 `PALE` | numero di pale, lunghezza, larghezza, spessore, raggio del mozzo, range di densità, giri, campioni |
| 9 `AMBIENTI` | un dizionario ordinato, un ambiente per soluzione: `attivo`, `pressione_Pa` e le sovrascritture di `DISTURBO`, `MANOVRA` (e, se serve, `CORPO`, `ATTUATORE`, `REGOLATORE`, `ENERGIA`, `RUOTE`) |

Due avvertenze. Il passo di integrazione deve essere piccolo rispetto al ritardo dei propulsori (al massimo
`t90 / 4,6`), altrimenti il codice si rifiuta di partire. E se si apre un `input.py` vecchio con le chiavi
`ampiezza_g`, `frequenza_Hz`, `fase_gradi` nel disturbo, la run lo dice e indica le chiavi nuove.


## Cosa esce

```
risultati/
├── registro_esecuzioni.csv        una riga per ogni run: data, caso, impronta, durata
└── <caso>/                        per esempio RUN_POST_FIX_11-11
    ├── caso.json                  nome, impronta, data, ambienti
    ├── input_usato.py             copia esatta dell'input della run
    ├── log.txt                    quello che la run ha scritto a schermo
    ├── CONFRONTO.md               tabella affiancata degli ambienti: da leggere per primo
    ├── Pale/                      squilibrio dei rotori, uguale per tutti gli ambienti: calcolato una volta
    │   ├── PALE.md, pale.json
    │   └── pale.svg               squilibrio dei rotori estratti e forza rotante in funzione dei giri
    ├── Volo_Parabolico/           una cartella per ogni ambiente attivo, con lo stesso nome dell'ambiente
    │   ├── 00_sintesi/
    │   │   ├── RISULTATO.md       i numeri dell'ambiente
    │   │   └── riepilogo.json     gli stessi numeri, da leggere con Python
    │   ├── 01_grafici/
    │   │   ├── 01_moto_tre_assi.svg   caso peggiore: posizione, velocità, spinta, disturbo e potenza elettrica nel tempo
    │   │   ├── 02_spazio_massimo.svg  spazio percorribile in funzione del tempo della manovra
    │   │   └── 03_monte_carlo.svg     errore nel tempo (mediana, fascia 5-95 %, inviluppo) e istogramma dell'errore finale
    │   └── 02_dati/
    │       ├── serie_temporali.csv    caso peggiore, un punto ogni 0,01 s, con la potenza per asse e totale (separatore ;)
    │       └── monte_carlo.csv        un campione per riga: disturbo estratto, risultati per asse, potenza totale
    └── ISS/                       stessa struttura
```

Le verifiche analitiche, l'analisi delle pale e il margine di fase si eseguono una sola volta per run, non per ambiente.
`CONFRONTO.md` mette in colonna gli ambienti: pressione e sigma, spinta massima, disturbo, errore a fine manovra e
massimo nel caso peggiore, spinta massima usata e quota della massima, tempo in saturazione, quota di manovre
assestate nel Monte Carlo, potenza di picco totale, energia totale, corrente di picco, margine di fase, e gli avvisi
del controllo contro il dimensionamento.

Il nome automatico del caso finisce con l'impronta, otto caratteri calcolati dagli input che cambiano i risultati
(non dal nome o dal formato dei grafici). Stessa impronta, stessi risultati. Rilanciare con gli stessi input riscrive
lo stesso caso; con input diversi il nome cambia e nessuna run cancella un'altra. Accendere o spegnere un ambiente
cambia l'impronta, perché cambia l'insieme dei risultati.

Come leggere `RISULTATO.md` di un ambiente: la tabella del caso peggiore dice se il cubo arriva e si ferma anche nelle condizioni
più sfavorevoli; la tabella del Monte Carlo dice quanto spesso ce la fa in condizioni realistiche. La riga da guardare
è "assestati su tutti e tre gli assi": è la probabilità che la manovra riesca. `Pale/PALE.md` dice quanto
vibrano i rotori e quanto poco questo sposti il cubo.


## Cosa dicono i numeri oggi

I numeri della tabella vengono da una run con input precedenti (4,31 kg, 1,46 N per verso, t90 0,29 s; 0,3 m in 3 s su
ogni asse, finestra di 5 s, tolleranza 5 mm, `wn` = 2 rad/s) e non sono ancora ricalcolati con gli input attuali
(4,5 kg, 1,974 N per faccia, t90 0,16 s, 0,2 m in 5 s): vanno rifatti con una nuova run. L'errore è il peggiore dei tre assi:

| regolatore | errore a fine finestra, 95 % dei campioni | campioni assestati su tutti e tre gli assi |
|---|---|---|
| PD | circa 25 mm | 0 % |
| PD con feedforward | circa 25 mm | 0 % |
| PID, alfa 0,5 | circa 9,5 mm | 16 % |
| PID, alfa 0,5, con feedforward | circa 5,4 mm | 84 % |
| PID, alfa 1, con feedforward (il default di `input.py`) | circa 3,9 mm | 96 % |

Con un bias di 0,01 g il PD non ce la fa per costruzione. Serve l'integrale, e serve il feedforward perché l'integrale
non si carichi del ritardo d'inseguimento.


## Le verifiche

Prima di ogni run il codice viene messo alla prova su casi di cui si conosce la risposta esatta:

- massa libera con disturbo sinusoidale: picco dello spostamento `2 a / omega^2`;
- massa libera con bias e velocità iniziale: `x = v0 t - a t^2 / 2`;
- PD senza disturbo: sovraelongazione del secondo ordine `exp(-pi zeta / sqrt(1 - zeta^2))`;
- la spinta non supera mai il massimo;
- spazio da fermo a fermo a spinta costante `F t^2 / (4 m)`;
- il riferimento parte e arriva da fermo;
- il riferimento bang-bang: x(T) = d, v(0) = v(T) = 0, picco di accelerazione 4 d / T², x e v continue a T/2;
- ambiente: con sigma = 1 gli indicatori sono identici a prima, la spinta massima scala con sigma, la potenza a spinta
  fissata scala con 1 / sqrt(sigma), la potenza totale è la somma dei tre assi (anche in energia) e la corrente è
  potenza di picco / tensione;
- il rumore ha la deviazione standard chiesta e nessuna potenza sopra la banda;
- con un bias il PD si ferma a `bias / wn^2` e il PID a zero;
- 200 campioni simulati insieme danno gli stessi numeri di 200 simulazioni separate;
- pale tutte uguali, squilibrio nullo; una pala più pesante di `dm`, squilibrio `dm r_cg`;
- il fattore del caso peggiore delle pale coincide con il massimo su tutte le combinazioni (da 2 a 7 pale), e nessun
  rotore estratto a caso lo supera;
- oscillazione del cubo uguale a `U / M`.

Se una fallisce, la run non parte. Le verifiche si spengono con `ESECUZIONE["verifiche"] = False`, ma conviene farlo
solo per lavorare sul codice.


## Collegamento con il dimensionamento

La dinamica non legge il dimensionamento da sola: i dati si copiano a mano in `input.py` (fonte `[DIM]`) da
`../Dimensionamento_Sistema_Propulsivo/risultati/<caso>/`, dove `<caso>` è `RUN_POST_FIX_11-11`:

- `1_spinta/spinta.json`: massa, distanza, tempo, disturbo residuo, spinta di una faccia e di un ugello;
- `3_ventola/00_sintesi/report.json` e `3_ventola/02_excel/sections.csv`: numero di pale (3, NACA0012), giri (18515 rpm),
  potenza all'albero, mozzo, corda e geometria della pala;
- `2_venturi/05_convergenza/design.json`: pressione di progetto (`p_amb`);
- `4_sistema/04_cfd/condotto_con_ventola.json` e `4_sistema/00_sintesi/curva_potenza.json`: spinta con la ventola vera
  (1,974 N per faccia, 0,987 N per ugello) e curva di potenza (fino a 23349 rpm).

Le chiavi di `input.py` con fonte `[DIM]` sono `ATTUATORE` (spinte massime, pressione di progetto), `ENERGIA`
(`potenza_rif_W`, `spinta_rif_N`, `esponente`), `RUOTE["spinta_per_unita_N"]` e le chiavi di `PALE` che descrivono la
ventola (numero, lunghezza, larghezza, spessore, mozzo, giri). Tempo di salita, braccio della coppia, coppia di reazione dei
rotori e disposizione delle ventole non escono dal dimensionamento e restano `[STIMA]` o `[team]`.

Spinta, potenza e giri copiati valgono a 101 325 Pa. La scala all'ambiente (sigma, vedi sopra) la fa il codice: non si
riscalano a mano.

`dinamica_designer/confronto_dimensionamento.py` confronta questi dati con il caso del dimensionamento che ha lo stesso
nome di `CASO["nome"]` (se non c'è, con l'ultimo caso calcolato) e scrive gli avvisi nel log e in `CONFRONTO.md`. Controlla
massa, distanza e tempo (tolleranza 1 %), pressione di progetto (1 %), spinta di riferimento, spinta per ugello, potenza
elettrica (ugelli x potenza all'albero / rendimento), giri e raggio del mozzo (5 %), il numero di pale, che la spinta
massima non superi quella di progetto della faccia, e che il bias di un ambiente attivo non superi il disturbo residuo
del dimensionamento. Il controllo avvisa e non ferma la run.


## Limiti da tenere a mente

- Il cubo è un punto: niente rotazioni, niente accoppiamento fra gli assi. Lo squilibrio delle pale produce anche una
  coppia sul cubo, che qui non è calcolata.
- Il disturbo è tarato su una sola registrazione di volo. Dipende molto dal pilota e dal giorno: ERMES racconta che il
  momento giusto per il rilascio cambiava da volo a volo.
- Gli ambienti cambiano pressione, spinta, potenza e disturbo ma non la temperatura né la massa; la similitudine delle
  ventole è la più semplice (giri e geometria fissi). I valori della ISS sono stime da sostituire. Lo squilibrio delle
  pale è calcolato ai giri di progetto, senza correggerli per la densità dell'aria.
- Il bias è costante nella finestra. La deriva vera è lenta ma non ferma; su 5 s l'approssimazione regge, su finestre
  più lunghe no.
- Le pale sono parallelepipedi pieni con la corda nel piano del rotore: la massa è giusta a meno del profilo, il
  momento d'inerzia è un limite superiore. La variazione di densità è uniforme e indipendente fra le pale; nella
  realtà pale stampate nella stessa lavorazione si somigliano di più, quindi il range intero è un'ipotesi prudente.
- Il momento massimo delle ruote è ancora un segnaposto.
- Il controllo contro il dimensionamento (`confronto_dimensionamento.py`) confronta massa, distanza, tempo, spinta,
potenza, giri e pale, e la pressione di progetto con la `p_amb` di `2_venturi/05_convergenza/design.json`. Il bias non
si confronta per uguaglianza: nel dimensionamento `disturbo_residuo_g` è il caso peggiore con cui si dimensiona la
spinta, qui il bias è un disturbo realistico; la run avvisa solo se il bias di un ambiente attivo lo supera.
I dati `[DIM]` vanno ricopiati a ogni nuova run del dimensionamento: la dinamica non li legge da sola.


## Fonti

- ERMES team, *ESA Fly Your Thesis 2022, Experiment Report v8*: Fig. 6.3.2 (livello di gravità nella parabola),
  requisiti P.4.1-P.4.2 (velocità al rilascio), §5.2 e pp. 86-87 (tempi della manovra, g-jitter, rilascio).
- *Deploy! Proposal*, §6.3.2: g-jitter di ±0,05 g a circa 1 Hz (testo del modello ESA).
- Chat del team COMPANION: bias di 0,01 g (Mattia Ridolfi), rumore bianco a 1 Hz più bias (Fabrizio Pilone),
  rumore gaussiano a media non nulla (Francesco Salzo), velocità iniziale in direzione casuale (Giovanni Romagnoli).
- `../Dimensionamento_Sistema_Propulsivo`, caso RUN_POST_FIX_11-11: spinta, potenza, giri, geometria della ventola.
