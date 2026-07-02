# Backup e Restauração

## Backup Manual do SQLite

O banco de dados é um único arquivo. Basta copiá-lo:

```bash
# Linux/Mac
cp instance/rdsolucoes.db backups/rdsolucoes_$(date +%Y%m%d_%H%M%S).db

# Windows PowerShell
Copy-Item instance\rdsolucoes.db "backups\rdsolucoes_$(Get-Date -Format 'yyyyMMdd_HHmmss').db"
```

## Backup Automático (Cron — Linux)

Adicione ao crontab (`crontab -e`):

```cron
# Backup diário às 3h
0 3 * * * cp /var/www/rdsolucoes-platform/instance/rdsolucoes.db /var/backups/rdsolucoes/rdsolucoes_$(date +\%Y\%m\%d).db

# Manter apenas os últimos 30 dias
0 4 * * * find /var/backups/rdsolucoes/ -name "*.db" -mtime +30 -delete
```

## Restauração

```bash
# Pare o servidor antes de restaurar
sudo systemctl stop rdsolucoes

# Substitua o banco
cp backups/rdsolucoes_20250115.db instance/rdsolucoes.db

# Reinicie
sudo systemctl start rdsolucoes
```

## Exportar para SQL (sqlite3)

```bash
sqlite3 instance/rdsolucoes.db .dump > backup_$(date +%Y%m%d).sql
```

## Restaurar de SQL

```bash
sqlite3 instance/rdsolucoes_novo.db < backup_20250115.sql
```

## Backup para Google Drive / S3

Para enviar automaticamente para nuvem, use `rclone`:

```bash
# Instalar rclone e configurar destino (rclone config)
rclone copy instance/rdsolucoes.db gdrive:backups/rdsolucoes/
```

## O que está no banco de dados

- Usuários e senhas (hashes)
- Pedidos e histórico de pagamentos
- Keys de licença (disponíveis, vendidas, reservadas)
- Licenças ativas
- Logs de atividade
- Configurações do site

**Não estão no banco:** arquivos de instalador (ficam em `app/static/uploads/versoes/`). Faça backup dessa pasta separadamente.
