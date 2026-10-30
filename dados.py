# -*- coding: utf-8 -*-
"""Base de dados de compostos puros — fonte única de verdade.

Antes, as tabelas de propriedades críticas (``puras``) estavam duplicadas em
``EquacaoDeEstado`` e ``PressaodeSaturacao``, com nomes divergentes
(``isobutano``/``iso-butano``, ``metilciclohexano``/``metilciclo-hexano``), o
que fazia o mesmo composto ser encontrado em um módulo e não em outro.

Aqui os dados brutos (``_PURAS``, ``_ANTOINE``, ``_CP_IDEAL``) são convertidos
para unidades do SI e consolidados em ``Substancia``. A busca é feita por nome
normalizado (sem acentos, sem diferença de caixa), com apelidos.
"""
import unicodedata
from typing import Dict, Optional, Tuple

from utilidades import CompostoNaoEncontrado

#: Constante dos gases, J/(mol.K)
R = 8.314


class Substancia:
    """Propriedades de um composto puro (unidades do SI).

    Atributos ausentes valem ``None`` por falta de dado na fonte.
    """

    __slots__ = (
        "nome",
        "fator_acentrico",
        "temperatura_critica",
        "pressao_critica",
        "fator_compressibilidade_critico",
        "volume_molar_critico",
        "antoine",
        "cp_ideal",
    )

    def __init__(
        self,
        nome,
        fator_acentrico=None,
        temperatura_critica=None,
        pressao_critica=None,
        fator_compressibilidade_critico=None,
        volume_molar_critico=None,
        antoine=None,
        cp_ideal=None,
    ):
        self.nome = nome
        self.fator_acentrico = fator_acentrico
        self.temperatura_critica = temperatura_critica
        self.pressao_critica = pressao_critica
        self.fator_compressibilidade_critico = fator_compressibilidade_critico
        self.volume_molar_critico = volume_molar_critico
        #: (A, B, C) de Antoine -> ln(P/kPa) = A - B/(T/°C + C)
        self.antoine = antoine
        #: (A, B, C, D) tais que Cp/R = A + B*T + C*T^2 + D*T^-2
        self.cp_ideal = cp_ideal

    @property
    def tem_dados_criticos(self):
        return None not in (
            self.fator_acentrico,
            self.temperatura_critica,
            self.pressao_critica,
        )

    def __repr__(self):
        return f"Substancia({self.nome!r})"


