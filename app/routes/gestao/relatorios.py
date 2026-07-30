from datetime import date

from flask import render_template, request

from . import bp, gestao_required
from ...models.erp import ErpBanco, ErpEmpresa, ErpTransacao
from ...services.gestao import consultas


@bp.route("/relatorios")
@gestao_required
def relatorios():
    """Relatórios financeiros na tela, com filtros. O botão de imprimir usa o
    diálogo nativo do navegador (Salvar como PDF) via CSS @media print — assim
    dá pra conferir na hora e no celular, sem gerar arquivo no servidor."""
    hoje = date.today()
    ano = request.args.get("ano", type=int) or hoje.year
    mes = request.args.get("mes", type=int)
    banco_id = request.args.get("banco_id", type=int)

    if mes:
        de, ate = consultas.limites_do_mes(ano, mes)
        periodo = f"{mes:02d}/{ano}"
    else:
        de, ate = date(ano, 1, 1), date(ano, 12, 31)
        periodo = str(ano)

    resumo = consultas.resumo_periodo(de, ate, banco_id)

    query = ErpTransacao.query.filter(ErpTransacao.data >= de, ErpTransacao.data <= ate)
    if banco_id:
        query = query.filter(ErpTransacao.banco_id == banco_id)
    lancamentos = query.order_by(ErpTransacao.data.asc(), ErpTransacao.id.asc()).all()

    qtd_entradas = sum(1 for t in lancamentos if t.tipo == "Entrada")
    banco = ErpBanco.query.get(banco_id) if banco_id else None

    return render_template(
        "gestao/relatorios.html",
        empresa=ErpEmpresa.get(),
        ano=ano, mes=mes, banco_id=banco_id, banco=banco, periodo=periodo,
        anos=consultas.anos_disponiveis(),
        bancos=ErpBanco.query.order_by(ErpBanco.nome).all(),
        resumo=resumo,
        saldo_conta=consultas.saldo_atual(banco_id),
        entradas_cat=consultas.por_categoria("Entrada", de, ate, banco_id),
        saidas_cat=consultas.por_categoria("Saída", de, ate, banco_id),
        serie=consultas.serie_mensal(ano, banco_id),
        saldos=consultas.saldos_por_banco(),
        lancamentos=lancamentos,
        qtd_entradas=qtd_entradas,
        qtd_saidas=len(lancamentos) - qtd_entradas,
        ticket_medio=(resumo["entradas"] / qtd_entradas) if qtd_entradas else 0,
        gerado_em=hoje,
    )
