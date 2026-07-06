from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from ..extensions import csrf, limiter
from ..models.key import Key
from ..models.site_config import SiteConfig
from ..models.download import Download

bp = Blueprint("main", __name__)

# Eventos de comportamento aceitos pelo beacon da LP. Whitelist fechada:
# qualquer outro valor é descartado sem gravar nada.
LP_EVENTOS_PERMITIDOS = {
    "lp_scroll_25", "lp_scroll_50", "lp_scroll_75", "lp_scroll_100",
    "lp_viu_oferta", "lp_form_focus", "lp_cta_hero", "lp_cta_bar", "lp_whatsapp",
}


@bp.route("/")
def home():
    keys_disponiveis = Key.total_disponiveis()
    cfg = SiteConfig.get_all()
    return render_template("marketing/home.html",
                           keys_disponiveis=keys_disponiveis, cfg=cfg)


@bp.route("/recursos")
def recursos():
    return render_template("marketing/recursos.html")


@bp.route("/como-funciona")
def como_funciona():
    return render_template("marketing/como_funciona.html")


@bp.route("/planos")
def planos():
    keys_disponiveis = Key.total_disponiveis()
    return render_template("marketing/planos.html", keys_disponiveis=keys_disponiveis)


@bp.route("/faq")
def faq():
    return render_template("marketing/faq.html")


@bp.route("/contato", methods=["GET", "POST"])
def contato():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()
        mensagem = request.form.get("mensagem", "").strip()
        if nome and email and mensagem:
            from ..services.email_service import send_email
            send_email(
                to=current_app.config.get("MAIL_USERNAME", ""),
                subject=f"Contato via Site — {nome}",
                template="emails/contato_interno.html",
                nome=nome, email=email, mensagem=mensagem,
            )
            flash("Mensagem enviada! Retornaremos em até 24h.", "success")
        else:
            flash("Preencha todos os campos.", "danger")
        return redirect(url_for("main.contato"))
    return render_template("marketing/contato.html")


@bp.route("/lp")
def lp():
    """Landing page de conversão (tráfego pago) — sem menu, um único CTA."""
    from ..models.traffic_event import TrafficEvent
    TrafficEvent.registrar("lp_view", request)

    preco = float(SiteConfig.get("produto_preco", "297.00"))
    try:
        preco_de = float(SiteConfig.get("produto_preco_de") or 0)
    except ValueError:
        preco_de = 0.0
    if preco_de <= preco:
        preco_de = 597.0
    parcela = preco * 1.2 / 12  # 12x com acréscimo embutido (~20%)
    economia = preco_de - preco

    def _fmt(v):
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    keys_disponiveis = Key.total_disponiveis()
    return render_template(
        "marketing/lp.html",
        preco=preco,
        preco_fmt=_fmt(preco),
        preco_de_fmt=_fmt(preco_de),
        parcela_fmt=_fmt(parcela),
        economia_fmt=_fmt(economia),
        keys_disponiveis=keys_disponiveis,
    )


@bp.route("/lp/evento", methods=["POST"])
@csrf.exempt  # beacon anônimo via sendBeacon — não carrega token CSRF
@limiter.limit("60 per minute")  # visita normal gera no máx. 9 eventos
def lp_evento():
    """Registra eventos de comportamento na LP (scroll, oferta visível,
    foco no formulário, cliques em CTA). Sem dados pessoais: só o tipo
    do evento + device/IP que o TrafficEvent já registra para visitas."""
    tipo = (request.form.get("tipo") or "").strip()
    if tipo not in LP_EVENTOS_PERMITIDOS:
        return "", 204
    from ..models.traffic_event import TrafficEvent
    TrafficEvent.registrar(tipo, request)
    return "", 204


@bp.route("/privacidade")
def privacidade():
    return render_template("marketing/privacidade.html")


@bp.route("/termos")
def termos():
    return render_template("marketing/termos.html")


@bp.route("/health")
def health():
    from flask import jsonify
    return jsonify({"status": "ok"}), 200


@bp.route("/robots.txt")
def robots():
    from flask import Response
    base = current_app.config["BASE_URL"]
    content = f"User-agent: *\nDisallow: /admin/\nDisallow: /auth/\nDisallow: /payment/\nSitemap: {base}/sitemap.xml\n"
    return Response(content, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap():
    from flask import Response
    base = current_app.config["BASE_URL"]
    pages = ["", "/recursos", "/como-funciona", "/planos", "/faq", "/contato"]
    urls = "\n".join(f"  <url><loc>{base}{p}</loc></url>" for p in pages)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>"""
    return Response(xml, mimetype="application/xml")
