# -*- coding: utf-8 -*-
"""Equações de estado para cálculo de pressão e volume molar.

Cada modelo deriva de :class:`EquacaoDeEstado`, que concentra:

* armazenamento/validação das variáveis de estado (unidades do SI);
* busca das propriedades críticas em :mod:`dados`;
* resolução do polinômio cúbico em volume molar e escolha da raiz física.

As unidades são sempre ``P`` em Pa, ``T`` em K e ``v`` em m³/mol.
"""
import math
from abc import ABC, abstractmethod

import PressaodeSaturacao
import dados
from dados import R
from utilidades import (
    DadoIndisponivel,
    ErroTermodinamico,
    raizes_cubicas,
    selecionar_raiz_fisica,
)


def _positivo(valor, nome):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroTermodinamico(f"{nome} inválida: {valor!r}.") from None
    if not math.isfinite(numero) or numero <= 0.0:
        raise ErroTermodinamico(f"{nome} deve ser positiva (recebido {numero}).")
    return numero


class EquacaoDeEstado(ABC):
    """Base para as equações de estado."""

    NOME = "Equação de Estado"
    #: Indica se o modelo precisa de Tc/Pc/ω do composto.
    EXIGE_DADOS_CRITICOS = True

    def __init__(self):
        self._temperatura = None
        self._pressao = None
        self._volume_molar = None
        self._substancia = None
        self._raizes_volume = []
        #: Parâmetros atrativo/repercussivo da equação (quando aplicável).
        self.a = None
        self.b = None
        self.sim = False

    # ---------------------------------------------------------- estado ----
    @property
    def temperatura(self):
        """Temperatura em K."""
        return self._temperatura

    @temperatura.setter
    def temperatura(self, valor):
        self._temperatura = _positivo(valor, "Temperatura")

    @property
    def pressao(self):
        """Pressão em Pa."""
        return self._pressao

    @pressao.setter
    def pressao(self, valor):
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            raise ErroTermodinamico(f"Pressão inválida: {valor!r}.") from None
        if not math.isfinite(numero):
            raise ErroTermodinamico("Pressão precisa ser finita.")
        self._pressao = numero

    @property
    def volume_molar(self):
        """Volume molar em m³/mol."""
        return self._volume_molar

    @volume_molar.setter
    def volume_molar(self, valor):
        self._volume_molar = _positivo(valor, "Volume molar")

    # ------------------------------------------------------ composição ----
    @property
    def substancia(self):
        return self._substancia

    @property
    def nome_composto(self):
        return None if self._substancia is None else self._substancia.nome

    def buscarPuras(self, composto):
        """Carrega as propriedades críticas do composto.

        Retorna ``True`` em caso de sucesso (equivalente ao antigo ``getSim``).
        """
        substancia = dados.buscar(composto)
        if substancia is None or (
            self.EXIGE_DADOS_CRITICOS and not substancia.tem_dados_criticos
        ):
            self._substancia = None
            self.sim = False
            return False
        self._substancia = substancia
        self.sim = True
        return True

    def _exigir_substancia(self, propriedade):
        if self._substancia is None:
            raise ErroTermodinamico(
                "Informe o composto (buscarPuras) antes do cálculo."
            )
        valor = getattr(self._substancia, propriedade)
        if valor is None:
            raise DadoIndisponivel(self._substancia.nome, propriedade)
        return valor

    @property
    def temperatura_critica(self):
        """Temperatura crítica em K."""
        return self._exigir_substancia("temperatura_critica")

    @property
    def pressao_critica(self):
        """Pressão crítica em Pa."""
        return self._exigir_substancia("pressao_critica")

    @property
    def fator_acentrico(self):
        return self._exigir_substancia("fator_acentrico")

    @property
    def fator_compressibilidade_critico(self):
        return self._exigir_substancia("fator_compressibilidade_critico")

    @property
    def volume_molar_critico(self):
        """Volume molar crítico em m³/mol."""
        return self._exigir_substancia("volume_molar_critico")

    # -------------------------------------------------------- cálculo -----
    @abstractmethod
    def calcularPressao(self):
        """Calcula e retorna a pressão (Pa) a partir de T e v."""

    @abstractmethod
    def calcularVolumeMolar(self):
        """Calcula e retorna o volume molar (m³/mol) a partir de T e P."""

    @property
    def raizes_volume(self):
        """Raízes positivas obtidas no último cálculo de volume molar."""
        return tuple(self._raizes_volume)

    def calcularFatorCompressibilidade(self):
        """Calcula o volume molar e retorna ``Z = Pv/(RT)``."""
        self.calcularVolumeMolar()
        return self.fator_compressibilidade()

    def fator_compressibilidade(self):
        """``Z`` do estado atual (``None`` se faltar alguma variável)."""
        if None in (self.pressao, self.volume_molar, self.temperatura):
            return None
        return self.pressao * self.volume_molar / (R * self.temperatura)

    # ------------------------------------------------------ utilitários ---
    def _exigir_temperatura(self):
        if self._temperatura is None:
            raise ErroTermodinamico("Informe a temperatura antes do cálculo.")
        return self._temperatura

    def _exigir_volume(self):
        if self._volume_molar is None:
            raise ErroTermodinamico("Informe o volume molar antes do cálculo.")
        return self._volume_molar

    def _exigir_pressao(self):
        if self._pressao is None:
            raise ErroTermodinamico("Informe a pressão antes do cálculo.")
        return self._pressao

    def _pressao_saturacao(self):
        """Psat via Lee-Kesler (usada só para escolher entre líquido e vapor)."""
        if self.temperatura >= self.temperatura_critica:
            return math.inf
        modelo = PressaodeSaturacao.LeeKeslerSat()
        if not modelo.buscarLee(self.nome_composto):
            return math.inf
        modelo.temperatura = self.temperatura
        return modelo.pressaoSat()

    def _resolver_volume(self, coeficientes):
        """Resolve ``a*v^3 + b*v^2 + c*v + d = 0`` e guarda a raiz física."""
        self._exigir_pressao()
        volumes = [v for v in raizes_cubicas(coeficientes) if v > 0.0]
        if not volumes:
            raise ErroTermodinamico(
                f"{self.NOME}: nenhuma raiz de volume positivo para "
                f"T = {self.temperatura:.2f} K e P = {self.pressao:.1f} Pa."
            )
        self._raizes_volume = volumes
        volume = selecionar_raiz_fisica(
            volumes, self.pressao, self._pressao_saturacao()
        )
        self.volume_molar = volume
        return volume


