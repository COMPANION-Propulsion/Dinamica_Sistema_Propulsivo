"""INPUT DINAMICA S4: dinamica di volo del cubo (configurazione S4), massa puntiforme nel baricentro.

È l'unico file da modificare.  Dopo averlo salvato si lancia run_dinamica.py: i risultati vanno in
risultati/<caso>/ (sintesi in 00_sintesi/RISULTATO.md).
I dati di progetto (massa, manovra, spinta di una faccia, potenza, giri, pale, tempo di salita) NON si scrivono qui:
la run li legge da ../Dimensionamento_Sistema_Propulsivo/risultati/<caso>/, fonte [DIM], dove <caso> è il nome di CASO
(vedi il blocco "DATI DAL DIMENSIONAMENTO" qui sotto).  [STIMA] = valore stimato, da sostituire con un dato vero.

Sezioni:
      CASO            nome della cartella dei risultati
   0  ESECUZIONE      passo di integrazione, formato dei grafici, cartella dei risultati
   1  CORPO           (vuota: la massa viene dal dimensionamento)
   2  ATTUATORE       (vuota: spinta massima e tempo di salita vengono dal dimensionamento)
   3  MANOVRA         finestra di volo, tolleranza, profilo (valori comuni a tutti gli ambienti)
   4  DISTURBO        accelerazione residua, velocità al rilascio, Monte Carlo (valori comuni a tutti gli ambienti)
   5  REGOLATORE      PD o PID sulla posizione
   6  ENERGIA         tensione della batteria, rendimento elettrico
   7  RUOTE           bilancio delle ruote di reazione
   8  PALE            squilibrio dei rotori: densità delle pale stampate in 3D, Monte Carlo
   9  MOTORE          dati del motore: servono a calcolare il tempo di salita
  10  AMBIENTI        un ambiente per soluzione (Volo_Parabolico, ISS): pressione e sovrascritture di DISTURBO e MANOVRA

La run produce una soluzione per ogni ambiente attivo, in risultati/<caso>/<ambiente>/, più CONFRONTO.md.
I dati di spinta e potenza importati sono quelli di progetto, validi alla pressione ATTUATORE["pressione_progetto_Pa"]:
in un ambiente con sigma = pressione / pressione_progetto la spinta massima è quella di progetto x sigma e la potenza
per una data spinta è divisa per sqrt(sigma) (vedi dinamica_designer/volo.py).

Convenzione degli assi: X, Y, Z come nel resto del progetto (X destra, Y fronte, Z alto).  Gli elenchi [X, Y, Z]
seguono sempre questo ordine.  I tre assi sono indipendenti e si muovono contemporaneamente.

Fonti: [DIM] dimensionamento della propulsione (caso con il nome di CASO), [EUG] ESA User Guide, [XLS] foglio di dimensionamento,
[ERM] ERMES, ESA Fly Your Thesis 2022, Experiment Report v8 (Documentazione), [DPL] Deploy! Proposal (modello ESA),
[team] proposta della chat del team (bias 0,01 g, rumore a 1 Hz, velocità iniziale in direzione casuale).
SEGNAPOSTO = valore da sostituire appena disponibile un dato vero.
"""

