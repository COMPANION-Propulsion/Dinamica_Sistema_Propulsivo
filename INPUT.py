"""INPUT dell'analisi dei condotti di COMPANION.

Si modifica SOLO questo file (e, per aggiungere scenari, database_scenari.py).
Ogni valore riporta la fonte:
  [PIL]  indicazioni di Pilone riportate nella conversazione
  [COMP] documentazione COMPASS (proposta del gruppo di Pilone)
  [XLS]  Propulsione_dimensionamento.xlsx del team
  [EUG]  ESA User Guide, cap. 5 Parabolic Flights
  [ESA]  ESA Academy / SPFC / ESDP (regolamento volo parabolico)
  [LET]  letteratura (Idelchik, Pereira 2008, Akturk & Camci, Brandt & Selig, Graf 2005)
  SEGNAPOSTO = valore da sostituire appena disponibile un dato vero.
"""

# ============================================================== esecuzione
ESECUZIONE = {
    "etichetta": "",               # testo libero nel nome della cartella di output ("" = automatico)
    "scenari": "tutti",            # "tutti" oppure lista di id, es. ["S1_SFALSATI_12", "S4_Y6_MARGINI"]
    "risoluzione_voxel_mm": 4.0,   # 4 mm: buon compromesso; 2-3 mm per i risultati finali
    "formato_grafici": ["svg"],    # ["svg"] o ["svg", "png"]
    "cartella_output": "output",
}

# ============================================================== missione e spinta
MISSIONE = {
    "massa_cubo_kg": 5,          # [COMP] 4,15 kg componenti + 0,90 kg ruote, margine 20 % (conversazione)
    "disturbo_residuo_g": 0.01,     # [EUG] ±0,01 g sugli assi laterali [XLS]
    "distanza_traslazione_m": 0.3,  # [XLS] SEGNAPOSTO
    "tempo_traslazione_s": 3.0,     # [XLS] SEGNAPOSTO, dentro la finestra di 5 s
    "margine_spinta": 1.2,          # [XLS]
    "finestra_libera_s": 5.0,       # [ESA] finestra utile per oggetti liberi
    "durata_microgravita_s": 22.0,  # [EUG]
    "spinta_per_asse_N": None,      # None = calcolata come in [XLS]: k_m * m * (n g + 4 d / t^2)
    "assi_contemporanei_max": 3,    # per corrente di picco e verifica d'ingestione
}

# ============================================================== ambienti
# p in Pa, T in K.  Il primo è quello di progetto (dimensiona la spinta).
AMBIENTI = {
    "volo_20C":  {"p": 82500.0, "T": 293.15, "descrizione": "cabina A310 in parabola, 825 mbar, 20 °C [EUG]"},
    "volo_18C":  {"p": 82500.0, "T": 291.15, "descrizione": "cabina, estremo freddo 18 °C [EUG]"},
    "volo_25C":  {"p": 82500.0, "T": 298.15, "descrizione": "cabina, estremo caldo 25 °C [EUG]"},
    "lab_20C":   {"p": 101325.0, "T": 293.15, "descrizione": "banco in laboratorio, 1013 mbar"},
}
AMBIENTE_PROGETTO = "volo_20C"

# ============================================================== geometria del cubo
GEOMETRIA = {
    "lato_cubo_mm": 320.0,          # [XLS] scelta aperta, come Astrobee
    "parete_cubo_mm": 3.0,          # SEGNAPOSTO
    "parete_condotto_mm": 1.2,      # SEGNAPOSTO: stampa 3D, >= 0,8 mm per FDM
    "gioco_tra_condotti_mm": 5.0,   # SEGNAPOSTO
    "centro_di_massa_mm": [0.0, 0.0, 0.0],
    "scostamento_baricentro_mm": 5.0,   # [XLS] foglio Assetto: offset per il bilancio di momento
}

# Moduli interni fissi dietro il centro delle facce [PIL] (dimensioni SEGNAPOSTO):
# (asse 0=X 1=Y 2=Z, segno, larghezza_u, larghezza_v, profondità) in mm, u = asse+1, v = asse+2
ZONE_RISERVATE = {
    "stereocamera + LiDAR (fronte)": (1, +1, 70.0, 120.0, 60.0),
    "monocamera (retro)":            (1, -1, 50.0, 50.0, 40.0),
    "aggancio utensili Lego (alto)": (2, +1, 80.0, 80.0, 25.0),
    "docking non invasivo (basso)":  (2, -1, 80.0, 80.0, 25.0),
}
# Quadrato centrale di ogni faccia da lasciare libero da bocche (mm di lato)
ZONA_CENTRALE_FACCE_MM = 120.0
FACCIA_SPORTELLINO = (0, +1)       # [PIL] una faccia laterale = sportellino batteria
FACCIA_LIBERA = (0, -1)            # [PIL] l'altra laterale: libera

# Componenti da collocare all'interno (mm) [COMP], nell'ordine di priorità
COMPONENTI = {
    "batteria NiMH 24 V (sportellino)": {"dim": (150.0, 100.0, 80.0), "criterio": "faccia_sportellino"},
    "ruote di reazione (3 x Ø100 x 30)": {"dim": (130.0, 130.0, 130.0), "criterio": "centro"},   # inviluppo SEGNAPOSTO
    "blocco avionica": {"dim": (200.0, 150.0, 50.0), "criterio": "centro"},
    "regolatori ESC": {"dim": None, "criterio": "centro"},   # calcolato dal numero di motori
}
ESC_4IN1_MM = (36.0, 36.0, 12.0)    # una scheda ogni 4 motori, SEGNAPOSTO