# composto, fator acêntrico, Tc [K], Pc [bar], Zc, Vc [cm3/mol]
_PURAS = (
    ("metano", 0.012, 190.6, 45.99, 0.286, 98.6),
    ("etano", 0.1, 305.3, 48.72, 0.279, 145.5),
    ("propano", 0.152, 369.8, 42.48, 0.276, 200.0),
    ("n-butano", 0.2, 425.1, 37.96, 0.274, 255.0),
    # Zc do n-pentano era 0.7 na tabela original (erro de digitação; ~0.27).
    ("n-pentano", 0.252, 469.7, 33.7, 0.270, 313.0),
    ("n-hexano", 0.301, 507.6, 30.25, 0.266, 371.0),
    ("n-heptano", 0.35, 540.2, 27.4, 0.261, 428.0),
    ("n-octano", 0.4, 568.7, 24.9, 0.256, 486.0),
    ("n-nonano", 0.444, 594.6, 22.9, 0.252, 544.0),
    ("n-decano", 0.492, 617.7, 21.1, 0.247, 600.0),
    ("isobutano", 0.181, 408.1, 36.48, 0.282, 262.7),
    ("isooctano", 0.302, 544.0, 25.68, 0.266, 468.0),
    ("ciclopentano", 0.196, 511.8, 45.02, 0.273, 258.0),
    ("ciclo-hexano", 0.21, 553.6, 40.73, 0.273, 308.0),
    ("metilciclopentano", 0.23, 532.8, 37.85, 0.272, 319.0),
    ("metilciclohexano", 0.235, 572.2, 34.71, 0.269, 368.0),
    ("etileno", 0.087, 282.3, 50.4, 0.281, 131.0),
    ("propileno", 0.14, 365.6, 46.65, 0.289, 188.4),
    ("1-buteno", 0.191, 420.0, 40.43, 0.277, 239.3),
    ("cis-2-buteno", 0.205, 435.6, 42.43, 0.273, 233.8),
    ("trans-2-buteno", 0.218, 428.6, 41.0, 0.275, 237.7),
    ("1-hexeno", 0.28, 504.0, 31.4, 0.265, 354.0),
    ("isobutileno", 0.194, 417.9, 40.0, 0.275, 239.9),
    ("1,3-butadieno", 0.19, 425.2, 42.77, 0.267, 220.4),
    ("ciclo-hexeno", 0.212, 560.4, 43.5, 0.272, 291.0),
    ("acetileno", 0.187, 308.3, 61.39, 0.271, 113.0),
    ("benzeno", 0.21, 562.2, 48.98, 0.271, 259.0),
    ("tolueno", 0.262, 591.8, 41.06, 0.264, 316.0),
    ("etilbenzeno", 0.303, 617.2, 36.06, 0.263, 374.0),
    ("cumeno", 0.326, 631.1, 32.09, 0.261, 427.0),
    ("o-xileno", 0.31, 630.3, 37.34, 0.263, 369.0),
    ("m-xileno", 0.326, 617.1, 35.36, 0.259, 376.0),
    ("p-xileno", 0.322, 616.2, 35.11, 0.26, 379.0),
    ("estireno", 0.297, 636.0, 38.4, 0.256, 352.0),
    ("naftaleno", 0.302, 748.4, 40.51, 0.269, 413.0),
    ("bifenil", 0.365, 789.3, 38.5, 0.295, 502.0),
    ("formaldeído", 0.282, 408.0, 65.9, 0.223, 115.0),
    ("acetaldeído", 0.291, 466.0, 55.5, 0.221, 154.0),
    ("acetato de metila", 0.331, 506.6, 47.5, 0.257, 228.0),
    ("acetato de etila", 0.366, 523.3, 38.8, 0.255, 286.0),
    ("acetona", 0.307, 508.2, 47.01, 0.233, 209.0),
    ("metiletilcetona", 0.323, 535.5, 41.5, 0.249, 267.0),
    ("éter dietílico", 0.281, 466.7, 36.4, 0.263, 280.0),
    ("éter metil-t-butílico", 0.266, 497.1, 34.3, 0.273, 329.0),
    ("metanol", 0.564, 512.6, 80.97, 0.224, 118.0),
    ("etanol", 0.645, 513.9, 61.48, 0.24, 167.0),
    ("1-propanol", 0.622, 536.8, 51.75, 0.254, 219.0),
    ("1-butanol", 0.594, 563.1, 44.23, 0.26, 275.0),
    ("1-hexanol", 0.579, 611.4, 35.1, 0.263, 381.0),
    ("2-propanol", 0.668, 508.3, 47.62, 0.248, 220.0),
    ("fenol", 0.444, 694.3, 61.3, 0.243, 229.0),
    ("etileno glicol", 0.487, 719.7, 77.0, 0.246, 191.0),
    ("ácido acético", 0.467, 592.0, 57.86, 0.211, 179.7),
    ("ácido n-butírico", 0.681, 615.7, 40.64, 0.232, 291.7),
    ("ácido benzóico", 0.603, 751.0, 44.7, 0.246, 344.0),
    ("acetonitrila", 0.338, 545.5, 48.3, 0.184, 173.0),
    ("metilamina", 0.281, 430.1, 74.6, 0.321, 154.0),
    ("etilamina", 0.285, 456.2, 56.2, 0.307, 207.0),
    ("nitrometano", 0.348, 588.2, 63.1, 0.223, 173.0),
    ("tetracloreto de carbono", 0.193, 556.4, 45.6, 0.272, 276.0),
    ("clorofórmio", 0.222, 536.4, 54.72, 0.293, 239.0),
    ("diclorometano", 0.199, 510.0, 60.8, 0.265, 185.0),
    ("cloreto de metila", 0.153, 416.3, 66.8, 0.276, 143.0),
    ("cloreto de etila", 0.19, 460.4, 52.7, 0.275, 200.0),
    ("clorobenzeno", 0.25, 632.4, 45.2, 0.265, 308.0),
    ("tetrafluoroetano", 0.327, 374.2, 40.6, 0.258, 198.0),
    ("argônio", 0.0, 150.9, 48.98, 0.291, 74.6),
    ("criptônio", 0.0, 209.4, 55.02, 0.288, 91.2),
    ("xenônio", 0.0, 289.7, 58.4, 0.286, 118.0),
    ("hélio", -0.39, 5.2, 2.28, 0.302, 57.3),
    ("hidrogênio", -0.216, 33.19, 13.13, 0.305, 64.1),
    ("oxigênio", 0.022, 154.6, 50.43, 0.288, 73.4),
    ("nitrogênio", 0.038, 126.2, 34.0, 0.289, 89.2),
    ("ar", 0.035, 132.2, 37.45, 0.289, 84.8),
    ("cloro", 0.069, 417.2, 77.1, 0.265, 124.0),
    ("monóxido de carbono", 0.048, 132.9, 34.99, 0.299, 93.4),
    ("dióxido de carbono", 0.224, 304.2, 73.83, 0.274, 94.0),
    ("dissulfeto de carbono", 0.111, 552.0, 79.0, 0.275, 160.0),
    ("sulfeto de hidrogênio", 0.094, 373.5, 89.63, 0.284, 98.5),
    ("dióxido de enxofre", 0.245, 430.8, 78.84, 0.269, 122.0),
    ("trióxido de enxofre", 0.424, 490.9, 82.1, 0.255, 127.0),
    ("óxido nítrico", 0.583, 180.2, 64.8, 0.251, 58.0),
    ("óxido nitroso", 0.141, 309.6, 72.45, 0.274, 97.4),
    ("cloreto de hidrogênio", 0.132, 324.7, 83.1, 0.249, 81.0),
    ("cianeto de hidrogênio", 0.41, 456.7, 53.9, 0.197, 139.0),
    ("água", 0.345, 647.1, 220.55, 0.229, 55.9),
    ("amônia", 0.253, 405.7, 112.8, 0.242, 72.5),
    ("ácido nítrico", 0.714, 520.0, 68.9, 0.231, 145.0),
    ("ácido sulfúrico", 0.0, 924.0, 64.0, 0.147, 177.0),
)

