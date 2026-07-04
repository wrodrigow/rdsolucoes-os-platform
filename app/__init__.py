import os
from flask import Flask
from .config import config
from .extensions import db, login_manager, mail, csrf, migrate, limiter


def create_app(env=None):
    env = env or os.environ.get("FLASK_ENV", "default")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[env])

    # ProxyFix: necessário para funcionar atrás de proxy reverso (Passenger/nginx)
    # x_prefix=1 faz Flask respeitar o SCRIPT_NAME setado pelo Passenger (/rdos)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Extensões
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para acessar esta página."
    login_manager.login_message_category = "warning"

    # Blueprints
    from .routes.main import bp as main_bp
    from .routes.auth import bp as auth_bp
    from .routes.client import bp as client_bp
    from .routes.admin import bp as admin_bp
    from .routes.checkout import bp as checkout_bp
    from .routes.payment import bp as payment_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(client_bp, url_prefix="/cliente")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(checkout_bp, url_prefix="/checkout")
    app.register_blueprint(payment_bp, url_prefix="/payment")

    # Contexto global para templates
    @app.context_processor
    def inject_globals():
        from .models.site_config import SiteConfig
        try:
            cfg = SiteConfig.get_all()
        except Exception:
            cfg = {}
        return {"site_cfg": cfg, "site_name": app.config["SITE_NAME"]}

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://sdk.mercadopago.com https://www.googletagmanager.com https://connect.facebook.net; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "frame-src https://www.mercadopago.com.br https://www.mercadolibre.com; "
            "connect-src 'self' https://api.mercadopago.com https://www.facebook.com https://connect.facebook.net;"
        )
        return response

    # Handlers de erro
    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("404.html"), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        from flask import render_template
        return render_template("429.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template("500.html"), 500

    # Criar tabelas e dados iniciais
    with app.app_context():
        db.create_all()
        _seed_initial_data(app)

    return app


def _seed_initial_data(app):
    from .models.site_config import SiteConfig
    from .models.download import Download

    defaults = {
        "site_nome": "RD Soluções OS",
        "site_email_contato": "contato@rdsolucoes.com.br",
        "site_telefone": "(11) 94157-9827",
        "site_whatsapp": "5511941579827",
        "hero_headline": "Chega de Bagunça. Gerencie Sua Empresa com Profissionalismo.",
        "hero_subheadline": "Orçamentos, Ordens de Serviço, Controle Financeiro e Cadastro de Clientes — tudo em um único sistema. Sem internet. Sem mensalidade.",
        "produto_preco": "297.00",
        "produto_nome": "RD Soluções OS — Licença Vitalícia",
        "produto_versao_atual": "v1.19",
        "mp_ativo": "1",
        "manutencao_ativa": "0",
    }
    for k, v in defaults.items():
        SiteConfig.set_if_missing(k, v)

    # Versão inicial do download
    if not Download.query.first():
        d = Download(
            versao="v1.19",
            nome="RD Soluções OS v1.19",
            nome_arquivo="OrcamentosRD_Instalador_v1.19.exe",
            tamanho="60.5 MB",
            changelog="Versão inicial oficial. Inclui Orçamentos, Ordens de Serviço e Controle Financeiro.",
            ativo=True,
        )
        from .extensions import db
        db.session.add(d)
        db.session.commit()
