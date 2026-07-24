"""
app.py
-------
Ponto de entrada da aplicação Flask. Orquestra o fluxo completo:

    upload do CSV -> validação -> análise (analyzer.py)
    -> gráficos (charts.py) -> insights de IA (insights.py)
    -> resposta em JSON para o front-end renderizar

Rodar localmente:

    pip install -r requirements.txt
    python app.py

Por padrão sobe em http://127.0.0.1:5000
"""

from __future__ import annotations

import os
import uuid

from flask import Flask, jsonify, render_template, request

from utils.analyzer import DatasetAnalyzer
from utils.charts import ChartGenerator
from utils.insights import InsightsGenerator
from utils.validators import (
    FileValidationError,
    MAX_FILE_SIZE_BYTES,
    validate_dataframe_shape,
    validate_upload,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# Um pouco de folga acima do limite do validators.py, pra garantir que é
# a mensagem amigável do validators (e não o 413 cru do Flask) que aparece
# na maioria dos casos.
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_BYTES + (1 * 1024 * 1024)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-troque-em-producao")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Uma única instância reaproveitada entre requisições — evita recriar o
# client HTTP da Anthropic a cada upload.
insights_generator = InsightsGenerator()


# ---------------------------------------------------------------------- #
# Páginas
# ---------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------- #
# API
# ---------------------------------------------------------------------- #
@app.route("/analyze", methods=["POST"])
def analyze():
    upload_path = None

    try:
        file = request.files.get("file")
        filename = validate_upload(file)

        # Nome único em disco pra evitar colisão entre uploads simultâneos,
        # mantendo o nome original só para exibição.
        stored_filename = f"{uuid.uuid4().hex}_{filename}"
        upload_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)
        file.save(upload_path)

        analyzer = DatasetAnalyzer(upload_path)
        rows, cols = analyzer.df.shape
        validate_dataframe_shape(rows, cols)

        analysis = analyzer.run_full_analysis()

        chart_generator = ChartGenerator(analyzer.df, analysis["column_types"])
        charts = chart_generator.generate_all()

        insights = insights_generator.generate(analysis)

        return jsonify(
            {
                "success": True,
                "filename": filename,
                "analysis": analysis,
                "charts": charts,
                "insights": insights,
            }
        )

    except FileValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:  # noqa: BLE001
        # Não vaza detalhes internos (stack trace, caminhos de disco) pro
        # usuário final — só loga no servidor e devolve mensagem genérica.
        app.logger.exception("Falha ao processar upload")
        return jsonify(
            {"success": False, "error": "Não foi possível processar o arquivo. Verifique o CSV e tente novamente."}
        ), 500

    finally:
        # O arquivo já foi lido e analisado em memória — não há motivo
        # pra manter o CSV do usuário em disco depois da resposta.
        if upload_path and os.path.exists(upload_path):
            os.remove(upload_path)


# ---------------------------------------------------------------------- #
# Handlers de erro
# ---------------------------------------------------------------------- #
@app.errorhandler(413)
def file_too_large(_e):
    return jsonify({"success": False, "error": "Arquivo muito grande."}), 413


@app.errorhandler(404)
def not_found(_e):
    return jsonify({"success": False, "error": "Rota não encontrada."}), 404


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)