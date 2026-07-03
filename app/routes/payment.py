import hashlib
import hmac
import json
from datetime import datetime, timezone
from flask import Blueprint, request, current_app, jsonify
from ..extensions import db, csrf
from ..models.order import Order
from ..models.log import Log

bp = Blueprint("payment", __name__)


@bp.route("/webhook", methods=["POST"])
@csrf.exempt  # Webhooks externos não enviam CSRF token
def webhook():
    """
    Recebe notificações do Mercado Pago e processa pagamentos aprovados.
    MP envia tanto IPN (id + topic) quanto Webhooks (type + data).
    """
    try:
        _verificar_assinatura(request)
    except ValueError as e:
        current_app.logger.warning(f"Webhook com assinatura inválida: {e}")
        # Retorna 200 mesmo assim para evitar reenvios infinitos do MP
        return jsonify({"ok": False, "msg": str(e)}), 200

    payload = request.get_json(silent=True) or {}
    current_app.logger.info(f"Webhook MP recebido: {json.dumps(payload)}")

    # Formato Webhook (v2)
    if payload.get("type") == "payment" and payload.get("action") == "payment.updated":
        payment_id = str(payload.get("data", {}).get("id", ""))
        if payment_id:
            _processar_pagamento(payment_id)
        return jsonify({"ok": True}), 200

    # Formato IPN (legado)
    topic = request.args.get("topic") or payload.get("topic")
    resource_id = request.args.get("id") or str(payload.get("id", ""))

    if topic == "payment" and resource_id:
        _processar_pagamento(resource_id)

    return jsonify({"ok": True}), 200


def _verificar_assinatura(req):
    """Verifica o header x-signature do Mercado Pago (opcional mas recomendado)."""
    secret = current_app.config.get("MP_WEBHOOK_SECRET", "")
    if not secret:
        return  # Sem secret configurado, pular verificação

    sig_header = req.headers.get("x-signature", "")
    ts_header = req.headers.get("x-request-id", "")
    if not sig_header:
        return

    # Extrai ts e v1 do header
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    ts = parts.get("ts", "")
    v1 = parts.get("v1", "")

    # Monta o manifesto
    manifest = f"id:{req.args.get('data.id', '')};request-id:{ts_header};ts:{ts};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, v1):
        raise ValueError("Assinatura do webhook inválida.")


def _processar_pagamento(payment_id: str):
    """Verifica o status no MP e, se aprovado, processa o pedido."""
    from ..services.payment_service import verificar_pagamento
    from ..services.key_service import assign_key
    from ..services.email_service import enviar_confirmacao_compra
    from ..models.user import User

    dados = verificar_pagamento(payment_id)
    if not dados:
        current_app.logger.error(f"Pagamento {payment_id} não encontrado no MP.")
        return

    status_mp = dados.get("status")
    order_id = str(dados.get("external_reference", ""))

    if not order_id:
        current_app.logger.warning(f"Webhook sem external_reference. payment_id={payment_id}")
        return

    order = Order.query.get(order_id)
    if not order:
        current_app.logger.warning(f"Pedido {order_id} não encontrado.")
        return

    # Atualiza dados do MP no pedido
    order.mp_payment_id = payment_id
    order.mp_status = status_mp
    order.mp_payment_method = dados.get("payment_method_id")
    order.mp_payment_type = dados.get("payment_type_id")
    db.session.commit()

    if status_mp != "approved":
        if status_mp in ("cancelled", "rejected"):
            order.status = "cancelled"
            db.session.commit()
        Log.registrar("webhook_mp", f"payment={payment_id} status={status_mp} order={order_id}")
        return

    # Já processado anteriormente → idempotência
    if order.status == "approved":
        current_app.logger.info(f"Pedido {order_id} já estava aprovado. Ignorando.")
        return

    # Processa aprovação
    try:
        order.status = "approved"
        order.approved_at = datetime.now(timezone.utc)
        db.session.commit()

        license_ = assign_key(order)

        user = order.user

        # Comprador do checkout direto (nunca fez login): gera link para
        # definir a senha, válido por 7 dias, incluído no e-mail da compra
        set_password_url = None
        if user.ultimo_login is None:
            import secrets as _secrets
            from datetime import timedelta
            user.reset_token = _secrets.token_urlsafe(32)
            user.reset_token_exp = datetime.now(timezone.utc) + timedelta(days=7)
            db.session.commit()
            base_url = current_app.config["BASE_URL"]
            set_password_url = f"{base_url}/auth/nova-senha/{user.reset_token}"

        enviar_confirmacao_compra(order, license_, user, set_password_url=set_password_url)

        Log.registrar(
            "compra_aprovada",
            f"order={order.numero_pedido} key={license_.key_obj.key} user={user.email}",
            user_id=user.id,
        )
        current_app.logger.info(f"Compra aprovada: {order.numero_pedido} para {user.email}")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao processar aprovação {order_id}: {e}")
        # Reverte status para re-processar
        order.status = "pending"
        db.session.commit()
        raise
