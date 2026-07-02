# Guia da Área do Cliente

A área do cliente fica em `https://seusite.com.br/cliente/`.

## Como o Cliente Acessa

1. Realiza a compra no site
2. Recebe e-mail de confirmação com link para a Área do Cliente
3. Clica em "Criar conta" ou faz login se já cadastrado antes da compra
4. Acessa o painel com licença, downloads e histórico

## Seções da Área do Cliente

### Dashboard
Resumo rápido: status da licença, número de pedidos e disponibilidade de downloads.
Exibe um card com a key de ativação (parcialmente mascarada) e botão para copiar.

### Minha Licença
Certificado digital completo com:
- Nome do titular, número do pedido, data de emissão
- Tipo de licença (Vitalícia) e versão liberada
- Chave de ativação completa com botão de copiar
- Botões: Baixar Sistema, Imprimir Certificado

### Downloads
Lista as versões disponíveis com changelog. O cliente baixa diretamente da Área do Cliente.
Cada download incrementa o contador `downloads_count` na tabela `downloads`.

### Histórico de Compras
Tabela com todos os pedidos, valores, métodos de pagamento e status.

### Dados Cadastrais
Editar nome, telefone e empresa. E-mail não pode ser alterado diretamente (requer suporte).

### Alterar Senha
Formulário para trocar senha com validação da senha atual.

### Suporte
Canais de atendimento (WhatsApp e e-mail) + mini FAQ com as dúvidas mais comuns.

### FAQ
FAQ completo com 5 categorias: Licença, Instalação, Backup, Atualizações e Pagamento.

## Fluxo Pós-Compra (Perspectiva do Cliente)

```
Compra realizada
  → E-mail de confirmação com key
  → Link para Área do Cliente
  → Login / cadastro
  → Dashboard → card com key
  → Downloads → baixar instalador
  → Instalar e ativar com a key
  → Usar o sistema offline
```

## O que o Cliente Não Pode Fazer

- Alterar e-mail (exige suporte)
- Ver outros clientes ou pedidos
- Acessar o painel admin
- Baixar sem ter licença ativa

## Problemas Comuns de Clientes

**"Não recebi o e-mail com a key"**
→ Verifique o spam. A key também está em Área do Cliente → Minha Licença.

**"Esqueci minha senha"**
→ Use "Esqueci minha senha" na tela de login. E-mail de recuperação é enviado automaticamente.

**"Sistema não abre após instalar"**
→ Executar instalador como Administrador (botão direito → Executar como administrador).

**"Formatei o computador"**
→ Baixar o instalador novamente em Downloads → ativar com a mesma key disponível em Minha Licença.
