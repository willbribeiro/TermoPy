# -*- coding: utf-8 -*-
"""TermoPy — interface de linha de comando.

Programa de termodinâmica (pressão de saturação, equações de estado,
propriedades residuais, coeficiente de fugacidade e ELV).

Uso::

    python principal.py
"""
import CoeficienteDeFugacidade
import ELV
import EquacaoDeEstado
import PressaodeSaturacao
import PropriedadesResiduais as residuais
import dados
from utilidades import (
    CompostoNaoEncontrado,
    DadoIndisponivel,
    ErroTermodinamico,
    cabecalho,
    confirmar,
    destaque,
    erro,
    ler_float,
    ler_opcao,
    ler_texto,
)

MENU_PRINCIPAL = """Menu
  1 - Pressão de Saturação
  2 - Equações de Estado
  3 - Aplicações em equipamentos
  4 - Coeficiente de Fugacidade
  5 - Equilíbrio Líquido-Vapor
  0 - Sair"""

EQUACOES = {
    1: (EquacaoDeEstado.GasIdeal, "Gás Ideal"),
    2: (EquacaoDeEstado.Virial, "2º Coeficiente do Virial"),
    3: (EquacaoDeEstado.VDW, "van der Waals"),
    4: (EquacaoDeEstado.RK, "Redlich-Kwong"),
    5: (EquacaoDeEstado.SRK, "Soave-Redlich-Kwong"),
    6: (EquacaoDeEstado.PR, "Peng-Robinson"),
}


# ------------------------------------------------------------- utilitários ---

def _opcoes_texto(opcoes, complemento="[Enter] - voltar"):
    linhas = [f"  {chave} - {valor}" for chave, valor in opcoes.items()]
    if complemento:
        linhas.append(f"  {complemento}")
    return "\n".join(linhas)


def _satisfaz(substancia, exigencia):
    if exigencia == "criticos":
        return substancia.tem_dados_criticos
    return getattr(substancia, exigencia) is not None


def pedir_composto(exigencia=None):
    """Lê um composto até ser válido. ``None`` (Enter vazio) cancela."""
    while True:
        nome = ler_texto("Composto: ")
        if not nome:
            return None

        substancia = dados.buscar(nome)
        if substancia is None:
            erro(
                "Composto não encontrado "
                f"({len(dados.nomes_disponiveis())} disponíveis). "
                "Tente novamente ou pressione Enter para voltar."
            )
            continue

        if exigencia is not None and not _satisfaz(substancia, exigencia):
            erro(f"{substancia.nome!r} não possui os dados necessários ({exigencia}).")
            continue
        return substancia


def _mostrar_volume(modelo):
    """Imprime o volume molar, destacando as raízes líquido/vapor."""
    volume = modelo.calcularVolumeMolar()
    raizes = modelo.raizes_volume
    if len(raizes) > 1:
        print(f"Vapor saturado:   {max(raizes):.6e} m³/mol")
        print(f"Líquido saturado: {min(raizes):.6e} m³/mol")
        print(f"Raiz adotada:     {volume:.6e} m³/mol")
    else:
        print(f"Volume molar: {volume:.6e} m³/mol")

    fator = modelo.fator_compressibilidade()
    if fator is not None:
        print(f"Fator de compressibilidade: Z = {fator:.5f}")
    return volume


# ------------------------------------------------------------ 1. saturação ---

def pressao_saturacao():
    cabecalho("Pressão de Saturação")
    print(_opcoes_texto({1: "Antoine (T em °C)", 2: "Lee-Kesler (T em K)"}))
    opcao = ler_opcao("Opção: ", {1, 2})
    if opcao is None:
        return

    if opcao == 1:
        cabecalho("Pressão de Saturação - Antoine")
        substancia = pedir_composto("antoine")
        if substancia is None:
            return
        modelo = PressaodeSaturacao.Antoine()
        modelo.buscarAntoine(substancia.nome)
        modelo.temperatura = ler_float("Temperatura (°C): ")
    else:
        cabecalho("Pressão de Saturação - Lee-Kesler")
        substancia = pedir_composto("criticos")
        if substancia is None:
            return
        modelo = PressaodeSaturacao.LeeKeslerSat()
        modelo.buscarLee(substancia.nome)
        modelo.temperatura = ler_float("Temperatura (K): ", positivo=True)

    try:
        pressao = modelo.pressaoSat()
    except ErroTermodinamico as exc:
        erro(exc)
        return

    print(f"Pressão de saturação: {pressao / 1e3:.4f} kPa ({pressao:.3f} Pa)")


