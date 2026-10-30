# -*- coding: utf-8 -*-
"""Testes da interface gráfica (Tkinter).

São ignorados automaticamente quando não há display disponível.

Execução::

    python -m unittest discover -s testes -t . -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tkinter as tk

    import interface

    TK_DISPONIVEL = True
except Exception:  # pragma: no cover - ambiente sem Tkinter
    TK_DISPONIVEL = False


@unittest.skipUnless(TK_DISPONIVEL, "Tkinter indisponível")
class TestInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.app = interface.AplicacaoTermoPy()
            cls.app.update()
        except tk.TclError as exc:  # pragma: no cover - sem display
            raise unittest.SkipTest(f"sem display para o Tkinter: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def tearDown(self):
        # Cada teste começa do estado padrão: evita dependência de ordem.
        for aba in self.app.abas:
            aba.restaurar()
        self.app.update()

    # ------------------------------------------------------------ abas ---
    def test_cinco_abas(self):
        self.assertEqual(len(self.app.abas), 5)
        self.assertEqual(len(self.app.notebook.tabs()), 5)
        tipos = [type(aba).__name__ for aba in self.app.abas]
        self.assertEqual(
            tipos,
            [
                "AbaPressaoSaturacao",
                "AbaEquacaoDeEstado",
                "AbaEquipamentos",
                "AbaFugacidade",
                "AbaELV",
            ],
        )

    # ------------------------------------------------------ pressão sat. --
    def test_pressao_saturacao_antoine(self):
        aba = self.app.abas[0]
        aba.restaurar()
        aba._executar()
        texto = aba.caixa.get("1.0", "end")
        self.assertIn("101.3", texto)
        self.assertIn("kPa", texto)

    def test_pressao_saturacao_lee_kesler(self):
        aba = self.app.abas[0]
        aba.modelo.set("lee")
        aba._ao_trocar_modelo()
        aba.composto.set("benzeno")
        aba.temperatura.set("353.15")
        aba._executar()
        self.assertIn("kPa", aba.caixa.get("1.0", "end"))

    def test_unidade_muda_com_o_modelo(self):
        aba = self.app.abas[0]
        aba.restaurar()
        self.assertEqual(aba._rotulo_unidade.cget("text"), "°C")
        aba.modelo.set("lee")
        aba._ao_trocar_modelo()
        self.assertEqual(aba._rotulo_unidade.cget("text"), "K")
        aba.modelo.set("antoine")
        aba._ao_trocar_modelo()
        self.assertEqual(aba._rotulo_unidade.cget("text"), "°C")

    def test_troca_de_modelo_converte_a_temperatura(self):
        aba = self.app.abas[0]
        aba.restaurar()
        aba.temperatura.set("80")  # 80 °C
        aba.modelo.set("lee")
        self.assertAlmostEqual(353.15, float(aba.temperatura.get()), places=2)
        aba.modelo.set("antoine")
        self.assertAlmostEqual(80.0, float(aba.temperatura.get()), places=2)

    def test_lee_kesler_nao_zera_a_pressao_apos_digitar_celsius(self):
        # Regressão: a temperatura era lida como K e a pressão saía ~0 kPa.
        aba = self.app.abas[0]
        aba.restaurar()
        aba.temperatura.set("25")
        aba.modelo.set("lee")
        aba._executar()
        texto = aba.caixa.get("1.0", "end")
        self.assertIn("Lee-Kesler", texto)
        self.assertNotIn("0.0000 kPa", texto)
        self.assertIn("Tr =", texto)

    def test_lee_kesler_avisa_fora_da_faixa(self):
        aba = self.app.abas[0]
        aba.restaurar()
        aba.modelo.set("lee")
        aba.temperatura.set("80")  # 80 K é absurdamente baixo para a água
        aba._executar()
        texto = aba.caixa.get("1.0", "end")
        self.assertIn("fora da faixa recomendada", texto)
        self.assertIn("Faixa recomendada", texto)

    def test_lee_kesler_sem_dados_criticos_sugere_antoine(self):
        aba = self.app.abas[0]
        aba.restaurar()
        aba.modelo.set("lee")
        aba.composto.set("1,4-dioxano")
        aba._executar()
        self.assertIn("Selecione Antoine", aba.caixa.get("1.0", "end"))

    def test_aceita_virgula_como_decimal(self):
        aba = self.app.abas[0]
        aba.restaurar()
        aba.temperatura.set("100,0")
        aba._executar()
        self.assertIn("101.3", aba.caixa.get("1.0", "end"))

    # ---------------------------------------------------- equações EOS ---
    def test_equacao_pressao(self):
        aba = self.app.abas[1]
        aba.restaurar()
        aba._executar()
        texto = aba.caixa.get("1.0", "end")
        self.assertIn("Pa", texto)
        self.assertIn("Z =", texto)

    def test_equacao_volume(self):
        aba = self.app.abas[1]
        aba.restaurar()
        aba.tipo.set("volume")
        aba._ao_trocar_tipo()
        aba.composto.set("n-hexano")
        aba.temperatura.set("400")
        aba.pressao.set("50000")
        aba._executar()
        texto = aba.caixa.get("1.0", "end")
        self.assertIn("m³/mol", texto)
        self.assertIn("vapor", texto)  # abaixo de Psat

    def test_gas_ideal_desabilita_composto(self):
        aba = self.app.abas[1]
        aba.modelo.set("Gás Ideal")
        aba._ao_trocar_modelo()
        self.assertEqual(str(aba._combo_composto.cget("state")), "disabled")
        aba.modelo.set("Peng-Robinson")
        aba._ao_trocar_modelo()
        self.assertEqual(str(aba._combo_composto.cget("state")), "normal")

    # ----------------------------------------------------- equipamentos --
    def test_equipamentos(self):
        aba = self.app.abas[2]
        aba.restaurar()
        aba._executar()
        texto = aba.caixa.get("1.0", "end")
        self.assertIn("W = ΔH", texto)
        self.assertIn("J/mol", texto)
        self.assertIn("ΔS", texto)

    # ------------------------------------------------------- fugacidade --
    def test_fugacidade_pura(self):
        aba = self.app.abas[3]
        aba.restaurar()
        aba._executar()
        self.assertIn("φ =", aba.caixa.get("1.0", "end"))

    def test_fugacidade_mistura(self):
        aba = self.app.abas[3]
        aba.tipo.set("mistura")
        aba._ao_trocar_tipo()
        self.assertTrue(aba.quadro_mistura.grid_info())
        aba._executar()
        texto = aba.caixa.get("1.0", "end")
        self.assertIn("φ1", texto)
        self.assertIn("φ2", texto)

    def test_fracao_molar_invalida(self):
        aba = self.app.abas[3]
        aba.tipo.set("mistura")
        aba._ao_trocar_tipo()
        aba.fracao1.set("0.4")
        aba.fracao2.set("0.4")
        aba._executar()
        self.assertIn("somar 1", aba.app.status.get())

    # -------------------------------------------------------------- ELV --
    def test_elv_gera_grafico_e_tabela(self):
        aba = self.app.abas[4]
        aba.restaurar()
        # O canvas só tem tamanho real quando a aba está visível.
        self.app.notebook.select(aba)
        self.app.update()
        aba._executar()
        self.app.update()
        self.assertGreater(len(aba.tabela.get_children()), 5)
        self.assertGreater(len(aba.grafico.find_all()), 10)
        self.assertIsNotNone(aba.grafico._dados)

    def test_elv_rotulos_do_modelo(self):
        aba = self.app.abas[4]
        aba.modelo.set("Wilson")
        aba._ao_trocar_modelo()
        self.assertEqual(aba._rotulo_parametro1.cget("text"), "Λ12")
        aba.modelo.set("Margules")
        aba._ao_trocar_modelo()
        self.assertEqual(aba._rotulo_parametro1.cget("text"), "A12")

    def test_elv_legenda_do_azeotropo(self):
        aba = self.app.abas[4]
        aba.restaurar()
        aba._executar()
        self.assertIsNotNone(aba.grafico.azeotropo)
        self.assertIn("Azeótropo", aba.legenda.cget("text"))

    def test_elv_sem_azeotropo(self):
        aba = self.app.abas[4]
        aba.restaurar()
        aba.parametro1.set("0.3")
        aba.parametro2.set("0.3")
        aba._executar()
        self.assertIsNone(aba.grafico.azeotropo)
        self.assertIn("Sem azeótropo", aba.legenda.cget("text"))

    def test_elv_erro_aparece_no_canvas(self):
        aba = self.app.abas[4]
        aba.restaurar()
        aba.composto1.set("kriptonita")
        aba._executar()
        aba._executar()  # garante que repetir o erro não quebra a aba
        self.assertIsNotNone(aba.grafico._mensagem)
        self.assertEqual(len(aba.tabela.get_children()), 0)

    def test_elv_limpar_limpa_tabela_e_canvas(self):
        aba = self.app.abas[4]
        aba.restaurar()
        aba._executar()
        aba.restaurar()
        self.assertEqual(len(aba.tabela.get_children()), 0)
        self.assertIsNone(aba.grafico._dados)
        self.assertEqual(aba.legenda.cget("text"), "")

    # ----------------------------------------------------------- erros ---
    def test_entrada_invalida_nao_derruba_a_gui(self):
        aba = self.app.abas[0]
        aba.temperatura.set("abc")
        aba._executar()
        self.assertIn("inválido", aba.caixa.get("1.0", "end"))
        self.assertIn("inválido", aba.app.status.get())

    def test_composto_inexistente(self):
        aba = self.app.abas[0]
        aba.composto.set("kriptonita")
        aba._executar()
        self.assertIn("não encontrado", aba.caixa.get("1.0", "end"))

    def test_composto_sem_antoine(self):
        aba = self.app.abas[4]
        aba.composto1.set("propileno")
        aba._executar()
        self.assertIn("não possui", aba.app.status.get())

    def test_restaurar_limpa_resultado(self):
        aba = self.app.abas[0]
        aba._executar()
        aba.restaurar()
        self.assertEqual(aba.caixa.get("1.0", "end").strip(), "")


@unittest.skipUnless(TK_DISPONIVEL, "Tkinter indisponível")
class TestAzeotropo(unittest.TestCase):
    def test_azeotropo_no_interior(self):
        xs = [0.0, 0.25, 0.5, 0.75, 1.0]
        ys = [0.0, 0.4, 0.5, 0.6, 1.0]
        self.assertAlmostEqual(0.5, interface.GraficoPxy._azeotropo(xs, ys))

    def test_sem_azeotropo(self):
        xs = [0.0, 0.5, 1.0]
        ys = [0.0, 0.2, 1.0]
        self.assertIsNone(interface.GraficoPxy._azeotropo(xs, ys))

    def test_nao_confunde_extremos(self):
        # y1 = x1 nos extremos, mas as curvas não se cruzam no interior.
        xs = [0.0, 0.5, 1.0]
        ys = [0.0, 0.3, 1.0]
        self.assertIsNone(interface.GraficoPxy._azeotropo(xs, ys))


if __name__ == "__main__":
    unittest.main(verbosity=2)
