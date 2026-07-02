# Configuração do Mercado Pago

## 1. Criar Conta e Aplicação

1. Acesse [mercadopago.com.br](https://www.mercadopago.com.br) e crie ou acesse sua conta
2. Vá em **Seu negócio → Configurações → Gestão e administração → Credenciais**
3. Copie o **Access Token de Produção** e a **Public Key de Produção**

## 2. Variáveis no .env

```env
MP_ACCESS_TOKEN=APP_USR-xxxxxxxxxxxx
MP_PUBLIC_KEY=APP_USR-xxxxxxxxxxxx
MP_WEBHOOK_SECRET=   # Deixe vazio por ora, preencha após configurar o webhook
```

## 3. Configurar Webhook

O webhook é a URL que o Mercado Pago chama para notificar pagamentos aprovados.

### URL do Webhook
```
https://seudominio.com.br/payment/webhook
```

### No painel do Mercado Pago:
1. Vá em **Seu negócio → Configurações → Notificações**
2. Clique em **Webhooks**
3. Adicione a URL acima
4. Selecione o evento: **Pagamentos**
5. Salve e copie o **Segredo do Webhook** gerado

### No .env:
```env
MP_WEBHOOK_SECRET=seu_segredo_copiado_aqui
```

## 4. Testar em Sandbox

Para testar sem dinheiro real:
1. Nas credenciais do Mercado Pago, use o **Access Token de Teste** (começa com `TEST-`)
2. Use cartões de teste disponíveis na documentação do MP
3. O webhook em sandbox pode ser testado com [ngrok](https://ngrok.com):
   ```bash
   ngrok http 5000
   # Use a URL gerada: https://xxxx.ngrok.io/payment/webhook
   ```

## 5. Como Funciona o Fluxo

```
Cliente clica "Comprar"
  → Flask cria Order (status=pending)
  → Chama MP Preferences API com external_reference=order.id
  → Redireciona para MP Checkout (init_point)
  → Cliente paga
  → MP chama /payment/webhook
  → Flask verifica assinatura HMAC-SHA256
  → Busca Order pelo external_reference
  → Se status != 'approved': atribui key, cria License, envia e-mail
  → Retorna 200 OK para o MP
```

## 6. Idempotência

O webhook do MP pode ser chamado múltiplas vezes para o mesmo pagamento.
O código verifica `if order.status == 'approved': return` antes de processar,
garantindo que a key seja atribuída apenas uma vez.

## 7. Prevenção de Race Conditions

`Key.get_disponivel()` usa `SELECT FOR UPDATE` via `with_for_update()`.
Mesmo com dois webhooks simultâneos, apenas um obtém a key — o outro vê
a key já marcada como `vendida` e retorna erro.
