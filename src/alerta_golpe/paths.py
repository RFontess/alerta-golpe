"""Caminhos do projeto, resolvidos a partir do pacote.

O notebook roda de `notebooks/` e o app de `app/`, então caminho relativo ao
diretório de trabalho não serve.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