# composto, A, B, C  (P em kPa, T em °C)
_ANTOINE = (
    ("acetona", 14.3145, 2756.22, 228.06),
    ("ácido acético", 15.0717, 3580.8, 224.65),
    ("acetonitrila", 14.895, 3413.1, 250.523),
    ("benzeno", 13.7819, 2726.81, 217.572),
    ("iso-butano", 13.8254, 2181.79, 248.87),
    ("n-butano", 13.6608, 2154.7, 238.789),
    ("1-butanol", 15.3144, 3212.43, 182.739),
    ("2-butanol", 15.1989, 3026.03, 186.5),
    ("iso-butanol", 14.6047, 2740.95, 166.67),
    ("tert-butanol", 14.8445, 2658.29, 177.65),
    ("tetracloreto de carbono", 14.0572, 2914.23, 232.148),
    ("clorobenzeno", 13.8635, 3174.78, 211.7),
    ("1-clorobutano", 13.7965, 2723.73, 218.265),
    ("clorofórmio", 13.7324, 2548.74, 218.552),
    ("ciclo-hexano", 13.6568, 2723.44, 220.618),
    ("ciclopentano", 13.9727, 2653.9, 234.51),
    ("n-decano", 13.9748, 3442.76, 193.858),
    ("diclorometano", 13.9891, 2463.93, 223.24),
    ("éter dietílico", 14.0735, 2511.29, 231.2),
    ("1,4-dioxano", 15.0967, 3579.78, 240.337),
    ("n-eicosano", 14.4575, 4680.46, 132.1),
    ("etanol", 16.8958, 3795.17, 230.918),
    ("etilbenzeno", 13.9726, 3259.93, 212.3),
    ("etileno glicol", 15.7567, 4187.46, 178.65),
    ("n-heptano", 13.8622, 2910.26, 216.432),
    ("n-hexano", 13.8193, 2696.04, 224.317),
    ("metanol", 16.5785, 3638.27, 239.5),
    ("acetato de metila", 14.2456, 2662.78, 219.69),
    ("metiletilcetona", 14.1334, 2838.24, 218.69),
    ("nitrometano", 14.7513, 3331.7, 227.6),
    ("n-nonano", 13.9854, 3311.19, 202.694),
    ("iso-octano", 13.6703, 2896.31, 220.767),
    ("n-octano", 13.9346, 3123.13, 209.635),
    ("n-pentano", 13.7667, 2451.88, 232.014),
    ("fenol", 14.4387, 3507.8, 175.4),
    ("1-propanol", 16.1154, 3483.67, 205.807),
    ("2-propanol", 16.6796, 3640.2, 219.61),
    ("tolueno", 13.932, 3056.96, 217.625),
    ("água", 16.3872, 3885.7, 230.17),
    ("o-xileno", 14.0415, 3358.79, 212.041),
    ("m-xileno", 14.1387, 3381.81, 216.12),
    ("p-xileno", 14.0579, 3331.45, 214.627),
)

