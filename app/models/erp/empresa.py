from ...extensions import db


class ErpEmpresa(db.Model):
    """Config singleton (id=1) da empresa dentro do módulo de Gestão —
    dados usados nos PDFs de orçamento/OS e os contadores de numeração."""
    __tablename__ = "erp_empresa"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False, default="RD Soluções")
    email = db.Column(db.String(180))
    site = db.Column(db.String(180))
    telefone = db.Column(db.String(30))
    cnpj = db.Column(db.String(30))
    logo_blob = db.Column(db.LargeBinary)
    logo_mime = db.Column(db.String(40))
    forma_pagamento_padrao = db.Column(db.String(120))
    validade_dias_padrao = db.Column(db.Integer, nullable=False, default=12)
    garantia_dias_padrao = db.Column(db.Integer, nullable=False, default=90)
    proximo_numero = db.Column(db.Integer, nullable=False, default=1)
    proximo_os = db.Column(db.Integer, nullable=False, default=1)
    tema = db.Column(db.String(40), nullable=False, default="Teal Padrão")

    @classmethod
    def get(cls):
        empresa = db.session.get(cls, 1)
        if not empresa:
            empresa = cls(id=1, nome="RD Soluções")
            db.session.add(empresa)
            db.session.commit()
        return empresa
