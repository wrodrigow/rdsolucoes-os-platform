"""Migra os dados do app desktop Orçamentos (SQLite) para as tabelas erp_*
do RDSolucoes-OS-Platform, via os models SQLAlchemy (funciona tanto contra
o SQLite local de desenvolvimento quanto contra o Postgres do Render,
dependendo do DATABASE_URL/FLASK_ENV ativo no momento em que roda).

Uso:
    python scripts/migrate_erp_sqlite_to_postgres.py <caminho_do_orcamentos.db> [--dry-run] [--wipe-first]

Rodar sempre da raiz do projeto (RDSolucoes-OS-Platform/), com o venv ativo.
"""
import argparse
import os
import re
import sqlite3
import sys
from datetime import date
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolver_destino():
    """Define o DATABASE_URL do processo ANTES de importar o app.

    A classe Config lê DATABASE_URL no momento do import (é atributo de
    classe), então trocar a variável depois não teria efeito — o app abriria
    o banco local mesmo tendo sido pedido produção.
    """
    from dotenv import load_dotenv
    load_dotenv()

    destino = None
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == "--database-url" and i + 1 < len(argv):
            destino = argv[i + 1]
        elif arg.startswith("--database-url="):
            destino = arg.split("=", 1)[1]
    destino = destino or os.environ.get("PROD_DATABASE_URL")

    if destino:
        if destino.startswith("postgres://"):
            destino = destino.replace("postgres://", "postgresql://", 1)
        os.environ["DATABASE_URL"] = destino


_resolver_destino()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.erp import (  # noqa: E402
    ErpEmpresa, ErpCliente, ErpCatalogoItem, ErpOrcamento, ErpItemOrcamento,
    ErpOrdemServico, ErpBanco, ErpCategoriaFinanceira, ErpTransacao,
)

TABELAS_ORDEM = [
    "empresa", "clientes", "catalogo_itens", "bancos", "cat_financeiras",
    "orcamentos", "itens_orcamento", "transacoes", "ordens_servico",
]


def _uri_sem_senha(uri):
    """Esconde a senha antes de imprimir a URI — o log da execução pode ser
    colado em conversa, ticket ou histórico de terminal."""
    return re.sub(r"://([^:/@]+):[^@]+@", r"://\1:***@", str(uri))


