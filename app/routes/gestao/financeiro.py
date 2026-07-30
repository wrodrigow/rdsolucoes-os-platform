from datetime import date

from flask import current_app, flash, redirect, render_template, request, url_for

from . import bp, gestao_required
from ...extensions import db
from ...models.erp import (
    ErpBanco, ErpCategoriaFinanceira, ErpOrcamento, ErpTransacao,
)
from ...services.gestao import consultas, extrato_parser
from ...services.gestao.formatos import parse_data, parse_decimal

TIPOS = ["Entrada", "Saída"]
TIPOS_CATEGORIA = ["Ambos", "Entrada", "Saída"]


# ── Transações ──────────────────────────────────────────────────────────────

@bp.route("/financeiro")
@gestao_required
def financeiro():
    q = request.args.get("q", "").strip()
    tipo = request.args.get("tipo", "").strip()
    categoria = request.args.get("categoria", "").strip()
    banco_id = request.args.get("banco_id", type=int)
    ano = request.args.get("ano", type=int)
    mes = request.args.get("mes", type=int)
    page = request.args.get("page", 1, type=int)

    query = ErpTransacao.query
    if q:
        query = query.filter(ErpTransacao.descricao.ilike(f"%{q}%"))
    if tipo:
        query = query.filter(ErpTransacao.tipo == tipo)
    if categoria:
        query = query.filter(ErpTransacao.categoria == categoria)
    if banco_id:
        query = query.filter(ErpTransacao.banco_id == banco_id)

    de = ate = None
    if ano and mes:
        de, ate = consultas.limites_do_mes(ano, mes)
    elif ano:
        de, ate = date(ano, 1, 1), date(ano, 12, 31)
    if de:
        query = query.filter(ErpTransacao.data >= de, ErpTransacao.data <= ate)

    pagination = (query.order_by(ErpTransacao.data.desc(), ErpTransacao.id.desc())
                  .paginate(page=page, per_page=50, error_out=False))

    # Resumo respeita os mesmos filtros de período/banco da listagem
    resumo = consultas.resumo_periodo(de, ate, banco_id)

    return render_template(
        "gestao/financeiro.html",
        transacoes=pagination.items, pagination=pagination,
        q=q, tipo=tipo, categoria=categoria, banco_id=banco_id, ano=ano, mes=mes,
        tipos=TIPOS,
        bancos=ErpBanco.query.order_by(ErpBanco.nome).all(),
        categorias=ErpCategoriaFinanceira.query.order_by(ErpCategoriaFinanceira.nome).all(),
        anos=consultas.anos_disponiveis(),
        resumo=resumo,
        saldo_geral=consultas.saldo_atual(),
        hoje=date.today(),
        orcamentos=ErpOrcamento.query.order_by(ErpOrcamento.numero.desc()).limit(200).all(),
    )


def _dados_transacao():
    return {
        "data": parse_data(request.form.get("data")) or date.today(),
        "descricao": request.form.get("descricao", "").strip() or None,
        "tipo": request.form.get("tipo", "Entrada"),
        "valor": parse_decimal(request.form.get("valor")),
        "categoria": request.form.get("categoria", "").strip() or None,
        "banco_id": request.form.get("banco_id", type=int) or None,
        "orcamento_id": request.form.get("orcamento_id", type=int) or None,
    }


@bp.route("/financeiro/nova", methods=["POST"])
@gestao_required
def transacao_nova():
    dados = _dados_transacao()
    if dados["valor"] <= 0:
        flash("Informe um valor maior que zero.", "danger")
        return redirect(url_for("gestao.financeiro"))

    db.session.add(ErpTransacao(**dados))
    db.session.commit()
    flash("Lançamento registrado.", "success")
    return redirect(url_for("gestao.financeiro"))


@bp.route("/financeiro/<int:transacao_id>/editar", methods=["POST"])
@gestao_required
def transacao_editar(transacao_id):
    transacao = ErpTransacao.query.get_or_404(transacao_id)
    dados = _dados_transacao()
    if dados["valor"] <= 0:
        flash("Informe um valor maior que zero.", "danger")
        return redirect(url_for("gestao.financeiro"))

    for campo, valor in dados.items():
        setattr(transacao, campo, valor)
    db.session.commit()
    flash("Lançamento atualizado.", "success")
    return redirect(url_for("gestao.financeiro"))


@bp.route("/financeiro/<int:transacao_id>/categoria", methods=["POST"])
@gestao_required
def transacao_categoria(transacao_id):
    """Categorização rápida direto da listagem (equivale ao menu de contexto
    do app desktop). Volta pra mesma página/filtros de onde saiu."""
    transacao = ErpTransacao.query.get_or_404(transacao_id)
    transacao.categoria = request.form.get("categoria", "").strip() or None
    db.session.commit()
    return redirect(request.referrer or url_for("gestao.financeiro"))


