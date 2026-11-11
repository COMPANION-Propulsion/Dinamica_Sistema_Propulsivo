"""INPUT DINAMICA S4: dinamica di volo del cubo (configurazione S4), massa puntiforme nel baricentro.

È l'unico file da modificare.  Dopo averlo salvato si lancia run_dinamica.py: i risultati vanno in
risultati/<caso>/ (sintesi in 00_sintesi/RISULTATO.md).
Non dipende da ../Analisi_Configurazioni (analisi dei condotti): i dati che arrivano dall'analisi (spinta massima,
tempo di salita, potenza, ...) sono qui sotto, copiati a mano dall'ultima run di S4 in ../Analisi_Configurazioni/risultati/<caso>/
(02_excel: fogli "Controllo e dinamica" e "Fluidodinamica"; oppure 00_sintesi/riepilogo.json).

Sezioni:
      CASO            nome della cartella dei risultati
   0  ESECUZIONE      passo di integrazione, formato dei grafici, cartella dei risultati
   1  CORPO           massa (concentrata nel baricentro)
   2  ATTUATORE       spinta massima per asse e tempo di salita (dall'analisi)
   3  MANOVRA         spostamento richiesto, tempo, finestra di volo, tolleranza
   4  DISTURBO        accelerazione residua del volo parabolico, velocità al rilascio, Monte Carlo
   5  REGOLATORE      PD o PID sulla posizione
   6  ENERGIA         potenza in funzione della spinta
   7  RUOTE           bilancio delle ruote di reazione (dai dati dell'analisi)
   8  PALE            squilibrio dei rotori: pale stampate in 3D con densità diversa

Convenzione degli assi: X, Y, Z come nell'analisi (X destra, Y fronte, Z alto).  Gli elenchi [X, Y, Z]
seguono sempre questo ordine.  I tre assi sono indipendenti e si muovono contemporaneamente.

Fonti: [ANL] risultato dell'ultima run di S4 dell'analisi, [EUG] ESA User Guide, [XLS] foglio di dimensionamento,
[ERM] ERMES, ESA Fly Your Thesis 2022, Experiment Report v8 (Documentazione), [DPL] Deploy! Proposal (modello ESA),
[team] proposta della chat del team (bias 0,01 g, rumore a 1 Hz, velocità iniziale in direzione casuale).
SEGNAPOSTO = valore da sostituire appena disponibile un dato vero.
"""

# =============================================================================
# CASO   (cartella dei risultati: risultati/<nome>/)
# =============================================================================
CASO = {
    "nome": "TEST1",                  # None = nome automatico (massa, distanza, tempo + impronta degli input)
    "sovrascrivi": False,          # True = riusa una cartella con nome anche se gli input erano diversi
}

# =============================================================================
# 0. ESECUZIONE
# =============================================================================
ESECUZIONE = {
    "passo_integrazione_s": 0.001, # passo dell'integrazione (s)
    "formato_grafici": ["svg"],    # ["svg"] oppure ["svg", "png"]
    "cartella_output": "risultati",
    "verifiche": False,             # prima della simulazione controlla il codice contro risultati noti
}

# =============================================================================
# 1. CORPO
# =============================================================================
CORPO = {
    "massa_kg": 4.5,              # [ANL] massa stimata dell'ultima run di S4 dell'analisi (obiettivo 4 kg)
}

# =============================================================================
# 2. ATTUATORE   (da analisi: foglio "Controllo e dinamica")
# =============================================================================
ATTUATORE = {
    "spinta_max_positiva_N": [0.2, 0.2, 0.2],   # [ANL] forza pura disponibile per verso, [X, Y, Z]
    "spinta_max_negativa_N": [0.2, 0.2, 0.2],   # [ANL] stesso per il verso opposto
    "tempo_salita_90_s": 0.1204,   # [ANL] tempo per arrivare al 90 % della spinta; il ritardo è tau = t90 / 2,3
}

# =============================================================================
# 3. MANOVRA
# =============================================================================
MANOVRA = {
    "distanza_m": [0.25, 0.25, 0.25],       # [XLS] SEGNAPOSTO: spostamento richiesto su X, Y, Z (da fermo a fermo)
    "tempo_manovra_s": 4.0,              # [XLS] SEGNAPOSTO: tempo per completarlo
    "finestra_s": 5.0,                   # [ESA] finestra utile per oggetti liberi: si simula fino a qui
    "tolleranza_posizione_mm": 5.0,      # per il tempo di assestamento
    "profilo": "minimo_jerk",            # "minimo_jerk" (polinomio di quinto grado) oppure "gradino"
}

