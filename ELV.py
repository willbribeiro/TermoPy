# -*- coding: utf-8 -*-
"""Equilíbrio líquido-vapor (ELV) de misturas binárias — modelos de atividade.

O modelo de Margules (dois parâmetros) e o de Wilson fornecem γ1 e γ2; a
pressão de bolha é calculada por::

    P = x1·γ1·P1sat + x2·γ2·P2sat
    y1 = x1·γ1·P1sat / P

com P1sat e P2sat obtidos por Antoine na temperatura informada (°C).
"""
import math
from abc import ABC, abstractmethod

import PressaodeSaturacao
from utilidades import ErroTermodinamico


class ModeloAtividade(ABC):
    """Base para modelos de coeficiente de atividade."""

    NOME = "Modelo de atividade"

    def __init__(self):
        self._composto1 = None
        self._composto2 = None
        self._temperatura = None
        self._variacao = None

    # ------------------------------------------------------- entrada -----
    @property
    def composto1(self):
        return self._composto1

    @composto1.setter
    def composto1(self, valor):
        self._composto1 = valor

    @property
    def composto2(self):
        return self._composto2

    @composto2.setter
    def composto2(self, valor):
        self._composto2 = valor

    @property
    def temperatura(self):
        """Temperatura em °C (a mesma usada por Antoine)."""
        return self._temperatura

    @temperatura.setter
    def temperatura(self, valor):
        self._temperatura = float(valor)

    @property
    def variacao(self):
        """Passo de x1 entre 0 e 1."""
        return self._variacao

    @variacao.setter
    def variacao(self, valor):
        passo = float(valor)
        if not 0.0 < passo <= 1.0:
            raise ErroTermodinamico(
                f"A variação deve estar em (0, 1] (recebido {passo})."
            )
        self._variacao = passo

    # -------------------------------------------------------- cálculo ----
    @abstractmethod
    def coeficientes_atividade(self, x1):
        """Retorna ``(γ1, γ2)`` para a fração molar ``x1``."""

    def _pressao_saturacao(self, composto):
        modelo = PressaodeSaturacao.Antoine()
        if not modelo.buscarAntoine(composto):
            raise ErroTermodinamico(
                f"Sem parâmetros de Antoine para o composto {composto!r}."
            )
        modelo.temperatura = self._temperatura
        return modelo.pressaoSat()

    def _validar(self):
        if self._composto1 is None or self._composto2 is None:
            raise ErroTermodinamico("Informe os dois compostos da mistura.")
        if self._temperatura is None:
            raise ErroTermodinamico("Informe a temperatura.")
        if self._variacao is None:
            raise ErroTermodinamico("Informe a variação de x1.")

    def pontos_x1(self):
        """Valores de x1 de 0 a 1, incluindo os extremos exatos."""
        self._validar()
        passos = max(1, int(round(1.0 / self._variacao)))
        return [indice / passos for indice in range(passos + 1)]

    def calcular(self):
        """Retorna ``(x1, y1, P)`` como listas (pressão em Pa)."""
        self._validar()
        p1sat = self._pressao_saturacao(self._composto1)
        p2sat = self._pressao_saturacao(self._composto2)

        xs, ys, pressoes = [], [], []
        for x1 in self.pontos_x1():
            gama1, gama2 = self.coeficientes_atividade(x1)
            pressao = x1 * gama1 * p1sat + (1.0 - x1) * gama2 * p2sat
            if pressao <= 0.0:
                raise ErroTermodinamico(
                    f"Pressão de bolha não positiva em x1 = {x1:.3f}."
                )
            xs.append(x1)
            ys.append(x1 * gama1 * p1sat / pressao)
            pressoes.append(pressao)
        return xs, ys, pressoes

    def grafico(self):
        """Plota o diagrama P-x1-y1 (requer matplotlib)."""
        try:
            import matplotlib.pyplot as plt
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise ImportError(
                "matplotlib é necessário para gerar gráficos: "
                "pip install matplotlib"
            ) from exc

        xs, ys, pressoes = self.calcular()
        pressoes_kpa = [pressao / 1e3 for pressao in pressoes]

        figura, eixo = plt.subplots()
        eixo.plot(xs, pressoes_kpa, "o-", color="#c0392b", label="P vs x1 (líquido)")
        eixo.plot(ys, pressoes_kpa, "s-", color="#2471a3", label="P vs y1 (vapor)")
        eixo.set_xlabel("x1, y1")
        eixo.set_ylabel("Pressão de bolha (kPa)")
        eixo.set_title(f"{self.NOME} — {self._composto1} / {self._composto2}")
        eixo.grid(True, alpha=0.3)
        eixo.legend()
        figura.tight_layout()
        plt.show()
        return xs, ys, pressoes


