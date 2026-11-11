"""INPUT DINAMICA S4: dinamica di volo del cubo (configurazione S4), massa puntiforme nel baricentro.

È l'unico file da modificare.  Dopo averlo salvato si lancia run_dinamica.py: i risultati vanno in
risultati/<caso>/ (sintesi in 00_sintesi/RISULTATO.md).
I dati della propulsione (spinta di una faccia, potenza, giri, pale) vengono dal dimensionamento, fonte [DIM]:
si copiano a mano da ../Dimensionamento_Sistema_Propulsivo/risultati/<caso>/ (1_spinta/spinta.json, RIEPILOGO.md) e
la run avvisa se non tornano con quel caso.  [STIMA] = valore stimato prima che il caso sia calcolato: da sostituire.

Sezioni:
      CASO            nome della cartella dei risultati
   0  ESECUZIONE      passo di integrazione, formato dei grafici, cartella dei risultati
   1  CORPO           massa (concentrata nel baricentro)
   2  ATTUATORE       spinta massima per asse e tempo di salita (dal dimensionamento)
   3  MANOVRA         spostamento richiesto, tempo, finestra di volo, tolleranza (valori comuni a tutti gli ambienti)
   4  DISTURBO        accelerazione residua, velocità al rilascio, Monte Carlo (valori comuni a tutti gli ambienti)
   5  REGOLATORE      PD o PID sulla posizione
   6  ENERGIA         potenza in funzione della spinta, tensione della batteria
   7  RUOTE           bilancio delle ruote di reazione (dai dati del dimensionamento)
   8  PALE            squilibrio dei rotori: pale stampate in 3D con densità diversa
   9  AMBIENTI        un ambiente per soluzione (Volo_Parabolico, ISS): pressione e sovrascritture di DISTURBO e MANOVRA

La run produce una soluzione per ogni ambiente attivo, in risultati/<caso>/<ambiente>/, più CONFRONTO.md.
I dati di ATTUATORE e ENERGIA sono quelli di progetto, validi alla pressione ATTUATORE["pressione_progetto_Pa"]:
in un ambiente con sigma = pressione / pressione_progetto la spinta massima è quella di progetto x sigma e la potenza
per una data spinta è divisa per sqrt(sigma) (vedi dinamica_designer/volo.py).

Convenzione degli assi: X, Y, Z come nel resto del progetto (X destra, Y fronte, Z alto).  Gli elenchi [X, Y, Z]
seguono sempre questo ordine.  I tre assi sono indipendenti e si muovono contemporaneamente.

Fonti: [DIM] dimensionamento della propulsione, caso RUN_POST_FIX_11-11, [EUG] ESA User Guide, [XLS] foglio di dimensionamento,
[ERM] ERMES, ESA Fly Your Thesis 2022, Experiment Report v8 (Documentazione), [DPL] Deploy! Proposal (modello ESA),
[team] proposta della chat del team (bias 0,01 g, rumore a 1 Hz, velocità iniziale in direzione casuale).
SEGNAPOSTO = valore da sostituire appena disponibile un dato vero.
"""

# =============================================================================
# CASO   (cartella dei risultati: risultati/<nome>/)
# =============================================================================
CASO = {
    "nome": "RUN_POST_FIX_11-11_v2",                  # None = nome automatico (massa, distanza, tempo + impronta degli input)
    "sovrascrivi": False,          # True = riusa una cartella con nome anche se gli input erano diversi
}

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
    "massa_kg": 4.5,            # [team] massa di missione, la stessa del Dimensionamento
}

# =============================================================================
# 2. ATTUATORE   (dal dimensionamento: valori a 101325 Pa)
# =============================================================================
ATTUATORE = {
    "spinta_max_positiva_N": [1.974, 1.974, 1.974],   # [DIM] spinta di una faccia a 101325 Pa: 2 ugelli x 0,987 N con la ventola vera nel
                                   # condotto ai giri di progetto (4_sistema/04_cfd/condotto_con_ventola.json; disco uniforme
                                   # 1,027 N). La curva di potenza arriva a 1,686 N per ugello a 23349 rpm: valore prudente
    "spinta_max_negativa_N": [1.974, 1.974, 1.974],   # [DIM] faccia opposta, uguale
    "pressione_progetto_Pa": 101325.0,  # [DIM] p_amb del dimensionamento, 2_venturi/05_convergenza/design.json
    "tempo_salita_90_s": 0.16,     # [STIMA] 0,11 s di salita dei giri (propulsore.tempo_salita: motore 1404 3800 kV, 24 V, I_max 10 A,
                                   # coppia 6,08 mN·m a 18515 rpm; J = 1,36e-6 kg·m² = pale 6,19e-7 [DIM] + mozzo pieno in PLA
                                   # 6,2e-7 + motore 1,2e-7) + 0,05 s di ritardo del regolatore.  Con il mozzo alleggerito J
                                   # scende verso 0,74e-6 e la salita a 0,06 s.  Il ritardo è tau = t90 / 2,3
}

