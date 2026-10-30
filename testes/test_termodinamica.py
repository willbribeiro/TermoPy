# -*- coding: utf-8 -*-
"""Testes de regressão do TermoPy.

Execução (a partir da raiz do projeto)::

    python -m unittest discover -s testes -t . -v
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import CoeficienteDeFugacidade
import ELV
import EquacaoDeEstado
import PressaodeSaturacao
import PropriedadesResiduais
import dados
from utilidades import (
    ErroTermodinamico,
    raizes_cubicas,
    selecionar_raiz_fisica,
)


class TestRaizes(unittest.TestCase):
    def test_tres_raizes_reais(self):
        # (x-1)(x-2)(x-3) = x³ - 6x² + 11x - 6
        raizes = raizes_cubicas([1.0, -6.0, 11.0, -6.0])
        self.assertEqual(len(raizes), 3)
        for esperado, obtido in zip((1.0, 2.0, 3.0), raizes):
            self.assertAlmostEqual(esperado, obtido, places=9)

    def test_uma_raiz_real(self):
        raizes = raizes_cubicas([1.0, 0.0, 1.0, 1.0])
        self.assertEqual(len(raizes), 1)
        self.assertAlmostEqual(-0.6823278038280193, raizes[0], places=9)

    def test_raiz_dupla(self):
        # (x-2)²(x+1) = x³ - 3x² + 4
        raizes = raizes_cubicas([1.0, -3.0, 0.0, 4.0])
        self.assertEqual(len(raizes), 2)
        self.assertAlmostEqual(-1.0, raizes[0], places=9)
        self.assertAlmostEqual(2.0, raizes[1], places=9)

    def test_escala(self):
        # Mesmo polinômio multiplicado por 1e-12 (coeficientes minúsculos).
        raizes = raizes_cubicas([1e-12, -6e-12, 11e-12, -6e-12])
        self.assertEqual(len(raizes), 3)
        self.assertAlmostEqual(1.0, raizes[0], places=6)

    def test_selecao_vapor_e_liquido(self):
        raizes = [1e-5, 2e-5, 1e-3]
        self.assertEqual(selecionar_raiz_fisica(raizes, 1e4, 1e5), 1e-3)
        self.assertEqual(selecionar_raiz_fisica(raizes, 2e5, 1e5), 1e-5)

    def test_sem_raiz_positiva(self):
        with self.assertRaises(ErroTermodinamico):
            selecionar_raiz_fisica([-1.0, -2.0], 1.0, 1.0)


class TestDados(unittest.TestCase):
    def test_zc_pentano_corrigido(self):
        self.assertAlmostEqual(0.270, dados.buscar("n-pentano").fator_compressibilidade_critico)

    def test_apelidos_e_acentos(self):
        self.assertIs(dados.buscar("iso-butano"), dados.buscar("isobutano"))
        self.assertIs(dados.buscar("AGUA"), dados.buscar("água"))
        self.assertIs(
            dados.buscar("metilciclo-hexano"), dados.buscar("metilciclohexano")
        )
        self.assertIs(dados.buscar("butano"), dados.buscar("n-butano"))

    def test_composto_inexistente(self):
        self.assertIsNone(dados.buscar("kriptonita"))

    def test_todas_as_linhas_das_tabelas_sao_encontradas(self):
        for nome, *_ in dados._PURAS:
            with self.subTest(tabela="puras", composto=nome):
                substancia = dados.buscar(nome)
                self.assertIsNotNone(substancia)
                self.assertTrue(substancia.tem_dados_criticos)
        for nome, *_ in dados._ANTOINE:
            with self.subTest(tabela="antoine", composto=nome):
                self.assertIsNotNone(dados.buscar(nome).antoine)
        for nome, *_ in dados._CP_IDEAL:
            with self.subTest(tabela="cp", composto=nome):
                self.assertIsNotNone(dados.buscar(nome).cp_ideal)

    def test_antoine_e_cp_consolidados(self):
        agua = dados.buscar("água")
        self.assertIsNotNone(agua.antoine)
        self.assertIsNotNone(agua.cp_ideal)
        self.assertIsNotNone(agua.temperatura_critica)


class TestAntoine(unittest.TestCase):
    def test_agua_a_100_c(self):
        modelo = PressaodeSaturacao.Antoine()
        self.assertTrue(modelo.buscarAntoine("água"))
        modelo.temperatura = 100.0
        # Valor tabelado: ~101.325 kPa.
        self.assertAlmostEqual(101.35e3, modelo.pressaoSat(), delta=200.0)

    def test_composto_sem_antoine(self):
        modelo = PressaodeSaturacao.Antoine()
        self.assertFalse(modelo.buscarAntoine("propileno"))

    def test_temperatura_extrema(self):
        modelo = PressaodeSaturacao.Antoine()
        modelo.buscarAntoine("água")
        modelo.temperatura = -500.0
        with self.assertRaises(ErroTermodinamico):
            modelo.pressaoSat()


class TestLeeKesler(unittest.TestCase):
    def test_proximo_de_antoine(self):
        # Benzeno: composto apolar, onde a correlação de Lee-Kesler é precisa.
        lee = PressaodeSaturacao.LeeKeslerSat()
        self.assertTrue(lee.buscarLee("benzeno"))
        lee.temperatura = 353.15  # 80 °C
        antoine = PressaodeSaturacao.Antoine()
        antoine.buscarAntoine("benzeno")
        antoine.temperatura = 80.0
        self.assertAlmostEqual(
            antoine.pressaoSat(), lee.pressaoSat(), delta=0.05 * antoine.pressaoSat()
        )


class TestEquacoesDeEstado(unittest.TestCase):
    def _modelo(self, classe, composto="metano"):
        modelo = classe()
        self.assertTrue(modelo.buscarPuras(composto))
        return modelo

    def test_classe_abstrata_nao_instanciavel(self):
        with self.assertRaises(TypeError):
            EquacaoDeEstado.EquacaoDeEstado()

    def test_gas_ideal(self):
        modelo = self._modelo(EquacaoDeEstado.GasIdeal)
        modelo.temperatura = 300.0
        modelo.volume_molar = 0.0249
        self.assertAlmostEqual(8.314 * 300.0 / 0.0249, modelo.calcularPressao(), places=6)

    def test_ida_e_volta_pressao_volume(self):
        for classe in (
            EquacaoDeEstado.VDW,
            EquacaoDeEstado.RK,
            EquacaoDeEstado.SRK,
            EquacaoDeEstado.PR,
            EquacaoDeEstado.Virial,
        ):
            with self.subTest(modelo=classe.NOME):
                modelo = self._modelo(classe)
                modelo.temperatura = 300.0
                modelo.pressao = 1.0e5
                volume = modelo.calcularVolumeMolar()
                self.assertGreater(volume, 0.0)

                modelo.volume_molar = volume
                pressao = modelo.calcularPressao()
                self.assertAlmostEqual(1.0e5, pressao, delta=1.0)

    def test_z_proximo_de_um_para_gas(self):
        modelo = self._modelo(EquacaoDeEstado.SRK)
        modelo.temperatura = 300.0
        modelo.pressao = 1.0e5
        self.assertAlmostEqual(1.0, modelo.calcularFatorCompressibilidade(), delta=0.02)

    def test_srk_liquido_e_vapor(self):
        modelo = self._modelo(EquacaoDeEstado.SRK, "n-hexano")
        modelo.temperatura = 400.0  # abaixo de Tc = 507.6 K
        modelo.pressao = 0.5e5  # abaixo de Psat
        modelo.calcularVolumeMolar()
        volume_vapor = modelo.volume_molar

        modelo.pressao = 50.0e5  # acima de Psat
        modelo.calcularVolumeMolar()
        volume_liquido = modelo.volume_molar

        self.assertLess(volume_liquido, volume_vapor)

    def test_parametro_atrativo_pr_consistente(self):
        """O PR usava alfa errado no cálculo de volume (kappa somado)."""
        modelo = self._modelo(EquacaoDeEstado.PR)
        modelo.temperatura = 400.0
        modelo.pressao = 20.0e5
        volume = modelo.calcularVolumeMolar()
        a = modelo.a
        modelo.volume_molar = volume
        modelo.calcularPressao()
        # Recalcula a com a mesma temperatura: precisa ser idêntico.
        self.assertAlmostEqual(a, modelo.a, delta=abs(a) * 1e-12)

    def test_composto_sem_dados_criticos(self):
        modelo = EquacaoDeEstado.SRK()
        self.assertFalse(modelo.buscarPuras("kriptonita"))

    def test_derivada_do_parametro_atrativo(self):
        modelo = self._modelo(EquacaoDeEstado.SRK)
        modelo.temperatura = 300.0
        modelo._parametros()
        derivada = modelo.derivada_a()

        passo = 1e-3
        outro = self._modelo(EquacaoDeEstado.SRK)
        outro.temperatura = 300.0 + passo
        outro._parametros()
        numerica = (outro.a - modelo.a) / passo

        self.assertAlmostEqual(numerica, derivada, delta=abs(numerica) * 1e-5)

    def test_estado_incompleto(self):
        modelo = self._modelo(EquacaoDeEstado.SRK)
        with self.assertRaises(ErroTermodinamico):
            modelo.calcularVolumeMolar()  # sem temperatura nem pressão


class TestFugacidade(unittest.TestCase):
    def test_pura_menor_que_um(self):
        modelo = CoeficienteDeFugacidade.CoefFugacidadePuras()
        modelo.composto = "metano"
        modelo.temperatura = 300.0
        modelo.pressao = 30.0e5
        phi = modelo.calcularFugacidade()
        self.assertGreater(phi, 0.0)
        self.assertLess(phi, 1.0)

    def test_pura_sem_dados(self):
        modelo = CoeficienteDeFugacidade.CoefFugacidadePuras()
        modelo.composto = "kriptonita"
        modelo.temperatura = 300.0
        modelo.pressao = 1e5
        with self.assertRaises(ErroTermodinamico):
            modelo.calcularFugacidade()

    def test_mistura(self):
        modelo = CoeficienteDeFugacidade.CoefFugacidadeMisturas()
        modelo.composto1 = "metano"
        modelo.composto2 = "etano"
        modelo.temperatura = 300.0
        modelo.pressao = 20.0e5
        modelo.fracao_molar1 = 0.4
        modelo.fracao_molar2 = 0.6
        phi1, phi2 = modelo.calcularFugacidade()
        self.assertGreater(phi1, 0.0)
        self.assertGreater(phi2, 0.0)

    def test_mistura_fracao_invalida(self):
        modelo = CoeficienteDeFugacidade.CoefFugacidadeMisturas()
        modelo.composto1 = "metano"
        modelo.composto2 = "etano"
        modelo.temperatura = 300.0
        modelo.pressao = 20.0e5
        modelo.fracao_molar1 = 0.4
        modelo.fracao_molar2 = 0.4
        with self.assertRaises(ErroTermodinamico):
            modelo.calcularFugacidade()


class TestPropriedadesResiduais(unittest.TestCase):
    def _modelo(self, temperatura_final=600.0):
        modelo = PropriedadesResiduais.PropriedadesResiduais()
        modelo.composto = "metano"
        modelo.equipamento = modelo.COMPRESSOR
        modelo.pressao_inicial = 1.0e5
        modelo.pressao_final = 5.0e5
        modelo.temperatura_inicial = 300.0
        modelo.temperatura_final = temperatura_final
        return modelo

    def test_entalpia_positiva_para_compressor(self):
        resultado = self._modelo().calcularResidual()
        self.assertGreater(resultado.delta_h, 0.0)
        self.assertEqual(resultado.trabalho, resultado.delta_h)

    def test_entropia_de_processo_irreversivel(self):
        resultado = self._modelo(temperatura_final=600.0).calcularResidual()
        self.assertGreater(resultado.delta_s, 0.0)

    def test_compressao_com_pouco_aquecimento_e_impossivel(self):
        # Com T subindo apenas de 300 K para 400 K e P de 1 bar para 5 bar,
        # a entropia cai: o processo adiabático é impossível.
        resultado = self._modelo(temperatura_final=400.0).calcularResidual()
        self.assertLess(resultado.delta_s, 0.0)

    def test_primeira_lei(self):
        modelo = self._modelo()
        resultado = modelo.calcularResidual()
        self.assertFalse(modelo.viola_primeira_lei(resultado))

        modelo.equipamento = modelo.TURBINA
        self.assertTrue(modelo.viola_primeira_lei(resultado))

    def test_integral_cp(self):
        cp = dados.buscar("água").cp_ideal
        # Integral numérica de referência (regra de Simpson).
        n = 2000
        t1, t2 = 300.0, 600.0
        passo = (t2 - t1) / n
        soma = 0.0
        for i in range(n + 1):
            t = t1 + i * passo
            valor = dados.R * (
                cp[0] + cp[1] * t + cp[2] * t ** 2 + cp[3] / t ** 2
            )
            peso = 1 if i in (0, n) else (4 if i % 2 else 2)
            soma += peso * valor
        numerica = soma * passo / 3.0
        self.assertAlmostEqual(
            numerica,
            PropriedadesResiduais._integral_cp(cp, t1, t2),
            delta=abs(numerica) * 1e-6,
        )

    def test_equipamento_invalido(self):
        with self.assertRaises(ErroTermodinamico):
            self._modelo().equipamento = 7


class TestELV(unittest.TestCase):
    def _margules(self, a12, a21):
        modelo = ELV.Margules()
        modelo.composto1 = "benzeno"
        modelo.composto2 = "tolueno"
        modelo.temperatura = 80.0
        modelo.variacao = 0.1
        modelo.a12 = a12
        modelo.a21 = a21
        return modelo

    def test_gama_nos_extremos(self):
        modelo = self._margules(1.2, 1.5)
        gama1, gama2 = modelo.coeficientes_atividade(1.0)
        self.assertAlmostEqual(1.0, gama1)
        self.assertAlmostEqual(math.exp(1.5), gama2)

        gama1, gama2 = modelo.coeficientes_atividade(0.0)
        self.assertAlmostEqual(math.exp(1.2), gama1)
        self.assertAlmostEqual(1.0, gama2)

    def test_pressao_nos_extremos(self):
        modelo = self._margules(0.0, 0.0)  # solução ideal
        xs, ys, pressoes = modelo.calcular()
        self.assertEqual(len(xs), len(ys))
        self.assertEqual(len(xs), 11)
        self.assertAlmostEqual(0.0, xs[0])
        self.assertAlmostEqual(1.0, xs[-1])
        self.assertAlmostEqual(xs[-1], ys[-1], places=9)
        self.assertTrue(all(p > 0 for p in pressoes))

    def test_wilson_simetria(self):
        modelo = ELV.Wilson()
        modelo.composto1 = "benzeno"
        modelo.composto2 = "tolueno"
        modelo.temperatura = 80.0
        modelo.variacao = 0.05
        modelo.lambda12 = 0.5
        modelo.lambda21 = 0.7
        xs, ys, pressoes = modelo.calcular()
        self.assertAlmostEqual(1.0, xs[-1])
        self.assertEqual(len(xs), 21)
        self.assertTrue(all(0.0 <= y <= 1.0 for y in ys))

    def test_variacao_invalida(self):
        modelo = self._margules(1.0, 1.0)
        with self.assertRaises(ErroTermodinamico):
            modelo.variacao = 0.0

    def test_composto_sem_antoine(self):
        modelo = self._margules(1.0, 1.0)
        modelo.composto1 = "propileno"
        with self.assertRaises(ErroTermodinamico):
            modelo.calcular()


if __name__ == "__main__":
    unittest.main(verbosity=2)
