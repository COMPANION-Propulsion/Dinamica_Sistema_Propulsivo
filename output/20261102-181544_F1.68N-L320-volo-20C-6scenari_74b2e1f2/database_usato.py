"""DATABASE DEGLI SCENARI DI CONDOTTI.

Ogni scenario è un dizionario.  Campi obbligatori:
  id, nome, topologia (uno dei generatori in condotti/scenari.py), origine,
  descrizione, pregi_attesi, difetti_attesi.
Gli altri campi sono parametri del generatore (valori di default sotto).
Per aggiungere uno scenario basta copiare un blocco e cambiare id e parametri:
lo script lo analizza in automatico.

Topologie disponibili
  sfalsati       condotti dritti lungo tutto il lato, sfalsamento ciclico
  spigoli_corti  condotti lunghi mezzo spigolo, presa laterale a metà spigolo
  spigoli_pieni  condotti lungo tutto lo spigolo con scalino vicino ai vertici
  y6_plenum      6 ventole, condotto sdoppiato a Y, aspirazione dal plenum interno
"""

SCENARI = [
    {
        "id": "S1_SFALSATI_12",
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
        "id": "S3_SPIGOLI_PIENI_12",
        "nome": "12 condotti sugli spigoli per tutta la lunghezza, scalino ai vertici",
        "topologia": "spigoli_pieni",
        "origine": "Proposta dell'utente: lo stesso del modello ma sugli spigoli",
        "descrizione": ("12 condotti a filo dei due lati dello spigolo nel tratto centrale; vicino ai vertici rientrano "
                        "con uno scalino a S per incrociarsi senza toccarsi. Ugelli inclinati verso il centro della "
                        "faccia (opzione) per allontanare i getti dalle prese dei condotti vicini."),
        "pregi_attesi": "Massimo arretramento verso l'esterno nel tratto centrale; nessuna parte mobile.",
        "difetti_attesi": "Quattro curve per condotto; zona d'estremità lunga; prese e ugelli vicini nei vertici.",
        "angolo_scalino_deg": 30.0,
        "raggio_scalino_su_D": 1.5,
        "angolo_deflessione_deg": 10.0,
    },
    {
        "id": "S4_Y6_MARGINI",
        "nome": "6 ventole con condotto a Y, ugelli ai margini opposti (dal file Excel)",
        "topologia": "y6_plenum",
        "origine": "Classifica del foglio Confronto architetture (conversazione): 6 ventole unidirezionali sdoppiate a Y",
        "descrizione": ("Una ventola unidirezionale per ciascun verso (±X, ±Y, ±Z). A valle della ventola il condotto "
                        "si divide in due rami uguali che escono a filo parete ai margini opposti della faccia. Le "
                        "ventole aspirano dal volume interno, alimentato da una griglia sulla faccia libera. Una "
                        "valvola per ramo parzializza un ugello e crea coppia per desaturare le ruote di reazione."),
        "pregi_attesi": "Solo 6 motori; pale curve e Venturi ottimizzati per un verso; frenata senza invertire i giri.",
        "difetti_attesi": "Perdite nella giunzione a Y; valvole con servo (parti mobili); ingombro dei rami; plenum condiviso.",
        "ugelli_diagonali": False,
        "rapporto_area_rami": 1.0,
        "raggio_giunzione_frazione": 0.55,
        "profondita_giunzione_frazione": 0.45,
        "lunghezza_stelo_su_D": 0.4,
        "distanza_ventola_giunzione_su_D": 1.0,
        "raggio_curva_ramo_su_D": 1.0,
        "valvole_per_unita": 2,
        "cerca_lato_giunzione": True,
        "forma_y": "spaziale",
        "varianti_geometria": {
            "forma_y": ["spaziale", "piatta"],
            "raggio_giunzione_frazione": [0.45, 0.60, 0.75],
            "profondita_giunzione_frazione": [0.35, 0.50, 0.65],
        },
    },
    {
        "id": "S5_REVERSIBILI_6",
        "nome": "6 ventole reversibili a coppie sfalsate (dal file Excel)",
        "topologia": "sfalsati",
        "origine": "Foglio Confronto architetture del compagno (primo nella classifica originale)",
        "descrizione": ("6 condotti dritti sfalsati, una coppia diagonale per asse; ogni ventola gira nei due versi. "
                        "Condotto simmetrico senza ugello né statore; per frenare si inverte la rotazione."),
        "pregi_attesi": "Metà dei condotti e dei motori di S1; più spazio interno; nessuna valvola.",
        "difetti_attesi": "Pale simmetriche (circa -10 %); niente Venturi né statore; inversione lenta; coppia dal vortice.",
        "reversibile": True,
        "verso_coppia_D1": -1,
    },
    {
        "id": "S6_Y6_DIAGONALI",
        "nome": "6 ventole con condotto a Y, ugelli negli angoli opposti",
        "topologia": "y6_plenum",
        "origine": "Variante di S4 per allontanare i rami dal centro delle facce",
        "descrizione": ("Come S4, ma i due ugelli di ogni faccia sono negli angoli opposti: la giunzione si sposta "
                        "verso gli altri due angoli e i rami corrono lungo il bordo della faccia, lontano dai moduli "
                        "riservati al centro."),
        "pregi_attesi": "Rami lontani dai sensori; braccio di coppia maggiore per la desaturazione.",
        "difetti_attesi": "Rami più lunghi; giunzione con angolo più aperto.",
        "ugelli_diagonali": True,
        "rapporto_area_rami": 1.0,
        "raggio_giunzione_frazione": 0.55,
        "profondita_giunzione_frazione": 0.45,
        "lunghezza_stelo_su_D": 0.4,
        "distanza_ventola_giunzione_su_D": 1.0,
        "raggio_curva_ramo_su_D": 1.0,
        "valvole_per_unita": 2,
        "cerca_lato_giunzione": True,
        "forma_y": "spaziale",
        "varianti_geometria": {
            "forma_y": ["spaziale", "piatta"],
            "margine_ugello_mm": [4.0, 35.0],
            "raggio_giunzione_frazione": [0.45, 0.75],
            "profondita_giunzione_frazione": [0.35, 0.50, 0.65],
        },
    },
]