# --------------------------------------------------------- 2. equação EOS ---

def equacao_estado():
    cabecalho("Equações de Estado")
    print(_opcoes_texto({chave: nome for chave, (_, nome) in EQUACOES.items()}))
    opcao = ler_opcao("Opção: ", EQUACOES.keys())
    if opcao is None:
        return

    classe, nome = EQUACOES[opcao]
    cabecalho(nome)
    print(_opcoes_texto({1: "Calcular pressão", 2: "Calcular volume molar"}))
    calculo = ler_opcao("Opção: ", {1, 2})
    if calculo is None:
        return

    modelo = classe()
    if modelo.EXIGE_DADOS_CRITICOS:
        substancia = pedir_composto("criticos")
        if substancia is None:
            return
        modelo.buscarPuras(substancia.nome)

    modelo.temperatura = ler_float("Temperatura (K): ", positivo=True)

    if calculo == 1:
        modelo.volume_molar = ler_float("Volume molar (m³/mol): ", positivo=True)
        pressao = modelo.calcularPressao()
        print(f"Pressão: {pressao:.3f} Pa ({pressao / 1e5:.6f} bar)")
    else:
        modelo.pressao = ler_float("Pressão (Pa): ", positivo=True)
        _mostrar_volume(modelo)


# ------------------------------------------------------ 3. equipamentos -----

def aplicacoes():
    cabecalho("Aplicações em equipamentos")
    nomes = residuais.PropriedadesResiduais.EQUIPAMENTOS
    print(_opcoes_texto(nomes))
    equipamento = ler_opcao("Equipamento: ", nomes.keys())
    if equipamento is None:
        return

    substancia = pedir_composto("criticos")
    if substancia is None:
        return

    modelo = residuais.PropriedadesResiduais()
    modelo.equipamento = equipamento
    modelo.composto = substancia.nome
    modelo.pressao_inicial = ler_float("Pressão de entrada (Pa): ", positivo=True)
    modelo.temperatura_inicial = ler_float("Temperatura de entrada (K): ", positivo=True)
    modelo.pressao_final = ler_float("Pressão de saída (Pa): ", positivo=True)
    modelo.temperatura_final = ler_float("Temperatura de saída (K): ", positivo=True)

    try:
        resultado = modelo.calcularResidual()
    except (ErroTermodinamico, DadoIndisponivel) as exc:
        erro(exc)
        return

    print(f"W = ΔH = {resultado.trabalho:.3f} J/mol")
    if modelo.viola_primeira_lei(resultado):
        erro("Viola a 1ª lei da termodinâmica para este equipamento.")
        return

    print(f"ΔS = {resultado.delta_s:.3f} J/(mol·K)")
    if resultado.delta_s < 0.0:
        print("Processo impossível (ΔS < 0).")
    elif abs(resultado.delta_s) < 1e-9:
        print("Processo possível e reversível (ΔS = 0).")
    else:
        print("Processo possível e irreversível (ΔS > 0).")


# --------------------------------------------------- 4. fugacidade ----------

