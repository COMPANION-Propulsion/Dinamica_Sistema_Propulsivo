"""Modelli di ventola (rotore + statore) e motore brushless.

Ventola: curva adimensionale psi(phi) ed eta(phi), scalata con le leggi di
affinità, corretta per
  - gioco di punta (perdita proporzionale a gioco / altezza pala),
  - numero di Reynolds (formula di Moody, esponente 0,2),
  - pale simmetriche se la ventola è reversibile,
  - assenza dello statore (energia del vortice persa, coppia sul corpo).
  phi = c_x / U_punta     psi = Dp_t / (rho U_punta^2)
  c_x = Q / A_anello      A_anello = pi/4 D^2 (1 - nu^2)

Le curve dei tipi in libreria sono FORME GENERICHE di ventole assiali,
non dati di catalogo: vanno sostituite con le curve misurate al banco
(tipo "tabellare") appena la ventola è scelta.

Motore: modello a tre parametri (Kv, R, I0):
  Kt = 60 / (2 pi Kv)      I = coppia / Kt + I0
  V  = N / Kv + I R        P_el = V I / eta_ESC
"""
from dataclasses import dataclass, field
import math
import numpy as np


@dataclass
class TipoVentola:
    nome: str
    phi_d: float            # coefficiente di flusso di progetto
    psi_d: float            # coefficiente di pressione di progetto (stadio con statore)
    psi_0_su_psi_d: float   # rapporto di pressione a portata nulla
    eta_max: float          # rendimento massimo a Re_rif
    Re_rif: float           # Reynolds di riferimento per eta_max
    larghezza_eta: float    # ampiezza relativa della campana del rendimento
    nu_min: float           # rapporto mozzo/punta minimo costruttivo
    Z: int                  # numero di pale
    corda_su_D: float       # corda / diametro (per Reynolds della pala)
    phi_stallo_su_phi_d: float = 0.65   # sotto questa portata relativa: zona di stallo
    tabella: dict = None    # opzionale: {"phi": [...], "psi": [...], "eta": [...]} misurati

    def psi(self, phi):
        if self.tabella:
            return float(np.interp(phi, self.tabella["phi"], self.tabella["psi"], right=0.0))
        psi0 = self.psi_0_su_psi_d * self.psi_d
        return psi0 - (psi0 - self.psi_d) * (phi / self.phi_d) ** 2

    def phi_max(self):
        if self.tabella:
            ph, ps = np.asarray(self.tabella["phi"]), np.asarray(self.tabella["psi"])
            idx = np.where(ps <= 0)[0]
            return float(ph[idx[0]]) if len(idx) else float(ph[-1])
        psi0 = self.psi_0_su_psi_d * self.psi_d
        return self.phi_d * math.sqrt(psi0 / (psi0 - self.psi_d))

    def eta(self, phi):
        if self.tabella:
            return float(np.interp(phi, self.tabella["phi"], self.tabella["eta"], left=0.05, right=0.05))
        x = (phi - self.phi_d) / (self.phi_d * self.larghezza_eta)
        return max(self.eta_max * (1 - x * x), 0.05)


@dataclass
class Motore:
    nome: str
    Kv: float          # giri/min per volt
    R: float           # ohm (fase-fase)
    I0: float          # A, corrente a vuoto
    I_max: float       # A, corrente massima continua
    massa_g: float
    diametro_mm: float
    lunghezza_mm: float
    J_rotore: float    # kg m^2, inerzia della campana

    @property
    def Kt(self):
        return 60.0 / (2 * math.pi * self.Kv)

    def punto(self, coppia, N, V_bus, eta_esc=0.93, duty_max=0.95):
        """Stato elettrico per erogare 'coppia' (N m) a N giri/min."""
        I = coppia / self.Kt + self.I0
        V = N / self.Kv + I * self.R
        ok_V = V <= V_bus * duty_max
        ok_I = I <= self.I_max
        P_el = V * I / eta_esc
        P_albero = coppia * N * 2 * math.pi / 60
        return {"I": I, "V": V, "P_el": P_el, "eta_motore": P_albero / max(V * I, 1e-9),
                "duty": V / V_bus, "ok_tensione": ok_V, "ok_corrente": ok_I}

    def N_max(self, V_bus, coppia_stimata=0.0, duty_max=0.95):
        I = coppia_stimata / self.Kt + self.I0
        return max((V_bus * duty_max - I * self.R) * self.Kv, 0.0)


