"""INPUT GENERICO dell'analisi dei condotti di COMPANION: scenari S1, S2, S3.

È il file da modificare per il confronto tra S1, S2 e S3.  Dopo averlo salvato si lancia RUN_generica.py.
La configurazione S4 (spigoli centrati) ha un input suo: INPUT_S4.py.

Sezioni, nell'ordine in cui conviene leggerle:
   0  ESECUZIONE        che cosa eseguire e come (veloce / completa)
   1  MISSIONE E MASSA  spinta richiesta, obiettivo di massa (4 kg)
   2  AMBIENTI          aria in cabina e in laboratorio
   3  CUBO              intervallo del lato (il lato ottimo è un RISULTATO), pareti, moduli fissi dietro le facce
   4  COMPONENTI        ingombri e masse di ciò che va dentro il cubo
   5  TELAIO            parametri della stima di massa della struttura
   6  ELEMENTI          griglie, imbocco, ventola, ugello del condotto
   7  VENTOLE E MOTORI  forme delle ventole, motori, batteria
   8  LIMITI            Mach, velocità di punta, ingestione, ruote
   9  MATERIALI         materiali di condotti e guscio, carichi
  10  OTTIMIZZAZIONE    diametri provati, pesi della classifica
  11  SCENARI           le configurazioni dei condotti da confrontare

Fonti indicate accanto ai valori:
  [PIL]  indicazioni di Pilone riportate nella conversazione
  [COMP] documentazione COMPASS (proposta del gruppo di Pilone)
  [XLS]  Propulsione_dimensionamento.xlsx del team
  [EUG]  ESA User Guide, cap. 5 Parabolic Flights
  [ESA]  ESA Academy / SPFC / ESDP (regolamento volo parabolico)
  [LET]  letteratura (Idelchik, Pereira 2008, Akturk & Camci, Brandt & Selig, Graf 2005)
  SEGNAPOSTO = valore da sostituire appena disponibile un dato vero.

Convenzione degli assi (origine nel centro del cubo, mm):
  X: +destra (faccia sportellino batteria) / -sinistra (faccia libera)
  Y: +fronte (stereocamera + LiDAR)        / -retro (monocamera)
  Z: +alto (aggancio utensili)              / -basso (docking)
"""

# =============================================================================
# 0. ESECUZIONE
# =============================================================================
ESECUZIONE = {
    "etichetta": "",               # testo libero nel nome della cartella di output ("" = automatico)
    "modalita": "completa",        # "completa" (qualche minuto) oppure "veloce" (griglia ridotta, per prove)
    "verifiche_fisiche": True,     # prima dell'analisi controlla il codice contro risultati noti
    "risoluzione_voxel_mm": 4.0,   # 4 mm: buon compromesso; 2-3 mm per i risultati finali
    "formato_grafici": ["svg"],    # ["svg"] oppure ["svg", "png"]
    "cartella_output": "output",
}
# Quali scenari analizzare: si sceglie con "attivo": True / False in fondo al file (sezione 11).

# =============================================================================
# 1. MISSIONE E MASSA
# =============================================================================
MISSIONE = {
    # --- massa
    "massa_per_spinta_kg": 5,       # massa con cui si dimensiona la spinta [COMP] 4,15 kg + 0,90 kg ruote, margine 20 %
    "massa_obiettivo_kg": 4.0,      # obiettivo del team: oltre, avviso e punteggio "massa" più basso
    "massa_massima_kg": None,       # oltre: progetto NON ammissibile (None = uguale a massa_per_spinta_kg,
                                    #   cioè la massa oltre la quale la spinta di progetto non basta più)
    "massa_vincolante": True,       # False = la massa massima dà solo un avviso, non esclude il progetto
    # --- spinta
    "disturbo_residuo_g": 0.01,     # [EUG] ±0,01 g sugli assi laterali [XLS]
    "distanza_traslazione_m": 0.3,  # [XLS] SEGNAPOSTO
    "tempo_traslazione_s": 3.0,     # [XLS] SEGNAPOSTO, dentro la finestra di 5 s
    "margine_spinta": 1.2,          # [XLS]
    "spinta_per_asse_N": None,      # None = calcolata come in [XLS]: k_m * m * (n g + 4 d / t^2)
    # --- tempi e uso
    "finestra_libera_s": 5.0,       # [ESA] finestra utile per oggetti liberi
    "durata_microgravita_s": 22.0,  # [EUG]
    "assi_contemporanei_max": 3,    # per corrente di picco e verifica d'ingestione
}

