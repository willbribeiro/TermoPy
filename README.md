# TermoPy

[![testes](https://github.com/willbribeiro/TermoPy/actions/workflows/testes.yml/badge.svg)](https://github.com/willbribeiro/TermoPy/actions/workflows/testes.yml)

Programa de termodinâmica em Python: pressão de saturação, equações de estado,
propriedades residuais em equipamentos, coeficiente de fugacidade e equilíbrio
líquido-vapor.

## Instalação

O núcleo e a interface gráfica usam apenas a biblioteca padrão do Python (3.8+).
`matplotlib` é necessário **somente** para o gráfico do item 5 no menu de
terminal — a interface desenha o mesmo diagrama em um `tk.Canvas`:

```bash
pip install -r requirements.txt   # opcional: gráficos
```

## Execução

Interface gráfica (recomendada):

```bash
python interface.py
```

O menu de terminal continua disponível:

```bash
python principal.py
```

Menu:

```
1 - Pressão de Saturação      (Antoine ou Lee-Kesler)
2 - Equações de Estado        (gás ideal, virial, vdW, RK, SRK, PR)
3 - Aplicações em equipamentos (compressor / turbina)
4 - Coeficiente de Fugacidade  (espécie pura ou mistura binária)
5 - Equilíbrio Líquido-Vapor   (Margules ou Wilson)
0 - Sair
```

As unidades são sempre do SI: pressão em Pa, temperatura em K, volume molar em
m³/mol. As duas exceções são explícitas na tela: Antoine recebe **°C** e o ELV
também usa **°C** (para casar com os parâmetros de Antoine).

## Interface gráfica

`python interface.py` abre uma janela com uma aba por calculadora:

| Aba | O que faz |
| --- | --- |
| Pressão de Saturação | Antoine (°C → kPa) ou Lee-Kesler (K), com aviso quando T ≥ Tc. |
| Equações de Estado | P a partir de (T, v) ou v a partir de (T, P), com as raízes líquido/vapor e Z. |
| Aplicações em equipamentos | Compressor/turbina: ΔH, ΔS e o teste da 1ª lei e da 2ª lei. |
| Coeficiente de Fugacidade | φ de espécie pura (SRK) ou de mistura binária (virial). |
| Equilíbrio Líquido-Vapor | Margules/Wilson: tabela de pontos e diagrama P-x1-y1 com detecção de azeótropo. |

Detalhes úteis:

* O diagrama é desenhado em um `tk.Canvas`, então **não** é preciso `matplotlib`
  para usar a interface.
* Ao alternar entre Antoine e Lee-Kesler a temperatura é convertida entre °C e K
  (o campo mostra a unidade usada pelo modelo selecionado).
* Os campos de composto aceitam digitação com filtro pelos nomes disponíveis
  (`Ajuda → Compostos disponíveis` lista todos).
* Enter em qualquer campo calcula; "Limpar" volta aos valores padrão da aba.
* Entradas inválidas mostram a mensagem no painel de resultado/status, sem
  fechar o programa.

## Uso como biblioteca

```python
import EquacaoDeEstado

modelo = EquacaoDeEstado.SRK()
modelo.buscarPuras("n-hexano")   # aceita "hexano", "água"/"agua", "iso-butano"...
modelo.temperatura = 400.0       # K
modelo.pressao = 0.5e5           # Pa
print(modelo.calcularVolumeMolar())   # m³/mol
print(modelo.raizes_volume)           # raízes líquido/vapor, se houver
print(modelo.fator_compressibilidade())
```

## Estrutura

| Arquivo | Responsabilidade |
| --- | --- |
| `principal.py` | Menu e entrada/saída (CLI). Nenhum cálculo. |
| `interface.py` | Interface gráfica em Tkinter: abas, formulários e diagrama no `Canvas`. |
| `dados.py` | Fonte única das tabelas: propriedades críticas, Antoine e Cp ideal. Busca com normalização de acentos e apelidos. |
| `PressaodeSaturacao.py` | Antoine e Lee-Kesler. |
| `EquacaoDeEstado.py` | Gás ideal, virial, vdW, RK, SRK e PR. Resolve o polinômio cúbico e escolhe a raiz física (líquido/vapor). |
| `PropriedadesResiduais.py` | ΔH e ΔS entre dois estados (SRK + Cp de gás ideal). |
| `CoeficienteDeFugacidade.py` | φ para espécie pura (SRK) e mistura binária (virial). |
| `ELV.py` | Margules e Wilson; tabela e diagrama P-x1-y1. |
| `utilidades.py` | Exceções, solução analítica de cúbicas e helpers de console. |

Não há dependência circular: `dados` → `PressaodeSaturacao` → `EquacaoDeEstado`
→ demais módulos → `principal`.

## Testes

```bash
python -m unittest discover -s testes -t . -v
```

Os testes cobrem a solução de cúbicas, a ida-e-volta P→v→P dos cinco modelos,
a consistência do fator α do Peng-Robinson, Antoine/Lee-Kesler, fugacidade,
ΔH/ΔS e os modelos de atividade. Os testes da interface são pulados
automaticamente quando não há display disponível.

## Dados

* Propriedades críticas e Cp ideal: Smith, Van Ness & Abbott, *Introdução à
  Termodinâmica da Engenharia Química* (apêndices B e C).
* Antoine: Poling, Prausnitz & O'Connell, *The Properties of Gases and Liquids*
  (P em kPa, T em °C).
* Lee-Kesler: Lee & Kesler (1975).

## Correções em relação à versão original

* `Peng-Robinson.calcularVolumeMolar` usava `(1 + κ + (1 - √Tr))²` em vez de
  `(1 + κ(1 - √Tr))²`; o volume calculado não fechava com a pressão.
* `PropriedadesResiduais` somava as propriedades residuais dos dois estados
  (deveria subtrair) e calculava ΔS ideal como ΔH/T; agora usa ∫Cp/T dT.
* `dZ/dT` do SRK nas propriedades residuais usava uma expressão incorreta.
* A tabela original dava `Zc = 0.7` para o n-pentano (valor correto ≈ 0.27) e
  grafava "dissulfeto de hidrogênio" com os coeficientes do H₂S.
* As tabelas de propriedades críticas estavam duplicadas em dois módulos, com
  nomes divergentes (`iso-butano`, `metilciclo-hexano`); hoje há uma só fonte.
* `__metaclass__ = ABCMeta` (sintaxe Python 2) não tinha efeito: a classe base
  era instanciável e `@abstractmethod` não era respeitado.
* A seleção da raiz cúbica (líquido/vapor) aparecia copiada em três módulos e
  deixava variáveis indefinidas em alguns casos; agora é uma função única.
* O volume molar das equações cúbicas não era armazenado nem retornado — só
  impresso por efeito colateral, e o menu não mostrava nada em vdW/RK/SRK/PR.
* `numpy` deixou de ser dependência: as raízes cúbicas são obtidas pela solução
  analítica de Cardano.
* O menu quebrava com `int(input())` em qualquer entrada não numérica, deixava
  `resp` indefinido em algumas opções e imprimia listas globais acumuladas
  (chamar `grafico()` duas vezes duplicava os pontos).
* Margules zerava γ1 em x1 = 0 e γ2 em x1 = 1; os valores corretos nos limites
  são exp(A12) e exp(A21).
* O laço `while x1 <= 1` com incremento flutuante podia não incluir x1 = 1 ou
  nunca terminar com variação ≤ 0; a malha agora é exata.
