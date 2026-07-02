#!/bin/bash
# ============================================================
# Setup inicial do RD Soluções OS Platform na Hostinger
# Execute uma única vez após o upload dos arquivos:
#   bash setup.sh
# ============================================================
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$APP_DIR/venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

echo "=== [1/5] Criando virtualenv ==="
python3 -m venv "$VENV_DIR"

echo "=== [2/5] Instalando dependências ==="
"$PIP" install --upgrade pip
"$PIP" install -r "$APP_DIR/requirements.txt"

echo "=== [3/5] Configurando .env de produção ==="
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.production" "$APP_DIR/.env"
    echo "  >> IMPORTANTE: edite o arquivo .env antes de continuar!"
    echo "     Troque SECRET_KEY, DATABASE_URL (username), ADMIN_PASSWORD e MAIL_PASSWORD."
    read -p "  >> Pressione Enter após editar o .env para continuar..."
fi

echo "=== [4/5] Inicializando banco de dados ==="
mkdir -p "$APP_DIR/instance"
cd "$APP_DIR"
"$PYTHON" scripts/init_db.py

echo "=== [5/5] Importando keys de licença ==="
KEYS_FILE="$APP_DIR/scripts/keys.txt"
if [ -f "$KEYS_FILE" ]; then
    "$PYTHON" scripts/import_keys.py "$KEYS_FILE"
else
    echo "  >> Arquivo de keys não encontrado em scripts/keys.txt"
    echo "     Faça upload do arquivo e execute manualmente:"
    echo "     $PYTHON scripts/import_keys.py /caminho/para/keys.txt"
fi

echo ""
echo "============================================================"
echo "  Setup concluído!"
echo "  Acesse: https://rdsolucoes.eco.br/rdos/admin"
echo "  Login:  (o e-mail e senha definidos no .env)"
echo "============================================================"
