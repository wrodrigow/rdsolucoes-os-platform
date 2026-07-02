# RDSolucoes-OS-Platform

Plataforma de vendas da licença vitalícia do **RD Soluções OS** — sistema de gestão profissional para pequenas empresas.

## Stack

- **Backend:** Flask 3.x + SQLAlchemy + SQLite
- **Auth:** Flask-Login + CSRF (Flask-WTF)
- **Pagamentos:** Mercado Pago (Checkout API + Webhooks)
- **E-mail:** Flask-Mail (SMTP)
- **Frontend:** CSS/JS puro (sem frameworks), design system próprio

## Início Rápido

```bash
# 1. Clone e entre na pasta
cd RDSolucoes-OS-Platform

# 2. Crie o ambiente virtual
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# 3. Instale dependências
pip install -r requirements.txt

# 4. Configure o ambiente
copy .env.example .env
# Edite .env com suas chaves

# 5. Inicialize o banco
python scripts/init_db.py

# 6. Importe as keys de licença
python scripts/import_keys.py keys.txt

# 7. (Opcional) Crie admin manualmente se não usou .env
python scripts/create_admin.py

# 8. Rode o servidor
python run.py
```

Acesse: `http://localhost:5000`  
Admin: `http://localhost:5000/admin`

## Estrutura

```
RDSolucoes-OS-Platform/
├── app/
│   ├── __init__.py          # Application factory
│   ├── config.py            # Configurações por ambiente
│   ├── extensions.py        # db, login_manager, mail, csrf, migrate
│   ├── models/              # User, Order, Key, License, Download, Log, SiteConfig
│   ├── routes/              # main, auth, checkout, payment, client, admin
│   ├── services/            # key_service, payment_service, email_service
│   ├── static/css/          # main.css, client.css, admin.css
│   ├── static/js/           # main.js, admin.js
│   └── templates/           # Jinja2 templates
├── scripts/
│   ├── init_db.py
│   ├── import_keys.py
│   └── create_admin.py
├── docs/                    # Documentação detalhada
├── .env.example
├── requirements.txt
├── run.py                   # Desenvolvimento
└── wsgi.py                  # Produção (Gunicorn)
```

## Documentação

- [docs/INSTALACAO.md](docs/INSTALACAO.md) — instalação completa
- [docs/MERCADOPAGO.md](docs/MERCADOPAGO.md) — configuração de pagamentos
- [docs/HOSPEDAGEM.md](docs/HOSPEDAGEM.md) — deploy em produção
- [docs/ADMIN.md](docs/ADMIN.md) — guia do painel administrativo
- [docs/BACKUP.md](docs/BACKUP.md) — backup e restore do banco
