import os
import csv
import io
from datetime import datetime, timezone
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, current_app, Response)
from flask_login import login_required, current_user
from ..extensions import db
from ..models.user import User
from ..models.order import Order
from ..models.key import Key
from ..models.license import License
from ..models.download import Download
from ..models.log import Log
from ..models.site_config import SiteConfig

bp = Blueprint("admin", __name__)


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            flash("Acesso restrito a administradores.", "danger")
            return redirect(url_for("main.home"))
        return fn(*args, **kwargs)
    return wrapped


# ── Dashboard ──────────────────────────────────────────────────────────────────

@bp.route("/")
@bp.route("/dashboard")
@admin_required
def dashboard():
    from sqlalchemy import func, extract
    now = datetime.now()

    receita_total = db.session.query(func.sum(Order.valor)).filter_by(status="approved").scalar() or 0.0
    pedidos_aprovados = Order.query.filter_by(status="approved").count()
    receita_mes = db.session.query(func.sum(Order.valor)).filter(
        Order.status == "approved",
        extract("month", Order.approved_at) == now.month,
        extract("year", Order.approved_at) == now.year,
    ).scalar() or 0.0
    ticket_medio = (receita_total / pedidos_aprovados) if pedidos_aprovados else 0.0

    stats = {
        "total_clientes": User.query.filter_by(is_admin=False).count(),
        "total_pedidos": Order.query.count(),
        "pedidos_aprovados": pedidos_aprovados,
        "keys_disponiveis": Key.total_disponiveis(),
        "receita_total": float(receita_total),
        "receita_mes": float(receita_mes),
        "ticket_medio": float(ticket_medio),
    }

    # Gráfico: últimos 12 meses
    from calendar import month_abbr
    meses_labels = []
    meses_values = []
    for i in range(11, -1, -1):
        import calendar
        m = (now.month - i - 1) % 12 + 1
        y = now.year - ((now.month - i - 1) // 12 + (1 if (now.month - i - 1) < 0 else 0))
        if (now.month - i - 1) < 0:
            y = now.year - 1
            m = (now.month - i - 1) % 12 + 1
        total = db.session.query(func.sum(Order.valor)).filter(
            Order.status == "approved",
            extract("month", Order.approved_at) == m,
            extract("year", Order.approved_at) == y,
        ).scalar() or 0
        meses_labels.append(f"{month_abbr[m]}/{str(y)[2:]}")
        meses_values.append(float(total))

    pedidos_recentes = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    logs_recentes = Log.query.order_by(Log.created_at.desc()).limit(20).all()

    return render_template("admin/dashboard.html",
                           stats=stats,
                           grafico_labels=meses_labels,
                           grafico_values=meses_values,
                           pedidos_recentes=pedidos_recentes,
                           logs_recentes=logs_recentes)


# ── Clientes ───────────────────────────────────────────────────────────────────

@bp.route("/clientes")
@admin_required
def clientes():
    if request.args.get("export") == "csv":
        return _exportar_clientes_csv()

    q = request.args.get("q", "").strip()
    tem_licenca = request.args.get("tem_licenca", "")
    page = request.args.get("page", 1, type=int)

    from sqlalchemy import exists as sa_exists
    query = User.query.filter_by(is_admin=False)
    if q:
        query = query.filter(
            (User.nome.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )
    if tem_licenca == "1":
        subq = sa_exists().where(License.user_id == User.id)
        query = query.filter(subq)
    elif tem_licenca == "0":
        subq = sa_exists().where(License.user_id == User.id)
        query = query.filter(~subq)

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("admin/clientes.html", clientes=pagination.items,
                           pagination=pagination, q=q, tem_licenca=tem_licenca)


def _exportar_clientes_csv():
    users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["Nome", "Email", "Telefone", "Empresa", "Cadastrado em"])
    for u in users:
        w.writerow([u.nome, u.email, u.telefone or "", u.empresa or "",
                    u.created_at.strftime("%d/%m/%Y %H:%M")])
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=clientes.csv"})


# ── Pedidos ────────────────────────────────────────────────────────────────────

@bp.route("/pedidos")
@admin_required
def pedidos():
    if request.args.get("export") == "csv":
        return _exportar_pedidos_csv()

    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)
    user_id = request.args.get("user_id", "")

    query = Order.query
    if q:
        query = query.filter(Order.numero_pedido.ilike(f"%{q}%"))
    if status_filter:
        query = query.filter_by(status=status_filter)
    if user_id:
        query = query.filter_by(user_id=user_id)

    pagination = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("admin/pedidos.html", pedidos=pagination.items,
                           pagination=pagination, q=q, status_filter=status_filter)


def _exportar_pedidos_csv():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["Número", "Cliente", "E-mail", "Valor", "Status", "Método", "Data"])
    for o in orders:
        w.writerow([o.numero_pedido, o.user.nome if o.user else "", o.user.email if o.user else "",
                    f"{float(o.valor):.2f}", o.status, o.mp_payment_method or "",
                    o.created_at.strftime("%d/%m/%Y %H:%M")])
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=pedidos.csv"})


