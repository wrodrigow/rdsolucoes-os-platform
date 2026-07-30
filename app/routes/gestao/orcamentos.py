from datetime import date, timedelta

from flask import flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import or_

from . import bp, gestao_required
from ...extensions import db
from ...models.erp import (
    ErpCatalogoItem, ErpCliente, ErpEmpresa, ErpItemOrcamento, ErpOrcamento,
    ErpOrdemServico,
)
from ...services.gestao import numeracao
from ...services.gestao.formatos import parse_data, parse_decimal
from ...services.gestao.pdf_orcamento import gerar_pdf_orcamento

SITUACOES = ["Aguardando Retorno", "Aprovado", "Reprovado", "Concluído", "Cancelado"]

# Classe CSS por situação — replica o color-coding das linhas no app desktop
CLASSE_SITUACAO = {
    "Aguardando Retorno": "gst-row-aguardando",
    "Cancelado": "gst-row-cancelado",
    "Reprovado": "gst-row-cancelado",
    "Aprovado": "gst-row-andamento",
}


@bp.route("/orcamentos")
@gestao_required
def orcamentos():
    q = request.args.get("q", "").strip()
    situacao = request.args.get("situacao", "").strip()
    page = request.args.get("page", 1, type=int)

    query = ErpOrcamento.query
    if q:
        filtros = [
            ErpOrcamento.cliente_nome.ilike(f"%{q}%"),
            ErpOrcamento.situacao.ilike(f"%{q}%"),
            ErpOrcamento.descricao_servico.ilike(f"%{q}%"),
        ]
        if q.isdigit():
            filtros.append(ErpOrcamento.numero == int(q))
        query = query.filter(or_(*filtros))
    if situacao:
        query = query.filter(ErpOrcamento.situacao == situacao)

    pagination = query.order_by(ErpOrcamento.numero.desc()).paginate(page=page, per_page=25, error_out=False)

    # OS já existentes pra estes orçamentos — evita oferecer "gerar OS" duplicada
    ids = [o.id for o in pagination.items]
    com_os = {r[0] for r in db.session.query(ErpOrdemServico.orcamento_id)
              .filter(ErpOrdemServico.orcamento_id.in_(ids)).all()} if ids else set()

    return render_template(
        "gestao/orcamentos.html",
        orcamentos=pagination.items, pagination=pagination,
        q=q, situacao=situacao, situacoes=SITUACOES,
        classe_situacao=CLASSE_SITUACAO, com_os=com_os,
        empresa=ErpEmpresa.get(), hoje=date.today(),
    )


@bp.route("/orcamentos/novo", methods=["POST"])
@gestao_required
def orcamento_novo():
    empresa = ErpEmpresa.get()
    cliente_nome = request.form.get("cliente_nome", "").strip()
    if not cliente_nome:
        flash("Informe o nome do cliente.", "danger")
        return redirect(url_for("gestao.orcamentos"))

    emissao = parse_data(request.form.get("data_emissao")) or date.today()
    validade = request.form.get("validade", "").strip()
    garantia = request.form.get("garantia", "").strip()

    # Padrões da empresa quando o usuário não informa (igual ao desktop)
    if not validade:
        validade = (emissao + timedelta(days=empresa.validade_dias_padrao or 12)).isoformat()
    if not garantia:
        garantia = (emissao + timedelta(days=empresa.garantia_dias_padrao or 90)).isoformat()

    cliente_id = request.form.get("cliente_id", type=int)
    orcamento = ErpOrcamento(
        numero=numeracao.proximo_numero_orcamento(),
        data_emissao=emissao,
        situacao=request.form.get("situacao", "Aguardando Retorno"),
        descricao_servico=request.form.get("descricao_servico", "").strip() or None,
        cliente_id=cliente_id or None,
        cliente_nome=cliente_nome,
        cliente_telefone=request.form.get("cliente_telefone", "").strip() or None,
        cliente_endereco=request.form.get("cliente_endereco", "").strip() or None,
        validade=validade,
        garantia=garantia,
        forma_pagamento=request.form.get("forma_pagamento", "").strip() or empresa.forma_pagamento_padrao,
        observacoes=request.form.get("observacoes", "").strip() or None,
    )
    db.session.add(orcamento)
    db.session.commit()
    flash(f"Orçamento Nº {orcamento.numero} criado. Adicione os itens abaixo.", "success")
    return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento.id))


@bp.route("/orcamentos/<int:orcamento_id>")
@gestao_required
def orcamento_editar(orcamento_id):
    orcamento = ErpOrcamento.query.get_or_404(orcamento_id)
    return render_template(
        "gestao/orcamento_editar.html",
        orcamento=orcamento,
        situacoes=SITUACOES,
        catalogo=ErpCatalogoItem.query.order_by(ErpCatalogoItem.descricao).all(),
        ordem_existente=ErpOrdemServico.query.filter_by(orcamento_id=orcamento.id).first(),
    )