# =============================================================================
# 2. AMBIENTI   (p in Pa, T in K; il primo indicato in AMBIENTE_PROGETTO dimensiona la spinta)
# =============================================================================
AMBIENTI = {
    "volo_20C":  {"p": 82500.0, "T": 293.15, "descrizione": "cabina A310 in parabola, 825 mbar, 20 °C [EUG]"},
    "volo_18C":  {"p": 82500.0, "T": 291.15, "descrizione": "cabina, estremo freddo 18 °C [EUG]"},
    "volo_25C":  {"p": 82500.0, "T": 298.15, "descrizione": "cabina, estremo caldo 25 °C [EUG]"},
    "lab_20C":   {"p": 101325.0, "T": 293.15, "descrizione": "banco in laboratorio, 1013 mbar"},
}
AMBIENTE_PROGETTO = "volo_20C"

# =============================================================================
# 3. CUBO
# =============================================================================
GEOMETRIA = {
    # Il lato del cubo NON è un dato: l'analisi lo cerca dentro questo intervallo, per ogni scenario.
    # Il lato ottimo di ogni scenario compare nel terminale, nell'Excel e nei dati di output.
    "lato_cubo_min_mm": 320.0,      # limite inferiore dell'intervallo (mm)
    "lato_cubo_max_mm": 360.0,      # limite superiore (mm)
    "lato_cubo_passo_mm": 10.0,     # passo: ogni lato in più allunga la run (280-350 con passo 10 = 8 lati)
    "parete_cubo_mm": 3.0,          # SEGNAPOSTO: ingombro della parete (per lo spazio interno)
    "parete_condotto_mm": 1.2,      # SEGNAPOSTO: stampa 3D, >= 0,8 mm per FDM
    "gioco_tra_condotti_mm": 5.0,   # SEGNAPOSTO
    "centro_di_massa_mm": [0.0, 0.0, 0.0],
    "scostamento_baricentro_mm": 5.0,   # [XLS] foglio Assetto: offset per il bilancio di momento
}

# Moduli fissi dietro il centro delle facce [PIL] (dimensioni SEGNAPOSTO):
# (asse 0=X 1=Y 2=Z, segno, larghezza_u, larghezza_v, profondità) in mm, u = asse+1, v = asse+2
ZONE_RISERVATE = {
    "stereocamera + LiDAR (fronte)": (1, +1, 70.0, 120.0, 60.0),
    "monocamera (retro)":            (1, -1, 50.0, 50.0, 40.0),
    "aggancio utensili Lego (alto)": (2, +1, 80.0, 80.0, 25.0),
    "docking non invasivo (basso)":  (2, -1, 80.0, 80.0, 25.0),
}
ZONA_CENTRALE_FACCE_MM = 120.0     # quadrato centrale di ogni faccia da lasciare libero da bocche
FACCIA_SPORTELLINO = (0, +1)       # [PIL] una faccia laterale = sportellino batteria
FACCIA_LIBERA = (0, -1)            # [PIL] l'altra laterale: libera (lì le bocche sono ammesse anche al centro)

# =============================================================================
# 4. COMPONENTI   (ingombri in mm e masse in kg; collocati in quest'ordine di priorità)
# =============================================================================
# criterio: "faccia_sportellino" = deve toccare la faccia dello sportellino; "centro" = il più vicino al centro
# dim None = calcolato dal numero di motori; massa None = calcolata (vedi TELAIO)
COMPONENTI = {
    "batteria NiMH 24 V (sportellino)":  {"dim": (150.0, 100.0, 80.0), "criterio": "faccia_sportellino",
                                          "massa_kg": 1.10},   # [COMP] 20 celle BK300SCP; massa SEGNAPOSTO
    "ruote di reazione (3 x Ø100 x 30)": {"dim": (130.0, 130.0, 130.0), "criterio": "centro",
                                          "massa_kg": 0.50},   # [COMP] 0,50 kg (conversazione); inviluppo SEGNAPOSTO
    "blocco avionica":                   {"dim": (200.0, 150.0, 50.0), "criterio": "centro",
                                          "massa_kg": 0.30},   # SEGNAPOSTO
    "regolatori ESC":                    {"dim": None, "criterio": "centro", "massa_kg": None},
}
ESC_4IN1_MM = (36.0, 36.0, 12.0)    # una scheda ogni 4 motori, SEGNAPOSTO

# Masse fisse che non occupano volume da collocare (moduli delle facce, cavi, ...) in kg, tutte SEGNAPOSTO
MASSE_FISSE = {
    "stereocamera + LiDAR": 0.15,
    "monocamera": 0.03,
    "aggancio utensili Lego": 0.05,
    "docking non invasivo": 0.08,
    "cablaggi e connettori (non propulsione)": 0.10,
}

