"""
charts.py
----------
Módulo responsável por gerar automaticamente os gráficos mais adequados
para o dataset carregado, com base nos tipos de coluna identificados
pelo analyzer.py.

Cada gráfico é retornado como um dicionário Plotly (data + layout) pronto
para ser serializado em JSON e renderizado no front-end com Plotly.js
(`Plotly.newPlot(elementId, chart.figure.data, chart.figure.layout)`).

Uso básico:

    from utils.analyzer import DatasetAnalyzer
    from utils.charts import ChartGenerator

    analyzer = DatasetAnalyzer("uploads/meu_arquivo.csv")
    column_types = analyzer.classify_columns()

    charts = ChartGenerator(analyzer.df, column_types)
    resultado = charts.generate_all()
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Paleta consistente com o tema escuro do dashboard (definida aqui para que
# todos os gráficos, sem exceção, saiam com a mesma identidade visual).
THEME = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font_color": "#e2e8f0",
    "gridcolor": "rgba(148, 163, 184, 0.15)",
    "colorway": [
        "#6366f1", "#22d3ee", "#f472b6", "#fbbf24",
        "#34d399", "#a78bfa", "#fb7185", "#60a5fa",
    ],
}

# Limites para manter o dashboard enxuto — nada de gerar 40 gráficos
# só porque o dataset tem 40 colunas categóricas.
MAX_BAR_CHARTS = 4
MAX_PIE_CHARTS = 2
MAX_HISTOGRAMS = 4
MAX_CATEGORY_SLOTS = 10  # categorias exibidas antes de agrupar em "Outros"


class ChartGenerator:
    """Gera gráficos automaticamente a partir de um DataFrame já
    classificado por tipo de coluna (numeric / categorical / datetime /
    boolean — ver DatasetAnalyzer.classify_columns).
    """

    def __init__(self, df: pd.DataFrame, column_types: dict[str, str]):
        self.df = df
        self.column_types = column_types

        self.numeric_cols = [c for c, t in column_types.items() if t == "numeric"]
        self.categorical_cols = [c for c, t in column_types.items() if t == "categorical"]
        self.datetime_cols = [c for c, t in column_types.items() if t == "datetime"]

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _apply_theme(self, fig: go.Figure) -> go.Figure:
        fig.update_layout(
            paper_bgcolor=THEME["paper_bgcolor"],
            plot_bgcolor=THEME["plot_bgcolor"],
            font_color=THEME["font_color"],
            colorway=THEME["colorway"],
            margin=dict(l=40, r=20, t=50, b=40),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        fig.update_xaxes(gridcolor=THEME["gridcolor"], zerolinecolor=THEME["gridcolor"])
        fig.update_yaxes(gridcolor=THEME["gridcolor"], zerolinecolor=THEME["gridcolor"])
        return fig

    @staticmethod
    def _fig_to_dict(fig: go.Figure) -> dict[str, Any]:
        """Converte a figura para um dict 100% serializável em JSON
        (usa o encoder do próprio Plotly, que sabe lidar com numpy/pandas).
        """
        return json.loads(fig.to_json())

    def _package(self, chart_id: str, title: str, chart_type: str, fig: go.Figure) -> dict[str, Any]:
        return {
            "id": chart_id,
            "title": title,
            "chart_type": chart_type,
            "figure": self._fig_to_dict(self._apply_theme(fig)),
        }

    def _cardinality(self, col: str) -> int:
        return int(self.df[col].nunique(dropna=True))

    # ------------------------------------------------------------------ #
    # Gráfico de barras (categórica x contagem)
    # ------------------------------------------------------------------ #
    def bar_chart(self, column: str, top_n: int = MAX_CATEGORY_SLOTS) -> dict[str, Any]:
        counts = self.df[column].value_counts(dropna=True).head(top_n)
        fig = px.bar(
            x=counts.index.astype(str),
            y=counts.values,
            labels={"x": column, "y": "Contagem"},
        )
        fig.update_traces(marker_line_width=0)
        return self._package(f"bar_{column}", f"Distribuição de {column}", "bar", fig)

    # ------------------------------------------------------------------ #
    # Histograma (distribuição numérica)
    # ------------------------------------------------------------------ #
    def histogram(self, column: str, bins: int = 30) -> dict[str, Any]:
        fig = px.histogram(self.df, x=column, nbins=bins)
        fig.update_traces(marker_line_width=0)
        return self._package(f"hist_{column}", f"Distribuição de {column}", "histogram", fig)

    # ------------------------------------------------------------------ #
    # Pizza (proporção de categorias, agrupando o excedente em "Outros")
    # ------------------------------------------------------------------ #
    def pie_chart(self, column: str, top_n: int = 6) -> dict[str, Any]:
        counts = self.df[column].value_counts(dropna=True)

        if len(counts) > top_n:
            top = counts.head(top_n)
            outros = counts.iloc[top_n:].sum()
            counts = pd.concat([top, pd.Series({"Outros": outros})])

        fig = px.pie(names=counts.index.astype(str), values=counts.values, hole=0.45)
        return self._package(f"pie_{column}", f"Proporção de {column}", "pie", fig)

    # ------------------------------------------------------------------ #
    # Linha (série temporal: data x métrica numérica agregada)
    # ------------------------------------------------------------------ #
    def line_chart(self, date_col: str, value_col: str) -> dict[str, Any]:
        temp = self.df[[date_col, value_col]].copy()
        temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce", format="mixed")
        temp = temp.dropna(subset=[date_col])

        # Escolhe a granularidade de agregação conforme o intervalo de datas
        # coberto — evita um gráfico com milhares de pontos diários.
        span_days = (temp[date_col].max() - temp[date_col].min()).days if len(temp) else 0
        freq = "D" if span_days <= 60 else "W" if span_days <= 400 else "ME"

        grouped = (
            temp.set_index(date_col)[value_col]
            .resample(freq)
            .mean()
            .dropna()
            .reset_index()
        )

        fig = px.line(grouped, x=date_col, y=value_col, markers=True)
        return self._package(
            f"line_{date_col}_{value_col}",
            f"Evolução de {value_col} ao longo do tempo",
            "line",
            fig,
        )

    # ------------------------------------------------------------------ #
    # Scatter (relação entre duas colunas numéricas)
    # ------------------------------------------------------------------ #
    def scatter_plot(self, x_col: str, y_col: str) -> dict[str, Any]:
        fig = px.scatter(self.df, x=x_col, y=y_col, trendline="ols")
        return self._package(
            f"scatter_{x_col}_{y_col}", f"{x_col} vs {y_col}", "scatter", fig
        )

    # ------------------------------------------------------------------ #
    # Heatmap de correlação
    # ------------------------------------------------------------------ #
    def correlation_heatmap(self) -> dict[str, Any] | None:
        if len(self.numeric_cols) < 2:
            return None

        corr = self.df[self.numeric_cols].corr(numeric_only=True).round(2)
        fig = px.imshow(
            corr,
            text_auto=True,
            color_continuous_scale="RdBu_r",
            zmin=-1,
            zmax=1,
        )
        return self._package("correlation_heatmap", "Correlação entre variáveis", "heatmap", fig)

    # ------------------------------------------------------------------ #
    # Seleção automática — decide quais gráficos fazem sentido
    # ------------------------------------------------------------------ #
    def generate_all(self) -> list[dict[str, Any]]:
        charts: list[dict[str, Any]] = []

        # 1) Categóricas -> barras (e pizza quando a cardinalidade é baixa,
        #    porque pizza com 20 fatias não comunica nada).
        bar_count, pie_count = 0, 0
        for col in self.categorical_cols:
            cardinality = self._cardinality(col)
            if cardinality < 2:
                continue  # coluna constante, não gera gráfico

            if bar_count < MAX_BAR_CHARTS:
                charts.append(self.bar_chart(col))
                bar_count += 1

            if cardinality <= 8 and pie_count < MAX_PIE_CHARTS:
                charts.append(self.pie_chart(col))
                pie_count += 1

        # 2) Numéricas -> histogramas
        for col in self.numeric_cols[:MAX_HISTOGRAMS]:
            if self.df[col].dropna().empty:
                continue
            charts.append(self.histogram(col))

        # 3) Duas ou mais numéricas -> heatmap de correlação + scatter
        #    do par mais correlacionado (positiva ou negativamente).
        if len(self.numeric_cols) >= 2:
            heatmap = self.correlation_heatmap()
            if heatmap:
                charts.append(heatmap)

            corr_matrix = self.df[self.numeric_cols].corr(numeric_only=True).abs()
            # Remove a diagonal (correlação de cada coluna com ela mesma)
            for col in corr_matrix.columns:
                corr_matrix.loc[col, col] = 0

            if corr_matrix.to_numpy().max() > 0:
                col_x, col_y = corr_matrix.stack().idxmax()
                charts.append(self.scatter_plot(col_x, col_y))

        # 4) Data + numérica -> linha do tempo (usa a primeira coluna de
        #    cada tipo disponível, que costuma ser o par mais relevante).
        if self.datetime_cols and self.numeric_cols:
            charts.append(self.line_chart(self.datetime_cols[0], self.numeric_cols[0]))

        return charts


if __name__ == "__main__":
    # Teste manual rápido, reaproveitando o mesmo dataset de exemplo do
    # analyzer.py.
    import io
    from analyzer import DatasetAnalyzer

    csv_sample = io.StringIO(
        """nome,idade,salario,cidade,data_admissao
Ana,28,4500.50,São Paulo,2020-01-15
Bruno,34,6200.00,Rio de Janeiro,2019-03-22
Carla,31,5100.75,São Paulo,2021-07-01
Diego,45,15000.00,Curitiba,2018-11-30
Elaine,29,4800.00,São Paulo,2020-01-15
Fábio,29,4800.00,São Paulo,2020-06-20
"""
    )
    df_sample = pd.read_csv(csv_sample)
    analyzer = DatasetAnalyzer(df=df_sample)
    types = analyzer.classify_columns()

    generator = ChartGenerator(df_sample, types)
    all_charts = generator.generate_all()

    print(f"Gráficos gerados: {len(all_charts)}")
    for c in all_charts:
        print(f"- [{c['chart_type']}] {c['title']}")