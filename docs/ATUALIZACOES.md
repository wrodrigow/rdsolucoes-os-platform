# Publicar Atualizações do Software

## Fluxo Completo

Quando uma nova versão do RD Soluções OS estiver pronta (ex: v1.20):

### 1. Gerar o instalador (INSTALADOR/)

No diretório `INSTALADOR/`:
```
4_gerar_atualizacao.bat   → defina VERSION=1.20 e execute
```
Isso gera `Atualizacao_v1.20.zip` com o instalador.

### 2. Publicar no painel admin

1. Acesse `Admin → Downloads / Versões`
2. Clique em **Publicar Nova Versão**
3. Preencha:
   - **Versão:** `1.20`
   - **Nome:** `RD Soluções OS v1.20`
   - **Arquivo:** faça upload do `.zip` ou `.exe` do instalador
   - **Changelog:** liste as novidades (ex: `• Novo módulo X\n• Correção Y`)
4. Marque **"Tornar ativa imediatamente"**
5. Clique em **Publicar**

### 3. O que acontece automaticamente

- A nova versão aparece em **Área do Cliente → Downloads** para todos os clientes com licença ativa
- A versão anterior continua listada (clientes podem ver o histórico)
- O campo `versao_liberada` na tabela `licencas` não muda automaticamente — se quiser atualizar, edite via SQL ou adicione uma rota admin para isso

### 4. Notificar clientes (opcional)

Atualmente a notificação é manual. Para enviar e-mail em massa, você pode:
- Exportar CSV de clientes em `Admin → Clientes`
- Usar uma ferramenta de e-mail marketing (ex: Mailchimp, Brevo) com a lista exportada

### 5. Atualizar versão nas configurações do site

```
Admin → Configurações → Produto & Preço → Versão atual → salvar
```

Isso atualiza o número de versão exibido na landing page e nos documentos.

## Versionamento Recomendado

- `1.x` — atualizações menores e correções de bugs
- `2.0` — nova versão principal com mudanças significativas

Mantenha o changelog detalhado para que os clientes saibam o que mudou.
