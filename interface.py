# -*- coding: utf-8 -*-
"""Interface gráfica (Tkinter) do TermoPy.

Execução::

    python interface.py

A GUI usa apenas a biblioteca padrão: a lógica de cálculo continua nos módulos
existentes (``dados``, ``PressaodeSaturacao``, ``EquacaoDeEstado``,
``PropriedadesResiduais``, ``CoeficienteDeFugacidade`` e ``ELV``) e o diagrama
P-x1-y1 é desenhado em um ``tk.Canvas`` — não é necessário matplotlib.
"""
import math
import sys
import traceback
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

import CoeficienteDeFugacidade
import ELV
import EquacaoDeEstado
import PressaodeSaturacao
import PropriedadesResiduais as residuais
import dados
from utilidades import CompostoNaoEncontrado, DadoIndisponivel, ErroTermodinamico


class ErroEntrada(ValueError):
    """Entrada inválida digitada pelo usuário na interface."""


# ------------------------------------------------------------------ estilos ---

COR_PRIMARIA = "#1b4f72"
COR_TEXTO_SUAVE = "#5d6d7e"
COR_ERRO = "#b03a2e"
COR_OK = "#1e8449"
COR_AVISO = "#9a7d0a"


def _ativar_dpi():
    """Evita interface borrada no Windows em monitores com escala > 100%."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # pragma: no cover - depende do sistema
        pass


def _passo_agradavel(valor, divisoes=5):
    """Passo "redondo" para as marcas dos eixos do gráfico."""
    if valor <= 0:
        return 1.0
    bruto = valor / divisoes
    magnitude = 10.0 ** math.floor(math.log10(bruto))
    for multiplo in (1.0, 2.0, 2.5, 5.0, 10.0):
        if bruto <= multiplo * magnitude:
            return multiplo * magnitude
    return 10.0 * magnitude


def _formatar_numero(valor):
    """Formata números grandes/muito pequenos sem perder informação."""
    if valor == 0:
        return "0"
    if 1e-3 <= abs(valor) < 1e5:
        return f"{valor:.4g}"
    return f"{valor:.4e}"


def _numero_curto(valor, casas=2):
    """Texto enxuto para campos de entrada, sem zeros inúteis."""
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return "0" if texto in ("", "-0") else texto


# ------------------------------------------------------------------ gráfico ---

class GraficoPxy(tk.Canvas):
    """Diagrama P-x1-y1 desenhado diretamente no canvas (sem matplotlib)."""

    MARGEM_ESQUERDA = 68
    MARGEM_DIREITA = 20
    MARGEM_TOPO = 42
    MARGEM_BASE = 46

    def __init__(self, mestre, altura=300):
        super().__init__(
            mestre,
            height=altura,
            background="white",
            highlightthickness=1,
            highlightbackground="#c8c8c8",
        )
        self._dados = None
        self._mensagem = None
        self.azeotropo = None
        self.bind("<Configure>", lambda _evento: self._renderizar())

    # ------------------------------------------------------------ API -----
    def limpar(self):
        self._dados = None
        self._mensagem = None
        self.azeotropo = None
        self._renderizar()

    def mostrar_mensagem(self, texto, cor=COR_ERRO):
        """Substitui o gráfico por uma mensagem (usado em erros de entrada)."""
        self._dados = None
        self._mensagem = (texto, cor)
        self.azeotropo = None
        self._renderizar()

    def desenhar(self, xs, ys, pressoes):
        self._mensagem = None
        self._dados = (
            list(xs),
            list(ys),
            [pressao / 1e3 for pressao in pressoes],  # Pa -> kPa
        )
        self._renderizar()

    # ------------------------------------------------------- desenho -----
    def _renderizar(self):
        self.delete("all")
        largura = self.winfo_width()
        altura = self.winfo_height()
        if largura < 140 or altura < 120:
            return
        if self._dados is None:
            if self._mensagem is not None:
                texto, cor = self._mensagem
            else:
                texto, cor = "Informe os dados e clique em Calcular.", "#95a5a6"
            self.create_text(
                largura / 2,
                altura / 2,
                text=texto,
                fill=cor,
                width=max(120, largura - 40),
                justify="center",
            )
            return

        xs, ys, pressoes = self._dados
        esquerda = self.MARGEM_ESQUERDA
        direita = largura - self.MARGEM_DIREITA
        topo = self.MARGEM_TOPO
        base = altura - self.MARGEM_BASE
        if direita - esquerda < 60 or base - topo < 40:
            return

        maximo = max(pressoes)
        passo = _passo_agradavel(maximo * 1.05)
        limite = math.ceil(maximo * 1.05 / passo) * passo
        if limite <= 0:
            limite = 1.0

        def px(x):
            return esquerda + x * (direita - esquerda)

        def py(p):
            return base - (p / limite) * (base - topo)

        # Grade horizontal + marcas do eixo Y (pressão em kPa).
        pressao = 0.0
        while pressao <= limite + passo * 0.5:
            y = py(pressao)
            self.create_line(esquerda, y, direita, y, fill="#ecf0f1")
            self.create_text(
                esquerda - 8,
                y,
                text=f"{pressao:.0f}",
                anchor="e",
                fill=COR_TEXTO_SUAVE,
            )
            pressao += passo

        # Grade vertical + marcas do eixo X (frações molares).
        for indice in range(6):
            x1 = indice / 5.0
            x = px(x1)
            self.create_line(x, topo, x, base, fill="#ecf0f1")
            self.create_text(
                x, base + 8, text=f"{x1:.1f}", anchor="n", fill=COR_TEXTO_SUAVE
            )

        # Eixos.
        self.create_line(esquerda, topo, esquerda, base, fill="#7f8c8d")
        self.create_line(esquerda, base, direita, base, fill="#7f8c8d")
        self.create_text(
            (esquerda + direita) / 2,
            base + 30,
            text="x1, y1",
            fill="#34495e",
        )
        self.create_text(
            esquerda,
            topo - 18,
            text="P (kPa)",
            anchor="w",
            fill="#34495e",
        )

        # Curvas: líquido (x1) e vapor (y1).
        self._desenhar_serie([(px(x), py(p)) for x, p in zip(xs, pressoes)], "#c0392b")
        self._desenhar_serie([(px(y), py(p)) for y, p in zip(ys, pressoes)], "#2471a3")

        # Azeótropo (se as curvas se cruzarem): linha-guia + marca.
        self.azeotropo = self._azeotropo(xs, ys)
        if self.azeotropo is not None:
            x = px(self.azeotropo)
            y = py(self._interpolar(self.azeotropo, xs, pressoes))
            self.create_line(x, topo, x, base, fill="#7d3c98", dash=(4, 3))
            self.create_oval(
                x - 4, y - 4, x + 4, y + 4, outline="#7d3c98", width=2
            )

        # Legenda no canto superior direito.
        self._legenda(direita, 12)

    def _desenhar_serie(self, pontos, cor):
        if len(pontos) < 2:
            return
        self.create_line(
            [coordenada for ponto in pontos for coordenada in ponto],
            fill=cor,
            width=2,
        )
        if len(pontos) <= 40:
            raio = 2.5 if len(pontos) <= 20 else 1.8
            for x, y in pontos:
                self.create_oval(
                    x - raio, y - raio, x + raio, y + raio, fill=cor, outline=""
                )

    def _legenda(self, x, y):
        itens = (("#c0392b", "líquido (x1)"), ("#2471a3", "vapor (y1)"))
        for indice, (cor, texto) in enumerate(itens):
            linha_y = y + indice * 17
            item = self.create_text(
                x, linha_y, text=texto, anchor="e", fill="#34495e"
            )
            esquerda_texto = self.bbox(item)[0]
            self.create_line(
                esquerda_texto - 22,
                linha_y,
                esquerda_texto - 6,
                linha_y,
                fill=cor,
                width=3,
            )

    @staticmethod
    def _interpolar(x, xs, valores):
        """Interpola linearmente ``valores`` na abcissa ``x``."""
        for indice in range(1, len(xs)):
            if xs[indice] >= x:
                x0, x1 = xs[indice - 1], xs[indice]
                v0, v1 = valores[indice - 1], valores[indice]
                if x1 == x0:
                    return v1
                fracao = (x - x0) / (x1 - x0)
                return v0 + fracao * (v1 - v0)
        return valores[-1]

    @staticmethod
    def _azeotropo(xs, ys):
        """Fração molar do azeótropo (onde x1 = y1), se houver, no interior."""
        diferencas = [x - y for x, y in zip(xs, ys)]
        for indice in range(1, len(diferencas)):
            if xs[indice - 1] <= 0.0 or xs[indice] >= 1.0:
                continue
            anterior = diferencas[indice - 1]
            atual = diferencas[indice]
            if anterior == 0.0:
                return xs[indice - 1]
            if anterior * atual < 0.0:
                fracao = abs(anterior) / (abs(anterior) + abs(atual))
                return xs[indice - 1] + fracao * (xs[indice] - xs[indice - 1])
        return None


# --------------------------------------------------------------------- aba ---

class Aba(ttk.Frame):
    """Base das abas: cabeçalho, formulário à esquerda e resultado à direita."""

    TITULO = "Aba"
    DESCRICAO = ""

    def __init__(self, mestre, app):
        super().__init__(mestre, padding=14)
        self.app = app
        self._linha = 0

        self.columnconfigure(0, weight=11, uniform="aba")
        self.columnconfigure(1, weight=14, uniform="aba")
        self.rowconfigure(1, weight=1)

        cabecalho = ttk.Frame(self)
        cabecalho.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ttk.Label(cabecalho, text=self.TITULO, style="Titulo.TLabel").pack(anchor="w")
        if self.DESCRICAO:
            ttk.Label(
                cabecalho,
                text=self.DESCRICAO,
                style="Descricao.TLabel",
                wraplength=880,
                justify="left",
            ).pack(anchor="w", pady=(3, 0))

        self.formulario = ttk.Frame(self)
        self.formulario.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        self.formulario.columnconfigure(1, weight=1)

        self.painel_direito = ttk.Frame(self)
        self.painel_direito.grid(row=1, column=1, sticky="nsew")
        self.painel_direito.columnconfigure(0, weight=1)
        self.painel_direito.rowconfigure(0, weight=1)

        self._criar_variaveis()
        self._montar_formulario()
        self._montar_resultado()

    # ------------------------------------------------------ variáveis ----
    def _criar_variaveis(self):
        pass

    def _montar_formulario(self):
        raise NotImplementedError

    def _montar_resultado(self):
        self.caixa = self._criar_caixa_texto(self.painel_direito)

    # --------------------------------------------------------- widgets ---
    def _criar_caixa_texto(self, mestre, altura=12):
        quadro = ttk.LabelFrame(mestre, text="Resultado", padding=8)
        quadro.grid(row=0, column=0, sticky="nsew")
        quadro.columnconfigure(0, weight=1)
        quadro.rowconfigure(0, weight=1)

        caixa = tk.Text(
            quadro,
            height=altura,
            width=40,
            wrap="word",
            borderwidth=0,
            background="#fbfcfc",
            padx=8,
            pady=8,
            cursor="arrow",
        )
        caixa.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(quadro, orient="vertical", command=caixa.yview)
        barra.grid(row=0, column=1, sticky="ns")
        caixa.configure(yscrollcommand=barra.set, state="disabled")

        caixa.tag_configure("titulo", font=self.app.fonte_secao, foreground=COR_PRIMARIA)
        caixa.tag_configure("valor", font=self.app.fonte_valor, foreground="#1a5276")
        caixa.tag_configure("detalhe", foreground=COR_TEXTO_SUAVE)
        caixa.tag_configure("ok", foreground=COR_OK)
        caixa.tag_configure("erro", foreground=COR_ERRO)
        caixa.tag_configure("aviso", foreground=COR_AVISO)
        return caixa

    def _campo(self, rotulo, widget):
        """Adiciona uma linha "rótulo: widget" ao formulário."""
        ttk.Label(self.formulario, text=rotulo).grid(
            row=self._linha, column=0, sticky="w", pady=4
        )
        widget.grid(row=self._linha, column=1, sticky="ew", padx=(10, 0), pady=4)
        self._linha += 1
        return widget

    def _criar_entrada(self, var, unidade="", largura=14, mestre=None):
        quadro = ttk.Frame(mestre if mestre is not None else self.formulario)
        entrada = ttk.Entry(quadro, textvariable=var, width=largura, justify="right")
        entrada.pack(side="left")
        quadro.rotulo = None
        if unidade:
            quadro.rotulo = ttk.Label(
                quadro, text=unidade, style="Unidade.TLabel"
            )
            quadro.rotulo.pack(side="left", padx=(6, 0))
        entrada.bind("<Return>", self._atalho_calcular)
        quadro.entrada = entrada
        return quadro

    def _criar_combo(self, var, valores, largura=26, somente_leitura=True, mestre=None):
        combo = ttk.Combobox(
            mestre if mestre is not None else self.formulario,
            textvariable=var,
            values=list(valores),
            width=largura,
            state="readonly" if somente_leitura else "normal",
        )
        combo.bind("<Return>", self._atalho_calcular)
        return combo

    def _criar_combo_composto(self, var, mestre=None):
        combo = ttk.Combobox(
            mestre if mestre is not None else self.formulario,
            textvariable=var,
            values=self.app.compostos,
            width=26,
            state="normal",
        )
        filtrar = self.app.criar_filtro_compostos(combo)
        combo.bind("<KeyRelease>", filtrar)
        combo.bind("<Return>", self._atalho_calcular)
        return combo

    def _linha_botoes(self, comando_limpar=None):
        quadro = ttk.Frame(self.formulario)
        quadro.grid(row=self._linha, column=0, columnspan=2, sticky="w", pady=(16, 0))
        ttk.Button(
            quadro, text="Calcular", style="Acao.TButton", command=self._executar
        ).pack(side="left")
        ttk.Button(quadro, text="Limpar", command=comando_limpar or self.restaurar).pack(
            side="left", padx=(8, 0)
        )
        self._linha += 1
        return quadro

    def _grupo(self):
        """Novo sub-quadro dentro do formulário (para campos que ligam/desligam)."""
        quadro = ttk.Frame(self.formulario)
        quadro.columnconfigure(1, weight=1)
        quadro.grid(row=self._linha, column=0, columnspan=2, sticky="ew")
        self._linha += 1
        return quadro

    @staticmethod
    def _campo_grupo(quadro, linha, rotulo, widget):
        etiqueta = ttk.Label(quadro, text=rotulo)
        etiqueta.grid(row=linha, column=0, sticky="w", pady=4)
        widget.grid(row=linha, column=1, sticky="ew", padx=(10, 0), pady=4)
        return etiqueta

    @staticmethod
    def _habilitar(widget, ativo):
        widget.configure(state="normal" if ativo else "disabled")

    # -------------------------------------------------------- resultado ---
    def escrever(self, texto="", tag="normal"):
        if not getattr(self, "caixa", None):
            return
        self.caixa.configure(state="normal")
        self.caixa.insert("end", texto + "\n", tag)
        self.caixa.configure(state="disabled")
        self.caixa.see("end")

    def limpar_resultado(self):
        if getattr(self, "caixa", None):
            self.caixa.configure(state="normal")
            self.caixa.delete("1.0", "end")
            self.caixa.configure(state="disabled")

    # --------------------------------------------------------- helpers ----
    def _atalho_calcular(self, _evento=None):
        self._executar()
        return "break"

    def _executar(self):
        self.limpar_resultado()
        self.app.limpar_status()
        try:
            mensagem = self.calcular()
        except (
            ErroEntrada,
            ErroTermodinamico,
            CompostoNaoEncontrado,
            DadoIndisponivel,
            ValueError,
        ) as exc:
            self._reportar_erro(str(exc))
        except Exception as exc:  # pragma: no cover - proteção da GUI
            traceback.print_exc()
            self._reportar_erro(f"Erro inesperado: {exc}")
        else:
            self.app.informar(mensagem or "Cálculo concluído.")

    def _reportar_erro(self, mensagem):
        self.escrever(mensagem, "erro")
        self.app.erro(mensagem)

    def calcular(self):
        """Executa o cálculo e, opcionalmente, devolve a mensagem de status."""
        raise NotImplementedError

    def restaurar(self):
        self.limpar_resultado()
        self.app.limpar_status()

    # ------------------------------------------------------ validação -----
    def obter_composto(self, var, exigencia=None):
        nome = var.get().strip()
        if not nome:
            raise ErroEntrada("Informe o composto.")
        substancia = dados.buscar(nome)
        if substancia is None:
            raise ErroEntrada(
                f"Composto não encontrado: {nome!r}. "
                f"Há {len(dados.nomes_disponiveis())} compostos disponíveis."
            )
        if exigencia == "criticos" and not substancia.tem_dados_criticos:
            raise ErroEntrada(f"{substancia.nome} não possui dados críticos completos.")
        if exigencia and exigencia != "criticos":
            if getattr(substancia, exigencia, None) is None:
                raise ErroEntrada(
                    f"{substancia.nome} não possui os dados necessários ({exigencia})."
                )
        var.set(substancia.nome)
        return substancia

    def obter_numero(self, var, rotulo, positivo=False):
        texto = var.get().strip().replace(",", ".")
        if not texto:
            raise ErroEntrada(f"Informe {rotulo}.")
        try:
            valor = float(texto)
        except ValueError:
            raise ErroEntrada(f"{rotulo}: valor inválido ({var.get()!r}).") from None
        if not math.isfinite(valor):
            raise ErroEntrada(f"{rotulo} precisa ser finito.")
        if positivo and valor <= 0.0:
            raise ErroEntrada(f"{rotulo} deve ser maior que zero.")
        return valor


# ------------------------------------------------- 1. pressão de saturação ---

class AbaPressaoSaturacao(Aba):
    TITULO = "Pressão de Saturação"
    DESCRICAO = (
        "Antoine usa temperatura em °C e devolve a pressão em kPa; "
        "Lee-Kesler usa temperatura em K e é válida para T < Tc."
    )

    def _criar_variaveis(self):
        self.modelo = tk.StringVar(value="antoine")
        self.composto = tk.StringVar(value="água")
        self.temperatura = tk.StringVar(value="100")
        self.unidade = tk.StringVar(value="°C")
        # Necessário para converter a temperatura em °C <-> K ao trocar de modelo.
        self._modelo_anterior = "antoine"
        self.modelo.trace_add("write", lambda *_: self._ao_trocar_modelo())

    def _montar_formulario(self):
        linha = ttk.Frame(self.formulario)
        linha.grid(row=self._linha, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._linha += 1
        for valor, texto in (("antoine", "Antoine"), ("lee", "Lee-Kesler")):
            ttk.Radiobutton(
                linha,
                text=texto,
                value=valor,
                variable=self.modelo,
            ).pack(side="left", padx=(0, 18))

        self._campo("Composto", self._criar_combo_composto(self.composto))
        quadro_temperatura = self._criar_entrada(self.temperatura, unidade="°C")
        self._campo("Temperatura", quadro_temperatura)
        self._rotulo_unidade = quadro_temperatura.rotulo

        self._linha_botoes()
        self._ao_trocar_modelo()

    def _ao_trocar_modelo(self):
        novo = self.modelo.get()
        if novo not in ("antoine", "lee"):
            return
        anterior = self._modelo_anterior
        if novo != anterior:
            # Sem isto, um valor digitado em °C seria lido como K no Lee-Kesler
            # e a pressão sairia praticamente nula.
            self._converter_temperatura(anterior, novo)
            self._modelo_anterior = novo
        self.unidade.set("°C" if novo == "antoine" else "K")
        if getattr(self, "_rotulo_unidade", None) is not None:
            self._rotulo_unidade.configure(text=self.unidade.get())

    def _converter_temperatura(self, de, para):
        """Converte o campo entre °C e K quando o modelo é trocado."""
        texto = self.temperatura.get().strip().replace(",", ".")
        try:
            valor = float(texto)
        except ValueError:
            return
        if not math.isfinite(valor):
            return
        convertido = valor + 273.15 if para == "lee" else valor - 273.15
        self.temperatura.set(_numero_curto(convertido))

    def calcular(self):
        usa_lee = self.modelo.get() == "lee"
        substancia = self.obter_composto(self.composto)
        temperatura = self.obter_numero(
            self.temperatura, "a temperatura", positivo=usa_lee
        )

        if usa_lee:
            modelo = PressaodeSaturacao.LeeKeslerSat()
            if not modelo.buscarLee(substancia.nome):
                raise ErroEntrada(
                    f"{substancia.nome} não possui Tc, Pc e ω completos, então o "
                    "Lee-Kesler não pode ser usado. Selecione Antoine."
                )
            modelo.temperatura = temperatura
            rotulo = "Lee-Kesler"
            unidade_t = "K"
        else:
            modelo = PressaodeSaturacao.Antoine()
            if not modelo.buscarAntoine(substancia.nome):
                raise ErroEntrada(
                    f"{substancia.nome} não possui coeficientes de Antoine."
                )
            modelo.temperatura = temperatura
            rotulo = "Antoine"
            unidade_t = "°C"

        pressao = modelo.pressaoSat()

        self.escrever(f"{rotulo} — {substancia.nome}", "titulo")
        self.escrever(f"{pressao / 1e3:.4f} kPa", "valor")
        self.escrever()
        self.escrever(f"{pressao:.3f} Pa")
        self.escrever(f"{pressao / 1e5:.6f} bar")
        self.escrever()
        self.escrever(f"T = {temperatura:.2f} {unidade_t}", "detalhe")

        if not usa_lee:
            return

        tr = temperatura / substancia.temperatura_critica
        self.escrever(f"Tr = {tr:.4f}", "detalhe")
        self.escrever(
            f"Faixa recomendada: {0.3 * substancia.temperatura_critica:.1f} K a "
            f"{substancia.temperatura_critica:.1f} K (Tc = "
            f"{substancia.temperatura_critica:.1f} K)",
            "detalhe",
        )
        if tr >= 1.0:
            self.escrever(
                "Atenção: T ≥ Tc — Lee-Kesler está sendo extrapolada.", "aviso"
            )
        elif tr < 0.3:
            self.escrever(
                "Atenção: Tr < 0,3 está fora da faixa recomendada (0,3 ≤ Tr < 1). "
                "A correlação tende a zero e o valor não é confiável — confirme se "
                "a temperatura está mesmo em kelvin.",
                "aviso",
            )

    def restaurar(self):
        self.modelo.set("antoine")
        self._modelo_anterior = "antoine"
        self.composto.set("água")
        self.temperatura.set("100")
        self._ao_trocar_modelo()
        super().restaurar()


# ------------------------------------------------ 2. equações de estado -----

class AbaEquacaoDeEstado(Aba):
    TITULO = "Equações de Estado"
    DESCRICAO = (
        "Calcula pressão a partir de (T, v) ou volume molar a partir de (T, P). "
        "Nas equações cúbicas, P < Psat seleciona a raiz de vapor."
    )

    MODELOS = (
        ("Gás Ideal", EquacaoDeEstado.GasIdeal),
        ("2º Coeficiente do Virial", EquacaoDeEstado.Virial),
        ("van der Waals", EquacaoDeEstado.VDW),
        ("Redlich-Kwong", EquacaoDeEstado.RK),
        ("Soave-Redlich-Kwong", EquacaoDeEstado.SRK),
        ("Peng-Robinson", EquacaoDeEstado.PR),
    )

    def _criar_variaveis(self):
        self.modelo = tk.StringVar(value="Soave-Redlich-Kwong")
        self.composto = tk.StringVar(value="metano")
        self.tipo = tk.StringVar(value="pressao")
        self.temperatura = tk.StringVar(value="300")
        self.volume = tk.StringVar(value="0.0249")
        self.pressao = tk.StringVar(value="101325")

    def _montar_formulario(self):
        self._campo("Modelo", self._criar_combo(self.modelo, [n for n, _ in self.MODELOS]))
        self._combo_composto = self._campo(
            "Composto", self._criar_combo_composto(self.composto)
        )
        self._campo("Temperatura", self._criar_entrada(self.temperatura, "K"))

        linha = ttk.Frame(self.formulario)
        linha.grid(row=self._linha, column=0, columnspan=2, sticky="w", pady=(6, 6))
        self._linha += 1
        for valor, texto in (("pressao", "Calcular pressão"), ("volume", "Calcular volume")):
            ttk.Radiobutton(
                linha,
                text=texto,
                value=valor,
                variable=self.tipo,
                command=self._ao_trocar_tipo,
            ).pack(side="left", padx=(0, 18))

        quadro_volume = self._criar_entrada(self.volume, "m³/mol", largura=16)
        self._campo("Volume molar", quadro_volume)
        self._entrada_volume = quadro_volume.entrada

        quadro_pressao = self._criar_entrada(self.pressao, "Pa", largura=16)
        self._campo("Pressão", quadro_pressao)
        self._entrada_pressao = quadro_pressao.entrada

        self.modelo.trace_add("write", lambda *_: self._ao_trocar_modelo())
        self._linha_botoes()
        self._ao_trocar_tipo()
        self._ao_trocar_modelo()

    def _ao_trocar_tipo(self):
        calcula_pressao = self.tipo.get() == "pressao"
        self._habilitar(self._entrada_volume, calcula_pressao)
        self._habilitar(self._entrada_pressao, not calcula_pressao)

    def _ao_trocar_modelo(self):
        try:
            classe = dict(self.MODELOS)[self.modelo.get()]
        except KeyError:
            return
        self._habilitar(self._combo_composto, classe.EXIGE_DADOS_CRITICOS)

    def _classe(self):
        try:
            return dict(self.MODELOS)[self.modelo.get()]
        except KeyError:
            raise ErroEntrada(f"Modelo desconhecido: {self.modelo.get()!r}.") from None

    def calcular(self):
        classe = self._classe()
        modelo = classe()
        if modelo.EXIGE_DADOS_CRITICOS:
            substancia = self.obter_composto(self.composto, "criticos")
            modelo.buscarPuras(substancia.nome)
            nome = substancia.nome
        else:
            nome = "gás ideal"

        temperatura = self.obter_numero(self.temperatura, "a temperatura", positivo=True)
        modelo.temperatura = temperatura

        self.escrever(f"{modelo.NOME} — {nome}", "titulo")

        if self.tipo.get() == "pressao":
            modelo.volume_molar = self.obter_numero(
                self.volume, "o volume molar", positivo=True
            )
            pressao = modelo.calcularPressao()
            self.escrever(f"{_formatar_numero(pressao)} Pa", "valor")
            self.escrever()
            self.escrever(f"{pressao / 1e5:.6f} bar")
            self.escrever(f"T = {temperatura:.2f} K", "detalhe")
            self.escrever(f"v = {modelo.volume_molar:.6e} m³/mol", "detalhe")
            fator = modelo.fator_compressibilidade()
            if fator is not None:
                self.escrever(f"Z = {fator:.6f}", "detalhe")
            return

        modelo.pressao = self.obter_numero(self.pressao, "a pressão", positivo=True)
        volume = modelo.calcularVolumeMolar()
        raizes = modelo.raizes_volume

        self.escrever(f"{volume:.6e} m³/mol", "valor")
        self.escrever()
        if len(raizes) > 1:
            vapor = max(raizes)
            liquido = min(raizes)
            escolhida = "vapor" if abs(volume - vapor) <= abs(volume - liquido) else "líquido"
            self.escrever(f"Raiz adotada: {escolhida}")
            self.escrever(f"Vapor saturado:   {vapor:.6e} m³/mol", "detalhe")
            self.escrever(f"Líquido saturado: {liquido:.6e} m³/mol", "detalhe")
        self.escrever(f"T = {temperatura:.2f} K", "detalhe")
        self.escrever(f"P = {modelo.pressao:,.0f} Pa".replace(",", " "), "detalhe")
        fator = modelo.fator_compressibilidade()
        if fator is not None:
            self.escrever(f"Z = {fator:.6f}", "detalhe")

    def restaurar(self):
        self.modelo.set("Soave-Redlich-Kwong")
        self.composto.set("metano")
        self.tipo.set("pressao")
        self.temperatura.set("300")
        self.volume.set("0.0249")
        self.pressao.set("101325")
        self._ao_trocar_tipo()
        self._ao_trocar_modelo()
        super().restaurar()


# ------------------------------------------------------- 3. equipamentos ----

class AbaEquipamentos(Aba):
    TITULO = "Aplicações em equipamentos"
    DESCRICAO = (
        "Variação de entalpia e entropia entre entrada e saída "
        "(propriedades residuais por SRK + Cp de gás ideal)."
    )

    def _criar_variaveis(self):
        self.equipamento = tk.StringVar(value="1")
        self.composto = tk.StringVar(value="metano")
        self.pressao1 = tk.StringVar(value="100000")
        self.temperatura1 = tk.StringVar(value="300")
        self.pressao2 = tk.StringVar(value="500000")
        self.temperatura2 = tk.StringVar(value="600")

    def _montar_formulario(self):
        linha = ttk.Frame(self.formulario)
        linha.grid(row=self._linha, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._linha += 1
        for valor, texto in (("1", "Compressor"), ("2", "Turbina")):
            ttk.Radiobutton(
                linha, text=texto, value=valor, variable=self.equipamento
            ).pack(side="left", padx=(0, 18))

        self._campo("Composto", self._criar_combo_composto(self.composto))
        self._campo("Pressão de entrada", self._criar_entrada(self.pressao1, "Pa"))
        self._campo("Temperatura de entrada", self._criar_entrada(self.temperatura1, "K"))
        self._campo("Pressão de saída", self._criar_entrada(self.pressao2, "Pa"))
        self._campo("Temperatura de saída", self._criar_entrada(self.temperatura2, "K"))
        self._linha_botoes()

    def calcular(self):
        substancia = self.obter_composto(self.composto, "criticos")
        modelo = residuais.PropriedadesResiduais()
        modelo.equipamento = int(self.equipamento.get())
        modelo.composto = substancia.nome
        modelo.pressao_inicial = self.obter_numero(
            self.pressao1, "a pressão de entrada", positivo=True
        )
        modelo.temperatura_inicial = self.obter_numero(
            self.temperatura1, "a temperatura de entrada", positivo=True
        )
        modelo.pressao_final = self.obter_numero(
            self.pressao2, "a pressão de saída", positivo=True
        )
        modelo.temperatura_final = self.obter_numero(
            self.temperatura2, "a temperatura de saída", positivo=True
        )

        resultado = modelo.calcularResidual()
        nome_equipamento = modelo.EQUIPAMENTOS[modelo.equipamento]

        self.escrever(f"{nome_equipamento} — {substancia.nome}", "titulo")
        self.escrever(f"W = ΔH = {resultado.trabalho:,.2f} J/mol".replace(",", " "), "valor")
        self.escrever(f"ΔS = {resultado.delta_s:,.3f} J/(mol·K)".replace(",", " "), "valor")
        self.escrever()

        if modelo.viola_primeira_lei(resultado):
            self.escrever(
                "Viola a 1ª lei da termodinâmica para este equipamento.", "erro"
            )
            return

        if resultado.delta_s < 0.0:
            self.escrever("Processo impossível (ΔS < 0).", "erro")
        elif abs(resultado.delta_s) < 1e-9:
            self.escrever("Processo possível e reversível (ΔS = 0).", "ok")
        else:
            self.escrever("Processo possível e irreversível (ΔS > 0).", "ok")

        self.escrever()
        self.escrever(
            f"Entrada: {modelo.pressao_inicial / 1e5:.4f} bar, "
            f"{modelo.temperatura_inicial:.2f} K",
            "detalhe",
        )
        self.escrever(
            f"Saída:   {modelo.pressao_final / 1e5:.4f} bar, "
            f"{modelo.temperatura_final:.2f} K",
            "detalhe",
        )

    def restaurar(self):
        self.equipamento.set("1")
        self.composto.set("metano")
        self.pressao1.set("100000")
        self.temperatura1.set("300")
        self.pressao2.set("500000")
        self.temperatura2.set("600")
        super().restaurar()


# -------------------------------------------------------- 4. fugacidade -----

class AbaFugacidade(Aba):
    TITULO = "Coeficiente de Fugacidade"
    DESCRICAO = (
        "Espécie pura pela equação SRK; mistura binária pelo segundo "
        "coeficiente do virial."
    )

    def _criar_variaveis(self):
        self.tipo = tk.StringVar(value="pura")
        self.composto1 = tk.StringVar(value="metano")
        self.composto2 = tk.StringVar(value="etano")
        self.temperatura = tk.StringVar(value="300")
        self.pressao = tk.StringVar(value="3000000")
        self.fracao1 = tk.StringVar(value="0.4")
        self.fracao2 = tk.StringVar(value="0.6")

    def _montar_formulario(self):
        linha = ttk.Frame(self.formulario)
        linha.grid(row=self._linha, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._linha += 1
        for valor, texto in (("pura", "Espécie pura"), ("mistura", "Mistura binária")):
            ttk.Radiobutton(
                linha,
                text=texto,
                value=valor,
                variable=self.tipo,
                command=self._ao_trocar_tipo,
            ).pack(side="left", padx=(0, 18))

        self._campo("Composto 1", self._criar_combo_composto(self.composto1))
        self._campo("Temperatura", self._criar_entrada(self.temperatura, "K"))
        self._campo("Pressão", self._criar_entrada(self.pressao, "Pa"))

        self.quadro_mistura = self._grupo()
        self._campo_grupo(
            self.quadro_mistura,
            0,
            "Composto 2",
            self._criar_combo_composto(self.composto2, mestre=self.quadro_mistura),
        )
        self._campo_grupo(
            self.quadro_mistura,
            1,
            "Fração molar 1",
            self._criar_entrada(self.fracao1, largura=10, mestre=self.quadro_mistura),
        )
        self._campo_grupo(
            self.quadro_mistura,
            2,
            "Fração molar 2",
            self._criar_entrada(self.fracao2, largura=10, mestre=self.quadro_mistura),
        )

        self._linha_botoes()
        self._ao_trocar_tipo()

    def _ao_trocar_tipo(self):
        if self.tipo.get() == "mistura":
            self.quadro_mistura.grid()
        else:
            self.quadro_mistura.grid_remove()

    def calcular(self):
        temperatura = self.obter_numero(self.temperatura, "a temperatura", positivo=True)
        pressao = self.obter_numero(self.pressao, "a pressão", positivo=True)

        if self.tipo.get() == "pura":
            substancia = self.obter_composto(self.composto1, "criticos")
            modelo = CoeficienteDeFugacidade.CoefFugacidadePuras()
            modelo.composto = substancia.nome
            modelo.temperatura = temperatura
            modelo.pressao = pressao
            coeficiente = modelo.calcularFugacidade()

            self.escrever(f"Espécie pura (SRK) — {substancia.nome}", "titulo")
            self.escrever(f"φ = {coeficiente:.6f}", "valor")
            self.escrever()
            self.escrever(f"T = {temperatura:.2f} K", "detalhe")
            self.escrever(f"P = {pressao / 1e5:.4f} bar", "detalhe")
            return

        substancia1 = self.obter_composto(self.composto1, "criticos")
        substancia2 = self.obter_composto(self.composto2, "criticos")
        modelo = CoeficienteDeFugacidade.CoefFugacidadeMisturas()
        modelo.composto1 = substancia1.nome
        modelo.composto2 = substancia2.nome
        modelo.temperatura = temperatura
        modelo.pressao = pressao
        modelo.fracao_molar1 = self.obter_numero(self.fracao1, "a fração molar 1")
        modelo.fracao_molar2 = self.obter_numero(self.fracao2, "a fração molar 2")

        phi1, phi2 = modelo.calcularFugacidade()

        self.escrever(
            f"Mistura (virial) — {substancia1.nome} / {substancia2.nome}", "titulo"
        )
        self.escrever(f"φ1 = {phi1:.6f}", "valor")
        self.escrever(f"φ2 = {phi2:.6f}", "valor")
        self.escrever()
        self.escrever(f"T = {temperatura:.2f} K", "detalhe")
        self.escrever(f"P = {pressao / 1e5:.4f} bar", "detalhe")
        self.escrever(
            f"x1 = {modelo.fracao_molar1:.4f}, x2 = {modelo.fracao_molar2:.4f}",
            "detalhe",
        )

    def restaurar(self):
        self.tipo.set("pura")
        self.composto1.set("metano")
        self.composto2.set("etano")
        self.temperatura.set("300")
        self.pressao.set("3000000")
        self.fracao1.set("0.4")
        self.fracao2.set("0.6")
        self._ao_trocar_tipo()
        super().restaurar()


# --------------------------------------------------------------- 5. ELV -----

class AbaELV(Aba):
    TITULO = "Equilíbrio Líquido-Vapor"
    DESCRICAO = (
        "Pressão de bolha P = x1·γ1·P1sat + x2·γ2·P2sat com P1sat e P2sat por "
        "Antoine na temperatura informada (°C)."
    )

    def _criar_variaveis(self):
        self.modelo = tk.StringVar(value="Margules")
        self.composto1 = tk.StringVar(value="benzeno")
        self.composto2 = tk.StringVar(value="tolueno")
        self.temperatura = tk.StringVar(value="80")
        self.variacao = tk.StringVar(value="0.05")
        self.parametro1 = tk.StringVar(value="1.2")
        self.parametro2 = tk.StringVar(value="1.5")

    def _montar_formulario(self):
        combo = self._criar_combo(self.modelo, ["Margules", "Wilson"], largura=24)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._ao_trocar_modelo())
        self._campo("Modelo", combo)
        self._campo("Composto 1", self._criar_combo_composto(self.composto1))
        self._campo("Composto 2", self._criar_combo_composto(self.composto2))
        self._campo("Temperatura", self._criar_entrada(self.temperatura, "°C"))
        self._campo("Variação de x1", self._criar_entrada(self.variacao, largura=10))

        self.quadro_parametros = self._grupo()
        self._rotulo_parametro1 = self._campo_grupo(
            self.quadro_parametros,
            0,
            "A12",
            self._criar_entrada(
                self.parametro1, largura=10, mestre=self.quadro_parametros
            ),
        )
        self._rotulo_parametro2 = self._campo_grupo(
            self.quadro_parametros,
            1,
            "A21",
            self._criar_entrada(
                self.parametro2, largura=10, mestre=self.quadro_parametros
            ),
        )

        self._linha_botoes()
        self._ao_trocar_modelo()

    def _ao_trocar_modelo(self):
        margules = self.modelo.get() == "Margules"
        self._rotulo_parametro1.configure(text="A12" if margules else "Λ12")
        self._rotulo_parametro2.configure(text="A21" if margules else "Λ21")

    def _montar_resultado(self):
        self.painel_direito.rowconfigure(0, weight=3)
        self.painel_direito.rowconfigure(1, weight=2)

        self.quadro_grafico = ttk.LabelFrame(
            self.painel_direito, text="Diagrama P-x1-y1", padding=6
        )
        self.quadro_grafico.grid(row=0, column=0, sticky="nsew")
        self.quadro_grafico.columnconfigure(0, weight=1)
        self.quadro_grafico.rowconfigure(0, weight=1)
        self.grafico = GraficoPxy(self.quadro_grafico, altura=280)
        self.grafico.grid(row=0, column=0, sticky="nsew")

        self.legenda = ttk.Label(
            self.quadro_grafico,
            text="",
            style="Descricao.TLabel",
            anchor="w",
            wraplength=520,
        )
        self.legenda.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        quadro_tabela = ttk.LabelFrame(self.painel_direito, text="Pontos calculados", padding=6)
        quadro_tabela.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        quadro_tabela.columnconfigure(0, weight=1)
        quadro_tabela.rowconfigure(0, weight=1)

        self.tabela = ttk.Treeview(
            quadro_tabela, columns=("x1", "y1", "p"), show="headings", height=7
        )
        for coluna, texto, largura in (
            ("x1", "x1", 90),
            ("y1", "y1", 90),
            ("p", "P (kPa)", 110),
        ):
            self.tabela.heading(coluna, text=texto)
            self.tabela.column(coluna, width=largura, anchor="e")
        self.tabela.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(quadro_tabela, orient="vertical", command=self.tabela.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.tabela.configure(yscrollcommand=barra.set)

    def calcular(self):
        substancia1 = self.obter_composto(self.composto1, "antoine")
        substancia2 = self.obter_composto(self.composto2, "antoine")

        if self.modelo.get() == "Margules":
            modelo = ELV.Margules()
            modelo.a12 = self.obter_numero(self.parametro1, "A12")
            modelo.a21 = self.obter_numero(self.parametro2, "A21")
        else:
            modelo = ELV.Wilson()
            modelo.lambda12 = self.obter_numero(self.parametro1, "Λ12")
            modelo.lambda21 = self.obter_numero(self.parametro2, "Λ21")

        modelo.composto1 = substancia1.nome
        modelo.composto2 = substancia2.nome
        modelo.temperatura = self.obter_numero(self.temperatura, "a temperatura")
        modelo.variacao = self.obter_numero(self.variacao, "a variação de x1", positivo=True)

        xs, ys, pressoes = modelo.calcular()

        self.quadro_grafico.configure(
            text=f"Diagrama P-x1-y1 — {modelo.NOME}: "
            f"{substancia1.nome} / {substancia2.nome}"
        )
        self.grafico.desenhar(xs, ys, pressoes)

        if self.grafico.azeotropo is None:
            self.legenda.configure(
                text="Sem azeótropo: as curvas não se cruzam no interior do domínio."
            )
        else:
            pressao_azeotropo = self.grafico._interpolar(
                self.grafico.azeotropo, xs, pressoes
            )
            self.legenda.configure(
                text=f"Azeótropo em x1 = y1 ≈ {self.grafico.azeotropo:.3f} "
                f"(P ≈ {pressao_azeotropo / 1e3:.2f} kPa) — linha tracejada."
            )

        self.tabela.delete(*self.tabela.get_children())
        for x1, y1, pressao in zip(xs, ys, pressoes):
            self.tabela.insert(
                "", "end", values=(f"{x1:.3f}", f"{y1:.4f}", f"{pressao / 1e3:.4f}")
            )

        return (
            f"{len(xs)} pontos calculados — P de "
            f"{min(pressoes) / 1e3:.2f} a {max(pressoes) / 1e3:.2f} kPa."
        )

    def _reportar_erro(self, mensagem):
        self.app.erro(mensagem)
        if hasattr(self, "legenda"):
            self.legenda.configure(text="")
        self.grafico.mostrar_mensagem(mensagem)

    def limpar_resultado(self):
        if hasattr(self, "tabela"):
            self.tabela.delete(*self.tabela.get_children())
        if hasattr(self, "legenda"):
            self.legenda.configure(text="")
        if hasattr(self, "grafico"):
            self.grafico.limpar()

    def restaurar(self):
        self.modelo.set("Margules")
        self.composto1.set("benzeno")
        self.composto2.set("tolueno")
        self.temperatura.set("80")
        self.variacao.set("0.05")
        self.parametro1.set("1.2")
        self.parametro2.set("1.5")
        self._ao_trocar_modelo()
        super().restaurar()


# ------------------------------------------------------------ aplicação -----

class AplicacaoTermoPy(tk.Tk):
    """Janela principal com as cinco calculadoras em abas."""

    def __init__(self):
        super().__init__()
        self.title("TermoPy — Termodinâmica")
        self.geometry("1040x740")
        self.minsize(920, 660)
        self._centralizar(1040, 740)

        self._configurar_fontes()
        self._configurar_estilo()

        self.compostos = dados.nomes_disponiveis()
        self.abas = []

        self._criar_cabecalho()
        self._criar_abas()
        self._criar_status()
        self._criar_menu()

    # ---------------------------------------------------------- visual ---
    def _centralizar(self, largura, altura):
        """Coloca a janela no centro da tela."""
        largura_tela = self.winfo_screenwidth()
        altura_tela = self.winfo_screenheight()
        x = max(0, (largura_tela - largura) // 2)
        y = max(0, (altura_tela - altura) // 2 - 20)
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    def _configurar_fontes(self):
        base = tkfont.nametofont("TkDefaultFont")
        if base.cget("size") < 10:
            base.configure(size=10)
        self.fonte_padrao = base
        self.fonte_secao = base.copy()
        self.fonte_secao.configure(size=base.cget("size") + 1, weight="bold")
        self.fonte_valor = base.copy()
        self.fonte_valor.configure(size=base.cget("size") + 3, weight="bold")
        self.fonte_titulo = base.copy()
        self.fonte_titulo.configure(size=base.cget("size") + 6, weight="bold")
        self.option_add("*TCombobox*Listbox.font", base)

    def _configurar_estilo(self):
        estilo = ttk.Style(self)
        for tema in ("clam", "vista", "winnative", "default"):
            if tema in estilo.theme_names():
                estilo.theme_use(tema)
                break
        estilo.configure("Titulo.TLabel", font=self.fonte_secao, foreground=COR_PRIMARIA)
        estilo.configure("Descricao.TLabel", foreground=COR_TEXTO_SUAVE)
        estilo.configure("Unidade.TLabel", foreground=COR_TEXTO_SUAVE)
        estilo.configure("Acao.TButton", font=self.fonte_secao, padding=(16, 6))
        estilo.configure("TNotebook.Tab", padding=(16, 7))
        estilo.configure("Status.TLabel", foreground=COR_TEXTO_SUAVE)

    def _criar_cabecalho(self):
        faixa = tk.Frame(self, background=COR_PRIMARIA)
        faixa.pack(fill="x")
        tk.Label(
            faixa,
            text="TermoPy",
            font=self.fonte_titulo,
            background=COR_PRIMARIA,
            foreground="white",
            padx=16,
        ).pack(side="left", pady=(10, 6))
        tk.Label(
            faixa,
            text="Termodinâmica aplicada — pressão de saturação, equações de estado, "
            "propriedades residuais, fugacidade e ELV",
            background=COR_PRIMARIA,
            foreground="#d4e6f1",
            padx=12,
        ).pack(side="left", pady=(14, 10))

    def _criar_abas(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(10, 4))

        for classe in (
            AbaPressaoSaturacao,
            AbaEquacaoDeEstado,
            AbaEquipamentos,
            AbaFugacidade,
            AbaELV,
        ):
            aba = classe(notebook, self)
            notebook.add(aba, text=classe.TITULO)
            self.abas.append(aba)
        self.notebook = notebook

    def _criar_status(self):
        self.status = tk.StringVar(value="Pronto.")
        self._rotulo_status = ttk.Label(
            self,
            textvariable=self.status,
            style="Status.TLabel",
            anchor="w",
            padding=(14, 4),
        )
        self._rotulo_status.pack(fill="x", side="bottom")

    def _criar_menu(self):
        barra = tk.Menu(self)
        arquivo = tk.Menu(barra, tearoff=0)
        arquivo.add_command(label="Sair", accelerator="Ctrl+Q", command=self.destroy)
        barra.add_cascade(label="Arquivo", menu=arquivo)

        ajuda = tk.Menu(barra, tearoff=0)
        ajuda.add_command(label="Compostos disponíveis", command=self._mostrar_compostos)
        ajuda.add_command(label="Sobre", command=self._mostrar_sobre)
        barra.add_cascade(label="Ajuda", menu=ajuda)
        self.configure(menu=barra)
        self.bind_all("<Control-q>", lambda _e: self.destroy())

    # ---------------------------------------------------------- status ---
    def informar(self, mensagem):
        self.status.set(mensagem)
        self._rotulo_status.configure(foreground=COR_TEXTO_SUAVE)

    def erro(self, mensagem):
        self.status.set(mensagem)
        self._rotulo_status.configure(foreground=COR_ERRO)

    def limpar_status(self):
        self.status.set("Pronto.")
        self._rotulo_status.configure(foreground=COR_TEXTO_SUAVE)

    def criar_filtro_compostos(self, combo):
        """Preenche o combobox conforme o usuário digita (busca por substring)."""
        valores = self.compostos

        def filtrar(_evento=None):
            texto = combo.get().strip().lower()
            if len(texto) >= 2:
                encontrados = [nome for nome in valores if texto in nome.lower()]
                combo["values"] = encontrados or valores
            else:
                combo["values"] = valores

        return filtrar

    # ----------------------------------------------------------- ajuda ---
    def _mostrar_compostos(self):
        janela = tk.Toplevel(self)
        janela.title("Compostos disponíveis")
        janela.geometry("360x460")
        janela.transient(self)

        ttk.Label(
            janela,
            text=f"{len(self.compostos)} compostos na base de dados",
            style="Titulo.TLabel",
            padding=10,
        ).pack(anchor="w")

        quadro = ttk.Frame(janela, padding=(10, 0))
        quadro.pack(fill="both", expand=True)
        lista = tk.Listbox(quadro, activestyle="none")
        lista.pack(side="left", fill="both", expand=True)
        barra = ttk.Scrollbar(quadro, orient="vertical", command=lista.yview)
        barra.pack(side="right", fill="y")
        lista.configure(yscrollcommand=barra.set)
        for nome in self.compostos:
            lista.insert("end", nome)

    def _mostrar_sobre(self):
        messagebox.showinfo(
            "Sobre o TermoPy",
            "TermoPy — cálculo de propriedades termodinâmicas.\n\n"
            "Pressão de saturação (Antoine, Lee-Kesler), equações de estado "
            "(gás ideal, virial, vdW, RK, SRK, PR), propriedades residuais, "
            "coeficiente de fugacidade e ELV (Margules, Wilson).\n\n"
            "Interface Tkinter, sem dependências externas.",
            parent=self,
        )


def main():
    _ativar_dpi()
    app = AplicacaoTermoPy()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