@bp.route("/pedidos/<string:order_id>/reenviar-email", methods=["POST"])
@admin_required
def reenviar_email(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status != "approved" or not order.license:
        flash("Pedido não aprovado ou sem licença.", "warning")
        return redirect(url_for("admin.pedidos"))
    from ..services.email_service import enviar_confirmacao_compra
    ok = enviar_confirmacao_compra(order, order.license, order.user)
    flash("E-mail reenviado!" if ok else "Erro ao reenviar e-mail.", "success" if ok else "danger")
    return redirect(url_for("admin.pedidos"))


# ── Keys ────────────────────────────────────────────────────────────────────────

@bp.route("/keys")
@admin_required
def keys():
    status_filter = request.args.get("status_filter", "")
    page = request.args.get("page", 1, type=int)
    query = Key.query
    if status_filter:
        query = query.filter_by(status=status_filter)

    pagination = query.order_by(Key.id.desc()).paginate(page=page, per_page=50, error_out=False)
    total_disponiveis = Key.query.filter_by(status="disponivel").count()
    total_vendidas = Key.query.filter_by(status="vendida").count()
    total_reservadas = Key.query.filter_by(status="reservada").count()
    total_geral = Key.query.count()

    return render_template("admin/keys.html",
                           keys=pagination.items,
                           pagination=pagination,
                           status_filter=status_filter,
                           total_disponiveis=total_disponiveis,
                           total_vendidas=total_vendidas,
                           total_reservadas=total_reservadas,
                           total_geral=total_geral)


@bp.route("/keys/importar", methods=["POST"])
@admin_required
def importar_keys():
    raw = ""
    file = request.files.get("keys_file")
    if file and file.filename:
        raw = file.read().decode("utf-8", errors="ignore")
    else:
        raw = request.form.get("keys_texto", "")

    linhas = [l.strip() for l in raw.replace(",", "\n").splitlines() if l.strip()]
    importadas = 0
    duplicadas = 0
    for key_str in linhas:
        if not key_str or key_str.startswith("#"):
            continue
        if Key.query.filter_by(key=key_str).first():
            duplicadas += 1
            continue
        db.session.add(Key(key=key_str, status="disponivel"))
        importadas += 1

    db.session.commit()
    flash(f"{importadas} keys importadas. {duplicadas} duplicadas ignoradas.", "success")
    return redirect(url_for("admin.keys"))


# ── Licenças ───────────────────────────────────────────────────────────────────

@bp.route("/licencas")
@admin_required
def licencas():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status_filter", "")
    page = request.args.get("page", 1, type=int)

    query = License.query.join(User)
    if q:
        query = query.filter(
            (User.nome.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )
    if status_filter:
        query = query.filter(License.status == status_filter)

    pagination = query.order_by(License.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("admin/licencas.html",
                           licencas=pagination.items,
                           pagination=pagination,
                           q=q,
                           status_filter=status_filter)


@bp.route("/licencas/<string:lic_id>/status", methods=["POST"])
@admin_required
def alterar_status_licenca(lic_id):
    lic = License.query.get_or_404(lic_id)
    novo = request.form.get("novo_status")
    if novo in ("ativa", "suspensa", "cancelada"):
        lic.status = novo
        db.session.commit()
        flash(f"Licença atualizada para '{novo}'.", "success")
    return redirect(url_for("admin.licencas"))


# ── Downloads ──────────────────────────────────────────────────────────────────

@bp.route("/downloads")
@admin_required
def downloads():
    versoes = Download.query.order_by(Download.created_at.desc()).all()
    return render_template("admin/downloads.html", versoes=versoes)


@bp.route("/downloads/nova", methods=["POST"])
@admin_required
def nova_versao():
    versao = request.form.get("versao", "").strip()
    nome = request.form.get("nome", "").strip()
    changelog = request.form.get("changelog", "").strip()
    ativo = bool(request.form.get("ativo"))

    arquivo = request.files.get("arquivo")
    nome_arquivo = ""
    tamanho = ""
    if arquivo and arquivo.filename:
        nome_arquivo = arquivo.filename
        folder = os.path.join(current_app.root_path, "static", "uploads", "versoes")
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, nome_arquivo)
        arquivo.save(dest)
        size_bytes = os.path.getsize(dest)
        tamanho = f"{size_bytes / 1024 / 1024:.1f} MB"

    if not versao or not nome_arquivo:
        flash("Versão e arquivo são obrigatórios.", "danger")
        return redirect(url_for("admin.downloads"))

    if ativo:
        Download.query.update({"ativo": False})

    d = Download(versao=versao, nome=nome or f"RD Soluções OS {versao}",
                 nome_arquivo=nome_arquivo, tamanho=tamanho, changelog=changelog, ativo=ativo)
    db.session.add(d)
    db.session.commit()

    if ativo:
        SiteConfig.set("produto_versao_atual", versao)

    flash(f"Versão {versao} publicada!", "success")
    return redirect(url_for("admin.downloads"))


@bp.route("/downloads/<int:versao_id>/ativar", methods=["POST"])
@admin_required
def ativar_versao(versao_id):
    Download.query.update({"ativo": False})
    d = Download.query.get_or_404(versao_id)
    d.ativo = True
    db.session.commit()
    SiteConfig.set("produto_versao_atual", d.versao)
    flash(f"Versão {d.versao} definida como ativa.", "success")
    return redirect(url_for("admin.downloads"))


# ── Financeiro ─────────────────────────────────────────────────────────────────

@bp.route("/financeiro")
@admin_required
def financeiro():
    from sqlalchemy import func, extract
    from calendar import month_name as month_names
    now = datetime.now()

    receita_total = float(db.session.query(func.sum(Order.valor)).filter_by(status="approved").scalar() or 0)
    total_vendas = Order.query.filter_by(status="approved").count()
    ticket_medio = (receita_total / total_vendas) if total_vendas else 0.0

    receita_mes_atual = float(db.session.query(func.sum(Order.valor)).filter(
        Order.status == "approved",
        extract("month", Order.approved_at) == now.month,
        extract("year", Order.approved_at) == now.year,
    ).scalar() or 0)

    # Últimos 12 meses para gráfico
    grafico_labels = []
    grafico_values = []
    for i in range(11, -1, -1):
        offset = now.month - 1 - i
        y = now.year + offset // 12
        m = offset % 12 + 1
        if offset < 0:
            y = now.year - 1
            m = 12 + offset + 1
        total = float(db.session.query(func.sum(Order.valor)).filter(
            Order.status == "approved",
            extract("month", Order.approved_at) == m,
            extract("year", Order.approved_at) == y,
        ).scalar() or 0)
        from calendar import month_abbr
        grafico_labels.append(f"{month_abbr[m]}/{str(y)[2:]}")
        grafico_values.append(total)

    # Detalhamento mensal
    mensal = (
        db.session.query(
            extract("year", Order.approved_at).label("ano"),
            extract("month", Order.approved_at).label("mes"),
            func.sum(Order.valor).label("total"),
            func.count(Order.id).label("qtd"),
        )
        .filter(Order.status == "approved")
        .group_by("ano", "mes")
        .order_by(db.text("ano DESC, mes DESC"))
        .limit(24)
        .all()
    )

    meses_pt = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

    detalhamento = []
    for row in mensal:
        rec = float(row.total or 0)
        qtd = row.qtd or 0
        detalhamento.append({
            "mes_label": f"{meses_pt[int(row.mes)]} {int(row.ano)}",
            "qtd": qtd,
            "receita": rec,
            "ticket": rec / qtd if qtd else 0,
            "pct": (rec / receita_total * 100) if receita_total else 0,
        })

    return render_template("admin/financeiro.html",
                           receita_total=receita_total,
                           receita_mes_atual=receita_mes_atual,
                           total_vendas=total_vendas,
                           ticket_medio=ticket_medio,
                           grafico_labels=grafico_labels,
                           grafico_values=grafico_values,
                           detalhamento=detalhamento)


# ── Configurações ──────────────────────────────────────────────────────────────

@bp.route("/configuracoes", methods=["GET", "POST"])
@admin_required
def configuracoes():
    if request.method == "POST":
        chaves_editaveis = [
            "site_name", "site_slogan", "site_email_contato", "site_whatsapp",
            "site_url", "site_cnpj", "seo_title", "seo_description", "seo_keywords",
            "ga_id", "produto_nome", "produto_preco", "produto_preco_de",
            "produto_versao", "mail_sender_name", "mail_footer", "mail_suporte",
        ]
        for chave in chaves_editaveis:
            valor = request.form.get(chave, "").strip()
            SiteConfig.set(chave, valor)

        vendas_abertas = "1" if request.form.get("vendas_abertas") else "0"
        SiteConfig.set("vendas_abertas", vendas_abertas)

        flash("Configurações salvas!", "success")
        return redirect(url_for("admin.configuracoes"))

    cfg = SiteConfig.get_all()
    return render_template("admin/configuracoes.html", cfg=cfg)


# ── Logs ───────────────────────────────────────────────────────────────────────

@bp.route("/logs")
@admin_required
def logs():
    q = request.args.get("q", "").strip()
    acao_filter = request.args.get("acao_filter", "")
    page = request.args.get("page", 1, type=int)

    query = Log.query
    if q:
        query = query.filter(
            (Log.acao.ilike(f"%{q}%")) | (Log.detalhes.ilike(f"%{q}%"))
        )
    if acao_filter:
        query = query.filter(Log.acao.ilike(f"%{acao_filter}%"))

    pagination = query.order_by(Log.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template("admin/logs.html",
                           logs=pagination.items,
                           pagination=pagination,
                           q=q,
                           acao_filter=acao_filter)
