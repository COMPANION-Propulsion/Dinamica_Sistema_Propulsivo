"""
Dinamica di volo del cubo COMPANION (configurazione S4): massa nel baricentro, tre assi, PD.

    cli.py         sequenza della run (input.py -> risultati/<caso>/)
    caso.py        cartella dei risultati del caso
    volo.py        dinamica di volo: riferimento, disturbo, simulazione di un asse, indicatori
    propulsore.py  dinamica del propulsore: salita della spinta, margine di fase, ruote
                   (usato anche da ../Analisi_Configurazioni)
    export.py      grafici, serie temporali, RISULTATO.md
    verifiche.py   verifiche contro soluzioni analitiche (girano prima di ogni run)
"""