# =============================================================================
# DATI DAL DIMENSIONAMENTO (non si scrivono qui)
# =============================================================================
# CASO["nome"] sceglie il caso di ../Dimensionamento_Sistema_Propulsivo/risultati/<nome>/ da cui la run importa i
# dati di progetto (anche una variante Statore / NoStatore o una serie di casi: vedi CASO più sotto).  Il suffisso
# dopo "__" non conta: "RUN_6kg" usa il caso "RUN_6kg"; "RUN_6kg__prova1" è una variante della dinamica sullo stesso
# dimensionamento (altro input, altra cartella dei risultati).  Se il caso non esiste, se il nome è None o se manca
# un file, la run si ferma con un errore (una catena di una serie che fallisce non ferma le altre).  Le grandezze importate non si
# scrivono in questo file né in AMBIENTI: se ci sono, la run si ferma ("viene dal dimensionamento").
# Le grandezze, con il file di origine (tutti dentro il caso) e il campo:
#   CORPO.massa_kg                                    1_spinta/spinta.json: input.massa
#   MANOVRA.distanza_m (uguale sui 3 assi)            1_spinta/spinta.json: input.distanza
#   MANOVRA.tempo_manovra_s                           1_spinta/spinta.json: input.tempo
#   ATTUATORE.pressione_progetto_Pa                   2_venturi/05_convergenza/design.json: case.p_amb
#   ATTUATORE.spinta_max_positiva_N / _negativa_N,    4_sistema/04_cfd/condotto_con_ventola.json: spinta_con_ventola_N
#     ENERGIA.spinta_rif_N                              x n_ugelli (spinta.json: input.n_ugelli)
#   RUOTE.spinta_per_unita_N                          condotto_con_ventola.json: spinta_con_ventola_N
#   ENERGIA.potenza_rif_W                             3_ventola/00_sintesi/report.json: best.cases[0].shaft_power_W
#                                                       x n_ugelli / ENERGIA.rendimento_elettrico
#   ENERGIA.esponente                                 4_sistema/00_sintesi/curva_potenza.json: fit potenza / spinta
#   RUOTE.coppia_reazione_rotori_Nm                   coppia netta vera sul veicolo (5_confronto_statore/confronto_statore.json,
#                                                       report.json: net_torque_Nm, 4_sistema/00_sintesi/confronto_statore.json)
#                                                       x squilibrio_coppia; solo se manca: report.json torque_Nm
#                                                       x vortice_residuo_statore (sezione RUOTE) con un avviso
#   PALE.numero_pale, raggio_mozzo_mm, giri_progetto_rpm   report.json: best.design, best.cases[0].rpm
#   PALE.lunghezza_mm, spessore_mm                    3_ventola/03_cad/CAD_info.json (diametro, mozzo, volume pala)
#   PALE.larghezza_mm                                 3_ventola/02_excel/sections.csv: corda media
#   PALE.giri_massimi_rpm                             curva_potenza.json: giri della potenza massima
#   PALE.inerzia_rotore_motore_kgm2                   dalla sezione MOTORE (inerzia_rotore_kgm2)
#   ATTUATORE.tempo_salita_90_s                       calcolato: propulsore.tempo_salita con l'inerzia delle pale
#                                                       (3_ventola/00_sintesi/confronto_pale.json), del mozzo (CAD_info.json)
#                                                       e del motore (sezione MOTORE) + ritardo del regolatore
# La run scrive i valori importati e le fonti in risultati/<caso>/dati_dimensionamento.json e in CONFRONTO.md.

# =============================================================================
# CASO   (cartella dei risultati: risultati/<nome>/; il nome sceglie anche il caso del dimensionamento)
# =============================================================================
CASO = {
    "nome": "Run_20261112_fine_4kg",  # obbligatorio: il dimensionamento da importare, poi eventualmente "__prova" (vedi sotto)
    "varianti": "tutte",           # "tutte" oppure un elenco, ad esempio ["NoStatore"]: quali varianti (Statore, NoStatore)
                                   # simulare quando il dimensionamento ha il confronto statore; ignorato se non ce l'ha
    "sovrascrivi": False,          # True = riusa una cartella con nome anche se gli input erano diversi
}
# Formati di "nome" (relativi a ../Dimensionamento_Sistema_Propulsivo/risultati, con "/" tra i pezzi):
#   "<caso>"                          un caso: Statore e NoStatore se il dimensionamento le ha, altrimenti la catena sola
#   "<caso>/<variante>"               una variante sola, ad esempio "Run_X/NoStatore"
#   "<serie>"                         tutti i casi di una serie del dimensionamento (valori con ";" nel suo input)
#   "<serie>/<etichetta>"             un caso della serie, ad esempio "Serie_Y/massa_4"
#   "<serie>/<etichetta>/<variante>"  una variante di un caso della serie
# Il suffisso "__vN" (o "__prova") in fondo si toglie: è una variante della dinamica sullo stesso dimensionamento.
# Con più catene (varianti o casi) ognuna ha la sua cartella in risultati/<nome>/<etichetta>/ e in risultati/<nome>/ c'è
# il confronto fra le catene.  Con una sola catena senza varianti la struttura è quella di sempre.
# "python run_dinamica.py --elenca" stampa le catene trovate e le cartelle di uscita senza simulare.