class GasIdeal(EquacaoDeEstado):
    """``P v = R T``."""

    NOME = "Gás Ideal"
    EXIGE_DADOS_CRITICOS = False

    def calcularPressao(self):
        temperatura = self._exigir_temperatura()
        self.pressao = R * temperatura / self._exigir_volume()
        return self.pressao

    def calcularVolumeMolar(self):
        temperatura = self._exigir_temperatura()
        pressao = self._exigir_pressao()
        self._raizes_volume = [R * temperatura / pressao]
        self.volume_molar = self._raizes_volume[0]
        return self.volume_molar


class Virial(EquacaoDeEstado):
    """Segundo coeficiente do virial (correlação de Abbott)."""

    NOME = "2º Coeficiente do Virial"

    def _segundo_coeficiente(self):
        """Coeficiente ``B`` em m³/mol."""
        tr = self.temperatura / self.temperatura_critica
        b0 = 0.083 - 0.422 / tr ** 1.6
        b1 = 0.139 - 0.172 / tr ** 4.2
        return (
            (b0 + self.fator_acentrico * b1)
            * R
            * self.temperatura_critica
            / self.pressao_critica
        )

    def calcularPressao(self):
        temperatura = self._exigir_temperatura()
        b = self._segundo_coeficiente()
        volume = self._exigir_volume()
        if volume <= b:
            raise ErroTermodinamico(
                "O volume molar precisa ser maior que o coeficiente B do virial."
            )
        self.pressao = R * temperatura / (volume - b)
        return self.pressao

    def calcularVolumeMolar(self):
        temperatura = self._exigir_temperatura()
        pressao = self._exigir_pressao()
        self._raizes_volume = [
            R * temperatura / pressao + self._segundo_coeficiente()
        ]
        self.volume_molar = self._raizes_volume[0]
        return self.volume_molar


