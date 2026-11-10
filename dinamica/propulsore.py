"""Dinamica del propulsore e stabilità del controllo.

Salita della spinta: J dω/dt = Kt I - τ_aero(ω), con τ_aero = τ_rif (ω/ω_rif)^2
(rete fissa: coppia quadratica nei giri), corrente limitata dal regolatore
(I_max) e dalla tensione disponibile (V_bus d - ω/Kv)/R.  La spinta va con
ω^2, quindi il 90 % della spinta si raggiunge a ω = sqrt(0,9) ω_rif.

Margine di fase: anello di posizione su massa pura (1/(m s^2)), regolatore
PD con zero a ω_c/3 (anticipo atan 3 = 71,6°) e attuatore del primo
ordine con τ_a = t_90 / 2,3:   PM = 71,6° - atan(ω_c τ_a).

Bilancio di momento per le ruote di reazione nella finestra libera:
baricentro fuori asse, squilibrio tra le ventole di una coppia, coppia di
reazione dei rotori non compensati e momento angolare dei rotori in avvio.

Usato da RUN_S4_dinamica (margine di fase, ruote) e dall'analisi delle configurazioni
in ../Analisi_Configurazioni (condotti/ponte_dinamica.py): è l'unica copia di questo modello.
"""
import math
import numpy as np


def tempo_salita(motore, J_tot, N_rif, coppia_rif, V_bus, duty_max=0.95, frazione=0.9, N0=0.0):
    """Tempo (s) da N0 al 'frazione' della spinta a N_rif; ritorna anche la storia."""
    kv = motore.Kv * 2 * math.pi / 60          # rad/s/V
    Kt = 1 / kv
    w_rif = N_rif * 2 * math.pi / 60
    w_obj = math.sqrt(frazione) * w_rif
    w = N0 * 2 * math.pi / 60
    t, dt = 0.0, 2e-4
    storia = [(0.0, w)]
    while w < w_obj and t < 5.0:
        I_v = (V_bus * duty_max - w / kv) / motore.R
        I = max(min(motore.I_max, I_v), 0.0)
        tau_a = coppia_rif * (w / w_rif) ** 2
        dw = (Kt * (I - motore.I0) - tau_a) / J_tot
        if dw <= 0:
            return math.inf, storia
        w += dw * dt
        t += dt
        if len(storia) < 4000 and int(t / dt) % 20 == 0:
            storia.append((t, w))
    storia.append((t, w))
    return t, storia


def tempo_inversione(motore, J_tot, N_rif, coppia_rif, V_bus, duty_max=0.95):
    """Ventola reversibile: frenata attiva fino a zero e risalita nell'altro verso."""
    kv = motore.Kv * 2 * math.pi / 60
    Kt = 1 / kv
    w_rif = N_rif * 2 * math.pi / 60
    w, t, dt = w_rif, 0.0, 2e-4
    while w > 0 and t < 5.0:
        tau_a = coppia_rif * (w / w_rif) ** 2
        I = motore.I_max
        dw = -(Kt * I + tau_a) / J_tot
        w += dw * dt
        t += dt
    t_su, _ = tempo_salita(motore, J_tot, N_rif, coppia_rif, V_bus, duty_max)
    return t + t_su


def margine_fase(t90, omega_c):
    tau_a = t90 / 2.3
    return math.degrees(math.atan(3.0)) - math.degrees(math.atan(omega_c * tau_a))


def tau_max_per_margine(omega_c, PM_min=45.0):
    return math.tan(math.radians(math.degrees(math.atan(3.0)) - PM_min)) / omega_c


def bilancio_ruote(F_asse, scost_baricentro_m, braccio_coppia_m, squilibrio, F_unita,
                   coppia_reazione_netta, H_rotori_non_compensati, t_finestra, H_max):
    tau_cg = F_asse * scost_baricentro_m
    tau_sq = squilibrio * F_unita * braccio_coppia_m
    tau_tot = tau_cg + tau_sq + coppia_reazione_netta
    H = tau_tot * t_finestra + H_rotori_non_compensati
    return {"coppia_baricentro": tau_cg, "coppia_squilibrio": tau_sq,
            "coppia_reazione": coppia_reazione_netta, "H_rotori": H_rotori_non_compensati,
            "H_finestra": H, "quota_ruota": H / H_max if H_max > 0 else math.inf}