def parse_date(raw):
    if not raw:
        return None
    raw = str(raw).strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def parse_money(raw, default="0"):
    if raw is None:
        return Decimal(default)
    try:
        return Decimal(str(round(float(raw), 2)))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_path", help="Caminho do .db do app desktop (ou de um backup)")
    parser.add_argument("--dry-run", action="store_true", help="Só mostra as contagens da origem, não escreve nada")
    parser.add_argument("--wipe-first", action="store_true", help="Apaga os dados erp_* existentes antes de importar")
    parser.add_argument(
        "--database-url", default=None,
        help="Banco de destino. Se omitido, usa PROD_DATABASE_URL do ambiente/.env; "
             "se essa também não existir, usa o banco configurado normalmente (o local).",
    )
    args = parser.parse_args()
    # O destino já foi aplicado por _resolver_destino(), antes dos imports.

    if not os.path.isfile(args.sqlite_path):
        print(f"Arquivo não encontrado: {args.sqlite_path}")
        sys.exit(1)

    src = sqlite3.connect(args.sqlite_path)
    src.row_factory = sqlite3.Row

    def rows(table):
        return src.execute(f"SELECT * FROM {table}").fetchall()

    if args.dry_run:
        print("--- DRY RUN: contagens na origem ---")
        for t in TABELAS_ORDEM:
            print(f"{t}: {len(rows(t))} linha(s)")
        return

    app = create_app()
    print(f"Banco de destino: {_uri_sem_senha(app.config['SQLALCHEMY_DATABASE_URI'])}")

    with app.app_context():
        existentes = ErpOrcamento.query.count()
        if existentes and not args.wipe_first:
            print(f"ABORTADO: já existem {existentes} orçamento(s) em erp_orcamentos. "
                  f"Rode com --wipe-first se quer substituir tudo.")
            sys.exit(1)

        if args.wipe_first:
            print("Limpando tabelas erp_* existentes...")
            ErpTransacao.query.delete()
            ErpItemOrcamento.query.delete()
            ErpOrdemServico.query.delete()
            ErpOrcamento.query.delete()
            ErpCatalogoItem.query.delete()
            ErpCliente.query.delete()
            ErpBanco.query.delete()
            ErpCategoriaFinanceira.query.delete()
            ErpEmpresa.query.delete()
            db.session.commit()

        # 1. empresa (singleton) — atualiza se já existir, em vez de inserir.
        # A linha id=1 é criada sozinha no primeiro acesso ao painel, então um
        # insert cru falharia por chave duplicada.
        emp_rows = rows("empresa")
        if emp_rows:
            e = emp_rows[0]
            empresa = db.session.get(ErpEmpresa, 1)
            if not empresa:
                empresa = ErpEmpresa(id=1)
                db.session.add(empresa)
            empresa.nome = e["nome"] or "RD Soluções"
            empresa.email = e["email"]
            empresa.site = e["site"]
            empresa.telefone = e["telefone"]
            empresa.cnpj = e["cnpj"]
            empresa.forma_pagamento_padrao = e["forma_pagamento_padrao"]
            empresa.validade_dias_padrao = e["validade_dias_padrao"] or 12
            empresa.garantia_dias_padrao = e["garantia_dias_padrao"] or 90
            empresa.proximo_numero = e["proximo_numero"] or 1
            empresa.proximo_os = e["proximo_os"] or 1
            empresa.tema = e["tema"] or "Teal Padrão"
            db.session.commit()
        print(f"empresa: {len(emp_rows)} registro(s)")

        # 2. clientes — guarda um mapa nome-normalizado -> id pro backfill de cliente_id
        clientes_rows = rows("clientes")
        clientes_map = {}
        for r in clientes_rows:
            db.session.add(ErpCliente(
                id=r["id"], nome=r["nome"] or "(sem nome)", telefone=r["telefone"], email=r["email"],
                cep=r["cep"], endereco=r["endereco"], observacoes=r["observacoes"],
            ))
            clientes_map[(r["nome"] or "").strip().lower()] = r["id"]
        db.session.commit()
        print(f"clientes: {len(clientes_rows)} registro(s)")

        # 3. catálogo
        catalogo_rows = rows("catalogo_itens")
        for r in catalogo_rows:
            db.session.add(ErpCatalogoItem(
                id=r["id"], descricao=r["descricao"], valor_unitario=parse_money(r["valor_unitario"]),
                unidade=r["unidade"] or "unid",
            ))
        db.session.commit()
        print(f"catalogo_itens: {len(catalogo_rows)} registro(s)")

        # 4. bancos
        bancos_rows = rows("bancos")
        for r in bancos_rows:
            db.session.add(ErpBanco(
                id=r["id"], nome=r["nome"], agencia=r["agencia"], conta=r["conta"],
                cor=r["cor"] or "#1a5fa8", saldo_inicial=parse_money(r["saldo_inicial"]),
            ))
        db.session.commit()
        print(f"bancos: {len(bancos_rows)} registro(s)")

        # 5. categorias financeiras
        cat_rows = rows("cat_financeiras")
        for r in cat_rows:
            db.session.add(ErpCategoriaFinanceira(id=r["id"], nome=r["nome"], tipo=r["tipo"] or "Ambos", cor=r["cor"] or "#95a5a6"))
        db.session.commit()
        print(f"cat_financeiras: {len(cat_rows)} registro(s)")

        # 6. orçamentos — cliente_id é best-effort (match por nome normalizado); os
        # campos snapshot (cliente_nome/telefone/endereco) continuam a fonte de
        # verdade do PDF, o FK só habilita telas de "orçamentos deste cliente".
        orc_rows = rows("orcamentos")
        for r in orc_rows:
            cliente_id = clientes_map.get((r["cliente_nome"] or "").strip().lower())
            db.session.add(ErpOrcamento(
                id=r["id"], numero=r["numero"] or 0,
                data_emissao=parse_date(r["data_emissao"]) or date(1970, 1, 1),
                situacao=r["situacao"] or "Aguardando Retorno",
                descricao_servico=r["descricao_servico"],
                cliente_id=cliente_id,
                cliente_nome=r["cliente_nome"], cliente_telefone=r["cliente_telefone"],
                cliente_endereco=r["cliente_endereco"],
                validade=r["validade"], garantia=r["garantia"], forma_pagamento=r["forma_pagamento"],
                observacoes=r["observacoes"],
            ))
        db.session.commit()
        sem_match = sum(1 for r in orc_rows if not clientes_map.get((r["cliente_nome"] or "").strip().lower()))
        print(f"orcamentos: {len(orc_rows)} registro(s) ({sem_match} sem cliente_id encontrado por nome)")

        # 7. itens de orçamento
        itens_rows = rows("itens_orcamento")
        for r in itens_rows:
            db.session.add(ErpItemOrcamento(
                id=r["id"], orcamento_id=r["orcamento_id"], descricao=r["descricao"],
                valor_unitario=parse_money(r["valor_unitario"]),
                quantidade=parse_money(r["quantidade"], default="1") if r["quantidade"] is not None else Decimal("1"),
            ))
        db.session.commit()
        print(f"itens_orcamento: {len(itens_rows)} registro(s)")

        # 8. transações
        tx_rows = rows("transacoes")
        for r in tx_rows:
            db.session.add(ErpTransacao(
                id=r["id"], data=parse_date(r["data"]) or date(1970, 1, 1),
                descricao=(r["descricao"] or "").strip() or None,
                tipo=r["tipo"] or "Entrada", valor=parse_money(r["valor"]),
                orcamento_id=r["orcamento_id"],
                # O desktop gravava categoria vazia como '' — normaliza pra NULL,
                # senão ficam dois jeitos de dizer "sem categoria" no banco.
                categoria=(r["categoria"] or "").strip() or None,
                banco_id=r["banco_id"],
            ))
        db.session.commit()
        print(f"transacoes: {len(tx_rows)} registro(s)")

        # 9. ordens de serviço
        os_rows = rows("ordens_servico")
        for r in os_rows:
            db.session.add(ErpOrdemServico(
                id=r["id"], numero=r["numero"] or 1, orcamento_id=r["orcamento_id"],
                data_emissao=parse_date(r["data_emissao"]) or date(1970, 1, 1),
                status=r["status"] or "Aberta", observacoes=r["observacoes"],
            ))
        db.session.commit()
        print(f"ordens_servico: {len(os_rows)} registro(s)")

        # Reset de sequence — só relevante em Postgres (SQLite recalcula
        # automaticamente o próximo rowid a partir do MAX existente).
        if db.engine.dialect.name == "postgresql":
            from sqlalchemy import text
            for tabela in ["erp_clientes", "erp_catalogo_itens", "erp_bancos", "erp_categorias_financeiras",
                            "erp_orcamentos", "erp_itens_orcamento", "erp_transacoes", "erp_ordens_servico"]:
                db.session.execute(text(
                    f"SELECT setval('{tabela}_id_seq', COALESCE((SELECT MAX(id) FROM {tabela}), 1))"
                ))
            db.session.commit()
            print("Sequences do Postgres resetadas.")

        print("Migração concluída.")


if __name__ == "__main__":
    main()