# =============================================================================
# 0. ESECUZIONE
# =============================================================================
ESECUZIONE = {
    "passo_integrazione_s": 0.001, # passo dell'integrazione (s)
    "formato_grafici": ["svg"],    # ["svg"] oppure ["svg", "png"]
    "cartella_output": "risultati",
    "verifiche": True,             # prima della simulazione controlla il codice contro risultati noti
}

# =============================================================================
# 1. CORPO
# =============================================================================
CORPO = {
    # la massa di missione viene dal dimensionamento (1_spinta/spinta.json)
}

# =============================================================================
# 2. ATTUATORE   (tutto dal dimensionamento: valori alla pressione di progetto)
# =============================================================================
ATTUATORE = {
    # spinta massima per asse, pressione di progetto e tempo di salita al 90 % (t90) vengono dal dimensionamento:
    # t90 si calcola dal motore (sezione MOTORE) e dall'inerzia dell'albero.  Il ritardo dell'attuatore nella
    # simulazione è tau = t90 / 2,3
}

# =============================================================================
# 3. MANOVRA
# =============================================================================
MANOVRA = {
    # distanza_m (spostamento richiesto su X, Y, Z da fermo a fermo) e tempo_manovra_s vengono dal dimensionamento
    "finestra_s": 5.0,                   # [ESA] finestra utile per oggetti liberi: si simula fino a qui (>= tempo della manovra)
    "tolleranza_posizione_mm": 5.0,      # per il tempo di assestamento
    "profilo": "minimo_jerk",            # "minimo_jerk" (polinomio di quinto grado), "gradino" oppure "bang_bang"
                                         # (accelerazione 4 d / T^2 per T/2, poi l'opposta).  Il bang-bang è il profilo con cui
                                         # il dimensionamento calcola la spinta, ma con il ritardo dell'attuatore non è
                                         # inseguibile esattamente agli istanti di commutazione: serve come confronto
}

# =============================================================================
# 4. DISTURBO   (accelerazione residua nel riferimento del cubo; valori predefiniti, ogni ambiente può sovrascriverli)
# =============================================================================
# Modello: a_d(t) = bias costante + rumore gaussiano a media nulla in banda + sinusoide (facoltativa);
# il cubo parte con una velocità iniziale v0.  Bias e v0 hanno direzione casuale, diversa in ogni campione del
# Monte Carlo; il "caso peggiore" mette il modulo pieno di bias e v0 su ogni asse, contro il moto.
# Dati di riferimento: [ERM] Fig. 6.3.2, accelerometro Novespace (volo 302, A310): nei 22 s di 0 g |a| < 0,02 g su
# tutti gli assi, componente lenta ±0,01 g (deriva e oscillazione di circa 0,15 Hz), rumore veloce di circa ±0,003 g.
DISTURBO = {
    "bias_g": 0.01,                      # [ERM, team] modulo del bias costante, direzione casuale
    "rumore_sigma_g": 0.002,             # [ERM] deviazione standard per asse del rumore (±0,003 g visti ≈ 1,5 sigma)
    "rumore_banda_Hz": 1.0,              # [team] banda del rumore (passa-basso ideale)
    "velocita_iniziale_m_s": 0.01,       # [ERM] modulo di v0 al rilascio (Target: 0,005 ± 0,001 m/s per asse)
    "sinusoide_ampiezza_g": [0.0, 0.0, 0.0],      # facoltativa; prova: 0,01 g a 0,15 Hz (oscillazione lenta di Gz)
    "sinusoide_frequenza_Hz": [0.15, 0.15, 0.15], # [ERM]
    "sinusoide_fase_gradi": [0.0, 120.0, 240.0],  # usate nel caso peggiore; nel Monte Carlo fasi casuali
    "campioni_monte_carlo": 200,         # 0 = solo il caso peggiore
    "seme": 1,                           # seme dei numeri casuali: stessa run, stessi campioni
}
# Prova di robustezza: il g-jitter "di manuale" ESA ([DPL] §6.3.2) è ±0,05 g a circa 1 Hz, cioè rumore_sigma_g ≈ 0,025.

