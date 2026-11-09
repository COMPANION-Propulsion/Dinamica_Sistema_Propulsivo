"""Geometria 3D del cubo: condotti, ingombri, spazio libero, componenti interni.

Unità: millimetri.  Origine nel centro del cubo.
  X: +destra (faccia sportellino batteria) / -sinistra (faccia libera)
  Y: +fronte (stereocamera + LiDAR)        / -retro (monocamera)
  Z: +alto (aggancio utensili)              / -basso (docking)

Lo spazio interno è discretizzato a voxel.  I condotti sono tubi (capsule)
lungo la polilinea dell'asse con raggio esterno = D/2 + parete: lungo le
curve la capsula copre un po' più del tubo vero (stima prudente).
Per le configurazioni con volumetti d'angolo, questi sono prismi tolti al
volume interno (occupati e non usabili per i componenti).
"""
from dataclasses import dataclass, field
import itertools
import math
import numpy as np
from scipy import ndimage

ASSI = "XYZ"


# =========================================================================
# Strutture dati
# =========================================================================
@dataclass
class Percorso:
    nome: str
    punti: np.ndarray            # (n, 3) mm, nel verso del flusso
    raggi_curva: list            # raggio sull'asse in ogni nodo interno (mm); estremi ignorati
    D: float                     # mm, diametro interno
    D_fine: float = None         # mm, diametro all'ultima estremità (ugello)
    L_ugello: float = 0.0        # mm, lunghezza del tratto conico finale

    def lunghezze(self):
        return np.linalg.norm(np.diff(self.punti, axis=0), axis=1)

    def angoli(self):
        """Angolo di deviazione (gradi) in ogni nodo interno."""
        out = []
        for i in range(1, len(self.punti) - 1):
            a = self.punti[i] - self.punti[i - 1]
            b = self.punti[i + 1] - self.punti[i]
            c = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
            out.append(math.degrees(math.acos(max(-1.0, min(1.0, c)))))
        return out


@dataclass
class UnitaGeom:
    nome: str
    asse: int
    verso: np.ndarray            # versore della spinta prodotta
    tronco: Percorso
    rami: list                   # lista di Percorso (vuota se non si divide)
    s_ventola: float             # mm dall'imbocco lungo il tronco
    ingresso: dict               # {"pos", "normale", "D"}
    uscite: list                 # [{"pos", "getto", "D"}]
    canali: list = field(default_factory=list)     # [(p, q, raggio_esterno, nome)] mm: fori senza ventola
    reversibile: bool = False
    statore: bool = True


@dataclass
class Layout:
    scenario: str
    L: float
    parete: float
    unita: list
    tacche: list = field(default_factory=list)     # [(min, max)] mm: prismi tolti agli spigoli
    solidi: list = field(default_factory=list)     # [(min, max)] mm: pareti piene e travi portanti attorno ai condotti
    avvisi: list = field(default_factory=list)
    parametri: dict = field(default_factory=dict)


# =========================================================================
# Distanze
# =========================================================================
def dist_segmenti(p1, q1, p2, q2):
    """Distanza minima tra due segmenti 3D (Ericson)."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1 @ d1, d2 @ d2, d2 @ r
    if a < 1e-12 and e < 1e-12:
        return float(np.linalg.norm(r))
    if a < 1e-12:
        s, t = 0.0, min(max(f / e, 0.0), 1.0)
    else:
        c = d1 @ r
        if e < 1e-12:
            t, s = 0.0, min(max(-c / a, 0.0), 1.0)
        else:
            b = d1 @ d2
            den = a * e - b * b
            s = min(max((b * f - c * e) / den, 0.0), 1.0) if den > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0:
                t, s = 0.0, min(max(-c / a, 0.0), 1.0)
            elif t > 1:
                t, s = 1.0, min(max((b - c) / a, 0.0), 1.0)
    return float(np.linalg.norm((p1 + d1 * s) - (p2 + d2 * t)))


def tubi_unita(u, parete_condotto, con_canali=False):
    """Lista di capsule (p, q, raggio_esterno, nome) di un'unità (con i fori di vertice a richiesta)."""
    out = []
    for perc in [u.tronco] + list(u.rami):
        P_ = perc.punti
        n = len(P_) - 1
        for i in range(n):
            D = perc.D
            if perc.D_fine and i == n - 1:
                D = max(perc.D, perc.D_fine)
            out.append((P_[i], P_[i + 1], D / 2 + parete_condotto, f"{u.nome}/{perc.nome}"))
    if con_canali:
        out += [(p, q, r, f"{u.nome}/{nome}") for p, q, r, nome in u.canali]
    return out