def fugacidade():
    cabecalho("Coeficiente de Fugacidade")
    print(_opcoes_texto({1: "Pura", 2: "Mistura"}))
    opcao = ler_opcao("Opção: ", {1, 2})
    if opcao is None:
        return

    if opcao == 1:
        cabecalho("Coeficiente de Fugacidade - Espécie Pura (SRK)")
        substancia = pedir_composto("criticos")
        if substancia is None:
            return
        modelo = CoeficienteDeFugacidade.CoefFugacidadePuras()
        modelo.composto = substancia.nome
        modelo.temperatura = ler_float("Temperatura (K): ", positivo=True)
        modelo.pressao = ler_float("Pressão (Pa): ", positivo=True)
        try:
            coeficiente = modelo.calcularFugacidade()
        except ErroTermodinamico as exc:
            erro(exc)
            return
        print(f"φ = {coeficiente:.6f}")
        return

    cabecalho("Coeficiente de Fugacidade - Mistura (virial)")
    composto1 = pedir_composto("criticos")
    if composto1 is None:
        return
    composto2 = pedir_composto("criticos")
    if composto2 is None:
        return

    modelo = CoeficienteDeFugacidade.CoefFugacidadeMisturas()
    modelo.composto1 = composto1.nome
    modelo.composto2 = composto2.nome
    modelo.temperatura = ler_float("Temperatura (K): ", positivo=True)
    modelo.pressao = ler_float("Pressão (Pa): ", positivo=True)
    modelo.fracao_molar1 = ler_float("Fração molar (1): ")
    modelo.fracao_molar2 = ler_float("Fração molar (2): ")

    try:
        phi1, phi2 = modelo.calcularFugacidade()
    except ErroTermodinamico as exc:
        erro(exc)
        return
    print(f"φ1 = {phi1:.6f}")
    print(f"φ2 = {phi2:.6f}")


# ------------------------------------------------------------- 5. ELV ------

def _tabela_elv(xs, ys, pressoes, amostras=11):
    """Mostra até ``amostras`` linhas do diagrama calculado."""
    passo = max(1, len(xs) // amostras)
    print(f"{'x1':>8} {'y1':>10} {'P (kPa)':>14}")
    for indice in range(0, len(xs), passo):
        print(f"{xs[indice]:8.3f} {ys[indice]:10.4f} {pressoes[indice] / 1e3:14.4f}")


def equilibrio_liquido_vapor():
    cabecalho("Equilíbrio Líquido-Vapor")
    print(_opcoes_texto({1: "Margules", 2: "Wilson"}))
    opcao = ler_opcao("Opção: ", {1, 2})
    if opcao is None:
        return

    if opcao == 1:
        cabecalho("Equilíbrio Líquido-Vapor - Margules")
        parametros = ("a12", "a21")
        rotulos = ("A12", "A21")
        modelo = ELV.Margules()
    else:
        cabecalho("Equilíbrio Líquido-Vapor - Wilson")
        parametros = ("lambda12", "lambda21")
        rotulos = ("Λ12", "Λ21")
        modelo = ELV.Wilson()

    composto1 = pedir_composto("antoine")
    if composto1 is None:
        return
    composto2 = pedir_composto("antoine")
    if composto2 is None:
        return

    modelo.composto1 = composto1.nome
    modelo.composto2 = composto2.nome
    modelo.temperatura = ler_float("Temperatura (°C): ")
    modelo.variacao = ler_float("Variação de x1 (ex.: 0,05): ", positivo=True)
    setattr(modelo, parametros[0], ler_float(f"{rotulos[0]}: "))
    setattr(modelo, parametros[1], ler_float(f"{rotulos[1]}: "))

    try:
        xs, ys, pressoes = modelo.calcular()
    except ErroTermodinamico as exc:
        erro(exc)
        return

    _tabela_elv(xs, ys, pressoes)
    try:
        modelo.grafico()
    except ImportError as exc:
        erro(f"{exc} — resultado numérico exibido acima.")


# --------------------------------------------------------------- principal ---

ACOES = {
    1: pressao_saturacao,
    2: equacao_estado,
    3: aplicacoes,
    4: fugacidade,
    5: equilibrio_liquido_vapor,
}


def main():
    try:
        while True:
            cabecalho("TermoPy")
            print(MENU_PRINCIPAL)
            opcao = ler_opcao(
                "Escolha uma opção: ", set(ACOES) | {0}, permitir_voltar=False
            )
            if opcao is None or opcao == 0:
                break

            try:
                ACOES[opcao]()
            except (ErroTermodinamico, CompostoNaoEncontrado, DadoIndisponivel) as exc:
                erro(exc)
            except ValueError as exc:
                erro(f"Entrada inválida: {exc}")
            print()
            if not confirmar("Deseja continuar? [S/N] "):
                break
    except (KeyboardInterrupt, EOFError):
        print()
        destaque("Encerrando TermoPy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
