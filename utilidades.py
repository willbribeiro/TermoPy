# -*- coding: utf-8 -*-
"""Utilitários compartilhados: exceções, raízes de polinômios e console.

Este módulo concentra tudo o que não é termodinâmica:

* exceções específicas do programa;
* solução analítica de equações cúbicas (Cardano), usada para obter o
  volume molar das equações de estado sem depender de ``numpy``;
* seleção da raiz física (líquido ou vapor);
* helpers de entrada/saída usados pelo menu.
"""
import math
import sys


# --------------------------------------------------------------- exceções ---

class ErroTermodinamico(ValueError):
    """Entrada ou condição física inválida para o cálculo."""


class CompostoNaoEncontrado(LookupError):
    """O composto informado não existe nas tabelas de dados."""

    def __init__(self, composto, disponiveis=None):
        mensagem = f"Composto não encontrado: {composto!r}."
        if disponiveis is not None:
            mensagem += f" ({disponiveis} compostos disponíveis)"
        super().__init__(mensagem)
        self.composto = composto


class DadoIndisponivel(ValueError):
    """O composto existe, mas falta a propriedade necessária ao cálculo."""

    def __init__(self, composto, propriedade):
        super().__init__(
            f"Dado indisponível para {composto!r}: {propriedade}."
        )
        self.composto = composto
        self.propriedade = propriedade


# ----------------------------------------------------------------- raízes ---

def _raiz_cubica(valor):
    """Raiz cúbica real (``x ** (1/3)`` falha para valores negativos)."""
    return math.copysign(abs(valor) ** (1.0 / 3.0), valor)


def _raizes_quadraticas(a, b, c, tolerancia=1e-12):
    escala = max(abs(a), abs(b), abs(c))
    if escala == 0.0:
        return []
    if abs(a) <= tolerancia * escala:
        if abs(b) <= tolerancia * escala:
            return [] if abs(c) > tolerancia * escala else [0.0]
        return [-c / b]
    delta = b * b - 4.0 * a * c
    if delta < 0.0:
        if delta > -tolerancia * max(b * b, 1.0):
            delta = 0.0
        else:
            return []
    raiz = math.sqrt(delta)
    # Fórmula estável: evita cancelamento catastrófico quando b >> raiz.
    q = -0.5 * (b + math.copysign(raiz, b))
    if q == 0.0:
        return [0.0]
    return sorted((q / a, c / q))


def raizes_cubicas(coeficientes, tolerancia=1e-12):
    """Raízes reais de ``a*x**3 + b*x**2 + c*x + d``, em ordem crescente.

    Usa a solução de Cardano na forma trigonométrica (três raízes reais) ou
    hiperbólica (uma raiz real). Raízes repetidas aparecem uma única vez.
    """
    a, b, c, d = (float(valor) for valor in coeficientes)
    escala = max(abs(a), abs(b), abs(c), abs(d))
    if escala == 0.0:
        return []
    if abs(a) <= tolerancia * escala:
        return _raizes_quadraticas(b, c, d, tolerancia)

    p = b / a
    q = c / a
    r = d / a

    deslocamento = p / 3.0
    p_dep = q - p * p / 3.0
    q_dep = 2.0 * p ** 3 / 27.0 - p * q / 3.0 + r

    metade_q2 = (q_dep / 2.0) ** 2
    terco_p3 = (p_dep / 3.0) ** 3
    discriminante = metade_q2 + terco_p3
    escala_d = max(abs(metade_q2), abs(terco_p3), 1e-300)

    if discriminante > tolerancia * escala_d:
        # Uma raiz real: Cardano hiperbólico.
        raiz_d = math.sqrt(discriminante)
        u = _raiz_cubica(-q_dep / 2.0 + raiz_d)
        v = _raiz_cubica(-q_dep / 2.0 - raiz_d)
        ordenadas = [u + v]
    elif discriminante < -tolerancia * escala_d:
        # Três raízes reais distintas: forma trigonométrica.
        amplitude = 2.0 * math.sqrt(-p_dep / 3.0)
        cosseno = -4.0 * q_dep / amplitude ** 3
        cosseno = max(-1.0, min(1.0, cosseno))
        theta = math.acos(cosseno) / 3.0
        ordenadas = [
            amplitude * math.cos(theta - 2.0 * math.pi * k / 3.0)
            for k in range(3)
        ]
    else:
        # Discriminante nulo: raiz dupla.
        if p_dep == 0.0:
            ordenadas = [0.0]
        else:
            u = _raiz_cubica(-q_dep / 2.0)
            ordenadas = [2.0 * u, -u]

    raizes = sorted(raiz - deslocamento for raiz in ordenadas)

    unicas = []
    for raiz in raizes:
        if not unicas or abs(raiz - unicas[-1]) > 1e-9 * max(abs(raiz), 1e-12):
            unicas.append(raiz)
    return unicas


