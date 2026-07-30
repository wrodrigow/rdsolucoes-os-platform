import re

from flask import flash, jsonify, redirect, render_template, request, url_for

from . import bp, gestao_required
from ...extensions import db
from ...models.erp import ErpCliente, ErpOrcamento


@bp.route("/clientes")
@gestao_required
def clientes():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = ErpCliente.query
    if q:
        query = query.filter(
            (ErpCliente.nome.ilike(f"%{q}%")) | (ErpCliente.telefone.ilike(f"%{q}%"))
        )
    pagination = query.order_by(ErpCliente.nome.asc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("gestao/clientes.html", clientes=pagination.items, pagination=pagination, q=q)


def _dados_form():
    return {
        "nome": request.form.get("nome", "").strip(),
        "telefone": request.form.get("telefone", "").strip() or None,
        "email": request.form.get("email", "").strip() or None,
        "cep": request.form.get("cep", "").strip() or None,
        "endereco": request.form.get("endereco", "").strip() or None,
        "observacoes": request.form.get("observacoes", "").strip() or None,
    }


@bp.route("/clientes/novo", methods=["POST"])
@gestao_required
def cliente_novo():
    dados = _dados_form()
    if not dados["nome"]:
        flash("Nome é obrigatório.", "danger")
        return redirect(url_for("gestao.clientes"))

    cliente = ErpCliente(**dados)
    db.session.add(cliente)
    db.session.commit()
    flash(f"Cliente {cliente.nome} cadastrado.", "success")
    return redirect(url_for("gestao.clientes"))


@bp.route("/clientes/<int:cliente_id>/editar", methods=["POST"])
@gestao_required
def cliente_editar(cliente_id):
    cliente = ErpCliente.query.get_or_404(cliente_id)
    dados = _dados_form()
    if not dados["nome"]:
        flash("Nome é obrigatório.", "danger")
        return redirect(url_for("gestao.clientes"))

    for campo, valor in dados.items():
        setattr(cliente, campo, valor)
    db.session.commit()
    flash(f"Cliente {cliente.nome} atualizado.", "success")
    return redirect(url_for("gestao.clientes"))


@bp.route("/clientes/<int:cliente_id>/excluir", methods=["POST"])
@gestao_required
def cliente_excluir(cliente_id):
    cliente = ErpCliente.query.get_or_404(cliente_id)
    vinculados = ErpOrcamento.query.filter_by(cliente_id=cliente_id).count()
    nome = cliente.nome
    db.session.delete(cliente)
    db.session.commit()
    if vinculados:
        flash(f"Cliente {nome} excluído. {vinculados} orçamento(s) continuam no sistema "
              f"com os dados que já estavam gravados neles.", "success")
    else:
        flash(f"Cliente {nome} excluído.", "success")
    return redirect(url_for("gestao.clientes"))


# ── APIs usadas pelas telas (autocomplete de cliente, busca de CEP) ─────────

@bp.route("/api/clientes/buscar")
@gestao_required
def api_clientes_buscar():
    termo = request.args.get("q", "").strip()
    query = ErpCliente.query
    if termo:
        query = query.filter(
            (ErpCliente.nome.ilike(f"%{termo}%")) | (ErpCliente.telefone.ilike(f"%{termo}%"))
        )
    encontrados = query.order_by(ErpCliente.nome).limit(12).all()
    return jsonify([{
        "id": c.id,
        "nome": c.nome,
        "telefone": c.telefone or "",
        "endereco": c.endereco or "",
    } for c in encontrados])


@bp.route("/api/cep/<cep>")
@gestao_required
def api_cep(cep):
    """Proxy do ViaCEP — mantém a chamada no servidor, sem depender de CORS."""
    import requests

    cep_limpo = re.sub(r"\D", "", cep)
    if len(cep_limpo) != 8:
        return jsonify({"erro": True}), 400
    try:
        resp = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/", timeout=5)
        return jsonify(resp.json())
    except requests.RequestException:
        return jsonify({"erro": True}), 502
