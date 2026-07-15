import os
import re

from flask import Blueprint, jsonify, request

from ..extensions import csrf, db, limiter
from ..models.blog import BlogArticle, BlogLead, BlogSubscriber

bp = Blueprint("blog_api", __name__)

# Mesmo padrão do tracking.py: CORS isolado deste blueprint para o site
# estático (onde o blog é publicado), sem tocar no CSP global da app.
ORIGENS_PERMITIDAS = {
    "https://rdsolucoes.eco.br",
    "https://www.rdsolucoes.eco.br",
}

RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.after_request
def _cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in ORIGENS_PERMITIDAS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Vary"] = "Origin"
    return response


def _token_valido():
    esperado = os.environ.get("BLOG_API_TOKEN", "")
    recebido = request.headers.get("X-Blog-Token", "")
    return bool(esperado) and recebido == esperado


@bp.route("/artigos", methods=["GET", "POST", "OPTIONS"])
@csrf.exempt
@limiter.limit("30 per minute")
def artigos():
    """GET: lista artigos registrados (usado pela automação pra evitar tema
    duplicado). POST: registra uma publicação nova. Ambos exigem o token da
    automação — não são endpoints de navegador."""
    if request.method == "OPTIONS":
        return "", 204
    if not _token_valido():
        return jsonify({"erro": "não autorizado"}), 401

    if request.method == "GET":
        registros = BlogArticle.query.order_by(BlogArticle.published_at.desc()).all()
        return jsonify([
            {"slug": a.slug, "title": a.title, "category": a.category,
             "keyword": a.keyword, "url": a.url,
             "published_at": a.published_at.isoformat()}
            for a in registros
        ])

    dados = request.get_json(silent=True) or {}
    slug = (dados.get("slug") or "").strip()
    title = (dados.get("title") or "").strip()
    category = (dados.get("category") or "").strip()
    url = (dados.get("url") or "").strip()
    if not (slug and title and category and url):
        return jsonify({"erro": "slug, title, category e url são obrigatórios"}), 400

    artigo = BlogArticle.query.filter_by(slug=slug).first()
    if artigo is None:
        artigo = BlogArticle(slug=slug)
        db.session.add(artigo)
    artigo.title = title
    artigo.category = category
    artigo.url = url
    artigo.keyword = (dados.get("keyword") or "").strip() or None
    artigo.words = dados.get("words")
    artigo.status = (dados.get("status") or "publicado").strip()
    db.session.commit()
    return jsonify({"ok": True, "id": artigo.id}), 201


@bp.route("/newsletter", methods=["POST", "OPTIONS"])
@csrf.exempt
@limiter.limit("10 per minute")
def newsletter():
    """Inscrição pública de newsletter, chamada pelo form dos artigos."""
    if request.method == "OPTIONS":
        return "", 204

    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    if not RE_EMAIL.match(email):
        return jsonify({"erro": "email inválido"}), 400

    if not BlogSubscriber.query.filter_by(email=email).first():
        db.session.add(BlogSubscriber(
            email=email,
            origem=(dados.get("origem") or "")[:300] or None,
        ))
        db.session.commit()
    return jsonify({"ok": True})


@bp.route("/lead", methods=["POST", "OPTIONS"])
@csrf.exempt
@limiter.limit("10 per minute")
def lead():
    """Pedido de orçamento vindo do blog."""
    if request.method == "OPTIONS":
        return "", 204

    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    telefone = (dados.get("telefone") or "").strip()
    if not email and not telefone:
        return jsonify({"erro": "informe email ou telefone"}), 400
    if email and not RE_EMAIL.match(email):
        return jsonify({"erro": "email inválido"}), 400

    registro = BlogLead(
        nome=(dados.get("nome") or "")[:120] or None,
        email=email or None,
        telefone=telefone[:30] or None,
        mensagem=(dados.get("mensagem") or "")[:2000] or None,
        origem=(dados.get("origem") or "")[:300] or None,
    )
    db.session.add(registro)
    db.session.commit()

    try:
        from ..services.email_service import send_email
        send_email(
            os.environ.get("ADMIN_EMAIL", "contato@rdsolucoes.eco.br"),
            "Novo lead do Blog RD Soluções",
            "emails/blog_lead.html",
            lead=registro,
        )
    except Exception:
        pass  # lead já está salvo; falha de email não pode derrubar a resposta

    return jsonify({"ok": True})
