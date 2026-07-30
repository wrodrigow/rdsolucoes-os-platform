"""Contadores de numeração de Orçamento e OS.

No app desktop (SQLite, um usuário só) ler-e-incrementar nunca colidia. Aqui
Rodrigo e Dany podem salvar ao mesmo tempo, então o contador precisa ser lido
com a linha travada (`SELECT ... FOR UPDATE` no Postgres) dentro da mesma
transação que grava o registro. No SQLite o dialeto ignora o FOR UPDATE — não
é problema, ele já serializa escritas.

Uso (sem commit aqui — quem chama commita junto com o registro criado):
    numero = proximo_numero_orcamento()
    db.session.add(ErpOrcamento(numero=numero, ...))
    db.session.commit()
"""
from ...extensions import db
from ...models.erp import ErpEmpresa


def _empresa_travada():
    empresa = db.session.query(ErpEmpresa).filter_by(id=1).with_for_update().first()
    if not empresa:
        empresa = ErpEmpresa(id=1, nome="RD Soluções")
        db.session.add(empresa)
        db.session.flush()
    return empresa


def proximo_numero_orcamento():
    empresa = _empresa_travada()
    numero = empresa.proximo_numero or 1
    empresa.proximo_numero = numero + 1
    db.session.flush()
    return numero


def proximo_numero_os():
    empresa = _empresa_travada()
    numero = empresa.proximo_os or 1
    empresa.proximo_os = numero + 1
    db.session.flush()
    return numero
