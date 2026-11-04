"""Ricerca del progetto ottimo per ogni scenario.

Due livelli:
  esterno  geometria: lato del cubo L x varianti dello scenario x diametro del condotto D
           (lo spazio interno dipende solo da questi);
  interno  elementi: rapporto d'area dell'ugello sigma x tipo di ventola x
           motore.  Si sceglie la combinazione ammissibile (tensione,
           corrente, Mach) che dà la minima potenza elettrica per asse alla
           spinta richiesta: a parità di geometria è il criterio fisico giusto,
           perché spazio e realizzabilità non cambiano.
Poi il progetto (geometria + elementi) riceve la valutazione completa e il
punteggio pesato; l'ottimo dello scenario è il migliore tra gli ammissibili.
Se nessun progetto è ammissibile si riporta il meno peggio con l'elenco
delle violazioni, così si vede che cosa cambiare.
"""
import itertools
import math
import time

from . import valutazione as V
from .config import cfg_con_lato
from .scenari import genera_layout
from .ventole import libreria_ventole, libreria_motori


def varianti(sc):
    vg = sc.get("varianti_geometria")
    if not vg:
        return [{}]
    chiavi = list(vg.keys())
    out, visti = [], set()
    for comb in itertools.product(*[vg[k] for k in chiavi]):
        v = dict(zip(chiavi, comb))
        chiave = tuple(sorted(v.items()))
        if chiave not in visti:
            visti.add(chiave)
            out.append(v)
    return out


def migliori_elementi(gm, sc, cfg, tipi, motori, sigmas, log=None):
    """Combinazione sigma / ventola / motore a minima potenza per asse."""
    D = gm["D"]
    sc2 = dict(sc, **gm["variante"])
    best = None
    for sigma in sigmas:
        if sc.get("reversibile") and sigma != 1.0:
            continue                         # condotto simmetrico: niente Venturi
        lay_a = genera_layout(sc2, D, sigma, cfg)
        for tipo in tipi.values():
            for mot in motori.values():
                if (mot.diametro_mm + 2 * cfg["elementi"]["spessore_mozzo_mm"]) / D > 0.7:
                    continue
                try:
                    a = V.valuta_aero(lay_a, cfg, D, sigma, tipo, mot, completo=False)
                except Exception as exc:          # combinazione fuori campo: si scarta
                    if log:
                        log(f"      scartata {tipo.nome}/{mot.nome}/sigma={sigma}: {exc}")
                    continue
                if a is None:
                    continue
                ok = a["ok_motore"] and a["ok_mach"]
                chiave = (0 if ok else 1, a["P_asse_max"])
                if best is None or chiave < best[0]:
                    best = (chiave, sigma, tipo, mot, lay_a)
    return best


