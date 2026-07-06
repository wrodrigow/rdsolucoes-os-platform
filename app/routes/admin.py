import os
import re
import csv
import io
from datetime import datetime, timedelta, timezone
from collections import OrderedDict
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, current_app, Response, jsonify)
from flask_login import login_required, current_user
from ..extensions import db
from ..models.user import User
from ..models.order import Order
from ..models.key import Key
from ..models.license import License
from ..models.download import Download
from ..models.log import Log
from ..models.site_config import SiteConfig
from ..models.traffic_event import TrafficEvent

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

    # Extrai somente tokens no formato XXXX-XXXX-XXXX-XXXX de cada linha
    KEY_RE = re.compile(r'\b([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})\b')
    linhas = [l.strip() for l in raw.replace(",", "\n").splitlines()]
    candidatas = list(dict.fromkeys(
        match.group(1)
        for linha in linhas
        if linha and not linha.startswith("#")
        for match in [KEY_RE.search(linha.upper())]
        if match
    ))

    if not candidatas:
        flash("Nenhuma key válida encontrada no arquivo.", "warning")
        return redirect(url_for("admin.keys"))

    # 1 query para buscar todas as já existentes de uma vez
    existentes = {k.key for k in Key.query.filter(Key.key.in_(candidatas)).all()}
    novas = [k for k in candidatas if k not in existentes]
    duplicadas = len(candidatas) - len(novas)

    now = datetime.now(timezone.utc)
    for k in novas:
        db.session.add(Key(key=k, status="disponivel", created_at=now))
    db.session.commit()
    importadas = len(novas)
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
    url_externa = request.form.get("url_externa", "").strip()

    arquivo = request.files.get("arquivo")
    nome_arquivo = ""
    tamanho = "—"
    if arquivo and arquivo.filename:
        nome_arquivo = arquivo.filename
        folder = os.path.join(current_app.root_path, "static", "uploads", "versoes")
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, nome_arquivo)
        arquivo.save(dest)
        size_bytes = os.path.getsize(dest)
        tamanho = f"{size_bytes / 1024 / 1024:.1f} MB"
    elif url_externa:
        nome_arquivo = url_externa.split("/")[-1].split("?")[0] or f"instalador_{versao}.exe"

    if not versao or (not nome_arquivo and not url_externa):
        flash("Versão e URL de download (ou arquivo) são obrigatórios.", "danger")
        return redirect(url_for("admin.downloads"))

    if ativo:
        Download.query.update({"ativo": False})

    d = Download(versao=versao, nome=nome or f"RD Soluções OS {versao}",
                 nome_arquivo=nome_arquivo, tamanho=tamanho, changelog=changelog,
                 ativo=ativo, url_externa=url_externa or None)
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
            "site_telefone", "site_url", "site_cnpj", "seo_title", "seo_description",
            "seo_keywords", "ga_id", "meta_pixel_id", "gads_id", "gads_conversion_label",
            "produto_nome", "produto_preco",
            "produto_preco_de", "produto_versao", "mail_sender_name", "mail_footer", "mail_suporte",
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


# ── Simular Compra ─────────────────────────────────────────────────────────────

@bp.route("/clientes/<string:user_id>/simular-compra", methods=["POST"])
@admin_required
def simular_compra(user_id):
    from ..services.key_service import assign_key
    from ..services.email_service import enviar_confirmacao_compra

    user = User.query.get_or_404(user_id)

    if user.is_admin:
        flash("Não é possível simular compra para um administrador.", "warning")
        return redirect(url_for("admin.clientes"))

    licenca_existente = License.query.filter_by(user_id=user_id, status="ativa").first()
    if licenca_existente:
        flash(f"{user.nome} já possui uma licença ativa.", "warning")
        return redirect(url_for("admin.clientes"))

    if Key.total_disponiveis() == 0:
        flash("Não há keys disponíveis. Importe keys antes de simular.", "danger")
        return redirect(url_for("admin.keys"))

    try:
        now = datetime.now(timezone.utc)
        order = Order(
            numero_pedido=Order.gerar_numero(),
            user_id=user_id,
            produto_nome="RD Soluções OS — Licença Vitalícia",
            valor=297.00,
            status="approved",
            mp_payment_id="SIMULADO",
            mp_status="approved",
            mp_payment_method="SIMULADO",
            mp_payment_type="TESTE",
            approved_at=now,
        )
        db.session.add(order)
        db.session.flush()

        license_ = assign_key(order)

        Log.registrar(
            acao="COMPRA_SIMULADA",
            detalhes=f"Admin {current_user.email} simulou compra para {user.email} | pedido {order.numero_pedido} | key {license_.key_obj.key}",
            user_id=user_id,
            ip=request.remote_addr,
        )

        enviar_email = request.form.get("enviar_email") == "1"
        if enviar_email:
            enviar_confirmacao_compra(order, license_, user)

        flash(
            f"✅ Compra simulada para {user.nome}! "
            f"Pedido: {order.numero_pedido} | Key: {license_.key_obj.key}"
            + (" | E-mail de confirmação enviado." if enviar_email else ""),
            "success"
        )
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao simular compra: {e}", "danger")

    return redirect(url_for("admin.pedidos", user_id=user_id))


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