def selecionar_raiz_fisica(raizes, pressao, pressao_saturacao):
    """Escolhe o volume molar físico entre as raízes da equação cúbica.

    Uma única raiz positiva: é a resposta. Com três raízes (região de
    coexistência), usa-se o maior volume quando ``P < Psat`` (vapor) e o
    menor quando ``P >= Psat`` (líquido).
    """
    positivas = [raiz for raiz in raizes if raiz > 0.0]
    if not positivas:
        raise ErroTermodinamico(
            "A equação de estado não forneceu nenhuma raiz de volume positivo."
        )
    if len(positivas) == 1:
        return positivas[0]
    return max(positivas) if pressao < pressao_saturacao else min(positivas)


# ----------------------------------------------------------------- console ---

LARGURA = 60

VERMELHO = "\033[1;31m"
VERDE = "\033[1;32m"
AMARELO = "\033[1;33m"
CIANO = "\033[1;36m"
NEGRITO = "\033[1m"
RESET = "\033[0m"


def _colorir(texto, codigo):
    """Aplica cor apenas quando a saída é um terminal (permite redirecionar)."""
    if not sys.stdout.isatty():
        return texto
    return f"{codigo}{texto}{RESET}"


def cabecalho(titulo):
    linha = "=-" * (LARGURA // 2)
    print(linha)
    print(titulo.center(LARGURA))
    print(linha)


def erro(mensagem):
    print(_colorir(mensagem, VERMELHO))


def aviso(mensagem):
    print(_colorir(mensagem, AMARELO))


def destaque(mensagem):
    print(_colorir(mensagem, NEGRITO))


def ler_texto(mensagem):
    return input(mensagem).strip()


def ler_float(mensagem, positivo=False):
    """Lê um número real, aceitando vírgula como separador decimal."""
    while True:
        entrada = input(mensagem).strip().replace(",", ".")
        if not entrada:
            erro("Digite um número.")
            continue
        try:
            valor = float(entrada)
        except ValueError:
            erro(f"Valor inválido: {entrada!r}. Digite um número.")
            continue
        if not math.isfinite(valor):
            erro("O valor precisa ser finito.")
            continue
        if positivo and valor <= 0.0:
            erro("O valor precisa ser maior que zero.")
            continue
        return valor


def ler_opcao(mensagem, validas, permitir_voltar=True):
    """Lê uma opção numérica.

    Com ``permitir_voltar`` (padrão), entrada vazia ou não numérica devolve
    ``None`` — o equivalente a "voltar ao menu". Sem ele, a pergunta é
    repetida até o usuário informar uma opção válida.
    """
    validas = set(validas)
    while True:
        entrada = input(mensagem).strip()
        if not entrada:
            if permitir_voltar:
                return None
            erro(f"Escolha uma opção: {sorted(validas)}.")
            continue
        try:
            opcao = int(entrada)
        except ValueError:
            if permitir_voltar:
                return None
            erro(f"Opção inválida: {entrada!r}.")
            continue
        if opcao in validas:
            return opcao
        erro(f"Opção inválida. Válidas: {sorted(validas)} (Enter para voltar).")


def confirmar(mensagem="Deseja continuar? [S/N] "):
    while True:
        resposta = input(mensagem).strip().upper()
        if resposta in ("S", "SIM"):
            return True
        if resposta in ("N", "NAO", "NÃO", ""):
            return False
        erro("Responda com S ou N.")
