# -*- coding: utf-8 -*-
"""Propriedades residuais e variações de entalpia/entropia em equipamentos.

O cálculo usa SRK para as propriedades residuais e a capacidade calorífica
de gás ideal tabelada (``Cp/R = A + B·T + C·T² + D·T⁻²``) para a parcela de
gás ideal. Para um compressor/turbina em regime permanente::

    ΔH = ∫Cp dT + (H_res,saída - H_res,entrada)
    ΔS = ∫(Cp/T) dT - R·ln(P2/P1) + (S_res,saída - S_res,entrada)
"""
import math
from dataclasses import dataclass

import EquacaoDeEstado
from dados import R
from utilidades import DadoIndisponivel, ErroTermodinamico


@dataclass(frozen=True)
class ResultadoResidual:
    """Resultado do cálculo para o equipamento."""

    delta_h: float  # J/mol
    delta_s: float  # J/(mol·K)
    trabalho: float  # J/mol (igual a ΔH em regime permanente)


def _integral_cp(cp, t1, t2):
    """∫Cp dT entre t1 e t2 (J/mol)."""
    a, b, c, d = cp
    return R * (
        a * (t2 - t1)
        + b * (t2 ** 2 - t1 ** 2) / 2.0
        + c * (t2 ** 3 - t1 ** 3) / 3.0
        - d * (1.0 / t2 - 1.0 / t1)
    )


def _integral_cp_sobre_t(cp, t1, t2):
    """∫(Cp/T) dT entre t1 e t2 (J/(mol·K))."""
    a, b, c, d = cp
    return R * (
        a * math.log(t2 / t1)
        + b * (t2 - t1)
        + c * (t2 ** 2 - t1 ** 2) / 2.0
        - d * (1.0 / t2 ** 2 - 1.0 / t1 ** 2) / 2.0
    )


class PropriedadesResiduais:
    """Variação de entalpia e entropia entre dois estados (SRK + Cp ideal)."""

    COMPRESSOR = 1
    TURBINA = 2
    EQUIPAMENTOS = {COMPRESSOR: "Compressor", TURBINA: "Turbina"}

    def __init__(self):
        self._composto = None
        self._equipamento = None
        self._pressao_inicial = None
        self._pressao_final = None
        self._temperatura_inicial = None
        self._temperatura_final = None

    # ------------------------------------------------------- entrada -----
    @property
    def composto(self):
        return self._composto

    @composto.setter
    def composto(self, valor):
        self._composto = valor

    @property
    def equipamento(self):
        return self._equipamento

    @equipamento.setter
    def equipamento(self, valor):
        if int(valor) not in self.EQUIPAMENTOS:
            raise ErroTermodinamico(
                f"Equipamento inválido: {valor}. Use 1 (compressor) ou 2 (turbina)."
            )
        self._equipamento = int(valor)

    @property
    def pressao_inicial(self):
        return self._pressao_inicial

    @pressao_inicial.setter
    def pressao_inicial(self, valor):
        self._pressao_inicial = float(valor)

    @property
    def pressao_final(self):
        return self._pressao_final

    @pressao_final.setter
    def pressao_final(self, valor):
        self._pressao_final = float(valor)

    @property
    def temperatura_inicial(self):
        return self._temperatura_inicial

    @temperatura_inicial.setter
    def temperatura_inicial(self, valor):
        self._temperatura_inicial = float(valor)

    @property
    def temperatura_final(self):
        return self._temperatura_final

    @temperatura_final.setter
    def temperatura_final(self, valor):
        self._temperatura_final = float(valor)

    # ------------------------------------------------------- interno -----
    def _modelo(self):
        modelo = EquacaoDeEstado.SRK()
        if not modelo.buscarPuras(self._composto):
            raise ErroTermodinamico(
                f"Sem dados críticos para o composto {self._composto!r}."
            )
        return modelo

    @staticmethod
    def _residuais(modelo, temperatura, pressao):
        """``(Z, H_res, S_res)`` no estado (T, P) usando SRK."""
        modelo.temperatura = temperatura
        modelo.pressao = pressao
        z = modelo.calcularFatorCompressibilidade()
        a_dim, b_dim = modelo.A, modelo.B
        a, b = modelo.a, modelo.b
        da_dt = modelo.derivada_a()

        if z <= b_dim:
            raise ErroTermodinamico(
                f"Estado inconsistente: Z ({z:.4f}) <= B ({b_dim:.4f})."
            )

        logaritmo = math.log((z + b_dim) / z)
        h_res = R * temperatura * (z - 1.0) + ((temperatura * da_dt - a) / b) * logaritmo
        s_res = R * math.log(z - b_dim) + (da_dt / b) * logaritmo
        return z, h_res, s_res

    def _cp_ideal(self):
        substancia = self._modelo().substancia
        if substancia.cp_ideal is None:
            raise DadoIndisponivel(substancia.nome, "cp_ideal")
        return substancia.cp_ideal

    # -------------------------------------------------------- cálculo ----
    def calcularResidual(self):
        """Retorna :class:`ResultadoResidual` para o equipamento configurado."""
        if self._equipamento is None:
            raise ErroTermodinamico("Informe o equipamento (1 ou 2).")
        for nome, valor in (
            ("pressão de entrada", self._pressao_inicial),
            ("pressão de saída", self._pressao_final),
            ("temperatura de entrada", self._temperatura_inicial),
            ("temperatura de saída", self._temperatura_final),
        ):
            if valor is None or valor <= 0.0:
                raise ErroTermodinamico(f"Informe uma {nome} positiva.")

        modelo = self._modelo()
        _, h_res_1, s_res_1 = self._residuais(
            modelo, self._temperatura_inicial, self._pressao_inicial
        )
        _, h_res_2, s_res_2 = self._residuais(
            modelo, self._temperatura_final, self._pressao_final
        )

        cp = self._cp_ideal()
        delta_h = (
            _integral_cp(cp, self._temperatura_inicial, self._temperatura_final)
            + h_res_2
            - h_res_1
        )
        delta_s = (
            _integral_cp_sobre_t(
                cp, self._temperatura_inicial, self._temperatura_final
            )
            - R * math.log(self._pressao_final / self._pressao_inicial)
            + s_res_2
            - s_res_1
        )
        return ResultadoResidual(delta_h=delta_h, delta_s=delta_s, trabalho=delta_h)

    def viola_primeira_lei(self, resultado):
        """Compressor deve receber trabalho (ΔH > 0); turbina deve fornecê-lo."""
        if self._equipamento == self.COMPRESSOR:
            return resultado.delta_h < 0.0
        return resultado.delta_h > 0.0
