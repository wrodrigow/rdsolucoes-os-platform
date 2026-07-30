"""Módulo de Gestão — o sistema de Orçamentos/OS/Financeiro (ex-app desktop
Orcamentos), numa área própria em /gestao, separada do painel de vendas.

O controle de acesso fica no `gestao_required` daqui (hoje = admin logado).
Isolado de propósito: quando este módulo virar produto vendido a terceiros,
basta trocar a regra num único lugar, sem mexer em cada rota.
"""
from datetime import date
from functools import wraps

from flask import Blueprint, Response, redirect, render_template, url_for, flash
from flask_login import current_user, login_required

from ...extensions import db
from ...models.erp import ErpEmpresa, ErpOrcamento, ErpOrdemServico
from ...services.gestao import consultas
from ...services.gestao.formatos import data_br, moeda, numero_br

bp = Blueprint("gestao", __name__)

# Filtros de formatação brasileira usados em todos os templates da Gestão
bp.add_app_template_filter(moeda, "moeda")
bp.add_app_template_filter(data_br, "data_br")
bp.add_app_template_filter(numero_br, "numero_br")


def gestao_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.home"))
        return fn(*args, **kwargs)
    return wrapped


@bp.app_context_processor
def _injetar_empresa():
    """Nome da empresa no cabeçalho da sidebar. Silencioso em caso de erro
    (ex.: primeiro boot antes das tabelas existirem) pra não derrubar página."""
    try:
        empresa = db.session.get(ErpEmpresa, 1)
        return {"empresa_nome": empresa.nome if empresa else None}
    except Exception:
        return {"empresa_nome": None}


@bp.route("/logo")
@gestao_required
def logo():
    """Logo da empresa: bytes do banco, ou o padrão do projeto. Fica no banco
    porque o disco do Render é efêmero (perderia o upload em cada deploy)."""
    empresa = db.session.get(ErpEmpresa, 1)
    if empresa and empresa.logo_blob:
        return Response(empresa.logo_blob, mimetype=empresa.logo_mime or "image/png")
    return redirect(url_for("static", filename="img/logo.png"))


@bp.route("/")
@bp.route("/painel")
@gestao_required
def dashboard():
    hoje = date.today()
    inicio_mes, fim_mes = consultas.limites_do_mes(hoje.year, hoje.month)

    orcamentos_mes = ErpOrcamento.query.filter(
        ErpOrcamento.data_emissao >= inicio_mes,
        ErpOrcamento.data_emissao <= fim_mes,
    ).all()
    valor_mes = sum((o.valor_total for o in orcamentos_mes), start=0)

    resumo_mes = consultas.resumo_periodo(inicio_mes, fim_mes)

    stats = {
        "orcamentos_mes": len(orcamentos_mes),
        "valor_mes": valor_mes,
        "orcamentos_total": ErpOrcamento.query.count(),
        "aguardando": ErpOrcamento.query.filter(ErpOrcamento.situacao == "Aguardando Retorno").count(),
        "os_abertas": ErpOrdemServico.query.filter(ErpOrdemServico.status.in_(["Aberta", "Em Andamento"])).count(),
        "saldo_total": consultas.saldo_atual(),
        "entradas_mes": resumo_mes["entradas"],
        "saidas_mes": resumo_mes["saidas"],
    }

    return render_template(
        "gestao/dashboard.html",
        stats=stats,
        ultimos_orcamentos=ErpOrcamento.query.order_by(ErpOrcamento.numero.desc()).limit(8).all(),
        saldos=consultas.saldos_por_banco(),
        serie=consultas.serie_mensal(hoje.year),
        ano=hoje.year,
        top_saidas=consultas.por_categoria("Saída", inicio_mes, fim_mes, limite=6),
    )


# Submódulos: cada um faz `from . import bp` e registra suas rotas no
# blueprint criado acima. Importados por último pra evitar import circular.
from . import clientes        # noqa: E402,F401
from . import catalogo        # noqa: E402,F401
from . import orcamentos      # noqa: E402,F401
from . import ordens_servico  # noqa: E402,F401
from . import financeiro      # noqa: E402,F401
from . import relatorios      # noqa: E402,F401
from . import configuracoes   # noqa: E402,F401
