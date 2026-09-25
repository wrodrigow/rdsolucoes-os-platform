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

    # Formato Webhook (v2). Cartão aprovado na hora costuma chegar só como
    # "payment.created" — por isso os dois; o processamento é idempotente.
    if payload.get("type") == "payment" and payload.get("action") in ("payment.created", "payment.updated"):
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

    # Pedido já aprovado recebendo aviso de OUTRO pagamento: um recusado que chegou
    # fora de ordem não pode rebaixar o pedido pago; um segundo pagamento aprovado
    # (preferência antiga paga de novo) fica registrado para o admin reembolsar.
    if order.status == "approved" and order.mp_payment_id and str(order.mp_payment_id) != payment_id:
        if status_mp == "approved":
            Log.registrar("pagamento_duplicado", f"order={order.numero_pedido} payment={payment_id} "
                          f"(aprovado antes: {order.mp_payment_id}) — reembolsar", user_id=order.user_id)
            current_app.logger.warning(f"Pagamento duplicado {payment_id} para o pedido já aprovado {order_id}.")
        else:
            Log.registrar("webhook_mp", f"payment={payment_id} status={status_mp} order={order_id} (ignorado: pedido já aprovado)")
        return

    # Atualiza dados do MP no pedido
    order.mp_payment_id = payment_id
    order.mp_status = status_mp
    order.mp_payment_method = dados.get("payment_method_id")
    order.mp_payment_type = dados.get("payment_type_id")
    db.session.commit()

    if status_mp != "approved":
        if status_mp in ("cancelled", "rejected"):
            # condicional no banco: um aprovado processado ao mesmo tempo não é sobrescrito
            from sqlalchemy import update as _update
            db.session.execute(_update(Order).where(Order.id == order.id, Order.status != "approved")
                               .values(status="cancelled"))
            db.session.commit()
        elif status_mp in ("refunded", "charged_back"):
            # Reembolso (direito de arrependimento) ou estorno: o Pro deixa de valer.
            from ..services.ferramentas_service import eh_pedido_pro, revogar_pro
            if eh_pedido_pro(order):
                order.status = "refunded"
                db.session.commit()
                if revogar_pro(order):
                    Log.registrar("pro_revogado", f"order={order.numero_pedido} status={status_mp}", user_id=order.user_id)
        Log.registrar("webhook_mp", f"payment={payment_id} status={status_mp} order={order_id}")
        return

    # Pro das ferramentas: o valor pago tem que cobrir o pedido
    from ..services.ferramentas_service import eh_pedido_pro, liberar_pro
    pedido_pro = eh_pedido_pro(order)
    if pedido_pro:
        try:
            pago = float(dados.get("transaction_amount") or 0)
        except (TypeError, ValueError):
            pago = 0.0
        if pago + 0.01 < float(order.valor):
            current_app.logger.error(f"Pro {order.numero_pedido}: pago {pago} menor que {order.valor}. Não liberado.")
            Log.registrar("pro_valor_divergente", f"order={order.numero_pedido} pago={pago} valor={order.valor}")
            return

    # Aprovação atômica: o Mercado Pago avisa mais de uma vez (IPN + webhook, e o
    # retorno do checkout também confere). Só quem muda o status de fato continua.
    from sqlalchemy import update
    agora = datetime.now(timezone.utc)
    mudou = db.session.execute(
        update(Order)
        .where(Order.id == order.id, Order.status != "approved")
        .values(status="approved", approved_at=agora)
    ).rowcount
    db.session.commit()
    if not mudou:
        current_app.logger.info(f"Pedido {order_id} já estava aprovado. Ignorando.")
        return
    db.session.refresh(order)

    # Processa aprovação
    try:
        user = order.user

        # Pro das ferramentas online: libera o acesso e NÃO entrega chave do desktop.
        if pedido_pro:
            liberar_pro(order)
            from ..services.email_service import enviar_confirmacao_pro
            enviar_confirmacao_pro(order, user, set_password_url=_link_definir_senha(user))
            Log.registrar("compra_aprovada_pro", f"order={order.numero_pedido} user={user.email}", user_id=user.id)
            current_app.logger.info(f"Pro das ferramentas liberado: {order.numero_pedido} para {user.email}")
            return

        license_ = assign_key(order)

        enviar_confirmacao_compra(order, license_, user, set_password_url=_link_definir_senha(user))

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


def _link_definir_senha(user):
    """Comprador do checkout direto (nunca fez login): gera o link para definir
    a senha, válido por 7 dias, que vai no e-mail da compra. Quem já tem senha
    recebe None e o e-mail manda só entrar."""
    if user.ultimo_login is not None:
        return None
    import secrets as _secrets
    from datetime import timedelta
    user.reset_token = _secrets.token_urlsafe(32)
    user.reset_token_exp = datetime.now(timezone.utc) + timedelta(days=7)
    db.session.commit()
    return f"{current_app.config['BASE_URL']}/auth/nova-senha/{user.reset_token}"