class Margules(ModeloAtividade):
    """Margules de dois parâmetros.

    ``ln γ1 = x2²[A12 + 2(A21 - A12)·x1]``
    ``ln γ2 = x1²[A21 + 2(A12 - A21)·x2]``
    """

    NOME = "Margules"

    def __init__(self):
        super().__init__()
        self._a12 = None
        self._a21 = None

    @property
    def a12(self):
        return self._a12

    @a12.setter
    def a12(self, valor):
        self._a12 = float(valor)

    @property
    def a21(self):
        return self._a21

    @a21.setter
    def a21(self, valor):
        self._a21 = float(valor)

    def _validar(self):
        super()._validar()
        if self._a12 is None or self._a21 is None:
            raise ErroTermodinamico("Informe os parâmetros A12 e A21.")

    def coeficientes_atividade(self, x1):
        x1 = float(x1)
        if not 0.0 <= x1 <= 1.0:
            raise ErroTermodinamico("A fração molar x1 deve estar entre 0 e 1.")
        x2 = 1.0 - x1
        a12, a21 = self._a12, self._a21
        ln_gama1 = x2 * x2 * (a12 + 2.0 * (a21 - a12) * x1)
        ln_gama2 = x1 * x1 * (a21 + 2.0 * (a12 - a21) * x2)
        return math.exp(ln_gama1), math.exp(ln_gama2)


class Wilson(ModeloAtividade):
    """Wilson (parâmetros Λ12 e Λ21).

    ``ln γ1 = -ln(x1 + Λ12·x2) + x2·[Λ12/(x1+Λ12·x2) - Λ21/(x2+Λ21·x1)]``
    """

    NOME = "Wilson"

    def __init__(self):
        super().__init__()
        self._lambda12 = None
        self._lambda21 = None

    @property
    def lambda12(self):
        return self._lambda12

    @lambda12.setter
    def lambda12(self, valor):
        self._lambda12 = float(valor)

    @property
    def lambda21(self):
        return self._lambda21

    @lambda21.setter
    def lambda21(self, valor):
        self._lambda21 = float(valor)

    def _validar(self):
        super()._validar()
        for nome, valor in (
            ("Λ12", self._lambda12),
            ("Λ21", self._lambda21),
        ):
            if valor is None or valor <= 0.0:
                raise ErroTermodinamico(f"{nome} precisa ser positivo.")

    def coeficientes_atividade(self, x1):
        x1 = float(x1)
        if not 0.0 <= x1 <= 1.0:
            raise ErroTermodinamico("A fração molar x1 deve estar entre 0 e 1.")
        x2 = 1.0 - x1
        l12, l21 = self._lambda12, self._lambda21
        d1 = x1 + l12 * x2
        d2 = x2 + l21 * x1
        diferenca = l12 / d1 - l21 / d2
        ln_gama1 = -math.log(d1) + x2 * diferenca
        ln_gama2 = -math.log(d2) - x1 * diferenca
        return math.exp(ln_gama1), math.exp(ln_gama2)


MODELOS = {"Margules": Margules, "Wilson": Wilson}