# =============================================================================
# 5. TELAIO   (stima della massa della struttura; tutti SEGNAPOSTO finché non si pesa un prototipo)
# =============================================================================
# Ogni configurazione si porta dietro una massa strutturale diversa: condotti più lunghi,
# curve, staffe, fori nel guscio, tacche e blocchi di vertice.  Dettaglio delle voci in condotti/massa.py.
TELAIO = {
    "materiale_guscio": "PETG (FDM)",       # uno dei MATERIALI (sezione 9)
    "spessore_equivalente_guscio_mm": 1.0,  # massa del pannello / (area · densità): pannello nervato o sandwich
    "massa_longherone_g_per_m": 50.0,       # longheroni sugli spigoli (profilo a L 10x10x1 in alluminio ≈ 54 g/m)
    "massa_nodo_g": 12.0,                   # nodo d'angolo (8 vertici)
    "passo_staffe_mm": 100.0,               # una staffa ogni tanti mm di condotto (+1 per curva)
    "massa_staffa_g_a_D30": 4.0,            # massa di una staffa per D = 30 mm (scala con D)
    "spessore_alloggiamento_ventola_mm": 2.0,   # anello rinforzato attorno al rotore
    "massa_statore_g_a_D30": 2.0,           # palette dello statore + supporto motore per D = 30 mm (scala con D²)
    "larghezza_flangia_bocca_mm": 5.0,      # bordo di rinforzo attorno a ogni foro nel guscio
    "spessore_flangia_bocca_mm": 1.5,
    "densita_rete_griglia_g_m2": 600.0,     # rete di protezione (inox, filo 0,5 mm ≈ 0,6-0,8 kg/m²)
    "massa_esc_4in1_g": 12.0,
    "massa_cablaggio_per_motore_g": 6.0,
    "frazione_viteria_colla": 0.10,         # in più sulle voci strutturali
}

# =============================================================================
# 6. ELEMENTI DEL CONDOTTO
# =============================================================================
ELEMENTI = {
    # griglie di protezione [LET Idelchik]
    "griglia_ingresso": True,
    "porosita_griglia_ingresso": 0.60,    # SEGNAPOSTO: maglia fine anti-dita / anti-capelli
    "griglia_uscita": True,
    "porosita_griglia_uscita": 0.80,      # SEGNAPOSTO: maglia larga
    "diametro_filo_griglia_mm": 0.5,
    # imbocco [LET Graf 2005, Pereira 2008: labbro raggiato migliora l'hover]
    "raggio_imbocco_su_D": 0.10,
    # ventola
    "lunghezza_ventola_su_D": 0.7,        # rotore + statore + motore nel mozzo
    "gioco_punta_mm": 0.3,                # [XLS] stampa a resina con alesatura (stima)
    "spessore_mozzo_mm": 2.0,
    "statore": True,
    "k_gioco_eta": 1.5, "k_gioco_psi": 2.0,   # [LET] ordine di grandezza (Akturk & Camci, Pereira)
    "penalita_reversibile": 0.90,         # [XLS] pale simmetriche circa -10 %
    "frazione_vortice_residuo": 0.05,     # con statore
    # ugello / Venturi
    "semiangolo_ugello_deg": 8.0,
    "alfa_getto": 1.03, "beta_getto": 1.02,
    # parete
    "rugosita_parete_um": 20.0,           # stampa 3D lisciata
    "rendimento_esc": 0.93,
}

# =============================================================================
# 7. VENTOLE, MOTORI, BATTERIA
# =============================================================================
# Coefficienti adimensionali: phi = c_x/U_punta, psi = Dp_t/(rho U_punta^2).
# SEGNAPOSTO: sostituire con le curve misurate (chiave "tabella" con phi, psi, eta).
TIPI_VENTOLA = {
    "assiale_alta_pressione": dict(phi_d=0.55, psi_d=0.30, psi_0_su_psi_d=1.40, eta_max=0.72, Re_rif=2e5,
                                   larghezza_eta=0.60, nu_min=0.40, Z=7, corda_su_D=0.18),
    "assiale_media": dict(phi_d=0.45, psi_d=0.18, psi_0_su_psi_d=1.45, eta_max=0.70, Re_rif=2e5,
                          larghezza_eta=0.65, nu_min=0.30, Z=5, corda_su_D=0.22),
    "elica_intubata": dict(phi_d=0.35, psi_d=0.10, psi_0_su_psi_d=1.50, eta_max=0.65, Re_rif=2e5,
                           larghezza_eta=0.70, nu_min=0.22, Z=3, corda_su_D=0.25),
}