# =============================================================================
# 4. DISTURBO   (accelerazione residua nel riferimento del cubo)
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
    "polo_integrale_su_wn": 1.0,        # alfa: 0 = PD; > 0 = PID con un terzo polo in -alfa wn.
                                         # Con il PD il bias lascia un errore fisso bias / wn^2 (0,01 g, wn 2: 24,5 mm);
                                         # PID alfa 1 + feedforward: 99 % delle manovre assestate nel Monte Carlo
    "feedforward_riferimento": True,     # True = aggiunge m * a_riferimento al comando (segue meglio la traiettoria;
                                         # senza, l'integrale si carica del ritardo d'inseguimento)
}

# =============================================================================
# 6. ENERGIA   (potenza per asse in funzione della spinta: P = P_rif (F / F_rif)^esponente)
# =============================================================================
ENERGIA = {
    "potenza_rif_W": 146.9,              # [ANL] potenza elettrica per asse alla spinta di progetto (due ventole)
    "spinta_rif_N": 1.3886,              # [ANL] spinta di progetto per asse
    "esponente": 1.5,                    # SEGNAPOSTO: teoria dell'elica, potenza ~ spinta^1,5
}

# =============================================================================
# 7. RUOTE DI REAZIONE   (bilancio nella finestra libera, dai dati dell'analisi)
# =============================================================================
RUOTE = {
    "scostamento_baricentro_mm": 5.0,    # [XLS] offset del baricentro dalla linea della spinta
    "braccio_coppia_m": 0.162,          # [ANL] braccio tra due ventole di una coppia
    "squilibrio_coppia": 0.05,           # squilibrio di spinta tra le due ventole di una coppia (5 %)
    "spinta_per_unita_N": 0.108,        # [ANL] spinta di una ventola alla spinta di progetto
    "coppia_reazione_rotori_Nm": 2.89e-5,# [ANL] coppia di reazione netta dei rotori
    "momento_rotori_in_avvio_Nms": 0.0,  # [ANL] momento angolare dei rotori non compensati
    "momento_ruote_max_Nms": 0.15,       # [XLS] SEGNAPOSTO: momento angolare massimo delle ruote
    "frequenze_margine_fase_rad_s": [1.0, 2.0, 4.0],
}

# =============================================================================
# 8. PALE   (squilibrio dei rotori con pale stampate in 3D, densità diversa da pala a pala)
# =============================================================================
# Ogni pala è un parallelepipedo lunghezza x larghezza x spessore, attaccato al mozzo.  La densità di ogni pala è
# estratta a caso in [densita_min, densita_max]: le masse diverse spostano il baricentro del rotore e nasce una forza
# rotante ai giri della ventola.  Calcolo in forma chiusa (vedi dinamica_designer/pale.py), fuori dalla simulazione
# nel tempo.  Valori di partenza dall'ottimo S4 dell'analisi: D = 42 mm, mozzo/punta 0,524, corda / D = 0,25.
PALE = {
    "numero_pale": 3,                    # [ANL] tipo "elica_intubata" dell'ottimo S4 (Z = 3)
    "lunghezza_mm": 9.5,                 # lunghezza radiale, dal mozzo alla punta (21 - 11 mm, meno 0,5 mm di gioco)
    "larghezza_mm": 10.5,                # larghezza = corda della pala
    "spessore_mm": 1.0,                  # SEGNAPOSTO: circa 10 % della corda, vicino al minimo stampabile
    "raggio_mozzo_mm": 11.0,             # [ANL] dove comincia la pala: fissa il raggio del baricentro
    "densita_min_kg_m3": 1150.0,         # range di densità delle pale stampate.  PLA in FDM al 100 %: il filamento
    "densita_max_kg_m3": 1250.0,         # è 1240 kg/m^3, i vuoti tra le linee tolgono dal 2 all'8 %.  Altri
                                         # materiali: resina SLA 1100-1200, PETG 1230-1270, PA12 SLS 950-1010
    "giri_progetto_rpm": 45646.0,        # [ANL] "Progetto ottimo", S4
    "giri_massimi_rpm": 46823.0,         # [ANL] giri massimi ammessi, S4
    "inerzia_rotore_motore_kgm2": 1.2e-7,# [ANL] motore 1404 3800 kV
    "ventole_fuori_asse": 4,             # [ANL] S4: 6 ventole, 2 per asse; su un asse spingono quelle degli altri due
    "campioni": 2000,                    # rotori estratti nel Monte Carlo
    "seme": 1,
}
