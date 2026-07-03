from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from ..models.key import Key
from ..models.site_config import SiteConfig
from ..models.download import Download

bp = Blueprint("main", __name__)


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
    preco = float(SiteConfig.get("produto_preco", "297.00"))
    keys_disponiveis = Key.total_disponiveis()
    return render_template("marketing/lp.html", preco=preco, keys_disponiveis=keys_disponiveis)


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