@bp.route("/financeiro/<int:transacao_id>/excluir", methods=["POST"])
@gestao_required
def transacao_excluir(transacao_id):
    transacao = ErpTransacao.query.get_or_404(transacao_id)
    db.session.delete(transacao)
    db.session.commit()
    flash("Lançamento excluído.", "success")
    return redirect(url_for("gestao.financeiro"))


# ── Importação de extrato bancário ──────────────────────────────────────────

@bp.route("/financeiro/importar", methods=["POST"])
@gestao_required
def importar_extrato():
    banco_id = request.form.get("banco_id", type=int)
    banco = db.session.get(ErpBanco, banco_id) if banco_id else None
    if not banco:
        flash("Selecione o banco do extrato.", "danger")
        return redirect(url_for("gestao.financeiro"))

    arquivo = request.files.get("extrato")
    if not arquivo or not arquivo.filename:
        flash("Escolha o arquivo PDF do extrato.", "danger")
        return redirect(url_for("gestao.financeiro"))
    if not arquivo.filename.lower().endswith(".pdf"):
        flash("O extrato precisa ser um arquivo PDF.", "danger")
        return redirect(url_for("gestao.financeiro"))

    nome_banco = (banco.nome or "").lower()
    senha = request.form.get("senha", "").strip() or current_app.config.get("C6_STATEMENT_PASSWORD")

    # O upload é lido direto da memória — nada é gravado em disco (o disco do
    # Render é efêmero, e o extrato não precisa ser guardado mesmo).
    try:
        if "c6" in nome_banco:
            transacoes, saldo_final = extrato_parser.parse_c6(arquivo.stream, password=senha)
        else:
            transacoes, saldo_final = extrato_parser.parse_inter(arquivo.stream)
    except Exception as erro:
        flash(f"Não foi possível ler o extrato: {erro}", "danger")
        return redirect(url_for("gestao.financeiro"))

    if not transacoes:
        flash("Nenhum lançamento foi identificado neste PDF. Confira se o banco "
              "selecionado corresponde ao extrato enviado.", "warning")
        return redirect(url_for("gestao.financeiro"))

    # Dedupe contra o que já existe: carrega as chaves do banco em memória
    # (volume pequeno) em vez de uma consulta por linha do extrato.
    existentes = {
        (t.data.isoformat(), f"{float(t.valor):.2f}", t.tipo, extrato_parser.chave_dedupe(t.descricao))
        for t in ErpTransacao.query.filter_by(banco_id=banco_id).all()
    }

    importadas = ignoradas = 0
    for t in transacoes:
        chave = (t["data"], f"{float(t['valor']):.2f}", t["tipo"], extrato_parser.chave_dedupe(t["descricao"]))
        if chave in existentes:
            ignoradas += 1
            continue
        existentes.add(chave)
        db.session.add(ErpTransacao(
            data=parse_data(t["data"]),
            descricao=" ".join((t["descricao"] or "").split())[:200] or None,
            tipo=t["tipo"],
            valor=parse_decimal(t["valor"]),
            categoria=t["categoria"] or None,
            banco_id=banco_id,
        ))
        importadas += 1
    db.session.commit()

    msg = f"{importadas} lançamento(s) importado(s) do {banco.nome}. {ignoradas} já existia(m) e foi(ram) ignorado(s)."

    # Recalibra o saldo inicial pra que o saldo do sistema bata com o extrato
    saldo_informado = request.form.get("saldo_final", "").strip()
    if saldo_informado:
        saldo_final = float(parse_decimal(saldo_informado))
    if saldo_final and request.form.get("recalibrar"):
        novo = consultas.recalibrar_saldo_inicial(banco_id, saldo_final)
        msg += (f" Saldo inicial ajustado para {novo:.2f} — o saldo do sistema "
                f"agora fecha com o do extrato.")

    flash(msg, "success")
    return redirect(url_for("gestao.financeiro", banco_id=banco_id))


# ── Bancos ──────────────────────────────────────────────────────────────────

@bp.route("/bancos")
@gestao_required
def bancos():
    return render_template("gestao/bancos.html",
                           saldos=consultas.saldos_por_banco(),
                           saldo_geral=consultas.saldo_atual())


@bp.route("/bancos/novo", methods=["POST"])
@gestao_required
def banco_novo():
    nome = request.form.get("nome", "").strip()
    if not nome:
        flash("Nome do banco é obrigatório.", "danger")
        return redirect(url_for("gestao.bancos"))

    db.session.add(ErpBanco(
        nome=nome,
        agencia=request.form.get("agencia", "").strip() or None,
        conta=request.form.get("conta", "").strip() or None,
        cor=request.form.get("cor", "#1a5fa8"),
        saldo_inicial=parse_decimal(request.form.get("saldo_inicial")),
    ))
    db.session.commit()
    flash(f"Banco {nome} cadastrado.", "success")
    return redirect(url_for("gestao.bancos"))


