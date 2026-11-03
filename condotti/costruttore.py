"""Dal layout 3D alla rete fluidodinamica.

Percorre ogni polilinea: tratti dritti accorciati delle tangenti delle
curve, curve con raggio e angolo reali, ventola inserita alla sua ascissa,
effetti di sistema calcolati dalla distanza reale tra ventola e curve,
ugello e griglia all'uscita.
"""
import math
import numpy as np

from . import rete as R
from . import perdite as PE
from .ventole import Ventola


def _segmenti(perc):
    """Sequenza ('dritto', L_mm) / ('curva', R_mm, angolo_deg) di una polilinea."""
    P = perc.punti
    lung = list(perc.lunghezze())
    ang = perc.angoli()
    raggi = list(perc.raggi_curva) + [0.0] * max(0, len(ang) - len(perc.raggi_curva))
    tang = [r * math.tan(math.radians(a) / 2) for r, a in zip(raggi, ang)]
    avvisi = []
    # riduce i raggi se le tangenti non stanno nei segmenti
    for i in range(len(lung)):
        t_ini = tang[i - 1] if i - 1 >= 0 else 0.0
        t_fin = tang[i] if i < len(tang) else 0.0
        if t_ini + t_fin > lung[i] + 1e-9:
            f = lung[i] / (t_ini + t_fin)
            if i - 1 >= 0:
                tang[i - 1] *= f; raggi[i - 1] *= f
            if i < len(tang):
                tang[i] *= f; raggi[i] *= f
            avvisi.append(f"{perc.nome}: raggio di curva ridotto del {100 * (1 - f):.0f}% per mancanza di spazio")
    seq = []
    for i in range(len(lung)):
        t_ini = tang[i - 1] if i - 1 >= 0 else 0.0
        t_fin = tang[i] if i < len(tang) else 0.0
        seq.append(("dritto", max(lung[i] - t_ini - t_fin, 0.0)))
        if i < len(ang) and ang[i] > 0.5:
            seq.append(("curva", raggi[i], ang[i]))
    return seq, avvisi


def _lunghezza_seq(seq):
    return sum(s[1] if s[0] == "dritto" else s[1] * math.radians(s[2]) for s in seq)


def _converti(seq, D_mm, nome_base, rug, s_ventola=None, elem_ventola=None, L_ugello=0.0,
              D_fine=None, semiangolo=8.0, avvisi=None):
    """Lista di elementi di rete da una sequenza; inserisce ventola e ugello."""
    D = D_mm / 1000
    elementi = []
    s = 0.0                                    # mm
    pos_ventola = None
    ventola_messa = elem_ventola is None
    # ugello: accorcia l'ultimo tratto dritto
    seq = list(seq)
    if L_ugello > 0:
        for k in range(len(seq) - 1, -1, -1):
            if seq[k][0] == "dritto":
                if seq[k][1] < L_ugello:
                    avvisi.append(f"{nome_base}: ultimo tratto dritto più corto dell'ugello")
                seq[k] = ("dritto", max(seq[k][1] - L_ugello, 0.0))
                break
    n_d, n_c = 0, 0
    for item in seq:
        if item[0] == "dritto":
            Ld = item[1]
            if not ventola_messa and s <= s_ventola + 1e-6 <= s + Ld:
                Lf = elem_ventola.L * 1000
                a = s_ventola - s
                b = max(Ld - a - Lf, 0.0)
                if a > 0.1:
                    n_d += 1
                    elementi.append(R.Tratto(f"{nome_base} tratto {n_d}", L=a / 1000, D1=D, rugosita=rug))
                elementi.append(elem_ventola)
                pos_ventola = (s + a, s + a + Lf)
                if a + Lf > Ld + 1e-6:
                    avvisi.append(f"{nome_base}: la ventola sporge dal tratto dritto")
                if b > 0.1:
                    n_d += 1
                    elementi.append(R.Tratto(f"{nome_base} tratto {n_d}", L=b / 1000, D1=D, rugosita=rug))
                ventola_messa = True
            elif Ld > 0.1:
                n_d += 1
                elementi.append(R.Tratto(f"{nome_base} tratto {n_d}", L=Ld / 1000, D1=D, rugosita=rug))
            s += Ld
        else:
            Rm, ang = item[1], item[2]
            if not ventola_messa and s_ventola < s:
                avvisi.append(f"{nome_base}: ventola richiesta in una curva, spostata dopo la curva")
                s_ventola = s + Rm * math.radians(ang)
            n_c += 1
            Lc = Rm * math.radians(ang)
            elementi.append(R.Curva(f"{nome_base} curva {n_c}", L=Lc / 1000, D=D, R=Rm / 1000,
                                    angolo=ang, rugosita=rug))
            s += Lc
    if not ventola_messa:
        avvisi.append(f"{nome_base}: ventola non collocata (tratto troppo corto)")
        elementi.append(elem_ventola)
        pos_ventola = (s, s + elem_ventola.L * 1000)
    if L_ugello > 0 and D_fine:
        elementi.append(R.Ugello(f"{nome_base} ugello", L=L_ugello / 1000, D1=D, D2=D_fine / 1000,
                                 semiangolo=semiangolo, rugosita=rug))
    return elementi, pos_ventola