# =============================================================================
# 5. REGOLATORE   (PD o PID sulla posizione, massa pura)
# =============================================================================
REGOLATORE = {
    "frequenza_propria_rad_s": 2.0,      # wn: banda dell'anello di posizione
    "smorzamento": 0.8,                  # zeta
    "polo_integrale_su_wn": 1.0,         # alfa: 0 = PD; > 0 = PID con un terzo polo in -alfa wn.
                                         # Con il PD il bias lascia un errore fisso bias / wn^2 (0,01 g, wn 2: 24,5 mm);
                                         # PID alfa 1 + feedforward: 99 % delle manovre assestate nel Monte Carlo
    "feedforward_riferimento": True,     # True = aggiunge m * a_riferimento al comando (segue meglio la traiettoria;
                                         # senza, l'integrale si carica del ritardo d'inseguimento)
}

# =============================================================================
# 6. ENERGIA   (potenza per asse in funzione della spinta alla pressione di progetto: P = P_rif (F / F_rif)^esponente,
#               con P_rif, F_rif ed esponente dal dimensionamento;
#               nell'ambiente si divide per sqrt(sigma), sigma = pressione / pressione_progetto)
# =============================================================================
ENERGIA = {
    "tensione_batteria_V": 24.0,         # pacco NiMH 20S: corrente di picco = potenza totale di picco / tensione
    "rendimento_elettrico": 0.75,        # [STIMA] motore 0,80 x regolatore 0,93: potenza elettrica = potenza all'albero / questo
    # potenza di riferimento, spinta di riferimento ed esponente vengono dal dimensionamento
}

# =============================================================================
# 7. RUOTE DI REAZIONE   (bilancio nella finestra libera)
# =============================================================================
RUOTE = {
    "scostamento_baricentro_mm": 5.0,    # [XLS] offset del baricentro dalla linea della spinta
    "braccio_coppia_m": 0.2104,          # braccio della spinta: 12 condotti sugli spigoli di un cubo da 340 mm
    "squilibrio_coppia": 0.05,           # squilibrio di spinta tra le due ventole di una coppia (5 %)
    "vortice_residuo_statore": 0.05,     # [STIMA] RIPIEGO: serve solo se il dimensionamento non ha la coppia netta sul veicolo (la
                                         # coppia di reazione dei rotori = squilibrio_coppia x coppia netta [DIM], che con lo statore è
                                         # circa 0 e senza è la coppia del rotore).  Il ripiego usa questo x coppia del rotore e avvisa.
                                         # spinta_per_unita_N e coppia_reazione_rotori_Nm vengono dal dimensionamento
    "momento_rotori_in_avvio_Nms": 0.0,  # [team] momento angolare dei rotori non compensati
    "momento_ruote_max_Nms": 0.15,       # [XLS] SEGNAPOSTO: momento angolare massimo delle ruote
    "frequenze_margine_fase_rad_s": [1.0, 2.0, 4.0],
}

