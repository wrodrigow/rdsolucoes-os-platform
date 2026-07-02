# Hospedagem em Produção

## Opções Recomendadas

| Provedor | Tipo | Custo | Observação |
|---|---|---|---|
| **Railway** | PaaS | ~$5/mês | Deploy via GitHub, SSL automático |
| **Render** | PaaS | Grátis / $7/mês | Sleep em plano free — use pago |
| **DigitalOcean** | VPS | $6/mês | Mais controle, precisa configurar Nginx |
| **Hostinger VPS** | VPS | ~R$30/mês | Opção BR, suporte em português |

## Deploy com Gunicorn (VPS)

### 1. Instalar dependências no servidor

```bash
pip install -r requirements.txt
```

### 2. Testar Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:application
```

### 3. Systemd service (Linux)

Crie `/etc/systemd/system/rdsolucoes.service`:

```ini
[Unit]
Description=RD Solucoes OS Platform
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/rdsolucoes-platform
Environment="PATH=/var/www/rdsolucoes-platform/venv/bin"
EnvironmentFile=/var/www/rdsolucoes-platform/.env
ExecStart=/var/www/rdsolucoes-platform/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable rdsolucoes
sudo systemctl start rdsolucoes
```

### 4. Nginx como Reverse Proxy

```nginx
server {
    listen 80;
    server_name rdsolucoes.eco.br www.rdsolucoes.eco.br;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name rdsolucoes.eco.br www.rdsolucoes.eco.br;

    ssl_certificate /etc/letsencrypt/live/rdsolucoes.eco.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/rdsolucoes.eco.br/privkey.pem;

    client_max_body_size 50M;

    location /static {
        alias /var/www/rdsolucoes-platform/app/static;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 5. SSL com Certbot

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d rdsolucoes.eco.br -d www.rdsolucoes.eco.br
```

## Deploy no Railway

1. Crie um projeto no Railway e conecte ao repositório GitHub
2. Adicione as variáveis de ambiente no painel do Railway
3. O Railway detecta automaticamente o `wsgi.py` e usa Gunicorn
4. Configure o domínio personalizado no painel

## Variáveis de Produção Obrigatórias

```env
FLASK_ENV=production
SECRET_KEY=<string longa e aleatória>
DATABASE_URL=sqlite:///instance/rdsolucoes.db
BASE_URL=https://rdsolucoes.eco.br
MP_ACCESS_TOKEN=<token de produção do MP>
MP_PUBLIC_KEY=<public key de produção do MP>
MP_WEBHOOK_SECRET=<segredo do webhook MP>
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=<seu-email>
MAIL_PASSWORD=<senha de app>
ADMIN_EMAIL=<email do admin>
ADMIN_PASSWORD=<senha forte>
```
