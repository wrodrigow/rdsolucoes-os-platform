# Guia do Painel Administrativo

Acesse em: `https://seusite.com.br/admin`

## Acesso

Use as credenciais definidas em `ADMIN_EMAIL` e `ADMIN_PASSWORD` no `.env`, ou criadas via `scripts/create_admin.py`.

## Seções

### Dashboard
Visão geral em tempo real: total de pedidos, clientes, receita, keys disponíveis e gráfico mensal de vendas.

**Atenção:** Se o contador de keys disponíveis ficar abaixo de 50, um aviso aparece no dashboard. Importe mais keys antes de acabar.

### Pedidos
Lista todos os pedidos com filtro por status e busca. Funcionalidades:
- **Reenviar e-mail:** reenvia o e-mail de confirmação com a chave para pedidos aprovados
- **Exportar CSV:** exporta todos os pedidos filtrados

### Clientes
Lista de usuários cadastrados. Filtros: com/sem licença, busca por nome/e-mail.

### Licenças
Lista todas as licenças emitidas. Ações:
- **Suspender:** desativa temporariamente (cliente não consegue baixar)
- **Reativar:** reativa uma licença suspensa
- **Cancelar:** cancela permanentemente

### Keys
Gerenciamento do estoque de chaves de ativação.

**Importar Keys:**
- Cole as keys diretamente no textarea (uma por linha)
- Ou envie um arquivo `.txt` / `.csv`
- Duplicatas são ignoradas automaticamente

**Monitorar estoque:**
- Verde: disponíveis (para venda)
- Azul: vendidas (atribuídas a licenças)
- Amarelo: reservadas (pagamentos em processamento)

### Downloads / Versões
Publique novas versões do instalador:
1. Preencha versão e nome de exibição
2. Faça upload do arquivo `.exe` / `.zip`
3. Adicione o changelog
4. Marque "Tornar ativa" para que clientes vejam imediatamente

### Financeiro
Relatório de receita com gráfico mensal e tabela detalhada por mês (quantidade de vendas, receita, ticket médio, % do total).

### Configurações
Edite informações do site sem mexer no código:
- Nome, slogan, e-mail, WhatsApp
- SEO (title, description, keywords)
- Preço e nome do produto
- Flags como "Vendas abertas"

### Logs
Histórico completo de ações: compras aprovadas, logins, falhas de autenticação, ações do admin. Filtráveis por tipo de ação.

## Operações Comuns

### Adicionar keys antes de acabar
```
Admin → Keys → Cole as keys no textarea → Importar Keys
```

### Publicar nova versão do software
```
Admin → Downloads → Nova Versão → Upload do instalador → Publicar
```

### Reenviar key para um cliente
```
Admin → Pedidos → Localizar pedido → Ícone de envelope
```

### Suspender licença de um cliente
```
Admin → Licenças → Localizar → Suspender
```
