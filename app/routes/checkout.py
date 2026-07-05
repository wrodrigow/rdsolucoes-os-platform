import secrets
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import current_user, login_required
from ..extensions import db, limiter
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


@bp.route("/direto", methods=["POST"])
@limiter.limit("15 per hour;5 per minute")
def direto():
    """
    Checkout sem cadastro (fluxo da landing page): o comprador informa apenas
    nome e e-mail, a conta é criada automaticamente e ele vai direto ao
    Mercado Pago. A senha é definida depois, pelo link enviado no e-mail
    de confirmação da compra.
    """
    from ..models.user import User

    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip().lower()
    telefone = request.form.get("whatsapp", "").strip()

    if not nome or len(nome) < 3:
        flash("Informe seu nome completo.", "danger")
        return redirect(url_for("main.lp") + "#comprar")
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        flash("Informe um e-mail válido — é nele que você receberá sua licença.", "danger")
        return redirect(url_for("main.lp") + "#comprar")

    if Key.total_disponiveis() < 1:
        flash("Não há licenças disponíveis no momento. Entre em contato com o suporte.", "danger")
        return redirect(url_for("main.lp") + "#comprar")

    # Reusa a conta se o e-mail já existir; senão cria com senha aleatória
    # (o comprador define a senha real pelo link do e-mail de confirmação)
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(nome=nome, email=email, telefone=telefone)
        user.set_senha(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.commit()

    preco = float(SiteConfig.get("produto_preco", "297.00"))
    nome_produto = SiteConfig.get("produto_nome", "RD Soluções OS — Licença Vitalícia")

    # Reaproveita pedido pendente recente do mesmo usuário (evita duplicar a cada clique)
    order = (
        Order.query.filter_by(user_id=user.id, status="pending")
        .order_by(Order.created_at.desc())
        .first()
    )
    if not order:
        order = Order(
            numero_pedido=Order.gerar_numero(),
            user_id=user.id,
            produto_nome=nome_produto,
            valor=preco,
            status="pending",
        )
        db.session.add(order)
        db.session.commit()

    try:
        from ..services.payment_service import criar_preferencia
        preference = criar_preferencia(order, user)
        order.mp_preference_id = preference.get("id")
        db.session.commit()

        init_point = preference.get("init_point") or preference.get("sandbox_init_point")
        if not init_point:
            raise RuntimeError("init_point não retornado pelo Mercado Pago.")

        from ..models.traffic_event import TrafficEvent
        TrafficEvent.registrar("checkout_start", request, order_id=order.id)

        return redirect(init_point)

    except Exception as e:
        current_app.logger.error(f"Erro ao criar preferência MP (checkout direto): {e}")
        flash("Erro ao iniciar o pagamento. Tente novamente em instantes.", "danger")
        return redirect(url_for("main.lp") + "#comprar")


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

    from ..models.traffic_event import TrafficEvent
    TrafficEvent.registrar("checkout_success", request, order_id=order_id)

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
    from ..models.traffic_event import TrafficEvent
    TrafficEvent.registrar("checkout_fail", request)
    return render_template("checkout/falha.html")
