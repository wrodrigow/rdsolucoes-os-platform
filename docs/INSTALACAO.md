# Instalação

## Pré-requisitos

- Python 3.10 ou superior
- pip
- Git (opcional)

## Passo a Passo (Windows / Linux / Mac)

### 1. Ambiente Virtual

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 2. Dependências

```bash
pip install -r requirements.txt
```

### 3. Variáveis de Ambiente

Copie `.env.example` para `.env` e preencha:

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

Campos obrigatórios no `.env`:
- `SECRET_KEY` — string aleatória longa (gere com `python -c "import secrets; print(secrets.token_hex(32))"`)
- `MP_ACCESS_TOKEN` — token de produção do Mercado Pago
- `MP_PUBLIC_KEY` — chave pública do Mercado Pago
- `MAIL_*` — credenciais SMTP
- `ADMIN_EMAIL` + `ADMIN_PASSWORD` — credenciais do admin inicial
- `BASE_URL` — URL completa do site (ex: `https://rdsolucoes.eco.br`)

### 4. Banco de Dados

```bash
python scripts/init_db.py
```

Cria todas as tabelas e o admin inicial (se ADMIN_EMAIL/ADMIN_PASSWORD estiverem no .env).

### 5. Importar Keys

Coloque o arquivo `keys.txt` (uma key por linha) na raiz e rode:

```bash
python scripts/import_keys.py keys.txt
```

Para testar sem alterar o banco:
```bash
python scripts/import_keys.py keys.txt --dry-run
```

### 6. Criar Admin Manualmente (alternativa)

```bash
python scripts/create_admin.py --email admin@seusite.com --senha SuaSenha123!
```

### 7. Desenvolvimento

```bash
python run.py
```

Acesse `http://localhost:5000`.

### 8. Produção

Veja [docs/HOSPEDAGEM.md](HOSPEDAGEM.md).

## Estrutura de Pastas para Uploads

Crie a pasta antes de subir arquivos de versão pelo admin:

```bash
mkdir -p app/static/uploads/versoes
```

## Verificação

- `http://localhost:5000` — site público
- `http://localhost:5000/admin` — painel admin
- `http://localhost:5000/auth/login` — login cliente