# =============================================================================
# 8. PALE   (squilibrio dei rotori con pale stampate in 3D, densità diversa da pala a pala)
# =============================================================================
# Ogni pala è un parallelepipedo lunghezza x larghezza x spessore, attaccato al mozzo.  La densità di ogni pala è
# estratta a caso in [densita_min, densita_max]: le masse diverse spostano il baricentro del rotore e nasce una forza
# rotante ai giri della ventola.  Calcolo in forma chiusa (vedi dinamica_designer/pale.py), fuori dalla simulazione
# nel tempo.  Numero di pale, geometria e giri vengono dal dimensionamento [DIM]; la pala è trattata come parallelepipedo di pari volume.
PALE = {
    "densita_min_kg_m3": 1150.0,         # range di densità delle pale stampate.  PLA in FDM al 100 %: il filamento
    "densita_max_kg_m3": 1250.0,         # è 1240 kg/m^3, i vuoti tra le linee tolgono dal 2 all'8 %.  Altri
                                         # materiali: resina SLA 1100-1200, PETG 1230-1270, PA12 SLS 950-1010
    "ventole_fuori_asse": 8,             # 12 ventole, 2 per verso: su un asse spingono le 8 degli altri due
    "campioni": 2000,                    # rotori estratti nel Monte Carlo
    "seme": 1,
}

# =============================================================================
# 9. MOTORE   (motore e regolatore: servono a calcolare il tempo di salita, vedi propulsore.tempo_salita)
# =============================================================================
# t90 = tempo per portare l'albero al 90 % della spinta di progetto + ritardo del regolatore.  L'inerzia dell'albero è
# la somma di pale [DIM], mozzo (cilindro pieno: diametro e lunghezza dal CAD x densità x riempimento) e rotore del motore.
MOTORE = {
    "Kv": 3800.0,                        # [team] motore 1404: giri/min per volt a vuoto
    "R": 0.16,                           # [team] resistenza di fase (ohm)
    "I0": 0.4,                           # [team] corrente a vuoto (A)
    "I_max": 10.0,                       # [team] corrente massima del regolatore (A)
    "inerzia_rotore_kgm2": 1.2e-7,       # [team] inerzia del rotore del motore
    "duty_max": 0.95,                    # tensione massima applicabile = duty_max x tensione della batteria
    "ritardo_regolatore_s": 0.05,        # [STIMA] ritardo del regolatore di giri, sommato alla salita dei giri
    "densita_mozzo_kg_m3": 1200.0,       # PLA stampato pieno
    "riempimento_mozzo": 1.0,            # 1 = mozzo pieno; < 1 = alleggerito (massa del mozzo x riempimento)
}

# =============================================================================
# 10. AMBIENTI   (una soluzione per ambiente attivo: risultati/<caso>/<ambiente>/)
# =============================================================================
# Ogni ambiente ha "attivo", "pressione_Pa" e, facoltative, le sezioni DISTURBO e MANOVRA (anche CORPO, ATTUATORE,
# REGOLATORE, ENERGIA, RUOTE): le chiavi scritte qui sovrascrivono quelle delle sezioni di base, le altre restano.
AMBIENTI = {
    "Volo_Parabolico": {
        "attivo": True,
        "pressione_Pa": 82500.0,                 # cabina durante le parabole (rho 0,98 kg/m3)
        "DISTURBO": {
            "bias_g": 0.01,                      # [ERM, team] come il valore di base
            "rumore_sigma_g": 0.002,             # [ERM]
            "velocita_iniziale_m_s": 0.01,       # [ERM]
        },
        "MANOVRA": {
            "finestra_s": 5.0,                   # [ESA] finestra utile per oggetti liberi
        },
    },
    "ISS": {
        "attivo": True,
        "pressione_Pa": 101325.0,                # cabina della Stazione, da sostituire se serve
        "DISTURBO": {
            "bias_g": 4e-5,                      # [STIMA] resistenza dell'aria di ventilazione della cabina: 0,15 m/s su un cubo
                                                 # da 0,34 m, Cd 1,05 -> 1,6 mN, cioè 4e-5 g per una massa di circa 4 kg (dipende dalla massa); la microgravità quasi statica (circa
                                                 # 1e-6 g) è trascurabile al confronto.  Da sostituire
            "rumore_sigma_g": 1e-5,              # [STIMA] vibrazioni di bordo.  Da sostituire
            "velocita_iniziale_m_s": 0.005,      # [STIMA] rilascio a mano.  Da sostituire
        },
        "MANOVRA": {
            "finestra_s": 10.0,                  # nessun limite di 5 s: si osserva anche l'assestamento
        },
    },
}