# ============================================================== elementi del condotto
ELEMENTI = {
    # griglie di protezione [LET Idelchik]
    "griglia_ingresso": True,
    "porosita_griglia_ingresso": 0.60,    # SEGNAPOSTO: maglia fine anti-dita / anti-capelli
    "griglia_uscita": True,
    "porosita_griglia_uscita": 0.80,      # SEGNAPOSTO: maglia larga
    "diametro_filo_griglia_mm": 0.5,
    # imbocco [LET Graf 2005, Pereira 2008: labbro raggiato migliora l'hover]
    "raggio_imbocco_su_D": 0.10,
    "raggio_imbocco_plenum_su_D": 0.15,
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
    # valvole (Y6)
    "k_valvola_aperta": 0.20,
    "apertura_minima_valvola": 0.30,      # parzializzazione per desaturare
    # plenum (Y6)
    "velocita_griglia_plenum_m_s": 4.0,
    "margine_griglia_plenum_mm": 20.0,
    "K_passaggio_interno_plenum": 1.0,    # SEGNAPOSTO: da CFD
    # parete
    "rugosita_parete_um": 20.0,           # stampa 3D lisciata
    "rendimento_esc": 0.93,
}

# ============================================================== ventole (forme generiche)
# Coefficienti adimensionali: phi = c_x/U_punta, psi = Dp_t/(rho U_punta^2).
# SEGNAPOSTO: sostituire con le curve misurate (chiave "tabella").
TIPI_VENTOLA = {
    "assiale_alta_pressione": dict(phi_d=0.55, psi_d=0.30, psi_0_su_psi_d=1.40, eta_max=0.72, Re_rif=2e5,
                                   larghezza_eta=0.60, nu_min=0.40, Z=7, corda_su_D=0.18),
    "assiale_media": dict(phi_d=0.45, psi_d=0.18, psi_0_su_psi_d=1.45, eta_max=0.70, Re_rif=2e5,
                          larghezza_eta=0.65, nu_min=0.30, Z=5, corda_su_D=0.22),
    "elica_intubata": dict(phi_d=0.35, psi_d=0.10, psi_0_su_psi_d=1.50, eta_max=0.65, Re_rif=2e5,
                           larghezza_eta=0.70, nu_min=0.22, Z=3, corda_su_D=0.25),
}

# ============================================================== motori brushless
# SEGNAPOSTO: valori tipici di catalogo per la taglia, da sostituire con le schede tecniche.
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

# ============================================================== limiti
LIMITI = {
    "mach_punta_max": 0.30,          # sopra: le formule incomprimibili non bastano
    "velocita_punta_max_m_s": 150.0, # resistenza del rotore stampato, SEGNAPOSTO
    "indice_ingestione_attenzione": 0.05,
    "indice_ingestione_critico": 0.20,
    "tempo_salita_spinta_max_s": 0.5,   # [XLS] foglio Risposta
    "momento_ruote_max_Nms": 0.15,      # [XLS] foglio Assetto, SEGNAPOSTO per ruota
    "differenza_spinta_coppia": 0.05,   # squilibrio tra le due ventole di una coppia (5 %)
}

# ============================================================== struttura del condotto
# E (Pa), nu, rho (kg/m3), sigma_snervamento (Pa): valori tipici di scheda tecnica, SEGNAPOSTO
MATERIALI = {
    "PETG (FDM)":        dict(E=2.0e9, nu=0.38, rho=1270.0, sigma_snervamento=50e6, stampabile_max_mm=250.0),
    "PA12 (SLS)":        dict(E=1.7e9, nu=0.40, rho=1010.0, sigma_snervamento=48e6, stampabile_max_mm=300.0),
    "resina tenace (SLA)": dict(E=2.5e9, nu=0.38, rho=1180.0, sigma_snervamento=55e6, stampabile_max_mm=200.0),
    "alluminio 6061":    dict(E=69e9, nu=0.33, rho=2700.0, sigma_snervamento=276e6, stampabile_max_mm=1000.0),
}
MATERIALE_CONDOTTO = "PETG (FDM)"
CARICHI = {"g_ipergravita": 1.8, "g_atterraggio_emergenza": 9.0}   # [EUG] 1,8 g; [ESA] carichi d'emergenza

# ============================================================== ottimizzazione
OTTIMIZZAZIONE = {
    "diametri_mm": [26, 30, 34, 38, 42, 46, 50, 55, 60],   # diametri del condotto alla ventola
    "sigma": [0.70, 0.80, 0.90, 1.00],                    # A_uscita / A_ventola (Venturi)
    "pesi": {                                             # peso dei criteri nel punteggio (somma libera)
        "spazio": 0.30,          # volume libero dopo i componenti
        "perdite": 0.25,         # potenza elettrica per la spinta richiesta e quota di perdite
        "semplicita": 0.25,      # realizzabilità e numero di parti
        "robustezza": 0.10,      # tolleranza ai guasti, parti mobili
        "dinamica": 0.10,        # tempo di salita, desaturazione, ingestione
    },
    # scale dei punteggi (0 al primo valore, 1 al secondo)
    "scala_volume_libero": (0.40, 0.80),
    "scala_potenza_asse_W": (300.0, 50.0),
    "scala_tempo_salita_s": (0.6, 0.1),
}

# ============================================================== realizzabilità (pesi interni)
REALIZZABILITA = {
    "pesi": {"parti": 0.25, "curve": 0.20, "giunzioni": 0.15, "attuatori": 0.20, "stampa": 0.20},
    "parti_rif": (40, 12),        # numero di parti stampate: 0 punti a 40, 1 a 12
    "curve_rif": (30, 0),
    "attuatori_rif": (24, 6),     # motori + servo
}
