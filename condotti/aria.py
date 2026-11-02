"""Proprietà dell'aria (gas perfetto secco, viscosità di Sutherland).

Tutte le grandezze in unità SI. L'umidità è trascurata: sposta la densità
di meno dell'1 % alle temperature di cabina.
"""
from dataclasses import dataclass
import math

R_ARIA = 287.05      # J/(kg K), aria secca
GAMMA = 1.4


@dataclass(frozen=True)
class Aria:
    nome: str
    p: float          # Pa
    T: float          # K
    rho: float        # kg/m^3
    mu: float         # Pa s
    nu: float         # m^2/s
    a: float          # m/s, velocità del suono

    def q(self, v):
        """Pressione dinamica 1/2 rho v^2 (Pa)."""
        return 0.5 * self.rho * v * v


def viscosita_sutherland(T):
    """Viscosità dinamica dell'aria [Pa s] (Sutherland, valida 200-1000 K)."""
    return 1.458e-6 * T ** 1.5 / (T + 110.4)


def crea_aria(nome, p_Pa, T_K):
    rho = p_Pa / (R_ARIA * T_K)
    mu = viscosita_sutherland(T_K)
    return Aria(nome=nome, p=p_Pa, T=T_K, rho=rho, mu=mu, nu=mu / rho,
                a=math.sqrt(GAMMA * R_ARIA * T_K))
