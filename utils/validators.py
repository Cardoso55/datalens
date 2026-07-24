"""
validators.py
--------------
Validações do arquivo enviado pelo usuário, antes de qualquer
processamento pesado (Pandas, IA, etc). Falha rápido e com mensagens
claras é melhor do que deixar o Pandas estourar uma exceção genérica
lá na frente.
"""

from __future__ import annotations

import os

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"csv"}
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class FileValidationError(Exception):
    """Erro de validação com mensagem amigável para exibir ao usuário."""


def _has_allowed_extension(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_file_size(file: FileStorage) -> int:
    """Descobre o tamanho do arquivo sem precisar salvá-lo em disco antes."""
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)  # devolve o ponteiro pro início, senão o save() sai vazio
    return size


def validate_upload(file: FileStorage | None) -> str:
    """Valida o arquivo enviado no upload. Retorna o filename sanitizado
    em caso de sucesso, ou levanta FileValidationError com uma mensagem
    pronta para ser exibida ao usuário.
    """
    if file is None or file.filename == "":
        raise FileValidationError("Nenhum arquivo foi selecionado.")

    filename = secure_filename(file.filename)
    if not filename:
        raise FileValidationError("Nome de arquivo inválido.")

    if not _has_allowed_extension(filename):
        raise FileValidationError(
            f"Formato não suportado. Envie um arquivo .csv "
            f"(extensões aceitas: {', '.join(sorted(ALLOWED_EXTENSIONS))})."
        )

    size = _get_file_size(file)
    if size == 0:
        raise FileValidationError("O arquivo está vazio.")

    if size > MAX_FILE_SIZE_BYTES:
        raise FileValidationError(
            f"O arquivo excede o tamanho máximo permitido de {MAX_FILE_SIZE_MB}MB."
        )

    return filename


def validate_dataframe_shape(rows: int, columns: int) -> None:
    """Validação pós-leitura: garante que o CSV tem conteúdo analisável.
    Chamado depois que o Pandas já leu o arquivo (analyzer.py).
    """
    if rows == 0:
        raise FileValidationError("O arquivo CSV não contém nenhuma linha de dados.")

    if columns < 1:
        raise FileValidationError("Não foi possível identificar colunas no arquivo CSV.")

    if columns == 1:
        raise FileValidationError(
            "Apenas uma coluna foi identificada — verifique se o separador do "
            "CSV está correto (vírgula ou ponto e vírgula)."
        )