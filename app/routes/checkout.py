from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import current_user, login_required
from ..extensions import db
from ..models.order import Order
from ..models.site_config import SiteConfig
from ..models.key import Key

bp = Blueprint("checkout", __name__)


@bp.route("/")
def index():
    keys_disponiveis = Key.total_disponiveis()
    preco = float(SiteConfig.get("produto_preco", "297.00"))
    nome = SiteConfig.get("produto_nome", "RD Soluções OS — Licença Vitalícia")
    mp_public_key = current_app.config.get("MP_PUBLIC_KEY", "")
    return render_template(
        "checkout/checkout.html",
        preco=preco,
        nome=nome,
        keys_disponiveis=keys_disponiveis,
        mp_public_key=mp_public_key,
    )


@bp.route("/iniciar", methods=["POST"])
def iniciar():
    """Cria o pedido e redireciona para o Mercado Pago."""
    if not current_user.is_authenticated:
        # Salva intenção de compra e redireciona para login
        session["checkout_intencao"] = True
        flash("Faça login ou crie sua conta para continuar com a compra.", "info")
        return redirect(url_for("auth.login", next=url_for("checkout.index")))

    # Verifica keys disponíveis
    if Key.total_disponiveis() < 1:
        flash("Não há licenças disponíveis no momento. Entre em contato com o suporte.", "danger")
        return redirect(url_for("checkout.index"))

    preco = float(SiteConfig.get("produto_preco", "297.00"))
    nome = SiteConfig.get("produto_nome", "RD Soluções OS — Licença Vitalícia")

    # Cria pedido
    order = Order(
        numero_pedido=Order.gerar_numero(),
        user_id=current_user.id,
        produto_nome=nome,
        valor=preco,
        status="pending",
    )
    db.session.add(order)
    db.session.commit()

    try:
        from ..services.payment_service import criar_preferencia
        preference = criar_preferencia(order, current_user)
        order.mp_preference_id = preference.get("id")
        db.session.commit()

        # Redireciona para o checkout do Mercado Pago
        init_point = preference.get("init_point") or preference.get("sandbox_init_point")
        if not init_point:
            raise RuntimeError("init_point não retornado pelo Mercado Pago.")
        return redirect(init_point)

    except Exception as e:
        current_app.logger.error(f"Erro ao criar preferência MP: {e}")
        db.session.delete(order)
        db.session.commit()
        flash("Erro ao processar pagamento. Tente novamente.", "danger")
        return redirect(url_for("checkout.index"))


@bp.route("/sucesso")
def sucesso():
    payment_id = request.args.get("payment_id")
    order_id = request.args.get("external_reference")
    status = request.args.get("status")

    order = None
    license_ = None

    if order_id:
        order = Order.query.get(order_id)
        if order and order.license:
            license_ = order.license

    return render_template(
        "checkout/sucesso.html",
        order=order,
        license=license_,
        payment_id=payment_id,
        status=status,
    )


@bp.route("/pendente")
def pendente():
    order_id = request.args.get("external_reference")
    order = Order.query.get(order_id) if order_id else None
    return render_template("checkout/pendente.html", order=order)


@bp.route("/falha")
def falha():
    return render_template("checkout/falha.html")