# Motori brushless. SEGNAPOSTO: valori tipici di catalogo per la taglia, da sostituire con le schede tecniche.
MOTORI = {
    "1404_3800kv": dict(Kv=3800, R=0.16, I0=0.4, I_max=10, massa_g=10, diametro_mm=18, lunghezza_mm=16, J_rotore=1.2e-7),
    "1806_2300kv": dict(Kv=2300, R=0.12, I0=0.6, I_max=12, massa_g=18, diametro_mm=23, lunghezza_mm=20, J_rotore=3.0e-7),
    "2205_2300kv": dict(Kv=2300, R=0.08, I0=0.8, I_max=20, massa_g=28, diametro_mm=27.5, lunghezza_mm=24, J_rotore=6.0e-7),
    "2207_1750kv": dict(Kv=1750, R=0.06, I0=1.0, I_max=30, massa_g=32, diametro_mm=28, lunghezza_mm=28, J_rotore=8.0e-7),
    "2814_900kv":  dict(Kv=900,  R=0.10, I0=0.7, I_max=25, massa_g=60, diametro_mm=35, lunghezza_mm=30, J_rotore=2.5e-6),
}
ELETTRICO = {
    "tensione_bus_V": 24.0,          # [COMP] NiMH 20S1P Panasonic BK300SCP, 3 Ah, 72 Wh
    "capacita_Wh": 72.0,             # [COMP]
    "duty_massimo": 0.95,
    "corrente_max_pacco_A": 15.0,    # [COMP] 5 C sul pacco da 3 Ah (conversazione), SEGNAPOSTO
}
# massa del rotore della ventola: m = c * D^3 (riferimento: 3 g a D = 30 mm) SEGNAPOSTO
ROTORE = {"massa_rif_g": 3.0, "D_rif_mm": 30.0, "k_inerzia": 0.30}

# =============================================================================
# 8. LIMITI
# =============================================================================
LIMITI = {
    "mach_punta_max": 0.30,          # sopra: le formule incomprimibili non bastano
    "velocita_punta_max_m_s": 150.0, # resistenza del rotore stampato, SEGNAPOSTO
    "indice_ingestione_attenzione": 0.05,
    "indice_ingestione_critico": 0.20,
    "tempo_salita_spinta_max_s": 0.5,   # [XLS] foglio Risposta
    "momento_ruote_max_Nms": 0.15,      # [XLS] foglio Assetto, SEGNAPOSTO per ruota
    "differenza_spinta_coppia": 0.05,   # squilibrio tra le due ventole di una coppia (5 %)
}

# =============================================================================
# 9. MATERIALI E CARICHI
# =============================================================================
# E (Pa), nu, rho (kg/m3), sigma_snervamento (Pa): valori tipici di scheda tecnica, SEGNAPOSTO
MATERIALI = {
    "PETG (FDM)":          dict(E=2.0e9, nu=0.38, rho=1270.0, sigma_snervamento=50e6, stampabile_max_mm=250.0),
    "PA12 (SLS)":          dict(E=1.7e9, nu=0.40, rho=1010.0, sigma_snervamento=48e6, stampabile_max_mm=300.0),
    "resina tenace (SLA)": dict(E=2.5e9, nu=0.38, rho=1180.0, sigma_snervamento=55e6, stampabile_max_mm=200.0),
    "alluminio 6061":      dict(E=69e9, nu=0.33, rho=2700.0, sigma_snervamento=276e6, stampabile_max_mm=1000.0),
}
MATERIALE_CONDOTTO = "PETG (FDM)"
CARICHI = {"g_ipergravita": 1.8, "g_atterraggio_emergenza": 9.0}   # [EUG] 1,8 g; [ESA] carichi d'emergenza

# =============================================================================
# 10. OTTIMIZZAZIONE E CLASSIFICA
# =============================================================================
OTTIMIZZAZIONE = {
    "diametri_mm": [26, 30, 34, 38, 42, 46, 50, 55, 60],   # diametri del condotto alla ventola provati
    "sigma": [0.70, 0.80, 0.90, 1.00],                    # A_uscita / A_ventola (Venturi)
    "pesi": {                                             # peso dei criteri nel punteggio (somma libera)
        "spazio": 0.30,          # volume libero dopo i componenti
        "perdite": 0.25,         # potenza elettrica per la spinta richiesta e quota di perdite
        "semplicita": 0.25,      # realizzabilità e numero di parti
        "robustezza": 0.10,      # tolleranza ai guasti
        "dinamica": 0.10,        # tempo di salita, desaturazione, ingestione
        "massa": 0.20,           # massa totale stimata: 1 all'obiettivo o sotto, 0 alla massa massima
    },
    # scale dei punteggi (0 al primo valore, 1 al secondo)
    "scala_volume_libero": (0.40, 0.80),
    "scala_potenza_asse_W": (300.0, 50.0),
    "scala_tempo_salita_s": (0.6, 0.1),
}