# ── Tráfego (Google Ads / LP) ────────────────────────────────────────────────

@bp.route("/trafego")
@admin_required
def trafego():
    return render_template("admin/trafego.html")


BRT = timezone(timedelta(hours=-3))  # Horário de Brasília (sem horário de verão desde 2019)


@bp.route("/trafego/dados")
@admin_required
def trafego_dados():
    now = datetime.now(timezone.utc)
    now_local = now.astimezone(BRT)
    desde = now - timedelta(hours=24)

    eventos = (
        TrafficEvent.query.filter(TrafficEvent.created_at >= desde)
        .order_by(TrafficEvent.created_at.asc())
        .all()
    )

    buckets = OrderedDict()
    for i in range(23, -1, -1):
        hora_dt = (now_local - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        buckets[hora_dt.strftime("%d/%m %Hh")] = {"real": 0, "bot": 0}

    lp_real = lp_bot = checkout_start = checkout_success = checkout_fail = 0
    device_mobile = device_desktop = 0
    canal_visitas_24h = {"google_ads": 0, "meta_ads": 0, "direto": 0}

    for e in eventos:
        # created_at é salvo em UTC; convertemos para horário local antes de exibir
        criado_local = e.created_at.replace(tzinfo=timezone.utc).astimezone(BRT)
        if e.event_type == "lp_view":
            hora_dt = criado_local.replace(minute=0, second=0, microsecond=0)
            label = hora_dt.strftime("%d/%m %Hh")
            if label in buckets:
                buckets[label]["bot" if e.is_bot else "real"] += 1
            if e.is_bot:
                lp_bot += 1
            else:
                lp_real += 1
                canal_visitas_24h[e.canal or "direto"] += 1
                if e.device == "mobile":
                    device_mobile += 1
                elif e.device == "desktop":
                    device_desktop += 1
        elif e.event_type == "checkout_start":
            checkout_start += 1
        elif e.event_type == "checkout_success":
            checkout_success += 1
        elif e.event_type == "checkout_fail":
            checkout_fail += 1

    total_lp = lp_real + lp_bot
    insights = []
    if lp_real > 0 and checkout_start == 0:
        insights.append({
            "tipo": "warning",
            "texto": f"{lp_real} visita(s) real(is) na LP nas últimas 24h, mas nenhuma tentativa de checkout. "
                     f"Pode ser preço, copy ou oferta — considere revisar a página ou testar um novo anúncio.",
        })
    if checkout_start > 0 and checkout_success == 0:
        insights.append({
            "tipo": "danger",
            "texto": f"{checkout_start} tentativa(s) de checkout iniciada(s), nenhuma concluída. "
                     f"O atrito está no Mercado Pago (ou o comprador desistiu no meio do pagamento), não na sua LP.",
        })
    if checkout_fail > 0:
        insights.append({
            "tipo": "danger",
            "texto": f"{checkout_fail} retorno(s) de falha/cancelamento do Mercado Pago nas últimas 24h.",
        })
    if total_lp > 0 and (lp_bot / total_lp) > 0.4:
        pct = round(lp_bot / total_lp * 100)
        insights.append({
            "tipo": "info",
            "texto": f"{lp_bot} de {total_lp} acessos à LP ({pct}%) são tráfego de robô/crawler "
                     f"(ex.: verificação automática do Google Ads), não cliques pagos reais.",
        })
    if not insights:
        insights.append({"tipo": "success", "texto": "Nenhum alerta no momento — funil sem gargalos aparentes nas últimas 24h."})

    eventos_recentes = [
        {
            "hora": e.created_at.replace(tzinfo=timezone.utc).astimezone(BRT).strftime("%d/%m %H:%M"),
            "tipo": e.event_type,
            "bot": e.is_bot,
            "device": e.device or "—",
        }
        for e in reversed(eventos[-40:])
    ]

    # Totais gerais (desde sempre, não só as últimas 24h) — dão o panorama
    # completo de acessos e vendas para acompanhamento contínuo da campanha.
    total_acessos_reais = TrafficEvent.query.filter(
        TrafficEvent.event_type == "lp_view", TrafficEvent.is_bot == False
    ).count()
    total_acessos_bot = TrafficEvent.query.filter(
        TrafficEvent.event_type == "lp_view", TrafficEvent.is_bot == True
    ).count()

    canal_visitas_total = {}
    for canal_key in ("google_ads", "meta_ads", "direto"):
        canal_visitas_total[canal_key] = TrafficEvent.query.filter(
            TrafficEvent.event_type == "lp_view",
            TrafficEvent.is_bot == False,
            TrafficEvent.canal == canal_key,
        ).count()

    CANAL_LABELS = {"google_ads": "Google Ads", "meta_ads": "Meta Ads", "direto": "Direto/Outro"}

    vendas_aprovadas = Order.query.filter(Order.status == "approved").order_by(Order.approved_at.desc()).all()
    total_vendas = len(vendas_aprovadas)
    receita_total = sum(float(o.valor) for o in vendas_aprovadas)

    # O canal de uma venda vem do evento "checkout_start" ligado ao pedido
    # (o gclid/fbclid só está disponível no clique que trouxe o comprador
    # até o formulário, não depois — por isso olhamos o checkout_start, não
    # o checkout_success).
    canal_por_order_id = {
        ev.order_id: ev.canal
        for ev in TrafficEvent.query.filter(TrafficEvent.event_type == "checkout_start").all()
        if ev.order_id
    }
    canal_vendas_total = {"google_ads": 0, "meta_ads": 0, "direto": 0}
    for o in vendas_aprovadas:
        canal_vendas_total[canal_por_order_id.get(o.id, "direto")] += 1

    vendas_recentes = [
        {
            "numero_pedido": o.numero_pedido,
            "cliente": o.user.nome if o.user else "—",
            "email": o.user.email if o.user else "—",
            "valor": o.valor_formatado(),
            "canal": CANAL_LABELS.get(canal_por_order_id.get(o.id, "direto"), "Direto/Outro"),
            "data": (o.approved_at or o.created_at).replace(tzinfo=timezone.utc).astimezone(BRT).strftime("%d/%m/%Y %H:%M"),
        }
        for o in vendas_aprovadas[:15]
    ]

    return jsonify({
        "chart_labels": list(buckets.keys()),
        "chart_real": [v["real"] for v in buckets.values()],
        "chart_bot": [v["bot"] for v in buckets.values()],
        "funil": {
            "lp_real": lp_real,
            "lp_bot": lp_bot,
            "checkout_start": checkout_start,
            "checkout_success": checkout_success,
            "checkout_fail": checkout_fail,
        },
        "device": {"mobile": device_mobile, "desktop": device_desktop},
        "canal": {
            "visitas_24h": canal_visitas_24h,
            "visitas_total": canal_visitas_total,
            "vendas_total": canal_vendas_total,
        },
        "insights": insights,
        "eventos_recentes": eventos_recentes,
        "totais": {
            "acessos_reais": total_acessos_reais,
            "acessos_bot": total_acessos_bot,
            "total_vendas": total_vendas,
            "receita_total": f"R$ {receita_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        },
        "vendas_recentes": vendas_recentes,
        "atualizado_em": now_local.strftime("%H:%M:%S"),
    })


# ── Manutenção: limpar dados de teste ────────────────────────────────────────

def _pedidos_de_teste_query():
    """Pedidos de teste/incompletos: a venda simulada (fictícia) e qualquer
    pedido que nunca foi de fato aprovado com pagamento real (pendente,
    cancelado, em processamento). Vendas realmente aprovadas (não simuladas)
    nunca são tocadas por esta rotina."""
    return Order.query.filter(
        db.or_(
            Order.mp_payment_id == "SIMULADO",
            Order.status.in_(["pending", "cancelled", "in_process"]),
        )
    )


@bp.route("/manutencao/limpar-testes", methods=["GET", "POST"])
@admin_required
def limpar_testes():
    pedidos_teste = _pedidos_de_teste_query().order_by(Order.created_at.desc()).all()
    total_logs = Log.query.count()
    total_traffic_events = TrafficEvent.query.count()

    if request.method == "POST":
        if request.form.get("confirmar") != "CONFIRMAR":
            flash("Digite CONFIRMAR (em maiúsculas) para prosseguir com a limpeza.", "warning")
            return redirect(url_for("admin.limpar_testes"))

        total_logs_removidos = Log.query.delete()
        total_traffic_removidos = TrafficEvent.query.delete()

        keys_liberadas = 0
        pedidos_removidos = 0
        for o in pedidos_teste:
            if o.license and o.license.key_obj:
                k = o.license.key_obj
                k.status = "disponivel"
                k.order_id = None
                k.user_id = None
                k.data_venda = None
                keys_liberadas += 1
            db.session.delete(o)  # cascade remove a License associada
            pedidos_removidos += 1

        db.session.commit()

        flash(
            f"Limpeza concluída: {total_logs_removidos} log(s), {total_traffic_removidos} evento(s) de "
            f"tráfego e {pedidos_removidos} pedido(s) de teste removidos. {keys_liberadas} key(s) "
            f"liberada(s) de volta ao estoque disponível.",
            "success",
        )
        return redirect(url_for("admin.dashboard"))

    return render_template(
        "admin/limpar_testes.html",
        pedidos_teste=pedidos_teste,
        total_logs=total_logs,
        total_traffic_events=total_traffic_events,
    )
