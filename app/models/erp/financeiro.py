from ...extensions import db


class ErpBanco(db.Model):
    __tablename__ = "erp_bancos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    agencia = db.Column(db.String(20))
    conta = db.Column(db.String(30))
    cor = db.Column(db.String(10), nullable=False, default="#1a5fa8")
    saldo_inicial = db.Column(db.Numeric(10, 2), nullable=False, default=0)


class ErpCategoriaFinanceira(db.Model):
    __tablename__ = "erp_categorias_financeiras"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    tipo = db.Column(db.String(10), nullable=False, default="Ambos")  # Entrada | Saída | Ambos
    cor = db.Column(db.String(10), nullable=False, default="#95a5a6")


class ErpTransacao(db.Model):
    __tablename__ = "erp_transacoes"

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, index=True)
    descricao = db.Column(db.String(300))
    tipo = db.Column(db.String(10), nullable=False, default="Entrada")  # Entrada | Saída
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    orcamento_id = db.Column(db.Integer, db.ForeignKey("erp_orcamentos.id", ondelete="SET NULL"), nullable=True)
    categoria = db.Column(db.String(80))
    banco_id = db.Column(db.Integer, db.ForeignKey("erp_bancos.id", ondelete="SET NULL"), nullable=True)

    banco = db.relationship("ErpBanco")
    orcamento = db.relationship("ErpOrcamento")