REALIZZABILITA = {
    "pesi": {"parti": 0.25, "curve": 0.20, "attuatori": 0.20, "stampa": 0.20},
    "parti_rif": (40, 12),        # numero di parti stampate: 0 punti a 40, 1 a 12
    "curve_rif": (30, 0),
    "attuatori_rif": (24, 6),     # motori
}

# =============================================================================
# 11. SCENARI   (le configurazioni dei condotti da confrontare)
# =============================================================================
# Campi obbligatori: id, nome, topologia, descrizione.  "attivo": False esclude lo scenario.
# Topologie disponibili (generatori in condotti/scenari.py):
#   sfalsati           condotti dritti lungo tutto il lato, sfalsamento ciclico
#   spigoli_corti      condotti lunghi mezzo spigolo, presa laterale a metà spigolo
# Per aggiungere uno scenario: copiare un blocco, cambiare id e parametri.
SCENARI = [
    {
        "id": "S1_SFALSATI_12",
        "attivo": True,
        "nome": "12 condotti dritti sfalsati (modello interattivo)",
        "topologia": "sfalsati",
        "origine": "Modello interattivo precedente (schizzo con intersezione risolta)",
        "descrizione": ("12 condotti dritti, 4 per asse, lungo tutto il lato. Ognuno è a filo di una faccia e "
                        "arretrato dall'altra di un diametro esterno più il gioco, a rotazione (X lungo Z, Y lungo "
                        "X, Z lungo Y). Ventole unidirezionali: per ogni verso lavora una coppia diagonale, con "
                        "eliche controrotanti. Presa sulla faccia opposta all'uscita."),
        "pregi_attesi": "Nessuna curva; 12 parti uguali; spinta pura con coppie diagonali; coppia disponibile per desaturare.",
        "difetti_attesi": "12 motori; condotti lunghi quanto il lato (oltre il piatto di stampa); arretramento che ruba spazio.",
        "reversibile": False,
        "posizione_ventola_frazione": 0.25,
        "verso_coppia_D1": -1,
    },
    {
        "id": "S2_SPIGOLI_CORTI_12",
        "attivo": True,
        "nome": "12 condotti corti sugli spigoli, presa a metà spigolo",
        "topologia": "spigoli_corti",
        "origine": "Proposta dell'utente: condotti sugli spigoli ma non per tutta la lunghezza",
        "descrizione": ("12 condotti lunghi mezzo spigolo, a filo dei due lati dello spigolo. L'uscita è nel vertice, "
                        "la presa è a metà spigolo su una faccia adiacente, raggiunta con una curva di 90°: presa e "
                        "ugello distano circa mezzo lato, così il cubo non riaspira i propri getti. Con la scelta "
                        "delle parità in ogni vertice arrivano al massimo due condotti; quelli Z rientrano di un "
                        "diametro per non toccare gli X."),
        "pregi_attesi": "Metà della lunghezza di condotto; prese lontane dagli ugelli; centro del cubo libero.",
        "difetti_attesi": "Curva stretta subito prima della ventola (effetto di sistema); 12 motori; prese anche sulla faccia dello sportellino.",
        "posizione_presa_frazione": 0.0,
        "raggio_curva_presa_max_su_D": 1.5,
        "distanza_ventola_da_curva_su_D": 1.0,
    },
    {
        "id": "S3_REVERSIBILI_6",
        "attivo": True,
        "nome": "6 ventole reversibili a coppie sfalsate (dal file Excel)",
        "topologia": "sfalsati",
        "origine": "Foglio Confronto architetture del compagno (primo nella classifica originale)",
        "descrizione": ("6 condotti dritti sfalsati, una coppia diagonale per asse; ogni ventola gira nei due versi. "
                        "Condotto simmetrico senza ugello né statore; per frenare si inverte la rotazione."),
        "pregi_attesi": "Metà dei condotti e dei motori di S1; più spazio interno; nessuna parte mobile oltre ai rotori.",
        "difetti_attesi": "Pale simmetriche (circa -10 %); niente Venturi né statore; inversione lenta; coppia dal vortice.",
        "reversibile": True,
        "verso_coppia_D1": -1,
    },
]
