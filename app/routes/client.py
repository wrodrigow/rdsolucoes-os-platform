import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models.order import Order
from ..models.license import License
from ..models.download import Download
from ..services.key_service import get_license_for_user

bp = Blueprint("client", __name__)


def _require_client(fn):
    """Decorator: requer login e conta não-admin."""
    from functools import wraps
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return fn(*args, **kwargs)
    return wrapped


@bp.route("/")
@bp.route("/dashboard")
@_require_client
def dashboard():
    license_ = get_license_for_user(current_user.id)
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()
    return render_template("client/dashboard.html", license=license_, orders=orders)


@bp.route("/licenca")
@_require_client
def licenca():
    license_ = get_license_for_user(current_user.id)
    if not license_:
        flash("Nenhuma licença encontrada. Realize a compra para ter acesso.", "warning")
        return redirect(url_for("checkout.index"))
    download = Download.get_ativo()
    return render_template("client/licenca.html", license=license_, download=download)


@bp.route("/downloads")
@_require_client
def downloads():
    license_ = get_license_for_user(current_user.id)
    if not license_:
        flash("Acesso restrito a clientes com licença ativa.", "warning")
        return redirect(url_for("checkout.index"))
    versions = Download.query.filter_by(ativo=True).order_by(Download.created_at.desc()).all()
    return render_template("client/downloads.html", versions=versions, license=license_)


@bp.route("/download/<int:download_id>")
@_require_client
def fazer_download(download_id):
    license_ = get_license_for_user(current_user.id)
    if not license_:
        flash("Licença necessária para realizar o download.", "danger")
        return redirect(url_for("checkout.index"))

    dl = Download.query.get_or_404(download_id)
    dl.downloads_count = (dl.downloads_count or 0) + 1
    db.session.commit()

    folder = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(folder, dl.nome_arquivo, as_attachment=True)


@bp.route("/historico")
@_require_client
def historico():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("client/historico.html", orders=orders)


@bp.route("/dados", methods=["GET", "POST"])
@_require_client
def dados():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = request.form.get("telefone", "").strip()
        empresa = request.form.get("empresa", "").strip()
        if len(nome) < 3:
            flash("Nome deve ter pelo menos 3 caracteres.", "danger")
        else:
            current_user.nome = nome
            current_user.telefone = telefone
            current_user.empresa = empresa
            db.session.commit()
            flash("Dados atualizados com sucesso!", "success")
        return redirect(url_for("client.dados"))
    return render_template("client/dados.html")


@bp.route("/senha", methods=["GET", "POST"])
@_require_client
def senha():
    if request.method == "POST":
        senha_atual = request.form.get("senha_atual", "")
        nova = request.form.get("nova", "")
        nova2 = request.form.get("nova2", "")

        if not current_user.check_senha(senha_atual):
            flash("Senha atual incorreta.", "danger")
        elif len(nova) < 8:
            flash("Nova senha deve ter pelo menos 8 caracteres.", "danger")
        elif nova != nova2:
            flash("As senhas não conferem.", "danger")
        else:
            current_user.set_senha(nova)
            db.session.commit()
            flash("Senha alterada com sucesso!", "success")
        return redirect(url_for("client.senha"))
    return render_template("client/senha.html")


@bp.route("/suporte")
@_require_client
def suporte():
    return render_template("client/suporte.html")


@bp.route("/faq")
@_require_client
def faq():
    return render_template("client/faq_client.html")
