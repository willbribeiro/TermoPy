# -*- coding: utf-8 -*-
"""Pressão de saturação: correlação de Antoine e de Lee-Kesler."""
import math

import dados
from utilidades import DadoIndisponivel, ErroTermodinamico


class _ModeloSaturacao:
    """Comportamento comum: composto, temperatura e pressão calculada."""

    NOME = "Saturação"
    PROPRIEDADE = "antoine"

    def __init__(self):
        self._substancia = None
        self._temperatura = None
        self._pressao = None
        self.sim = False

    @property
    def substancia(self):
        return self._substancia

    @property
    def temperatura(self):
        return self._temperatura

    @temperatura.setter
    def temperatura(self, valor):
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            raise ErroTermodinamico(f"Temperatura inválida: {valor!r}.") from None
        if not math.isfinite(numero):
            raise ErroTermodinamico("Temperatura precisa ser finita.")
        self._temperatura = numero

    @property
    def pressao(self):
        """Pressão de saturação calculada (Pa)."""
        return self._pressao

    def _exigir_temperatura(self):
        if self._temperatura is None:
            raise ErroTermodinamico("Informe a temperatura antes do cálculo.")
        return self._temperatura

    def _exigir_substancia(self):
        if self._substancia is None:
            raise ErroTermodinamico(
                "Informe o composto (buscarAntoine/buscarLee) antes do cálculo."
            )
        return self._substancia

    def _carregar(self, composto, propriedade):
        substancia = dados.buscar(composto)
        if substancia is None:
            self._substancia = None
            self.sim = False
            return False
        if getattr(substancia, propriedade) is None:
            self._substancia = substancia
            self.sim = False
            return False
        self._substancia = substancia
        self.sim = True
        return True


class Antoine(_ModeloSaturacao):
    """``ln(P/kPa) = A - B/(T/°C + C)``."""

    NOME = "Antoine"
    PROPRIEDADE = "antoine"

    def __init__(self):
        super().__init__()
        self._coeficientes = None

    @property
    def coeficientes(self):
        if self._coeficientes is None:
            self._exigir_substancia()
        return self._coeficientes

    def buscarAntoine(self, composto):
        """Carrega A, B e C do composto. Retorna ``True`` se encontrado."""
        if not self._carregar(composto, "antoine"):
            self._coeficientes = None
            return False
        self._coeficientes = self._substancia.antoine
        return True

    def pressaoSat(self):
        """Pressão de saturação em Pa (a correlação é avaliada em kPa)."""
        a, b, c = self.coeficientes
        temperatura = self._exigir_temperatura()
        denominador = temperatura + c
        if denominador <= 0.0:
            raise ErroTermodinamico(
                "Temperatura fora do intervalo da correlação de Antoine "
                f"para {self._substancia.nome}."
            )
        pressao_kpa = math.exp(a - b / denominador)
        self._pressao = pressao_kpa * 1e3
        return self._pressao


class LeeKeslerSat(_ModeloSaturacao):
    """Correlação de Lee-Kesler (válida para ``Tr < 1``)."""

    NOME = "Lee-Kesler"
    PROPRIEDADE = "temperatura_critica"

    def buscarLee(self, composto):
        """Carrega Tc, Pc e ω do composto. Retorna ``True`` se encontrado."""
        if not self._carregar(composto, "temperatura_critica"):
            return False
        self.sim = self._substancia.tem_dados_criticos
        return self.sim

    def pressaoSat(self):
        """Pressão de saturação em Pa."""
        substancia = self._exigir_substancia()
        if not substancia.tem_dados_criticos:
            raise DadoIndisponivel(substancia.nome, "dados críticos")
        temperatura = self._exigir_temperatura()
        if temperatura <= 0.0:
            raise ErroTermodinamico("Temperatura deve ser positiva.")

        tr = temperatura / substancia.temperatura_critica
        ln_pr0 = (
            5.92714 - 6.09648 / tr - 1.28862 * math.log(tr) + 0.169347 * tr ** 6
        )
        ln_pr1 = (
            15.2518 - 15.6875 / tr - 13.4721 * math.log(tr) + 0.43577 * tr ** 6
        )
        pr = math.exp(ln_pr0 + substancia.fator_acentrico * ln_pr1)
        self._pressao = pr * substancia.pressao_critica
        return self._pressao