# =============================================================================
# 3. MANOVRA
# =============================================================================
MANOVRA = {
    "distanza_m": [0.2, 0.2, 0.2],       # [team] spostamento richiesto su X, Y, Z (da fermo a fermo), come negli altri due progetti
    "tempo_manovra_s": 5.0,              # [team] tempo per completarlo, uguale alla finestra
    "finestra_s": 5.0,                   # [ESA] finestra utile per oggetti liberi: si simula fino a qui
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
# 6. ENERGIA   (potenza per asse in funzione della spinta alla pressione di progetto: P = P_rif (F / F_rif)^esponente;
#               nell'ambiente si divide per sqrt(sigma), sigma = pressione / pressione_progetto)
# =============================================================================
ENERGIA = {
    "tensione_batteria_V": 24.0,         # pacco NiMH 20S: corrente di picco = potenza totale di picco / tensione
    "potenza_rif_W": 31.43,              # [DIM] elettrica per faccia: 2 ugelli x 11,787 W all'albero / 0,75
    "spinta_rif_N": 1.974,               # [DIM] spinta della faccia a quella potenza (ventola vera, 18515 rpm)
    "rendimento_elettrico": 0.75,        # [STIMA] motore 0,80 x regolatore 0,93: potenza elettrica = potenza all'albero / questo
    "esponente": 1.4,                    # [DIM] dalla curva di potenza (4_sistema/00_sintesi/curva_potenza.json): fit 1,37 tra 0,1 e
                                         # 1,03 N per ugello; con 1,4 a 0,25 N per ugello l'errore è circa 1 %
}

# =============================================================================
# 7. RUOTE DI REAZIONE   (bilancio nella finestra libera)
# =============================================================================
RUOTE = {
    "scostamento_baricentro_mm": 5.0,    # [XLS] offset del baricentro dalla linea della spinta
    "braccio_coppia_m": 0.2104,          # braccio della spinta: 12 condotti sugli spigoli di un cubo da 340 mm
    "squilibrio_coppia": 0.05,           # squilibrio di spinta tra le due ventole di una coppia (5 %)
    "spinta_per_unita_N": 0.987,        # [DIM] spinta di un ugello con la ventola vera
    "coppia_reazione_rotori_Nm": 1.5e-5,# [STIMA] 5 % di squilibrio x 5 % di vortice residuo dopo lo statore x 6,08 mN·m [DIM] (lo statore a 7 pale annulla la coppia netta nel calcolo)
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
# nel tempo.  Dati della ventola del dimensionamento [DIM]: ventola da 58,07 mm, mozzo da 26,13 mm, pala trattata come parallelepipedo di pari volume.
PALE = {
    "numero_pale": 3,                    # [DIM] NACA0012
    "lunghezza_mm": 15.47,               # [DIM] lunghezza della pala nel CAD (raggio 28,54 - mozzo 13,07, gioco di punta 0,5 mm incluso)
    "larghezza_mm": 15.4,                # [DIM] corda media (10,4 mm alla radice, 18,4 in punta: 3_ventola/02_excel/sections.csv)
    "spessore_mm": 1.46,                 # [DIM] spessore equivalente: volume della pala nel CAD 347,6 mm³ / (15,47 x 15,4)
    "raggio_mozzo_mm": 13.07,            # [DIM] mozzo da 26,13 mm
    "densita_min_kg_m3": 1150.0,         # range di densità delle pale stampate.  PLA in FDM al 100 %: il filamento
    "densita_max_kg_m3": 1250.0,         # è 1240 kg/m^3, i vuoti tra le linee tolgono dal 2 all'8 %.  Altri
                                         # materiali: resina SLA 1100-1200, PETG 1230-1270, PA12 SLS 950-1010
    "giri_progetto_rpm": 18515.0,        # [DIM]
    "giri_massimi_rpm": 23349.0,         # [DIM] fine della curva di potenza (23,57 W all'albero, 1,686 N per ugello)
    "inerzia_rotore_motore_kgm2": 1.2e-7,# [team] motore 1404 3800 kV
    "ventole_fuori_asse": 8,             # 12 ventole, 2 per verso: su un asse spingono le 8 degli altri due
    "campioni": 2000,                    # rotori estratti nel Monte Carlo
    "seme": 1,
}

# =============================================================================
# 9. AMBIENTI   (una soluzione per ambiente attivo: risultati/<caso>/<ambiente>/)
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
                                                 # da 0,34 m, Cd 1,05 -> 1,6 mN su 4,5 kg; la microgravità quasi statica (circa
                                                 # 1e-6 g) è trascurabile al confronto.  Da sostituire
            "rumore_sigma_g": 1e-5,              # [STIMA] vibrazioni di bordo.  Da sostituire
            "velocita_iniziale_m_s": 0.005,      # [STIMA] rilascio a mano.  Da sostituire
        },
        "MANOVRA": {
            "finestra_s": 10.0,                  # nessun limite di 5 s: si osserva anche l'assestamento
        },
    },
}
