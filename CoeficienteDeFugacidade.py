# -*- coding: utf-8 -*-
"""Coeficientes de fugacidade (espécie pura e mistura binária).

* Pura: equação de estado SRK — ``ln φ = Z - 1 - ln(Z - B) - (A/B)·ln((Z+B)/Z)``.
* Mistura: segundo coeficiente do virial com regra de mistura
  ``B = ΣΣ y_i y_j B_ij`` (correlação de Abbott para os termos puros).
"""
import math

import EquacaoDeEstado
import dados
from dados import R
from utilidades import ErroTermodinamico


class CoefFugacidadePuras:
    """Coeficiente de fugacidade de uma espécie pura via SRK."""

    def __init__(self):
        self._composto = None
        self._temperatura = None
        self._pressao = None
        self._coeficiente = None

    @property
    def composto(self):
        return self._composto

    @composto.setter
    def composto(self, valor):
        self._composto = valor

    @property
    def temperatura(self):
        """Temperatura em K."""
        return self._temperatura

    @temperatura.setter
    def temperatura(self, valor):
        self._temperatura = float(valor)

    @property
    def pressao(self):
        """Pressão em Pa."""
        return self._pressao

    @pressao.setter
    def pressao(self, valor):
        self._pressao = float(valor)

    @property
    def coeficiente(self):
        """Resultado do último cálculo (``None`` antes de calcular)."""
        return self._coeficiente

    def calcularFugacidade(self):
        """Calcula e retorna o coeficiente de fugacidade (adimensional)."""
        modelo = EquacaoDeEstado.SRK()
        if not modelo.buscarPuras(self._composto):
            raise ErroTermodinamico(
                f"Sem dados críticos para o composto {self._composto!r}."
            )
        modelo.temperatura = self._temperatura
        modelo.pressao = self._pressao

        z = modelo.calcularFatorCompressibilidade()
        a_dim = modelo.A
        b_dim = modelo.B

        if z <= b_dim:
            raise ErroTermodinamico(
                f"Z ({z:.4f}) precisa ser maior que B ({b_dim:.4f})."
            )
        if b_dim <= 0.0:
            raise ErroTermodinamico("Coeficiente B precisa ser positivo.")

        ln_phi = (
            z
            - 1.0
            - math.log(z - b_dim)
            - (a_dim / b_dim) * math.log((z + b_dim) / z)
        )
        self._coeficiente = math.exp(ln_phi)
        return self._coeficiente


class CoefFugacidadeMisturas:
    """Coeficientes de fugacidade de uma mistura binária (virial)."""

    TOLERANCIA_SOMA = 1e-6

    def __init__(self):
        self._composto1 = None
        self._composto2 = None
        self._temperatura = None
        self._pressao = None
        self._fracao_molar1 = None
        self._fracao_molar2 = None
        self._coeficientes = None

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
        return self._temperatura

    @temperatura.setter
    def temperatura(self, valor):
        self._temperatura = float(valor)

    @property
    def pressao(self):
        return self._pressao

    @pressao.setter
    def pressao(self, valor):
        self._pressao = float(valor)

    @property
    def fracao_molar1(self):
        return self._fracao_molar1

    @fracao_molar1.setter
    def fracao_molar1(self, valor):
        self._fracao_molar1 = float(valor)

    @property
    def fracao_molar2(self):
        return self._fracao_molar2

    @fracao_molar2.setter
    def fracao_molar2(self, valor):
        self._fracao_molar2 = float(valor)

    @property
    def coeficientes(self):
        return self._coeficientes

    # -------------------------------------------------------- cálculo ----
    def _validar(self):
        if self._composto1 is None or self._composto2 is None:
            raise ErroTermodinamico("Informe os dois compostos da mistura.")
        if self._fracao_molar1 is None or self._fracao_molar2 is None:
            raise ErroTermodinamico("Informe as frações molares dos dois compostos.")
        if self._fracao_molar1 < 0.0 or self._fracao_molar2 < 0.0:
            raise ErroTermodinamico("As frações molares não podem ser negativas.")
        soma = self._fracao_molar1 + self._fracao_molar2
        if abs(soma - 1.0) > self.TOLERANCIA_SOMA:
            raise ErroTermodinamico(
                f"As frações molares devem somar 1 (soma atual: {soma:.6f})."
            )

    def _segundo_coeficiente(self, substancia):
        tr = self._temperatura / substancia.temperatura_critica
        b0 = 0.083 - 0.422 / tr ** 1.6
        b1 = 0.139 - 0.172 / tr ** 4.2
        return (
            (b0 + substancia.fator_acentrico * b1)
            * R
            * substancia.temperatura_critica
            / substancia.pressao_critica
        )

    def calcularFugacidade(self):
        """Retorna ``(φ1, φ2)``."""
        self._validar()
        s1 = dados.exigir(self._composto1)
        s2 = dados.exigir(self._composto2)
        for substancia in (s1, s2):
            if not substancia.tem_dados_criticos:
                raise ErroTermodinamico(
                    f"Sem dados críticos para o composto {substancia.nome!r}."
                )

        b11 = self._segundo_coeficiente(s1)
        b22 = self._segundo_coeficiente(s2)

        # Pseudo-propriedades da mistura (regras de mistura do virial).
        omega12 = (s1.fator_acentrico + s2.fator_acentrico) / 2.0
        tc12 = math.sqrt(s1.temperatura_critica * s2.temperatura_critica)
        zc12 = (
            s1.fator_compressibilidade_critico + s2.fator_compressibilidade_critico
        ) / 2.0
        vc12 = (
            (s1.volume_molar_critico ** (1.0 / 3.0)
             + s2.volume_molar_critico ** (1.0 / 3.0))
            / 2.0
        ) ** 3
        pc12 = zc12 * R * tc12 / vc12
        tr12 = self._temperatura / tc12
        b012 = 0.083 - 0.422 / tr12 ** 1.6
        b112 = 0.139 - 0.172 / tr12 ** 4.2
        b12 = (R * tc12 / pc12) * (b012 + omega12 * b112)

        delta = 2.0 * b12 - b11 - b22
        fator = self._pressao / (R * self._temperatura)

        phi1 = math.exp(
            fator * (b11 + self._fracao_molar2 ** 2 * delta)
        )
        phi2 = math.exp(
            fator * (b22 + self._fracao_molar1 ** 2 * delta)
        )
        self._coeficientes = (phi1, phi2)
        return self._coeficientes