class VDW(EquacaoDeEstado):
    """van der Waals: ``P = RT/(v-b) - a/v²``."""

    NOME = "van der Waals"

    def _parametros(self):
        tc, pc = self.temperatura_critica, self.pressao_critica
        self.a = 27.0 * R * R * tc * tc / (64.0 * pc)
        self.b = R * tc / (8.0 * pc)
        return self.a, self.b

    def calcularPressao(self):
        a, b = self._parametros()
        temperatura = self._exigir_temperatura()
        volume = self._exigir_volume()
        if volume <= b:
            raise ErroTermodinamico("O volume molar precisa ser maior que b.")
        self.pressao = R * temperatura / (volume - b) - a / volume ** 2
        return self.pressao

    def calcularVolumeMolar(self):
        a, b = self._parametros()
        pressao, temperatura = self._exigir_pressao(), self._exigir_temperatura()
        # P v³ - (Pb + RT) v² + a v - ab = 0
        return self._resolver_volume(
            [pressao, -(pressao * b + R * temperatura), a, -a * b]
        )


class RK(EquacaoDeEstado):
    """Redlich-Kwong: ``P = RT/(v-b) - a/(v(v+b)√T)``."""

    NOME = "Redlich-Kwong"

    def _parametros(self):
        tc, pc = self.temperatura_critica, self.pressao_critica
        self.a = 0.42748 * R * R * tc ** 2.5 / pc
        self.b = 0.08664 * R * tc / pc
        return self.a, self.b

    def _a_sobre_raiz_t(self):
        return self.a / math.sqrt(self.temperatura)

    def calcularPressao(self):
        a, b = self._parametros()
        temperatura = self._exigir_temperatura()
        volume = self._exigir_volume()
        if volume <= b:
            raise ErroTermodinamico("O volume molar precisa ser maior que b.")
        self.pressao = R * temperatura / (volume - b) - self._a_sobre_raiz_t() / (
            volume * (volume + b)
        )
        return self.pressao

    def calcularVolumeMolar(self):
        a, b = self._parametros()
        pressao, temperatura = self._exigir_pressao(), self._exigir_temperatura()
        a_raiz = a / math.sqrt(temperatura)
        # P v³ - RT v² + (a/√T - RTb - Pb²) v - ab/√T = 0
        return self._resolver_volume(
            [
                pressao,
                -R * temperatura,
                a_raiz - R * temperatura * b - b * b * pressao,
                -a_raiz * b,
            ]
        )


