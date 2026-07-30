from flask import flash, redirect, render_template, request, url_for

from . import bp, gestao_required
from ...extensions import db
from ...models.erp import (
    ErpCliente, ErpEmpresa, ErpOrcamento, ErpOrdemServico, ErpTransacao,
)

MIMES_PERMITIDOS = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
LIMITE_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB


@bp.route("/configuracoes", methods=["GET", "POST"])
@gestao_required
def configuracoes():
    empresa = ErpEmpresa.get()

    if request.method == "POST":
        empresa.nome = request.form.get("nome", "").strip() or empresa.nome
        empresa.cnpj = request.form.get("cnpj", "").strip() or None
        empresa.email = request.form.get("email", "").strip() or None
        empresa.site = request.form.get("site", "").strip() or None
        empresa.telefone = request.form.get("telefone", "").strip() or None
        empresa.forma_pagamento_padrao = request.form.get("forma_pagamento_padrao", "").strip() or None
        empresa.validade_dias_padrao = request.form.get("validade_dias_padrao", type=int) or 12
        empresa.garantia_dias_padrao = request.form.get("garantia_dias_padrao", type=int) or 90

        # O próximo número só avança — recuar geraria orçamentos com número
        # repetido, e o número já foi impresso em PDF que está com o cliente.
        proximo = request.form.get("proximo_numero", type=int)
        if proximo:
            maior = db.session.query(db.func.max(ErpOrcamento.numero)).scalar() or 0
            if proximo <= maior:
                flash(f"O próximo número precisa ser maior que {maior} "
                      f"(maior número de orçamento já existente).", "warning")
            else:
                empresa.proximo_numero = proximo

        db.session.commit()
        flash("Configurações salvas.", "success")
        return redirect(url_for("gestao.configuracoes"))

    return render_template(
        "gestao/configuracoes.html",
        empresa=empresa,
        tem_logo=bool(empresa.logo_blob),
        contagens={
            "orcamentos": ErpOrcamento.query.count(),
            "ordens": ErpOrdemServico.query.count(),
            "clientes": ErpCliente.query.count(),
            "transacoes": ErpTransacao.query.count(),
        },
        maior_numero=db.session.query(db.func.max(ErpOrcamento.numero)).scalar() or 0,
    )


@bp.route("/configuracoes/logo", methods=["POST"])
@gestao_required
def configuracoes_logo():
    """Logo vai pro banco (LargeBinary), não pro disco: o Render recria o
    sistema de arquivos em cada deploy e o upload seria perdido."""
    arquivo = request.files.get("logo")
    if not arquivo or not arquivo.filename:
        flash("Escolha um arquivo de imagem.", "danger")
        return redirect(url_for("gestao.configuracoes"))

    if arquivo.mimetype not in MIMES_PERMITIDOS:
        flash("Formato não suportado. Envie PNG, JPG, WEBP ou GIF.", "danger")
        return redirect(url_for("gestao.configuracoes"))

    dados = arquivo.read()
    if len(dados) > LIMITE_LOGO_BYTES:
        flash("A imagem passa de 2 MB. Envie uma versão menor.", "danger")
        return redirect(url_for("gestao.configuracoes"))

    empresa = ErpEmpresa.get()
    empresa.logo_blob = dados
    empresa.logo_mime = arquivo.mimetype
    db.session.commit()
    flash("Logo atualizado. Ele passa a valer nos próximos PDFs gerados.", "success")
    return redirect(url_for("gestao.configuracoes"))


@bp.route("/configuracoes/logo/remover", methods=["POST"])
@gestao_required
def configuracoes_logo_remover():
    empresa = ErpEmpresa.get()
    empresa.logo_blob = None
    empresa.logo_mime = None
    db.session.commit()
    flash("Logo removido — os PDFs voltam a usar o logo padrão.", "success")
    return redirect(url_for("gestao.configuracoes"))