# composto, A, B, C, D  (Cp/R = A + B*T + C*T^2 + D*T^-2, forma tabelada)
_CP_IDEAL = (
    ("metano", 1.702, 9.081, -2.164, 0.0),
    ("etano", 1.131, 19.225, -5.561, 0.0),
    ("propano", 1.213, 28.785, -8.824, 0.0),
    ("n-butano", 1.935, 36.915, -11.402, 0.0),
    ("iso-butano", 1.677, 37.853, -11.945, 0.0),
    ("n-pentano", 2.464, 45.351, -14.111, 0.0),
    ("n-hexano", 3.025, 53.722, -16.791, 0.0),
    ("n-heptano", 3.570, 62.127, -19.486, 0.0),
    ("n-octano", 4.108, 70.567, -22.208, 0.0),
    ("etileno", 1.424, 14.394, -4.392, 0.0),
    ("propileno", 1.637, 22.706, -6.915, 0.0),
    ("1-buteno", 1.967, 31.630, -9.873, 0.0),
    ("1-penteno", 2.691, 39.753, -12.447, 0.0),
    ("1-hexeno", 3.220, 48.189, -15.157, 0.0),
    ("1-hepteno", 3.768, 56.588, -17.847, 0.0),
    ("1-octeno", 4.324, 64.960, -20.521, 0.0),
    ("acetaldeído", 1.693, 17.978, -6.158, 0.0),
    ("acetileno", 6.132, 1.952, 0.0, -1.299),
    ("benzeno", -0.206, 39.064, -13.301, 0.0),
    ("1,3-butadieno", 2.734, 26.786, -8.882, 0.0),
    ("ciclo-hexano", -3.876, 63.249, -20.928, 0.0),
    ("etanol", 3.518, 20.001, -6.002, 0.0),
    ("etilbenzeno", 1.124, 55.380, -18.476, 0.0),
    ("óxido de etileno", -0.385, 22.463, -9.296, 0.0),
    ("formaldeído", 2.264, 7.022, -1.877, 0.0),
    ("metanol", 2.211, 12.216, -3.450, 0.0),
    ("estireno", 2.050, 50.192, -16.662, 0.0),
    ("tolueno", 0.290, 47.052, -15.716, 0.0),
    ("ar", 3.355, 0.575, 0.0, -0.016),
    ("amônia", 3.578, 3.020, 0.0, -0.186),
    ("bromo", 4.493, 0.056, 0.0, -0.154),
    ("monóxido de carbono", 3.376, 0.557, 0.0, -0.031),
    ("dióxido de carbono", 5.457, 1.045, 0.0, -1.157),
    ("dissulfeto de carbono", 6.311, 0.805, 0.0, -0.906),
    ("cloro", 4.442, 0.089, 0.0, -0.344),
    ("hidrogênio", 3.249, 0.422, 0.0, 0.083),
    # A tabela original traz "dissulfeto de hidrogênio", mas os coeficientes
    # são os do H2S (dissulfeto de carbono já está listado acima).
    ("sulfeto de hidrogênio", 3.931, 1.490, 0.0, -0.232),
    ("cloreto de hidrogênio", 3.156, 0.623, 0.0, 0.151),
    ("cianeto de hidrogênio", 4.736, 1.359, 0.0, -0.725),
    ("nitrogênio", 3.280, 0.593, 0.0, 0.040),
    ("óxido nitroso", 5.328, 1.214, 0.0, -0.928),
    ("óxido nítrico", 3.387, 0.629, 0.0, 0.014),
    ("dióxido de nitrogênio", 4.982, 1.195, 0.0, -0.792),
    ("tetraóxido de dinitrogênio", 11.660, 2.257, 0.0, -2.787),
    ("oxigênio", 3.639, 0.506, 0.0, -0.227),
    ("dióxido de enxofre", 5.699, 0.801, 0.0, -1.015),
    ("trióxido de enxofre", 8.060, 1.056, 0.0, -2.028),
    ("água", 3.470, 1.450, 0.0, 0.121),
)

