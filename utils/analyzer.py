"""
analyzer.py
------------
Módulo responsável por analisar automaticamente qualquer dataset CSV
carregado pelo usuário: identifica tipos de coluna, calcula estatísticas,
gera KPIs e detecta problemas de qualidade dos dados.

Uso básico:

    from utils.analyzer import DatasetAnalyzer

    analyzer = DatasetAnalyzer("uploads/meu_arquivo.csv")
    resultado = analyzer.run_full_analysis()
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any


class DatasetAnalyzer:
    """Analisa um DataFrame do Pandas e extrai informações estruturadas
    prontas para serem consumidas pelo front-end (via JSON) ou por outros
    módulos (charts.py, insights.py).
    """

    def __init__(self, filepath: str | None = None, df: pd.DataFrame | None = None):
        if df is not None:
            self.df = df
        elif filepath is not None:
            self.df = self._read_csv(filepath)
        else:
            raise ValueError("Informe um 'filepath' ou um DataFrame já carregado.")

        # Classificação de colunas é usada por vários métodos, então
        # calculamos uma vez e guardamos em cache.
        self._column_types: dict[str, str] | None = None

    # ------------------------------------------------------------------ #
    # Leitura e preparação
    # ------------------------------------------------------------------ #
    @staticmethod
    def _read_csv(filepath: str) -> pd.DataFrame:
        """Lê o CSV tentando detectar automaticamente separador e encoding.

        Datasets do mundo real vêm com separadores (',' vs ';') e
        encodings (utf-8 vs latin-1) diferentes — detectar isso evita que
        o usuário precise configurar nada manualmente.
        """
        encodings = ["utf-8", "latin-1", "cp1252"]
        separators = [",", ";", "\t"]

        last_error: Exception | None = None
        for encoding in encodings:
            for sep in separators:
                try:
                    df = pd.read_csv(filepath, encoding=encoding, sep=sep)
                    # Heurística simples: se só detectou 1 coluna, o
                    # separador provavelmente está errado — tenta o próximo.
                    if df.shape[1] > 1:
                        return df
                except Exception as e:  # noqa: BLE001
                    last_error = e
                    continue

        # Último recurso: deixa o pandas tentar sozinho.
        try:
            return pd.read_csv(filepath)
        except Exception as e:  # noqa: BLE001
            raise ValueError(
                f"Não foi possível ler o CSV. Verifique o arquivo. Erro: {last_error or e}"
            )

    # ------------------------------------------------------------------ #
    # Classificação de colunas
    # ------------------------------------------------------------------ #
    def classify_columns(self) -> dict[str, str]:
        """Classifica cada coluna em: 'numeric', 'categorical', 'datetime'
        ou 'boolean'. Resultado é cacheado.
        """
        if self._column_types is not None:
            return self._column_types

        types: dict[str, str] = {}

        for col in self.df.columns:
            series = self.df[col]

            if pd.api.types.is_bool_dtype(series):
                types[col] = "boolean"
                continue

            if pd.api.types.is_numeric_dtype(series):
                types[col] = "numeric"
                continue

            if pd.api.types.is_datetime64_any_dtype(series):
                types[col] = "datetime"
                continue

            # Tenta converter para data — colunas de data em CSV quase
            # sempre chegam como string/object.
            if self._looks_like_date(series):
                types[col] = "datetime"
                continue

            types[col] = "categorical"

        self._column_types = types
        return types

    @staticmethod
    def _looks_like_date(series: pd.Series, sample_size: int = 20) -> bool:
        """Verifica heuristicamente se uma coluna de texto representa datas,
        sem forçar a conversão de todo o dataset (caro em datasets grandes).
        """
        sample = series.dropna().astype(str).head(sample_size)
        if sample.empty:
            return False

        try:
            parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        except (ValueError, TypeError):
            parsed = pd.to_datetime(sample, errors="coerce")

        # Se pelo menos 80% da amostra converteu com sucesso, tratamos
        # a coluna inteira como data.
        success_rate = parsed.notna().mean()
        return success_rate >= 0.8

    # ------------------------------------------------------------------ #
    # Informações gerais do dataset
    # ------------------------------------------------------------------ #
    def general_info(self) -> dict[str, Any]:
        return {
            "rows": int(self.df.shape[0]),
            "columns": int(self.df.shape[1]),
            "memory_usage_kb": round(self.df.memory_usage(deep=True).sum() / 1024, 2),
            "missing_values": int(self.df.isna().sum().sum()),
            "duplicated_rows": int(self.df.duplicated().sum()),
            "column_names": list(self.df.columns),
        }

    # ------------------------------------------------------------------ #
    # KPIs (para os cards do dashboard)
    # ------------------------------------------------------------------ #
    def kpis(self) -> dict[str, Any]:
        types = self.classify_columns()
        numeric_cols = [c for c, t in types.items() if t == "numeric"]
        categorical_cols = [c for c, t in types.items() if t == "categorical"]

        return {
            "total_records": int(self.df.shape[0]),
            "total_columns": int(self.df.shape[1]),
            "missing_values": int(self.df.isna().sum().sum()),
            "duplicated_rows": int(self.df.duplicated().sum()),
            "numeric_columns": len(numeric_cols),
            "categorical_columns": len(categorical_cols),
        }

    # ------------------------------------------------------------------ #
    # Estatísticas automáticas (colunas numéricas)
    # ------------------------------------------------------------------ #
    def numeric_statistics(self) -> dict[str, dict[str, Any]]:
        types = self.classify_columns()
        numeric_cols = [c for c, t in types.items() if t == "numeric"]

        stats: dict[str, dict[str, Any]] = {}
        for col in numeric_cols:
            series = self.df[col].dropna()
            if series.empty:
                continue

            mode = series.mode()
            stats[col] = {
                "mean": round(float(series.mean()), 2),
                "median": round(float(series.median()), 2),
                "mode": round(float(mode.iloc[0]), 2) if not mode.empty else None,
                "min": round(float(series.min()), 2),
                "max": round(float(series.max()), 2),
                "std": round(float(series.std()), 2) if len(series) > 1 else 0.0,
                "q1": round(float(series.quantile(0.25)), 2),
                "q3": round(float(series.quantile(0.75)), 2),
            }
        return stats

    # ------------------------------------------------------------------ #
    # Qualidade dos dados
    # ------------------------------------------------------------------ #
    def data_quality(self) -> dict[str, Any]:
        types = self.classify_columns()
        report: dict[str, Any] = {
            "missing_values_by_column": {},
            "duplicated_rows": int(self.df.duplicated().sum()),
            "constant_columns": [],
            "outlier_columns": {},
            "invalid_date_columns": [],
        }

        # Valores nulos por coluna (só reporta colunas que têm algum nulo)
        missing = self.df.isna().sum()
        report["missing_values_by_column"] = {
            col: int(count) for col, count in missing.items() if count > 0
        }

        # Colunas constantes (mesmo valor em todas as linhas -> pouco úteis)
        for col in self.df.columns:
            if self.df[col].nunique(dropna=True) <= 1:
                report["constant_columns"].append(col)

        # Outliers via IQR, só em colunas numéricas
        for col, t in types.items():
            if t != "numeric":
                continue
            series = self.df[col].dropna()
            if len(series) < 4:
                continue

            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue

            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outliers = series[(series < lower) | (series > upper)]
            if len(outliers) > 0:
                report["outlier_columns"][col] = int(len(outliers))

        # Datas inválidas: colunas classificadas como datetime que ainda
        # têm valores que não convertem
        for col, t in types.items():
            if t != "datetime":
                continue
            converted = pd.to_datetime(self.df[col], errors="coerce", format="mixed")
            invalid_count = int(converted.isna().sum() - self.df[col].isna().sum())
            if invalid_count > 0:
                report["invalid_date_columns"].append(
                    {"column": col, "invalid_count": invalid_count}
                )

        return report

    # ------------------------------------------------------------------ #
    # Pré-visualização
    # ------------------------------------------------------------------ #
    def preview(self, n: int = 10) -> list[dict[str, Any]]:
        return self.df.head(n).replace({np.nan: None}).to_dict(orient="records")

    # ------------------------------------------------------------------ #
    # Execução completa
    # ------------------------------------------------------------------ #
    def run_full_analysis(self) -> dict[str, Any]:
        """Roda todas as análises e retorna um único dicionário pronto
        para ser serializado em JSON e enviado ao front-end.
        """
        return {
            "general_info": self.general_info(),
            "column_types": self.classify_columns(),
            "kpis": self.kpis(),
            "numeric_statistics": self.numeric_statistics(),
            "data_quality": self.data_quality(),
            "preview": self.preview(),
        }


if __name__ == "__main__":
    # Teste manual rápido: gera um CSV de exemplo e roda a análise.
    import io

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
    analyzer = DatasetAnalyzer(df=df_sample)

    import json

    print(json.dumps(analyzer.run_full_analysis(), indent=2, ensure_ascii=False))