@dataclass
class Ventola:
    tipo: TipoVentola
    D: float                 # m, diametro di punta (= diametro del condotto alla ventola)
    nu: float                # rapporto mozzo/punta effettivo
    gioco: float             # m, gioco radiale di punta
    statore: bool = True
    reversibile: bool = False
    k_gioco_eta: float = 1.5     # perdita di rendimento per unità di gioco/altezza pala
    k_gioco_psi: float = 2.0     # perdita di pressione per unità di gioco/altezza pala
    penalita_reversibile: float = 0.90   # pale simmetriche: circa -10 % [Excel, NASA]
    frazione_vortice_residuo: float = 0.05   # con statore: quota di vortice non recuperata
    k_perdita_statore: float = 0.0       # già inclusa nella mappa dello stadio
    avvisi: list = field(default_factory=list)

    @property
    def area_anello(self):
        return math.pi / 4 * self.D ** 2 * (1 - self.nu ** 2)

    @property
    def altezza_pala(self):
        return self.D / 2 * (1 - self.nu)

    def U(self, N):
        return math.pi * self.D * N / 60.0

    def _correzioni(self, aria, N):
        r = self.gioco / max(self.altezza_pala, 1e-9)
        f_psi = max(1 - self.k_gioco_psi * r, 0.3)
        f_eta_gioco = max(1 - self.k_gioco_eta * r, 0.3)
        corda = self.tipo.corda_su_D * self.D
        Re = max(self.U(N) * corda / aria.nu, 1.0)
        return f_psi, f_eta_gioco, Re

    def stato(self, Q, N, aria):
        """Prestazioni della ventola alla portata Q (m^3/s) e N (giri/min)."""
        U = self.U(N)
        if U <= 0:
            return {"dp_utile": 0.0, "dp_stadio": 0.0, "eta": 0.0, "P_albero": 0.0,
                    "coppia": 0.0, "phi": 0.0, "psi": 0.0, "Re": 0.0, "c_theta": 0.0,
                    "coppia_corpo": 0.0, "stallo": False}
        f_psi, f_eta_g, Re = self._correzioni(aria, N)
        phi = Q / self.area_anello / U
        psi = self.tipo.psi(phi) * f_psi
        eta = self.tipo.eta(phi) * f_eta_g
        if Re < self.tipo.Re_rif:                       # Moody: (1-eta)/(1-eta_rif) = (Re_rif/Re)^0.2
            eta = 1 - (1 - eta) * (self.tipo.Re_rif / Re) ** 0.2
        if self.reversibile:
            psi *= self.penalita_reversibile
            eta *= self.penalita_reversibile
        eta = max(eta, 0.05)
        dp_stadio = aria.rho * U * U * psi
        P_albero = max(Q * dp_stadio, 0.0) / eta
        omega = 2 * math.pi * N / 60
        coppia = P_albero / omega
        r_m = self.D / 4 * (1 + self.nu)                  # raggio medio
        U_m = omega * r_m
        # vortice all'uscita del rotore (Eulero): Dp_t,ideale = rho U_m c_theta
        # rendimento idraulico limitato (a portata nulla eta -> 0 ma il vortice resta finito)
        # e vortice limitato fisicamente a c_theta < U_m (nessun pre-vortice in ingresso)
        c_theta = min((dp_stadio / max(eta, 0.5)) / (aria.rho * max(U_m, 1e-6)), 0.9 * U_m)
        if self.statore:
            dp_utile = dp_stadio
            coppia_corpo = self.frazione_vortice_residuo * coppia
        else:
            dp_utile = dp_stadio - 0.5 * aria.rho * c_theta ** 2
            coppia_corpo = coppia                          # momento angolare che esce col getto
        return {"dp_utile": dp_utile, "dp_stadio": dp_stadio, "eta": eta, "P_albero": P_albero,
                "coppia": coppia, "phi": phi, "psi": psi, "Re": Re, "c_theta": c_theta,
                "coppia_corpo": coppia_corpo,
                "stallo": phi < self.tipo.phi_stallo_su_phi_d * self.tipo.phi_d}

    def Q_max(self, N):
        return self.tipo.phi_max() * self.U(N) * self.area_anello * 0.999


def libreria_ventole(cfg):
    """Costruisce i tipi di ventola dal dizionario in INPUT.py."""
    out = {}
    for nome, p in cfg.items():
        out[nome] = TipoVentola(nome=nome, **p)
    return out


def libreria_motori(cfg):
    out = {}
    for nome, p in cfg.items():
        out[nome] = Motore(nome=nome, **p)
    return out