#: Grafias alternativas aceitas na busca (a chave é normalizada).
_APELIDOS = {
    "butano": "n-butano",
    "pentano": "n-pentano",
    "hexano": "n-hexano",
    "heptano": "n-heptano",
    "octano": "n-octano",
    "nonano": "n-nonano",
    "decano": "n-decano",
    "mtbe": "éter metil-t-butílico",
    "tce": "tetracloreto de carbono",
    "dietil eter": "éter dietílico",
    "metil ciclo hexano": "metilciclohexano",
    "metil ciclo pentano": "metilciclopentano",
}


def normalizar(nome):
    """Normaliza um nome: sem acentos, minúsculo, espaços simples."""
    texto = unicodedata.normalize("NFKD", str(nome).strip().lower())
    texto = "".join(
        caractere for caractere in texto if not unicodedata.combining(caractere)
    )
    return " ".join(texto.replace("_", " ").split())


def _compacta(nome):
    """Chave secundária que ignora hífens e espaços.

    Torna ``metilciclo-hexano`` e ``metilciclohexano`` equivalentes, assim como
    ``iso-butano`` e ``isobutano`` — divergências que existiam entre as tabelas
    originais.
    """
    return normalizar(nome).replace("-", "").replace(" ", "")


def _construir_base():
    registros: Dict[str, dict] = {}

    def registro(nome):
        # A chave é a forma compacta para que "iso-butano" e "isobutano"
        # sejam o mesmo composto (as tabelas originais divergiam).
        chave = _compacta(nome)
        return registros.setdefault(chave, {"nome": nome.strip()})

    for nome, omega, tc, pc_bar, zc, vc_cm3 in _PURAS:
        registro(nome).update(
            fator_acentrico=omega,
            temperatura_critica=tc,
            pressao_critica=pc_bar * 1e5,
            fator_compressibilidade_critico=zc,
            volume_molar_critico=vc_cm3 * 1e-6,
        )

    for nome, a, b, c in _ANTOINE:
        registro(nome)["antoine"] = (a, b, c)

    for nome, a, b, c, d in _CP_IDEAL:
        # Cp/R = A + B*T + C*T^2 + D*T^-2 com B, C e D já nas unidades de T [K].
        registro(nome)["cp_ideal"] = (a, b * 1e-3, c * 1e-6, d * 1e5)

    base: Dict[str, Substancia] = {}
    for chave, valores in registros.items():
        substancia = Substancia(**valores)
        base[chave] = substancia
        base[normalizar(chave)] = substancia

    for apelido, alvo in _APELIDOS.items():
        substancia = base.get(normalizar(alvo)) or base.get(_compacta(alvo))
        if substancia is None:
            continue
        for chave in (normalizar(apelido), _compacta(apelido)):
            base.setdefault(chave, substancia)
    return base


#: Mapa nome-normalizado -> :class:`Substancia`
SUBSTANCIAS: Dict[str, Substancia] = _construir_base()


def buscar(nome: str) -> Optional[Substancia]:
    """Retorna a substância ou ``None`` se o nome não existir."""
    if not nome:
        return None
    return SUBSTANCIAS.get(normalizar(nome)) or SUBSTANCIAS.get(_compacta(nome))


def exigir(nome: str) -> Substancia:
    """Como :func:`buscar`, mas levanta :class:`CompostoNaoEncontrado`."""
    substancia = buscar(nome)
    if substancia is None:
        raise CompostoNaoEncontrado(nome, len(nomes_disponiveis()))
    return substancia


def nomes_disponiveis() -> Tuple[str, ...]:
    """Nomes canônicos, ordenados alfabeticamente."""
    return tuple(sorted({substancia.nome for substancia in SUBSTANCIAS.values()}))