@bp.route("/orcamentos/<int:orcamento_id>/salvar", methods=["POST"])
@gestao_required
def orcamento_salvar(orcamento_id):
    orcamento = ErpOrcamento.query.get_or_404(orcamento_id)
    cliente_nome = request.form.get("cliente_nome", "").strip()
    if not cliente_nome:
        flash("Informe o nome do cliente.", "danger")
        return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))

    orcamento.data_emissao = parse_data(request.form.get("data_emissao")) or orcamento.data_emissao
    orcamento.situacao = request.form.get("situacao", orcamento.situacao)
    orcamento.descricao_servico = request.form.get("descricao_servico", "").strip() or None
    orcamento.cliente_id = request.form.get("cliente_id", type=int) or None
    orcamento.cliente_nome = cliente_nome
    orcamento.cliente_telefone = request.form.get("cliente_telefone", "").strip() or None
    orcamento.cliente_endereco = request.form.get("cliente_endereco", "").strip() or None
    orcamento.validade = request.form.get("validade", "").strip() or None
    orcamento.garantia = request.form.get("garantia", "").strip() or None
    orcamento.forma_pagamento = request.form.get("forma_pagamento", "").strip() or None
    orcamento.observacoes = request.form.get("observacoes", "").strip() or None
    db.session.commit()
    flash("Orçamento salvo.", "success")
    return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))


@bp.route("/orcamentos/<int:orcamento_id>/excluir", methods=["POST"])
@gestao_required
def orcamento_excluir(orcamento_id):
    orcamento = ErpOrcamento.query.get_or_404(orcamento_id)
    numero = orcamento.numero
    db.session.delete(orcamento)  # cascade remove itens e OS vinculadas
    db.session.commit()
    flash(f"Orçamento Nº {numero} excluído.", "success")
    return redirect(url_for("gestao.orcamentos"))


@bp.route("/orcamentos/<int:orcamento_id>/pdf")
@gestao_required
def orcamento_pdf(orcamento_id):
    orcamento = ErpOrcamento.query.get_or_404(orcamento_id)
    buffer = gerar_pdf_orcamento(ErpEmpresa.get(), orcamento, orcamento.itens)
    nome_arquivo = f"Orcamento_{orcamento.numero}.pdf"
    # inline: abre no visualizador do navegador (o usuário salva/imprime de lá),
    # que é o equivalente web do os.startfile() do app desktop.
    return send_file(buffer, mimetype="application/pdf",
                     as_attachment=False, download_name=nome_arquivo)


# ── Itens do orçamento ──────────────────────────────────────────────────────

@bp.route("/orcamentos/<int:orcamento_id>/itens/novo", methods=["POST"])
@gestao_required
def item_novo(orcamento_id):
    ErpOrcamento.query.get_or_404(orcamento_id)
    descricao = request.form.get("descricao", "").strip()
    if not descricao:
        flash("Descrição do item é obrigatória.", "danger")
        return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))

    db.session.add(ErpItemOrcamento(
        orcamento_id=orcamento_id,
        descricao=descricao,
        valor_unitario=parse_decimal(request.form.get("valor_unitario")),
        quantidade=parse_decimal(request.form.get("quantidade"), default="1") or 1,
    ))
    db.session.commit()
    flash("Item adicionado.", "success")
    return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))


@bp.route("/orcamentos/<int:orcamento_id>/itens/<int:item_id>/editar", methods=["POST"])
@gestao_required
def item_editar(orcamento_id, item_id):
    item = ErpItemOrcamento.query.filter_by(id=item_id, orcamento_id=orcamento_id).first_or_404()
    descricao = request.form.get("descricao", "").strip()
    if not descricao:
        flash("Descrição do item é obrigatória.", "danger")
        return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))

    item.descricao = descricao
    item.valor_unitario = parse_decimal(request.form.get("valor_unitario"))
    item.quantidade = parse_decimal(request.form.get("quantidade"), default="1") or 1
    db.session.commit()
    flash("Item atualizado.", "success")
    return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))


@bp.route("/orcamentos/<int:orcamento_id>/itens/<int:item_id>/excluir", methods=["POST"])
@gestao_required
def item_excluir(orcamento_id, item_id):
    item = ErpItemOrcamento.query.filter_by(id=item_id, orcamento_id=orcamento_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Item removido.", "success")
    return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))


# ── Criar cliente rápido a partir do orçamento (fluxo do desktop) ───────────

@bp.route("/orcamentos/<int:orcamento_id>/salvar-cliente", methods=["POST"])
@gestao_required
def salvar_como_cliente(orcamento_id):
    """Cadastra o cliente do orçamento na base de clientes e vincula os dois."""
    orcamento = ErpOrcamento.query.get_or_404(orcamento_id)
    if orcamento.cliente_id:
        flash("Este orçamento já está vinculado a um cliente cadastrado.", "info")
        return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))
    if not orcamento.cliente_nome:
        flash("O orçamento não tem nome de cliente para cadastrar.", "warning")
        return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))

    cliente = ErpCliente(
        nome=orcamento.cliente_nome,
        telefone=orcamento.cliente_telefone,
        endereco=orcamento.cliente_endereco,
    )
    db.session.add(cliente)
    db.session.flush()
    orcamento.cliente_id = cliente.id
    db.session.commit()
    flash(f"{cliente.nome} cadastrado em Clientes e vinculado a este orçamento.", "success")
    return redirect(url_for("gestao.orcamento_editar", orcamento_id=orcamento_id))
