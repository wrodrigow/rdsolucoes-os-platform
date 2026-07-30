from flask import flash, jsonify, redirect, render_template, request, url_for

from . import bp, gestao_required
from ...extensions import db
from ...models.erp import ErpCatalogoItem
from ...services.gestao.formatos import parse_decimal


@bp.route("/catalogo")
@gestao_required
def catalogo():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = ErpCatalogoItem.query
    if q:
        query = query.filter(ErpCatalogoItem.descricao.ilike(f"%{q}%"))
    pagination = query.order_by(ErpCatalogoItem.descricao.asc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("gestao/catalogo.html", itens=pagination.items, pagination=pagination, q=q)


@bp.route("/catalogo/novo", methods=["POST"])
@gestao_required
def catalogo_novo():
    descricao = request.form.get("descricao", "").strip()
    if not descricao:
        flash("Descrição é obrigatória.", "danger")
        return redirect(url_for("gestao.catalogo"))

    db.session.add(ErpCatalogoItem(
        descricao=descricao,
        valor_unitario=parse_decimal(request.form.get("valor_unitario")),
        unidade=request.form.get("unidade", "unid").strip() or "unid",
    ))
    db.session.commit()
    flash("Item adicionado ao catálogo.", "success")
    return redirect(url_for("gestao.catalogo"))


@bp.route("/catalogo/<int:item_id>/editar", methods=["POST"])
@gestao_required
def catalogo_editar(item_id):
    item = ErpCatalogoItem.query.get_or_404(item_id)
    descricao = request.form.get("descricao", "").strip()
    if not descricao:
        flash("Descrição é obrigatória.", "danger")
        return redirect(url_for("gestao.catalogo"))

    item.descricao = descricao
    item.valor_unitario = parse_decimal(request.form.get("valor_unitario"))
    item.unidade = request.form.get("unidade", "unid").strip() or "unid"
    db.session.commit()
    flash("Item atualizado.", "success")
    return redirect(url_for("gestao.catalogo"))


@bp.route("/catalogo/<int:item_id>/excluir", methods=["POST"])
@gestao_required
def catalogo_excluir(item_id):
    item = ErpCatalogoItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Item removido do catálogo.", "success")
    return redirect(url_for("gestao.catalogo"))


@bp.route("/api/catalogo/buscar")
@gestao_required
def api_catalogo_buscar():
    """Alimenta o autocomplete de item na tela de Orçamento."""
    termo = request.args.get("q", "").strip()
    query = ErpCatalogoItem.query
    if termo:
        query = query.filter(ErpCatalogoItem.descricao.ilike(f"%{termo}%"))
    encontrados = query.order_by(ErpCatalogoItem.descricao).limit(12).all()
    return jsonify([{
        "id": i.id,
        "descricao": i.descricao,
        "valor_unitario": float(i.valor_unitario or 0),
        "unidade": i.unidade,
    } for i in encontrados])