def dist_segmenti_vett(P1, Q1, P2, Q2):
    """Distanze minime tra coppie di segmenti (array n x 3), versione vettoriale di Ericson."""
    d1, d2, r = Q1 - P1, Q2 - P2, P1 - P2
    a = np.einsum("ij,ij->i", d1, d1)
    e = np.einsum("ij,ij->i", d2, d2)
    f = np.einsum("ij,ij->i", d2, r)
    c = np.einsum("ij,ij->i", d1, r)
    b = np.einsum("ij,ij->i", d1, d2)
    den = a * e - b * b
    s = np.where(den > 1e-12, np.clip((b * f - c * e) / np.where(den > 1e-12, den, 1.0), 0, 1), 0.0)
    t = (b * s + f) / np.where(e > 1e-12, e, 1.0)
    t0 = t < 0
    t1 = t > 1
    s = np.where(t0, np.clip(-c / np.where(a > 1e-12, a, 1.0), 0, 1), s)
    s = np.where(t1, np.clip((b - c) / np.where(a > 1e-12, a, 1.0), 0, 1), s)
    t = np.clip(t, 0, 1)
    C1 = P1 + d1 * s[:, None]
    C2 = P2 + d2 * t[:, None]
    return np.linalg.norm(C1 - C2, axis=1)


def gioco_minimo(layout, parete_condotto):
    """Gioco minimo tra tubi di unità diverse (mm, negativo = intersezione)."""
    tubi, chi = [], []
    for k, u in enumerate(layout.unita):
        for t in tubi_unita(u, parete_condotto, con_canali=True):
            tubi.append(t)
            chi.append(k)
    n = len(tubi)
    if n < 2:
        return math.inf, None
    I, J = np.triu_indices(n, 1)
    chi = np.array(chi)
    m = chi[I] != chi[J]
    I, J = I[m], J[m]
    if len(I) == 0:
        return math.inf, None
    P = np.array([t[0] for t in tubi]); Q = np.array([t[1] for t in tubi]); Rr = np.array([t[2] for t in tubi])
    d = dist_segmenti_vett(P[I], Q[I], P[J], Q[J]) - Rr[I] - Rr[J]
    k = int(np.argmin(d))
    return float(d[k]), (tubi[I[k]][3], tubi[J[k]][3])


# =========================================================================
# Voxel
# =========================================================================
class Griglia3D:
    def __init__(self, L, parete, vox):
        self.L, self.parete, self.vox = L, parete, vox
        self.h_int = L / 2 - parete
        n = int(math.ceil(2 * self.h_int / vox))
        self.n = n
        self.c = -self.h_int + (np.arange(n) + 0.5) * vox      # centri lungo un asse
        self.occ = np.zeros((n, n, n), dtype=np.uint8)          # 0 libero, >0 codice dell'occupante

    def indice(self, x):
        return np.clip(((np.asarray(x) + self.h_int) / self.vox).astype(int), 0, self.n - 1)

    def capsula(self, p, q, r, codice):
        lo = np.minimum(p, q) - r
        hi = np.maximum(p, q) + r
        i0, i1 = self.indice(lo), self.indice(hi) + 1
        X, Y, Z = np.meshgrid(self.c[i0[0]:i1[0]], self.c[i0[1]:i1[1]], self.c[i0[2]:i1[2]], indexing="ij")
        pts = np.stack([X, Y, Z], axis=-1)
        d = q - p
        dd = float(d @ d)
        if dd < 1e-12:
            dist = np.linalg.norm(pts - p, axis=-1)
        else:
            t = np.clip(((pts - p) @ d) / dd, 0, 1)
            proj = p + t[..., None] * d
            dist = np.linalg.norm(pts - proj, axis=-1)
        blocco = self.occ[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]]
        blocco[(dist <= r) & (blocco == 0)] = codice
        return int(np.count_nonzero(dist <= r))

    def box(self, mn, mx, codice, sovrascrivi=False):
        i0 = self.indice(np.asarray(mn) + self.vox / 2)
        i1 = self.indice(np.asarray(mx) - self.vox / 2) + 1
        blocco = self.occ[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]]
        if sovrascrivi:
            blocco[:] = codice
        else:
            blocco[blocco == 0] = codice

    def conta_box(self, mn, mx):
        i0 = self.indice(np.asarray(mn) + self.vox / 2)
        i1 = self.indice(np.asarray(mx) - self.vox / 2) + 1
        return int(np.count_nonzero(self.occ[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]]))

    def volume_frazione(self, codici=None):
        if codici is None:
            return np.count_nonzero(self.occ) / self.occ.size
        return np.isin(self.occ, list(codici)).sum() / self.occ.size


# codici di occupazione
COD_CONDOTTI, COD_RISERVATO, COD_EXTRA, COD_COMP, COD_STRUTTURA = 1, 2, 3, 4, 5   # EXTRA: tacche e fori di vertice;
                                                                                    # STRUTTURA: pareti piene e travi portanti


