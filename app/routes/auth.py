import secrets
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db, limiter
from ..models.user import User
from ..models.log import Log

bp = Blueprint("auth", __name__)


def _get_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute;5 per second")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("client.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        lembrar = request.form.get("lembrar") == "on"

        user = User.query.filter_by(email=email).first()

        if not user or not user.is_active:
            flash("E-mail ou senha incorretos.", "danger")
            Log.registrar("login_falha", f"email={email}", ip=_get_ip())
            return render_template("auth/login.html")

        if user.is_locked():
            flash("Conta temporariamente bloqueada. Tente novamente em alguns minutos.", "danger")
            return render_template("auth/login.html")

        if not user.check_senha(senha):
            user.login_attempts = (user.login_attempts or 0) + 1
            max_attempts = current_app.config["MAX_LOGIN_ATTEMPTS"]
            if user.login_attempts >= max_attempts:
                lockout = current_app.config["LOGIN_LOCKOUT_MINUTES"]
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout)
                flash(f"Muitas tentativas. Conta bloqueada por {lockout} minutos.", "danger")
            else:
                flash("E-mail ou senha incorretos.", "danger")
            db.session.commit()
            Log.registrar("login_falha", f"email={email}", ip=_get_ip())
            return render_template("auth/login.html")

        # Sucesso
        user.login_attempts = 0
        user.locked_until = None
        user.ultimo_login = datetime.now(timezone.utc)
        db.session.commit()
        login_user(user, remember=lembrar)
        Log.registrar("login_sucesso", user_id=user.id, ip=_get_ip())

        next_page = request.args.get("next")
        if user.is_admin:
            return redirect(next_page or url_for("admin.dashboard"))
        return redirect(next_page or url_for("client.dashboard"))

    return render_template("auth/login.html")


@bp.route("/registro", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("client.dashboard"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        senha2 = request.form.get("senha2", "")
        telefone = request.form.get("telefone", "").strip()

        errors = []
        if not nome or len(nome) < 3:
            errors.append("Nome deve ter pelo menos 3 caracteres.")
        if not email or "@" not in email:
            errors.append("E-mail inválido.")
        if len(senha) < 8:
            errors.append("Senha deve ter pelo menos 8 caracteres.")
        if senha != senha2:
            errors.append("As senhas não conferem.")
        if User.query.filter_by(email=email).first():
            errors.append("Este e-mail já está cadastrado.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/registro.html", nome=nome, email=email, telefone=telefone)

        user = User(nome=nome, email=email, telefone=telefone)
        user.set_senha(senha)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        Log.registrar("cadastro", user_id=user.id, ip=_get_ip())
        flash(f"Bem-vindo, {nome.split()[0]}! Sua conta foi criada.", "success")
        return redirect(url_for("client.dashboard"))

    return render_template("auth/registro.html")


@bp.route("/logout")
@login_required
def logout():
    Log.registrar("logout", user_id=current_user.id, ip=_get_ip())
    logout_user()
    return redirect(url_for("main.home"))


@bp.route("/recuperar-senha", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def recuperar_senha():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_exp = datetime.now(timezone.utc) + timedelta(hours=2)
            db.session.commit()
            from ..services.email_service import enviar_recuperacao_senha
            enviar_recuperacao_senha(user, token)
        # Sempre mostrar a mesma mensagem (evita enumeração de e-mails)
        flash("Se este e-mail estiver cadastrado, você receberá as instruções em breve.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/recuperar_senha.html")


@bp.route("/nova-senha/<token>", methods=["GET", "POST"])
def nova_senha(token):
    user = User.query.filter_by(reset_token=token).first()
    # Coluna DateTime sem timezone: o banco devolve naive (UTC); normaliza antes de comparar
    exp = user.reset_token_exp if user else None
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if not user or not exp or exp < datetime.now(timezone.utc):
        flash("Link inválido ou expirado.", "danger")
        return redirect(url_for("auth.recuperar_senha"))

    if request.method == "POST":
        senha = request.form.get("senha", "")
        senha2 = request.form.get("senha2", "")
        if len(senha) < 8:
            flash("Senha deve ter pelo menos 8 caracteres.", "danger")
            return render_template("auth/nova_senha.html", token=token)
        if senha != senha2:
            flash("As senhas não conferem.", "danger")
            return render_template("auth/nova_senha.html", token=token)
        user.set_senha(senha)
        user.reset_token = None
        user.reset_token_exp = None
        db.session.commit()
        flash("Senha alterada com sucesso! Faça login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/nova_senha.html", token=token)