class SRK(EquacaoDeEstado):
    """Soave-Redlich-Kwong.

    Além do cálculo de P e v, expõe ``a``, ``b``, os coeficientes
    adimensionalizados ``A``/``B`` e ``dA/dT`` — usados no coeficiente de
    fugacidade e nas propriedades residuais.
    """

    NOME = "Soave-Redlich-Kwong"
    CONSTANTE_A = 0.42748
    CONSTANTE_B = 0.08664

    def _kappa(self):
        omega = self.fator_acentrico
        return 0.480 + 1.574 * omega - 0.176 * omega * omega

    def _alfa(self):
        tr = self._exigir_temperatura() / self.temperatura_critica
        return (1.0 + self._kappa() * (1.0 - math.sqrt(tr))) ** 2

    def _parametros(self):
        tc, pc = self.temperatura_critica, self.pressao_critica
        self.a = self.CONSTANTE_A * R * R * tc * tc * self._alfa() / pc
        self.b = self.CONSTANTE_B * R * tc / pc
        return self.a, self.b

    @property
    def A(self):
        """Coeficiente adimensional ``aP/(RT)²``."""
        self._parametros()
        return self.a * self.pressao / (R * self.temperatura) ** 2

    @property
    def B(self):
        """Coeficiente adimensional ``bP/(RT)``."""
        self._parametros()
        return self.b * self.pressao / (R * self.temperatura)

    def derivada_a(self):
        """``dA/dT`` do parâmetro atrativo (J·m³/(mol²·K))."""
        tc, pc = self.temperatura_critica, self.pressao_critica
        kappa = self._kappa()
        raiz_tr = math.sqrt(self.temperatura / tc)
        a_critico = self.CONSTANTE_A * R * R * tc * tc / pc
        return (
            -a_critico
            * kappa
            * (1.0 + kappa * (1.0 - raiz_tr))
            / math.sqrt(self.temperatura * tc)
        )

    def calcularPressao(self):
        a, b = self._parametros()
        temperatura = self._exigir_temperatura()
        volume = self._exigir_volume()
        if volume <= b:
            raise ErroTermodinamico("O volume molar precisa ser maior que b.")
        self.pressao = R * temperatura / (volume - b) - a / (
            volume * (volume + b)
        )
        return self.pressao

    def calcularVolumeMolar(self):
        a, b = self._parametros()
        pressao, temperatura = self._exigir_pressao(), self._exigir_temperatura()
        # P v³ - RT v² + (a - RTb - Pb²) v - ab = 0
        return self._resolver_volume(
            [
                pressao,
                -R * temperatura,
                a - R * temperatura * b - b * b * pressao,
                -a * b,
            ]
        )


class PR(EquacaoDeEstado):
    """Peng-Robinson: ``P = RT/(v-b) - a/(v²+2bv-b²)``."""

    NOME = "Peng-Robinson"
    CONSTANTE_A = 0.45724
    CONSTANTE_B = 0.07780

    def _kappa(self):
        omega = self.fator_acentrico
        return 0.37464 + 1.54226 * omega - 0.26992 * omega * omega

    def _alfa(self):
        tr = self._exigir_temperatura() / self.temperatura_critica
        return (1.0 + self._kappa() * (1.0 - math.sqrt(tr))) ** 2

    def _parametros(self):
        tc, pc = self.temperatura_critica, self.pressao_critica
        self.a = self.CONSTANTE_A * R * R * tc * tc * self._alfa() / pc
        self.b = self.CONSTANTE_B * R * tc / pc
        return self.a, self.b

    def calcularPressao(self):
        a, b = self._parametros()
        temperatura = self._exigir_temperatura()
        volume = self._exigir_volume()
        if volume <= b:
            raise ErroTermodinamico("O volume molar precisa ser maior que b.")
        denominador = volume * volume + 2.0 * b * volume - b * b
        self.pressao = R * temperatura / (volume - b) - a / denominador
        return self.pressao

    def calcularVolumeMolar(self):
        a, b = self._parametros()
        pressao, temperatura = self._exigir_pressao(), self._exigir_temperatura()
        # P v³ + (Pb - RT) v² + (a - 3Pb² - 2RTb) v + (Pb³ + RTb² - ab) = 0
        return self._resolver_volume(
            [
                -pressao,
                R * temperatura - pressao * b,
                2.0 * R * temperatura * b - a + 3.0 * b * b * pressao,
                -pressao * b ** 3 - R * temperatura * b * b + a * b,
            ]
        )


#: Modelos disponíveis, na ordem em que aparecem no menu.
MODELOS = {
    "GasIdeal": GasIdeal,
    "Virial": Virial,
    "VDW": VDW,
    "RK": RK,
    "SRK": SRK,
    "PR": PR,
}
