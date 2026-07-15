from datetime import datetime, timezone
from ..extensions import db


class BlogArticle(db.Model):
    """Registro (log administrativo) de cada artigo publicado no blog estático
    de rdsolucoes.eco.br/blog. O conteúdo em si vive como HTML no Hostinger;
    aqui fica só o índice — usado pelo painel admin e pela automação de
    publicação para consultar temas já cobertos e evitar duplicatas."""
    __tablename__ = "blog_articles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    slug = db.Column(db.String(200), nullable=False, unique=True, index=True)
    title = db.Column(db.String(300), nullable=False)
    category = db.Column(db.String(60), nullable=False, index=True)
    keyword = db.Column(db.String(200), nullable=True)
    url = db.Column(db.String(400), nullable=False)
    words = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="publicado")
    published_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class BlogSubscriber(db.Model):
    """Inscritos na newsletter do blog (formulário nas páginas de artigo)."""
    __tablename__ = "blog_subscribers"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    origem = db.Column(db.String(300), nullable=True)  # path do artigo de origem
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class BlogLead(db.Model):
    """Pedidos de orçamento vindos do blog (formulário/CTA das páginas)."""
    __tablename__ = "blog_leads"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    mensagem = db.Column(db.Text, nullable=True)
    origem = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
