from datetime import date

from flask import flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import or_

from . import bp, gestao_required
from ...extensions import db
from ...models.erp import ErpEmpresa, ErpOrcamento, ErpOrdemServico
from ...services.gestao.formatos import parse_data
from ...services.gestao.pdf_os import gerar_pdf_os

STATUS_OS = ["Aberta", "Em Andamento", "Concluída", "Cancelada"]

CLASSE_STATUS = {
    "Em Andamento": "gst-row-aguardando",
    "Cancelada": "gst-row-cancelado",
    "Aberta": "gst-row-andamento",
}

BADGE_STATUS = {
    "Aberta": "adm-badge-info",
    "Em Andamento": "adm-badge-warning",
    "Concluída": "adm-badge-success",
    "Cancelada": "adm-badge-danger",
}


@bp.route("/ordens-servico")
@gestao_required
def ordens_servico():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)

    query = ErpOrdemServico.query.join(ErpOrcamento, ErpOrdemServico.orcamento_id == ErpOrcamento.id)
    if q:
        filtros = [ErpOrcamento.cliente_nome.ilike(f"%{q}%")]
        if q.isdigit():
            filtros.append(ErpOrdemServico.numero == int(q))
        query = query.filter(or_(*filtros))
    if status:
        query = query.filter(ErpOrdemServico.status == status)

    pagination = query.order_by(ErpOrdemServico.numero.desc()).paginate(page=page, per_page=25, error_out=False)

    # Orçamentos que ainda não têm OS — opções do seletor "Nova OS"
    ja_com_os = db.session.query(ErpOrdemServico.orcamento_id).subquery()
    disponiveis = (ErpOrcamento.query
                   .filter(~ErpOrcamento.id.in_(db.session.query(ja_com_os.c.orcamento_id)))
                   .order_by(ErpOrcamento.numero.desc())
                   .limit(200).all())

    return render_template(
        "gestao/ordens_servico.html",
        ordens=pagination.items, pagination=pagination,
        q=q, status=status, status_lista=STATUS_OS,
        classe_status=CLASSE_STATUS, badge_status=BADGE_STATUS,
        disponiveis=disponiveis, hoje=date.today(),
    )


@bp.route("/ordens-servico/nova", methods=["POST"])
@gestao_required
def os_nova():
    orcamento_id = request.form.get("orcamento_id", type=int)
    orcamento = ErpOrcamento.query.get_or_404(orcamento_id) if orcamento_id else None
    if not orcamento:
        flash("Selecione um orçamento para gerar a Ordem de Serviço.", "danger")
        return redirect(url_for("gestao.ordens_servico"))

    existente = ErpOrdemServico.query.filter_by(orcamento_id=orcamento.id).first()
    if existente:
        flash(f"O orçamento Nº {orcamento.numero} já tem a OS Nº {existente.numero}.", "warning")
        return redirect(url_for("gestao.ordens_servico"))

    # O número da OS acompanha o do orçamento de origem (comportamento do desktop)
    ordem = ErpOrdemServico(
        numero=orcamento.numero,
        orcamento_id=orcamento.id,
        data_emissao=parse_data(request.form.get("data_emissao")) or date.today(),
        status=request.form.get("status", "Aberta"),
        observacoes=request.form.get("observacoes", "").strip() or None,
    )
    db.session.add(ordem)
    db.session.commit()
    flash(f"Ordem de Serviço Nº {ordem.numero} criada para {orcamento.cliente_nome}.", "success")
    return redirect(url_for("gestao.ordens_servico"))


@bp.route("/ordens-servico/<int:ordem_id>/editar", methods=["POST"])
@gestao_required
def os_editar(ordem_id):
    ordem = ErpOrdemServico.query.get_or_404(ordem_id)
    ordem.data_emissao = parse_data(request.form.get("data_emissao")) or ordem.data_emissao
    ordem.status = request.form.get("status", ordem.status)
    ordem.observacoes = request.form.get("observacoes", "").strip() or None
    db.session.commit()
    flash(f"Ordem de Serviço Nº {ordem.numero} atualizada.", "success")
    return redirect(url_for("gestao.ordens_servico"))


@bp.route("/ordens-servico/<int:ordem_id>/excluir", methods=["POST"])
@gestao_required
def os_excluir(ordem_id):
    ordem = ErpOrdemServico.query.get_or_404(ordem_id)
    numero = ordem.numero
    db.session.delete(ordem)
    db.session.commit()
    flash(f"Ordem de Serviço Nº {numero} excluída.", "success")
    return redirect(url_for("gestao.ordens_servico"))


@bp.route("/ordens-servico/<int:ordem_id>/pdf")
@gestao_required
def os_pdf(ordem_id):
    ordem = ErpOrdemServico.query.get_or_404(ordem_id)
    orcamento = ordem.orcamento
    buffer = gerar_pdf_os(ErpEmpresa.get(), ordem, orcamento, orcamento.itens if orcamento else [])
    return send_file(buffer, mimetype="application/pdf",
                     as_attachment=False, download_name=f"OS_{ordem.numero}.pdf")


@bp.route("/orcamentos/<int:orcamento_id>/gerar-os", methods=["POST"])
@gestao_required
def gerar_os_do_orcamento(orcamento_id):
    """Atalho a partir da tela do orçamento — mesma regra do os_nova."""
    orcamento = ErpOrcamento.query.get_or_404(orcamento_id)
    existente = ErpOrdemServico.query.filter_by(orcamento_id=orcamento.id).first()
    if existente:
        flash(f"Este orçamento já tem a OS Nº {existente.numero}.", "warning")
        return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))

    ordem = ErpOrdemServico(
        numero=orcamento.numero,
        orcamento_id=orcamento.id,
        data_emissao=date.today(),
        status="Aberta",
    )
    db.session.add(ordem)
    db.session.commit()
    flash(f"Ordem de Serviço Nº {ordem.numero} criada.", "success")
    return redirect(url_for("gestao.ordens_servico"))