def ottimizza_scenario(sc, cfg, log=print):
    """Cerca l'ottimo dello scenario su: lato del cubo L x variante geometrica x diametro D.

    Per ogni (L, variante) si sale con D e ci si ferma quando l'ingombro non regge (motore, Mach
    e massa non fermano la salita).  Per ogni (L, variante, D) si scelgono Venturi, ventola e motore.
    L'ottimo è il progetto ammissibile col punteggio più alto, a parità il condotto più centrato,
    poi il cubo più piccolo.
    """
    t0 = time.time()
    tipi = libreria_ventole(cfg["tipi_ventola"])
    motori = libreria_motori(cfg["motori"])
    ott = cfg["ottimizzazione"]
    lati = cfg["lati_cubo_mm"]
    progetti = []
    xi = {}                                      # (L, variante) -> massimo D ammissibile (informativo)
    for iL, L in enumerate(lati, start=1):
        cfgL = cfg_con_lato(cfg, L)
        t_L = time.time()
        for var in varianti(sc):
            chiave = (float(L), _txt_var(var) or "base")
            xi[chiave] = None
            for D in sorted(ott["diametri_mm"]):
                gm = V.valuta_geometria(sc, float(D), cfgL, var)
                amm = V.geometria_ammissibile(gm)
                rec = {"scenario": sc["id"], "L": float(L), "D": float(D), "variante": var, "geometria": gm,
                       "geometria_ammissibile": amm, "completo": None}
                if not amm or not gm["componenti_tutti"]:
                    # ingombro: cresce con D, quindi nessuna soluzione ammissibile per i D successivi
                    # (con questa variante). Motore, Mach e massa NON attivano questo stop.
                    progetti.append(rec)
                    log(f"   L {L:.0f} · D {D:>3} {_txt_var(var)}: spazio/geometria non ammissibile; "
                        f"diametri successivi non analizzati")
                    break
                best = migliori_elementi(gm, sc, cfgL, tipi, motori, ott["sigma"])
                if best is not None:
                    _, sigma, tipo, mot, lay_a = best
                    aero = V.valuta_aero(lay_a, cfgL, float(D), sigma, tipo, mot, completo=True)
                    if aero is not None:
                        rec["aero"] = aero
                        rec["completo"] = V.valuta_completo(gm, aero, cfgL, sc, tipo, mot, sigma)
                        rec["layout_aero"] = lay_a
                progetti.append(rec)
                c = rec["completo"]
                ok = bool(c and c["ammissibile"])
                if ok:
                    xi[chiave] = float(D)
                stato = ("spinta non raggiunta" if c is None else
                         f"punteggio {c['punteggio_totale']:.3f}" + ("" if ok else " con violazioni"))
                log(f"   L {L:.0f} · D {D:>3} {_txt_var(var)}: {stato}")
        validi_L = [p for p in progetti if p["L"] == float(L) and p["completo"] and p["completo"]["ammissibile"]]
        if validi_L:
            b = max(validi_L, key=_chiave_ottimo)
            log(f"   >> lato {L:.0f} mm ({iL}/{len(lati)}): miglior punteggio {b['completo']['punteggio_totale']:.3f} "
                f"con D {b['D']:.0f} mm {_txt_var(b['variante'])}, massa {b['completo']['massa_totale_kg']:.2f} kg"
                f"   [{time.time() - t_L:.0f} s]")
        else:
            log(f"   >> lato {L:.0f} mm ({iL}/{len(lati)}): nessun progetto ammissibile   [{time.time() - t_L:.0f} s]")
    validi = [p for p in progetti if p["completo"] and p["completo"]["ammissibile"]]
    if validi:
        ottimo = max(validi, key=_chiave_ottimo)
    else:
        ottimo = _meno_peggio(progetti, sc, cfg, tipi, motori, log)
    log(f"   -> ottimo: lato L = {ottimo['L']:.0f} mm, D = {ottimo['D']:.0f} mm {_txt_var(ottimo['variante'])}"
        f"{'' if ottimo['completo'] and ottimo['completo']['ammissibile'] else '  (NON AMMISSIBILE)'}"
        f"   [{time.time() - t0:.0f} s]")
    righe = []
    for L in lati:
        vals = [v for (l, _), v in xi.items() if l == float(L) and v is not None]
        righe.append(f"L {L:.0f}: " + (f"{min(vals):.0f}-{max(vals):.0f} mm" if vals else "nessuno"))
    log("   massimo diametro ammissibile (Xi) tra le varianti, per lato: " + "; ".join(righe))
    return {"scenario": sc, "progetti": progetti, "ottimo": ottimo,
            "xi": {f"L {l:.0f} {v}": d for (l, v), d in xi.items()}}


def _chiave_ottimo(p):
    """Punteggio a 4 cifre; a parità il condotto più centrato sullo spigolo, poi il cubo più piccolo."""
    spost = abs(p["geometria"]["layout"].parametri.get("spostamento_mm", 0.0))
    return (round(p["completo"]["punteggio_totale"], 4), -spost, -p["L"])


def _meno_peggio(progetti, sc, cfg, tipi, motori, log):
    """Nessun progetto ammissibile: valuta comunque la geometria meno critica."""
    con_c = [p for p in progetti if p["completo"]]
    if con_c:
        return min(con_c, key=lambda p: (len(p["completo"]["violazioni"]), -p["completo"]["punteggio_totale"]))
    def gravita(p):
        g = p["geometria"]
        return (g["irrealizzabile"], len(g["sovrapposizioni_zone_cm3"]) + len(g["bocche_in_zone_centrali"]),
                -g["gioco_min_mm"])
    for p in sorted(progetti, key=gravita):
        cfgL = cfg_con_lato(cfg, p["L"])
        if not p["geometria"]["componenti_valutati"]:      # ricalcola con i componenti per il rapporto
            p["geometria"] = V.valuta_geometria(sc, p["D"], cfgL, p["variante"], colloca_componenti=True)
        best = migliori_elementi(p["geometria"], sc, cfgL, tipi, motori, cfg["ottimizzazione"]["sigma"])
        if best is None:
            continue
        _, sigma, tipo, mot, lay_a = best
        aero = V.valuta_aero(lay_a, cfgL, p["D"], sigma, tipo, mot, completo=True)
        if aero is None:
            continue
        p["aero"] = aero
        p["completo"] = V.valuta_completo(p["geometria"], aero, cfgL, sc, tipo, mot, sigma)
        p["layout_aero"] = lay_a
        return p
    return sorted(progetti, key=gravita)[0]


def _txt_var(var):
    if not var:
        return ""
    return "(" + ", ".join(f"{k.split('_')[0]} {v}" for k, v in var.items()) + ")"
