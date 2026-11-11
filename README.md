# Dinamica di volo del cubo COMPANION

Questa cartella risponde a una domanda pratica: durante una parabola, il cubo riesce a spostarsi di quanto
vogliamo, nel tempo che abbiamo, e a fermarsi dove deve? Per rispondere simula il moto del cubo (configurazione S4)
con i suoi propulsori, il regolatore di posizione e i disturbi che troverà in volo: l'aereo che non è mai a 0 g
perfetti, il rilascio che lascia il cubo con un po' di velocità, le pale stampate che non pesano tutte uguali.

La scelta della configurazione dei condotti (scenari S1-S5, diametro, ventola, motore) non si fa qui ma nella cartella
accanto, `../Analisi_Configurazioni`. Da lì si copiano a mano in `input.py` i numeri che servono (spinta massima,
tempo di salita, potenza...). Il collegamento è spiegato più sotto.


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

La run dura un paio di secondi. Prima di simulare controlla il codice con 16 verifiche contro soluzioni note; se una
non torna, si ferma e non scrive risultati. Alla fine dice dove ha messo i file: il primo da aprire è
`risultati/<caso>/00_sintesi/RISULTATO.md`.

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
│   ├── propulsore.py      salita della spinta, margine di fase, ruote di reazione (lo usa anche l'analisi)
│   ├── export.py          grafici, tabelle, RISULTATO.md
│   ├── caso.py            nome e cartella del caso
│   └── verifiche.py       i controlli contro soluzioni analitiche
├── tests/                 test pytest
└── risultati/             un caso per cartella (non va su git)
```


## Il modello, un pezzo alla volta

### Il cubo

Il cubo è trattato come un punto con tutta la massa nel baricentro (4,31 kg oggi, la stima di S4 dell'analisi). Si muove lungo X, Y e Z nello
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

dove `t90` è il tempo che la spinta impiega ad arrivare al 90 % del valore chiesto (0,29 s per S4, dall'analisi). Le ventole di S4 sono reversibili e per cambiare verso
impiegano di più, 0,48 s: questo il modello non lo vede.
La spinta chiesta non può superare la spinta massima per verso; se la supera, viene tagliata (saturazione).

### Il regolatore

Il cubo deve seguire un riferimento: parte fermo, si sposta di 0,3 m in 3 s e si ferma. Il riferimento ha il profilo
"a minimo jerk", un polinomio di quinto grado che parte e arriva con velocità e accelerazione nulle, quindi senza
strattoni.

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

Il Monte Carlo estrae 200 volte (il numero si cambia) una direzione a caso per il bias, una per la velocità iniziale,
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

Facciamo i conti a mano con i numeri di S4. Pala di 9,5 x 10,5 x 1 mm: volume 100 mm³. In PLA tra 1150 e 1250 kg/m³
pesa tra 0,115 e 0,125 g, quindi la differenza massima fra due pale è 0,01 g. Il baricentro è a 15,75 mm dall'asse.
Lo squilibrio peggiore con 3 pale è una pala pesante e due leggere: 0,01 g x 15,75 mm = 0,157 g·mm. A 45 600 giri/min
(761 Hz, omega = 4780 rad/s) la forza è 0,157e-6 x 4780² = 3,6 N, due volte e mezzo la spinta massima di un asse (1,46 N).

Sembra enorme, ma gira a 761 Hz. Il regolatore lavora sotto 1 Hz e non la vede nemmeno; il cubo si comporta come una
massa libera spinta avanti e indietro, e una massa libera spinta da una forza `U omega^2 sin(omega t)` oscilla di

```
x = U / M
```

che non dipende dai giri: 0,157 g·mm / 4,31 kg = 0,036 µm. Anche con quattro ventole in fase sono 0,15 µm. Sulla
traiettoria le pale non contano. Contano invece sulle vibrazioni: 3,6 N a 761 Hz passano per i cuscinetti e la
struttura e arrivano ai sensori inerziali. Il messaggio pratico è che i rotori vanno equilibrati dopo la stampa.

Per questo motivo lo squilibrio non entra nella simulazione nel tempo: per seguire 761 Hz servirebbe un passo di
integrazione sotto 0,07 ms, e il risultato sarebbe comunque `U / M`. I conti sono in forma chiusa in `pale.py`.

Con più di tre pale il caso peggiore non è più una sola pala pesante: conviene che siano pesanti più pale vicine.
Il codice usa la formula generale (`fattore_peggiore`), verificata contro tutte le combinazioni possibili.

C'è anche un secondo effetto, piccolo. Ogni rotore ha un momento angolare `H = (I_pale + J_motore) omega`, circa
1e-3 N·m·s. Le due ventole di una coppia girano in versi opposti e i loro H si annullano, ma solo se le pale pesano
uguale. Il residuo, al 95 % circa 2e-5 N·m·s, finisce sulle ruote di reazione, che ne reggono 0,15.

### Spazio massimo, tempo minimo, ruote

Oltre alla simulazione, la run calcola a spinta massima quanto spazio si può fare nel tempo della manovra (accelerando
per metà del tempo e frenando per l'altra metà) e il tempo minimo per la distanza richiesta, con e senza bias. Infine
fa il margine di fase dell'anello di posizione con il ritardo dei propulsori e il bilancio del momento angolare delle
ruote di reazione nella finestra (modelli in `propulsore.py`).


## Il file di input, sezione per sezione

Tutti gli elenchi a tre valori seguono l'ordine [X, Y, Z]. Accanto a ogni numero c'è un commento con la fonte:
`[ANL]` viene dall'ultima run di S4 dell'analisi, `[ERM]` dal report ERMES, `[XLS]` dal foglio di dimensionamento,
`[team]` dalla chat del team. `SEGNAPOSTO` vuol dire che il valore è provvisorio e va sostituito appena c'è un dato vero.

| sezione | cosa si imposta |
|---|---|
| `CASO` | il nome della cartella dei risultati (`None` = automatico) e se si può sovrascrivere un caso con input diversi |
| 0 `ESECUZIONE` | passo di integrazione, formato dei grafici, cartella di uscita, verifiche sì o no |
| 1 `CORPO` | la massa del cubo |
| 2 `ATTUATORE` | spinta massima per verso e per asse, tempo di salita al 90 % |
| 3 `MANOVRA` | distanza, tempo della manovra, durata della finestra simulata, tolleranza, profilo del riferimento |
| 4 `DISTURBO` | bias, sigma e banda del rumore, velocità iniziale, sinusoide facoltativa, campioni del Monte Carlo, seme |
| 5 `REGOLATORE` | banda `wn`, smorzamento `zeta`, terzo polo `polo_integrale_su_wn` (0 = PD), feedforward sì o no |
| 6 `ENERGIA` | potenza in funzione della spinta, `P = P_rif (F / F_rif)^esponente` |
| 7 `RUOTE` | dati per il bilancio delle ruote di reazione |
| 8 `PALE` | numero di pale, lunghezza, larghezza, spessore, raggio del mozzo, range di densità, giri, campioni |

Due avvertenze. Il passo di integrazione deve essere piccolo rispetto al ritardo dei propulsori (al massimo
`t90 / 4,6`), altrimenti il codice si rifiuta di partire. E se si apre un `input.py` vecchio con le chiavi
`ampiezza_g`, `frequenza_Hz`, `fase_gradi` nel disturbo, la run lo dice e indica le chiavi nuove.


## Cosa esce

```
risultati/
├── registro_esecuzioni.csv        una riga per ogni run: data, caso, impronta, durata
└── <caso>/                        per esempio m5.00kg_d0.30m_t3.0s_h06cf3291
    ├── caso.json                  nome, impronta, data
    ├── input_usato.py             copia esatta dell'input della run
    ├── log.txt                    quello che la run ha scritto a schermo
    ├── 00_sintesi/
    │   ├── RISULTATO.md           da leggere per primo
    │   └── riepilogo.json         gli stessi numeri, da leggere con Python
    ├── 01_grafici/
    │   ├── 01_moto_tre_assi.svg   caso peggiore: posizione, velocità, spinta e disturbo nel tempo
    │   ├── 02_spazio_massimo.svg  spazio percorribile in funzione del tempo della manovra
    │   ├── 03_monte_carlo.svg     errore nel tempo (mediana, fascia 5-95 %, inviluppo) e istogramma dell'errore finale
    │   └── 04_pale.svg            squilibrio dei rotori estratti e forza rotante in funzione dei giri
    └── 02_dati/
        ├── serie_temporali.csv    caso peggiore, un punto ogni 0,01 s (separatore ;)
        └── monte_carlo.csv        un campione per riga: disturbo estratto e risultati per asse
```

Il nome automatico del caso finisce con l'impronta, otto caratteri calcolati dagli input che cambiano i risultati
(non dal nome o dal formato dei grafici). Stessa impronta, stessi risultati. Rilanciare con gli stessi input riscrive
lo stesso caso; con input diversi il nome cambia e nessuna run cancella un'altra.

Come leggere `RISULTATO.md`: la tabella del caso peggiore dice se il cubo arriva e si ferma anche nelle condizioni
più sfavorevoli; la tabella del Monte Carlo dice quanto spesso ce la fa in condizioni realistiche. La riga da guardare
è "assestati su tutti e tre gli assi": è la probabilità che la manovra riesca. La sezione delle pale dice quanto
vibrano i rotori e quanto poco questo sposti il cubo.


## Cosa dicono i numeri oggi

Con gli input attuali (S4 del 04/11: 4,31 kg, 1,46 N per verso, t90 0,29 s; 0,3 m in 3 s su ogni asse, finestra
di 5 s, tolleranza 5 mm, `wn` = 2 rad/s). L'errore è il peggiore dei tre assi:

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
- il rumore ha la deviazione standard chiesta e nessuna potenza sopra la banda;
- con un bias il PD si ferma a `bias / wn^2` e il PID a zero;
- 200 campioni simulati insieme danno gli stessi numeri di 200 simulazioni separate;
- pale tutte uguali, squilibrio nullo; una pala più pesante di `dm`, squilibrio `dm r_cg`;
- il fattore del caso peggiore delle pale coincide con il massimo su tutte le combinazioni (da 2 a 7 pale), e nessun
  rotore estratto a caso lo supera;
- oscillazione del cubo uguale a `U / M`.

Se una fallisce, la run non parte. Le verifiche si spengono con `ESECUZIONE["verifiche"] = False`, ma conviene farlo
solo per lavorare sul codice.


## Collegamento con l'analisi delle configurazioni

Dall'analisi alla dinamica il passaggio è a mano: spinta massima per verso, tempo di salita, potenza e spinta di
riferimento, braccio della coppia, spinta per unità, coppia di reazione, giri e geometria delle pale si copiano in
`input.py` (fonte `[ANL]`) dall'ultima run di S4 in `../Analisi_Configurazioni/risultati/<caso>/`. I fogli Excel da
guardare sono *Progetto ottimo*, *Controllo e dinamica* e *Fluidodinamica*, oppure `dati/riepilogo.json`.

Nell'altro verso il collegamento è nel codice: `../Analisi_Configurazioni/configurazioni_designer/core/ponte_dinamica.py`
importa `dinamica_designer/propulsore.py` per valutare ogni progetto. Il modello del propulsore esiste solo qui, quindi
se lo si cambia cambiano anche i risultati dell'analisi. Rinominare questa cartella o spostarla da accanto ad
`Analisi_Configurazioni` rompe l'analisi.


## Limiti da tenere a mente

- Il cubo è un punto: niente rotazioni, niente accoppiamento fra gli assi. Lo squilibrio delle pale produce anche una
  coppia sul cubo, che qui non è calcolata.
- Il disturbo è tarato su una sola registrazione di volo. Dipende molto dal pilota e dal giorno: ERMES racconta che il
  momento giusto per il rilascio cambiava da volo a volo.
- Il bias è costante nella finestra. La deriva vera è lenta ma non ferma; su 5 s l'approssimazione regge, su finestre
  più lunghe no.
- Le pale sono parallelepipedi pieni con la corda nel piano del rotore: la massa è giusta a meno del profilo, il
  momento d'inerzia è un limite superiore. La variazione di densità è uniforme e indipendente fra le pale; nella
  realtà pale stampate nella stessa lavorazione si somigliano di più, quindi il range intero è un'ipotesi prudente.
- Lo spessore delle pale, l'esponente della potenza e il momento massimo delle ruote sono ancora segnaposto.
- I dati `[ANL]` vanno ricopiati a ogni nuova run dell'analisi: la dinamica non li legge da sola.


## Fonti

- ERMES team, *ESA Fly Your Thesis 2022, Experiment Report v8*: Fig. 6.3.2 (livello di gravità nella parabola),
  requisiti P.4.1-P.4.2 (velocità al rilascio), §5.2 e pp. 86-87 (tempi della manovra, g-jitter, rilascio).
- *Deploy! Proposal*, §6.3.2: g-jitter di ±0,05 g a circa 1 Hz (testo del modello ESA).
- Chat del team COMPANION: bias di 0,01 g (Mattia Ridolfi), rumore bianco a 1 Hz più bias (Fabrizio Pilone),
  rumore gaussiano a media non nulla (Francesco Salzo), velocità iniziale in direzione casuale (Giovanni Romagnoli).
- `../Analisi_Configurazioni`, ultima run di S4: spinta, tempo di salita, potenza, giri, geometria della ventola.
