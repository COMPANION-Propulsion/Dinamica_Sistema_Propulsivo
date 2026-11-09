"""INPUT DINAMICA S4: dinamica di volo del cubo (configurazione S4), massa puntiforme nel baricentro.

È l'unico file da modificare per la run di dinamica.  Dopo averlo salvato si lancia RUN_S4_dinamica.py.
Non dipende da INPUT_S4.py né dall'analisi dei condotti: i dati che arrivano dall'analisi (spinta massima,
tempo di salita, potenza, ...) sono qui sotto, copiati a mano dall'ultima run di interazione
(foglio Excel "Controllo e dinamica" e "Fluidodinamica", oppure dati/riepilogo.json).

Sezioni:
   0  ESECUZIONE      passo di integrazione, formato dei grafici, cartella di output
   1  CORPO           massa (concentrata nel baricentro)
   2  ATTUATORE       spinta massima per asse e tempo di salita (dall'analisi)
   3  MANOVRA         spostamento richiesto, tempo, finestra di volo, tolleranza
   4  DISTURBO        accelerazione residua del volo parabolico
   5  REGOLATORE      PD sulla posizione
   6  ENERGIA         potenza in funzione della spinta
   7  RUOTE           bilancio delle ruote di reazione (dai dati dell'analisi)

Convenzione degli assi: X, Y, Z come nell'analisi (X destra, Y fronte, Z alto).  Gli elenchi [X, Y, Z]
seguono sempre questo ordine.  I tre assi sono indipendenti e si muovono contemporaneamente.

Fonti: [ANL] risultato dell'ultima run di interazione, [EUG] ESA User Guide, [XLS] foglio di dimensionamento.
SEGNAPOSTO = valore da sostituire appena disponibile un dato vero.
"""

# =============================================================================
# 0. ESECUZIONE
# =============================================================================
ESECUZIONE = {
    "etichetta": "",               # testo libero nel nome della cartella di output ("" = automatico)
    "passo_integrazione_s": 0.001, # passo dell'integrazione (s)
    "formato_grafici": ["svg"],    # ["svg"] oppure ["svg", "png"]
    "cartella_output": "output",
    "verifiche": True,             # prima della simulazione controlla il codice contro risultati noti
}

# =============================================================================
# 1. CORPO
# =============================================================================
CORPO = {
    "massa_kg": 5,              # [ANL] massa stimata dell'ultima run di interazione (obiettivo 4 kg)
}

# =============================================================================
# 2. ATTUATORE   (da analisi: foglio "Controllo e dinamica")
# =============================================================================
ATTUATORE = {
    "spinta_max_positiva_N": [1.9466, 1.9466, 1.9466],   # [ANL] forza pura disponibile per verso, [X, Y, Z]
    "spinta_max_negativa_N": [1.9466, 1.9466, 1.9466],   # [ANL] stesso per il verso opposto
    "tempo_salita_90_s": 0.1204,   # [ANL] tempo per arrivare al 90 % della spinta; il ritardo è tau = t90 / 2,3
}

# =============================================================================
# 3. MANOVRA
# =============================================================================
MANOVRA = {
    "distanza_m": [0.3, 0.3, 0.3],       # [XLS] SEGNAPOSTO: spostamento richiesto su X, Y, Z (da fermo a fermo)
    "tempo_manovra_s": 3.0,              # [XLS] SEGNAPOSTO: tempo per completarlo
    "finestra_s": 5.0,                   # [ESA] finestra utile per oggetti liberi: si simula fino a qui
    "tolleranza_posizione_mm": 5.0,      # per il tempo di assestamento
    "profilo": "minimo_jerk",            # "minimo_jerk" (polinomio di quinto grado) oppure "gradino"
}

# =============================================================================
# 4. DISTURBO   (accelerazione residua nel riferimento del cubo)
# =============================================================================
DISTURBO = {
    "ampiezza_g": [0.01, 0.01, 0.01],    # [EUG] ±0,01 g sugli assi laterali: ipotesi per tutti e tre
    "frequenza_Hz": [1.0, 1.0, 1.0],     # SEGNAPOSTO: serve una registrazione reale di volo
    "fase_gradi": [0.0, 120.0, 240.0],   # fasi diverse per i tre assi (0, 0, 0 = disturbo in fase)
}

# =============================================================================
# 5. REGOLATORE   (PD sulla posizione, massa pura)
# =============================================================================
REGOLATORE = {
    "frequenza_propria_rad_s": 2.0,      # wn: banda dell'anello di posizione
    "smorzamento": 0.8,                  # zeta
    "feedforward_riferimento": False,    # True = aggiunge m * a_riferimento al comando (segue meglio la traiettoria)
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
    "braccio_coppia_m": 0.2104,          # [ANL] braccio tra due ventole di una coppia
    "squilibrio_coppia": 0.05,           # squilibrio di spinta tra le due ventole di una coppia (5 %)
    "spinta_per_unita_N": 0.6943,        # [ANL] spinta di una ventola alla spinta di progetto
    "coppia_reazione_rotori_Nm": 2.89e-5,# [ANL] coppia di reazione netta dei rotori
    "momento_rotori_in_avvio_Nms": 0.0,  # [ANL] momento angolare dei rotori non compensati
    "momento_ruote_max_Nms": 0.15,       # [XLS] SEGNAPOSTO: momento angolare massimo delle ruote
    "frequenze_margine_fase_rad_s": [1.0, 2.0, 4.0],
}
