import sys
import os

# Garante que o diretório do app está no Python path
INTERP = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.insert(0, os.path.dirname(__file__))

# Carrega variáveis de ambiente do .env antes de importar o app
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app import create_app

application = create_app("production")
