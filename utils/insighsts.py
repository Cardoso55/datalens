"""
insights.py
------------
Módulo responsável por transformar os resultados numéricos da análise
(vindos do analyzer.py) em um resumo executivo em linguagem natural,
usando a API da Anthropic (Claude).

Importante: a IA NUNCA recebe o dataset bruto — apenas o resumo
estatístico já calculado pelo analyzer.py. Isso é mais barato, mais
rápido, evita estourar limite de tokens em datasets grandes, e evita
enviar dados potencialmente sensíveis do usuário para fora do necessário.

Uso básico:

    from utils.analyzer import DatasetAnalyzer
    from utils.insights import InsightsGenerator

    analyzer = DatasetAnalyzer("uploads/meu_arquivo.csv")
    resultado = analyzer.run_full_analysis()

    insights = InsightsGenerator()
    resumo = insights.generate(resultado)
"""

from __future__ import annotations

import os
from typing import Any

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


DEFAULT_MODEL = "claude-sonnet-5"


class InsightsGenerator:
    """Gera um resumo executivo em linguagem natural a partir do
    dicionário produzido por `DatasetAnalyzer.run_full_analysis()`.

    Se a API não estiver configurada (sem chave, sem pacote instalado,
    ou a chamada falhar), cai automaticamente em um modo local baseado
    em regras — assim o dashboard nunca fica "quebrado" numa demo ou
    numa avaliação de portfólio, mesmo sem internet ou cota de API.
    """

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

        if _ANTHROPIC_AVAILABLE and self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)

    # ------------------------------------------------------------------ #
    # Ponto de entrada principal
    # ------------------------------------------------------------------ #
    def generate(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Retorna um dict: {"summary": str, "source": "ai" | "fallback"}."""
        if self._client is not None:
            try:
                summary = self._generate_with_ai(analysis)
                return {"summary": summary, "source": "ai"}
            except Exception as e:  # noqa: BLE001
                # Nunca deixa a análise inteira falhar por causa da IA —
                # registra o erro e cai para o modo local.
                fallback = self._generate_fallback(analysis)
                return {
                    "summary": fallback,
                    "source": "fallback",
                    "error": str(e),
                }

        return {"summary": self._generate_fallback(analysis), "source": "fallback"}

    # ------------------------------------------------------------------ #
    # Construção do prompt
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_prompt(analysis: dict[str, Any]) -> str:
        general = analysis.get("general_info", {})
        kpis = analysis.get("kpis", {})
        quality = analysis.get("data_quality", {})
        stats = analysis.get("numeric_statistics", {})

        missing_pct = 0.0
        if general.get("rows") and general.get("columns"):
            total_cells = general["rows"] * general["columns"]
            if total_cells > 0:
                missing_pct = round((general.get("missing_values", 0) / total_cells) * 100, 1)

        lines = [
            "Você é um analista de dados. Com base no resumo estatístico abaixo "
            "(gerado automaticamente a partir de um CSV), escreva um resumo "
            "executivo curto (3 a 5 frases), em português do Brasil, em linguagem "
            "simples e direta, destacando: qualidade geral dos dados, principais "
            "problemas encontrados e uma recomendação prática. Não invente números "
            "que não estejam no resumo.",
            "",
            f"Linhas: {general.get('rows')}",
            f"Colunas: {general.get('columns')}",
            f"Percentual de valores ausentes: {missing_pct}%",
            f"Linhas duplicadas: {quality.get('duplicated_rows', 0)}",
            f"Colunas constantes (sem variação): {quality.get('constant_columns', [])}",
            f"Colunas com outliers: {quality.get('outlier_columns', {})}",
            f"Colunas com datas inválidas: {quality.get('invalid_date_columns', [])}",
            f"Colunas numéricas: {kpis.get('numeric_columns')}",
            f"Colunas categóricas: {kpis.get('categorical_columns')}",
        ]

        if stats:
            lines.append("Estatísticas por coluna numérica:")
            for col, s in stats.items():
                lines.append(
                    f"  - {col}: média={s['mean']}, mediana={s['median']}, "
                    f"min={s['min']}, max={s['max']}, desvio_padrao={s['std']}"
                )

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Chamada real à API
    # ------------------------------------------------------------------ #
    def _generate_with_ai(self, analysis: dict[str, Any]) -> str:
        prompt = self._build_prompt(analysis)

        response = self._client.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )

        # response.content é uma lista de blocos; concatenamos os de texto.
        text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return "\n".join(text_parts).strip()

    # ------------------------------------------------------------------ #
    # Modo local (sem IA) — baseado em regras
    # ------------------------------------------------------------------ #
    @staticmethod
    def _generate_fallback(analysis: dict[str, Any]) -> str:
        general = analysis.get("general_info", {})
        quality = analysis.get("data_quality", {})
        kpis = analysis.get("kpis", {})

        rows = general.get("rows", 0)
        cols = general.get("columns", 0)
        missing = general.get("missing_values", 0)
        duplicated = quality.get("duplicated_rows", 0)
        constant_cols = quality.get("constant_columns", [])
        outlier_cols = quality.get("outlier_columns", {})

        missing_pct = round((missing / (rows * cols)) * 100, 1) if rows and cols else 0.0

        # Qualidade geral, numa escala simples de 3 níveis
        if missing_pct < 2 and duplicated == 0:
            quality_phrase = "O conjunto de dados apresenta boa qualidade geral"
        elif missing_pct < 10 and duplicated < rows * 0.05:
            quality_phrase = "O conjunto de dados apresenta qualidade razoável, com alguns pontos de atenção"
        else:
            quality_phrase = "O conjunto de dados apresenta problemas relevantes de qualidade"

        sentences = [
            f"{quality_phrase}, com {rows} linhas e {cols} colunas "
            f"({kpis.get('numeric_columns', 0)} numéricas e {kpis.get('categorical_columns', 0)} categóricas)."
        ]

        if missing_pct > 0:
            sentences.append(f"Foram identificados {missing_pct}% de valores ausentes no total de células.")

        if duplicated > 0:
            sentences.append(f"Há {duplicated} linha(s) duplicada(s) que podem distorcer análises futuras.")

        if constant_cols:
            cols_str = ", ".join(constant_cols[:5])
            sentences.append(f"As colunas {cols_str} não variam e agregam pouco valor analítico.")

        if outlier_cols:
            top_outlier_col = max(outlier_cols, key=outlier_cols.get)
            sentences.append(
                f"A coluna '{top_outlier_col}' concentra o maior número de outliers "
                f"({outlier_cols[top_outlier_col]} registros) e merece uma investigação mais próxima."
            )

        needs_attention = missing_pct > 5 or duplicated > 0 or bool(outlier_cols) or bool(constant_cols)
        if needs_attention:
            sentences.append(
                "Recomenda-se tratar os pontos acima (valores ausentes, duplicados e/ou outliers) "
                "antes de usar este dataset em modelos de Machine Learning ou relatórios oficiais."
            )
        else:
            sentences.append("O dataset já está em condições adequadas para análises mais aprofundadas.")

        return " ".join(sentences)


if __name__ == "__main__":
    # Teste manual — roda só o modo fallback, já que não depende de API key.
    import io
    import json

    import pandas as pd
    from analyzer import DatasetAnalyzer

    csv_sample = io.StringIO(
        """nome,idade,salario,cidade,data_admissao
Ana,28,4500.50,São Paulo,2020-01-15
Bruno,34,6200.00,Rio de Janeiro,2019-03-22
Carla,,5100.75,São Paulo,2021-07-01
Diego,45,15000.00,Curitiba,2018-11-30
Elaine,29,4800.00,São Paulo,2020-01-15
Fábio,29,4800.00,São Paulo,2020-01-15
"""
    )
    df_sample = pd.read_csv(csv_sample)
    analysis_result = DatasetAnalyzer(df=df_sample).run_full_analysis()

    generator = InsightsGenerator(api_key=None)  # força o modo fallback
    result = generator.generate(analysis_result)

    print(json.dumps(result, indent=2, ensure_ascii=False))