# =========================================================================
# Zone riservate (moduli interni dietro il centro delle facce)
# =========================================================================
def box_dietro_faccia(L, parete, asse, segno, larghezza_u, larghezza_v, profondita, offset_uv=(0, 0)):
    """Box (min, max) adiacente alla parete interna della faccia (asse, segno)."""
    h = L / 2 - parete
    u, v = (asse + 1) % 3, (asse + 2) % 3
    mn, mx = np.zeros(3), np.zeros(3)
    if segno > 0:
        mn[asse], mx[asse] = h - profondita, h
    else:
        mn[asse], mx[asse] = -h, -h + profondita
    mn[u], mx[u] = offset_uv[0] - larghezza_u / 2, offset_uv[0] + larghezza_u / 2
    mn[v], mx[v] = offset_uv[1] - larghezza_v / 2, offset_uv[1] + larghezza_v / 2
    return mn, mx


# =========================================================================
# Collocazione dei componenti interni
# =========================================================================
def _integrale(libero):
    S = np.zeros(tuple(s + 1 for s in libero.shape), dtype=np.int32)
    S[1:, 1:, 1:] = libero.astype(np.int32).cumsum(0).cumsum(1).cumsum(2)
    return S


def _somma_box(S, i, j, k, a, b, c):
    """Somma su blocchi [i:i+a, j:j+b, k:k+c] per tutte le posizioni (vettoriale)."""
    return (S[i + a, j + b, k + c] - S[i, j + b, k + c] - S[i + a, j, k + c] - S[i + a, j + b, k]
            + S[i, j, k + c] + S[i + a, j, k] + S[i, j + b, k] - S[i, j, k])


def posizioni_libere(occ, dims_vox):
    """Maschera delle posizioni (angolo minimo) in cui un box di dims_vox è tutto libero."""
    libero = occ == 0
    a, b, c = dims_vox
    n0, n1, n2 = occ.shape
    if a > n0 or b > n1 or c > n2:
        return None
    S = _integrale(libero)
    I, J, K = np.meshgrid(np.arange(n0 - a + 1), np.arange(n1 - b + 1), np.arange(n2 - c + 1), indexing="ij")
    tot = _somma_box(S, I, J, K, a, b, c)
    return tot == a * b * c


def colloca(griglia, dims_mm, criterio, codice=COD_COMP, vincolo_faccia=None):
    """Prova le 6 orientazioni del box e sceglie la posizione libera migliore.

    criterio: "centro" (più vicino al centro del cubo, utile per il baricentro)
    vincolo_faccia: (asse, segno) -> il box deve toccare la parete interna di
    quella faccia (batteria estraibile dallo sportellino).
    Ritorna (mn, mx) in mm oppure None.
    """
    g = griglia
    migliore, d_best = None, math.inf
    for perm in set(itertools.permutations(dims_mm)):
        dv = [int(math.ceil(x / g.vox)) for x in perm]
        mask = posizioni_libere(g.occ, dv)
        if mask is None or not mask.any():
            continue
        idx = np.argwhere(mask)
        if vincolo_faccia is not None:
            ax, sg = vincolo_faccia
            if sg > 0:
                idx = idx[idx[:, ax] == g.n - dv[ax]]
            else:
                idx = idx[idx[:, ax] == 0]
            if len(idx) == 0:
                continue
        centri = (idx + np.array(dv) / 2.0) * g.vox - g.h_int
        dist = np.linalg.norm(centri, axis=1)
        if vincolo_faccia is not None:            # sulla faccia: il più centrato nella faccia
            ax, _ = vincolo_faccia
            m = np.ones(3, bool); m[ax] = False
            dist = np.linalg.norm(centri[:, m], axis=1)
        k = int(np.argmin(dist))
        if dist[k] < d_best:
            d_best = dist[k]
            mn = idx[k] * g.vox - g.h_int
            migliore = (mn, mn + np.array(dv) * g.vox)
    if migliore is not None:
        g.box(migliore[0], migliore[1], codice, sovrascrivi=False)
    return migliore


def cubo_libero_massimo(occ, vox):
    """Lato del più grande cubo vuoto allineato agli assi (mm), via distanza a scacchiera."""
    libero = occ == 0
    if not libero.any():
        return 0.0
    padded = np.pad(libero, 1, constant_values=False)
    d = ndimage.distance_transform_cdt(padded, metric="chessboard")
    m = int(d.max())
    return (2 * m - 1) * vox


def sfera_libera_massima(occ, vox):
    libero = occ == 0
    if not libero.any():
        return 0.0
    padded = np.pad(libero, 1, constant_values=False)
    d = ndimage.distance_transform_edt(padded)
    return 2 * float(d.max()) * vox
