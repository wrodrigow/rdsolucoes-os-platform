from ...extensions import db


class ErpOrdemServico(db.Model):
    """OS gerada a partir de um orçamento existente — o número é copiado
    do orçamento de origem (mesmo comportamento do app desktop)."""
    __tablename__ = "erp_ordens_servico"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False, default=1)
    orcamento_id = db.Column(db.Integer, db.ForeignKey("erp_orcamentos.id", ondelete="CASCADE"), nullable=False)
    data_emissao = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Aberta")
    observacoes = db.Column(db.Text)

    orcamento = db.relationship("ErpOrcamento", back_populates="ordens")
