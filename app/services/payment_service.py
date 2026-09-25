import mercadopago
from flask import current_app
from ..models.order import Order
from ..models.site_config import SiteConfig


def get_sdk():
    return mercadopago.SDK(current_app.config["MP_ACCESS_TOKEN"])


def criar_preferencia(order, user, *, item_id="rdsolucoes-os-vitalicia",
                      descricao="Licença Vitalícia — sem mensalidade, instale em 1 computador",
                      retorno="/checkout", descritor="RD SOLUCOES OS", parcelas=12,
                      tipos_excluidos=()):
    """Cria uma preference no Mercado Pago e retorna o init_point.

    Os padrões são os do RD OS desktop; as ferramentas online (Pro) passam os
    próprios valores — outro item, outras páginas de retorno, pagamento à vista.
    """
    sdk = get_sdk()
    base_url = current_app.config["BASE_URL"]

    preference_data = {
        "items": [
            {
                "id": item_id,
                "title": order.produto_nome,
                "quantity": 1,
                "unit_price": float(order.valor),
                "currency_id": "BRL",
                "description": descricao,
            }
        ],
        "payer": {
            "name": user.nome.split()[0] if user.nome else "",
            "surname": " ".join(user.nome.split()[1:]) if user.nome else "",
            "email": user.email,
        },
        "external_reference": order.id,
        "back_urls": {
            "success": f"{base_url}{retorno}/sucesso",
            "pending": f"{base_url}{retorno}/pendente",
            "failure": f"{base_url}{retorno}/falha",
        },
        # auto_return só funciona com URL pública; em localhost deixa desabilitado
        **({"auto_return": "approved"} if not base_url.startswith("http://localhost") else {}),
        "notification_url": f"{base_url}/payment/webhook",
        "statement_descriptor": descritor,
        "expires": False,
        "payment_methods": {
            "excluded_payment_types": [{"id": tipo} for tipo in tipos_excluidos],
            "installments": parcelas,
        },
        "metadata": {
            "order_id": order.id,
            "order_numero": order.numero_pedido,
            "user_email": user.email,
        },
    }

    result = sdk.preference().create(preference_data)
    response = result.get("response", {})

    if result.get("status") not in (200, 201):
        raise RuntimeError(f"Erro ao criar preferência MP: {response}")

    return response


def verificar_pagamento(payment_id):
    """Busca um pagamento na API do Mercado Pago."""
    sdk = get_sdk()
    result = sdk.payment().get(payment_id)
    if result.get("status") == 200:
        return result.get("response", {})
    return None