def _posizioni(elementi):
    """Ascisse di inizio e fine (mm) di ogni elemento."""
    out, s = [], 0.0
    for e in elementi:
        out.append((s, s + e.L * 1000))
        s += e.L * 1000
    return out


def costruisci_unita(ug, cfg, tipo_ventola, D_mm, sigma, motore, aperture=None):
    """UnitaRete da UnitaGeom con i parametri degli elementi."""
    el = cfg["elementi"]
    rug = el["rugosita_parete_um"] * 1e-6
    D = D_mm / 1000
    avvisi = []
    nu = max(tipo_ventola.nu_min, (motore.diametro_mm + 2 * el["spessore_mozzo_mm"]) / D_mm)
    if nu > 0.7:
        avvisi.append(f"mozzo/punta = {nu:.2f}: motore troppo grande per questo diametro")
    v = Ventola(tipo_ventola, D, min(nu, 0.85), el["gioco_punta_mm"] / 1000,
                statore=ug.statore and el["statore"], reversibile=ug.reversibile,
                k_gioco_eta=el["k_gioco_eta"], k_gioco_psi=el["k_gioco_psi"],
                penalita_reversibile=el["penalita_reversibile"],
                frazione_vortice_residuo=el["frazione_vortice_residuo"])
    ev = R.ElementoVentola("ventola", L=el["lunghezza_ventola_su_D"] * D, ventola=v)
    # --- imbocco
    ingresso = []
    if el["griglia_ingresso"]:
        ingresso.append(R.Griglia("griglia d'ingresso", D=D, porosita=el["porosita_griglia_ingresso"],
                                  d_filo=el["diametro_filo_griglia_mm"] / 1000))
    ingresso.append(R.Imbocco("imbocco", D=D, r_su_D=el["raggio_imbocco_su_D"]))
    seq_t, av = _segmenti(ug.tronco)
    avvisi += av
    De_mm = ug.uscite[0]["D"]
    tronco, pos_f = _converti(seq_t, ug.tronco.D, "tronco", rug, s_ventola=ug.s_ventola, elem_ventola=ev,
                              L_ugello=ug.tronco.L_ugello, D_fine=ug.tronco.D_fine,
                              semiangolo=el["semiangolo_ugello_deg"], avvisi=avvisi)
    # --- effetti di sistema (distanze reali)
    pos = _posizioni(tronco)
    i_f = tronco.index(ev)
    s_in_f, s_out_f = pos[i_f]
    extra_monte, extra_valle = [], []
    for e, (a, b) in zip(tronco, pos):
        if isinstance(e, R.Curva) and b <= s_in_f + 1e-6:
            dist = (s_in_f - b) / D_mm
            K = PE.k_effetto_sistema_curva_monte(e.R / e.D, dist)
            if K > 0:
                extra_monte.append(R.EffettoSistema(f"effetto di sistema: {e.nome} a {dist:.1f} D dalla ventola",
                                                    D=D, K=K))
        if isinstance(e, R.Curva) and a >= s_out_f - 1e-6:
            dist = (a - s_out_f) / D_mm
            K = PE.k_effetto_sistema_valle(dist, v.statore)
            if K > 0:
                extra_valle.append(R.EffettoSistema(f"effetto di sistema: {e.nome} a {dist:.1f} D a valle",
                                                    D=D, K=K))
    i_f = tronco.index(ev)
    tronco = ingresso + tronco[:i_f] + extra_monte + [ev] + extra_valle + tronco[i_f + 1:]
    # --- coda d'uscita
    usc = ug.uscite[0]
    coda = []
    if el["griglia_uscita"]:
        coda.append(R.Griglia("griglia d'uscita", D=De_mm / 1000, porosita=el["porosita_griglia_uscita"],
                              d_filo=el["diametro_filo_griglia_mm"] / 1000))
    if ug.reversibile:          # condotto simmetrico: imbocco raccordato anche all'altra estremità
        coda.insert(0, R.Imbocco("bordo raccordato d'uscita (reversibile)", D=De_mm / 1000, r_su_D=0.0))
        coda[0].dp = lambda Q, aria, ctx: 0.0       # all'uscita il raccordo non perde
    rami = [R.Ramo("uscita", coda, R.Uscita("uscita", D=De_mm / 1000, alfa_e=el["alfa_getto"],
                                            beta_e=el["beta_getto"], direzione_getto=tuple(usc["getto"]),
                                            posizione=tuple(np.asarray(usc["pos"]) / 1000)))]
    u = R.UnitaRete(ug.nome, tronco, rami, v, reversibile=ug.reversibile)
    return u, avvisi
