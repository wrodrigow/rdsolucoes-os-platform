"""Agregações financeiras — portadas de Orcamentos/database.py, que fazia isso
em SQL cru com strftime() do SQLite. Aqui usa SQLAlchemy, então funciona igual
em SQLite (dev) e Postgres (produção) sem SQL específico de dialeto.
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func

from ...extensions import db
from ...models.erp import ErpBanco, ErpTransacao

ENTRADA = "Entrada"
SAIDA = "Saída"


def _soma(tipo, banco_id=None, de=None, ate=None, categoria=None):
    q = db.session.query(func.coalesce(func.sum(ErpTransacao.valor), 0)).filter(ErpTransacao.tipo == tipo)
    if banco_id:
        q = q.filter(ErpTransacao.banco_id == banco_id)
    if de:
        q = q.filter(ErpTransacao.data >= de)
    if ate:
        q = q.filter(ErpTransacao.data <= ate)
    if categoria:
        q = q.filter(ErpTransacao.categoria == categoria)
    return Decimal(str(q.scalar() or 0))


def saldo_atual(banco_id=None):
    """saldo_inicial dos bancos + entradas − saídas (mesma conta do desktop)."""
    q = db.session.query(func.coalesce(func.sum(ErpBanco.saldo_inicial), 0))
    if banco_id:
        q = q.filter(ErpBanco.id == banco_id)
    inicial = Decimal(str(q.scalar() or 0))
    return inicial + _soma(ENTRADA, banco_id) - _soma(SAIDA, banco_id)


def resumo_periodo(de=None, ate=None, banco_id=None):
    entradas = _soma(ENTRADA, banco_id, de, ate)
    saidas = _soma(SAIDA, banco_id, de, ate)
    return {
        "entradas": entradas,
        "saidas": saidas,
        "resultado": entradas - saidas,
    }


def limites_do_mes(ano, mes):
    inicio = date(ano, mes, 1)
    fim = date(ano + 1, 1, 1) - timedelta(days=1) if mes == 12 else date(ano, mes + 1, 1) - timedelta(days=1)
    return inicio, fim


def anos_disponiveis():
    """Anos que têm transação, do mais recente pro mais antigo."""
    linhas = db.session.query(func.extract("year", ErpTransacao.data)).distinct().all()
    anos = sorted({int(a[0]) for a in linhas if a[0] is not None}, reverse=True)
    return anos or [date.today().year]


def serie_mensal(ano, banco_id=None):
    """12 meses do ano: labels + entradas + saídas (pro gráfico de barras)."""
    labels, entradas, saidas = [], [], []
    nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    for mes in range(1, 13):
        inicio, fim = limites_do_mes(ano, mes)
        labels.append(nomes[mes - 1])
        entradas.append(float(_soma(ENTRADA, banco_id, inicio, fim)))
        saidas.append(float(_soma(SAIDA, banco_id, inicio, fim)))
    return {"labels": labels, "entradas": entradas, "saidas": saidas}


def serie_diaria(dias=30, banco_id=None):
    """Últimos N dias — usado no painel."""
    hoje = date.today()
    labels, entradas, saidas = [], [], []
    for i in range(dias - 1, -1, -1):
        dia = hoje - timedelta(days=i)
        labels.append(dia.strftime("%d/%m"))
        entradas.append(float(_soma(ENTRADA, banco_id, dia, dia)))
        saidas.append(float(_soma(SAIDA, banco_id, dia, dia)))
    return {"labels": labels, "entradas": entradas, "saidas": saidas}


def por_categoria(tipo, de=None, ate=None, banco_id=None, limite=None):
    """Total por categoria, maior primeiro. Substitui o gráfico de pizza do
    desktop (aqui vira lista/barra, pra não trazer lib de gráfico nova)."""
    # nullif('') porque o app desktop gravava categoria vazia como string vazia,
    # não NULL — sem isso a linha sairia sem rótulo nenhum no relatório.
    rotulo = func.coalesce(func.nullif(ErpTransacao.categoria, ""), "(sem categoria)")
    q = (db.session.query(
            rotulo.label("categoria"),
            func.coalesce(func.sum(ErpTransacao.valor), 0).label("total"),
            func.count(ErpTransacao.id).label("qtd"),
         )
         .filter(ErpTransacao.tipo == tipo))
    if banco_id:
        q = q.filter(ErpTransacao.banco_id == banco_id)
    if de:
        q = q.filter(ErpTransacao.data >= de)
    if ate:
        q = q.filter(ErpTransacao.data <= ate)

    linhas = q.group_by(rotulo).order_by(func.sum(ErpTransacao.valor).desc()).all()
    if limite:
        linhas = linhas[:limite]

    total_geral = sum(float(l.total) for l in linhas) or 1.0
    return [{
        "categoria": l.categoria,
        "total": Decimal(str(l.total)),
        "qtd": l.qtd,
        "pct": round(float(l.total) / total_geral * 100, 1),
    } for l in linhas]


def saldos_por_banco():
    """Cada banco com o saldo atual calculado — usado no painel e em Bancos."""
    resultado = []
    for banco in ErpBanco.query.order_by(ErpBanco.nome).all():
        resultado.append({
            "banco": banco,
            "saldo": saldo_atual(banco.id),
            "entradas": _soma(ENTRADA, banco.id),
            "saidas": _soma(SAIDA, banco.id),
        })
    return resultado


def recalibrar_saldo_inicial(banco_id, saldo_final_desejado):
    """Ajusta o saldo_inicial do banco pra que o saldo calculado bata com o
    saldo real do extrato (mesma lógica do desktop, usada na importação)."""
    banco = db.session.get(ErpBanco, banco_id)
    if not banco:
        return None
    movimento = _soma(ENTRADA, banco_id) - _soma(SAIDA, banco_id)
    banco.saldo_inicial = Decimal(str(saldo_final_desejado)) - movimento
    db.session.commit()
    return banco.saldo_inicial