@bp.route("/bancos/<int:banco_id>/editar", methods=["POST"])
@gestao_required
def banco_editar(banco_id):
    banco = ErpBanco.query.get_or_404(banco_id)
    nome = request.form.get("nome", "").strip()
    if not nome:
        flash("Nome do banco é obrigatório.", "danger")
        return redirect(url_for("gestao.bancos"))

    banco.nome = nome
    banco.agencia = request.form.get("agencia", "").strip() or None
    banco.conta = request.form.get("conta", "").strip() or None
    banco.cor = request.form.get("cor", banco.cor)
    banco.saldo_inicial = parse_decimal(request.form.get("saldo_inicial"))
    db.session.commit()
    flash(f"Banco {banco.nome} atualizado.", "success")
    return redirect(url_for("gestao.bancos"))


@bp.route("/bancos/<int:banco_id>/excluir", methods=["POST"])
@gestao_required
def banco_excluir(banco_id):
    banco = ErpBanco.query.get_or_404(banco_id)
    vinculadas = ErpTransacao.query.filter_by(banco_id=banco_id).count()
    if vinculadas:
        flash(f"Não é possível excluir {banco.nome}: há {vinculadas} lançamento(s) "
              f"vinculado(s) a ele. Reclassifique ou exclua esses lançamentos primeiro.", "danger")
        return redirect(url_for("gestao.bancos"))

    nome = banco.nome
    db.session.delete(banco)
    db.session.commit()
    flash(f"Banco {nome} excluído.", "success")
    return redirect(url_for("gestao.bancos"))


# ── Categorias ──────────────────────────────────────────────────────────────

@bp.route("/categorias")
@gestao_required
def categorias():
    lista = ErpCategoriaFinanceira.query.order_by(ErpCategoriaFinanceira.nome).all()
    # Quantos lançamentos usam cada categoria (pela string, como no desktop)
    usos = {}
    for cat in lista:
        usos[cat.id] = ErpTransacao.query.filter_by(categoria=cat.nome).count()
    return render_template("gestao/categorias.html", categorias=lista,
                           usos=usos, tipos=TIPOS_CATEGORIA)


@bp.route("/categorias/nova", methods=["POST"])
@gestao_required
def categoria_nova():
    nome = request.form.get("nome", "").strip()
    if not nome:
        flash("Nome da categoria é obrigatório.", "danger")
        return redirect(url_for("gestao.categorias"))

    db.session.add(ErpCategoriaFinanceira(
        nome=nome,
        tipo=request.form.get("tipo", "Ambos"),
        cor=request.form.get("cor", "#95a5a6"),
    ))
    db.session.commit()
    flash(f"Categoria {nome} criada.", "success")
    return redirect(url_for("gestao.categorias"))


@bp.route("/categorias/<int:categoria_id>/editar", methods=["POST"])
@gestao_required
def categoria_editar(categoria_id):
    categoria = ErpCategoriaFinanceira.query.get_or_404(categoria_id)
    nome = request.form.get("nome", "").strip()
    if not nome:
        flash("Nome da categoria é obrigatório.", "danger")
        return redirect(url_for("gestao.categorias"))

    nome_antigo = categoria.nome
    categoria.nome = nome
    categoria.tipo = request.form.get("tipo", categoria.tipo)
    categoria.cor = request.form.get("cor", categoria.cor)

    # As transações guardam a categoria como texto — renomear aqui tem que
    # arrastar os lançamentos, senão eles ficariam órfãos da categoria antiga.
    renomeadas = 0
    if nome_antigo != nome:
        renomeadas = ErpTransacao.query.filter_by(categoria=nome_antigo).update(
            {"categoria": nome}, synchronize_session=False)
    db.session.commit()

    if renomeadas:
        flash(f"Categoria atualizada e {renomeadas} lançamento(s) reclassificado(s).", "success")
    else:
        flash("Categoria atualizada.", "success")
    return redirect(url_for("gestao.categorias"))


@bp.route("/categorias/<int:categoria_id>/excluir", methods=["POST"])
@gestao_required
def categoria_excluir(categoria_id):
    categoria = ErpCategoriaFinanceira.query.get_or_404(categoria_id)
    usos = ErpTransacao.query.filter_by(categoria=categoria.nome).count()
    nome = categoria.nome
    db.session.delete(categoria)
    db.session.commit()
    if usos:
        flash(f"Categoria {nome} excluída. {usos} lançamento(s) ficaram sem categoria "
              f"e podem ser reclassificados na tela de Transações.", "warning")
    else:
        flash(f"Categoria {nome} excluída.", "success")
    return redirect(url_for("gestao.categorias"))
