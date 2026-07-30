from datetime import datetime, timezone
from ...extensions import db


class ErpOrcamento(db.Model):
    """Orçamento (documento quase-legal). Mantém cliente_nome/telefone/
    endereco como snapshot no momento da emissão — um PDF já gerado não
    pode mudar retroativamente se o cadastro do cliente mudar depois.
    cliente_id é opcional: só liga ao cadastro pra permitir consultas tipo
    'todos os orçamentos deste cliente', sem virar a fonte de verdade do PDF."""
    __tablename__ = "erp_orcamentos"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False, index=True)
    data_emissao = db.Column(db.Date, nullable=False)
    situacao = db.Column(db.String(40), nullable=False, default="Aguardando Retorno")
    descricao_servico = db.Column(db.Text)

    cliente_id = db.Column(db.Integer, db.ForeignKey("erp_clientes.id", ondelete="SET NULL"), nullable=True)
    cliente_nome = db.Column(db.String(160))
    cliente_telefone = db.Column(db.String(30))
    cliente_endereco = db.Column(db.String(300))

    validade = db.Column(db.String(120))
    garantia = db.Column(db.String(120))
    forma_pagamento = db.Column(db.String(120))
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    cliente = db.relationship("ErpCliente")
    itens = db.relationship(
        "ErpItemOrcamento", backref="orcamento",
        cascade="all, delete-orphan", order_by="ErpItemOrcamento.id",
    )
    # Cascade declarado no ORM (não só no ondelete da FK): o SQLite não aplica
    # FK por padrão, então sem isto excluir um orçamento deixava a OS órfã,
    # apontando para um registro que não existe mais.
    ordens = db.relationship(
        "ErpOrdemServico", back_populates="orcamento",
        cascade="all, delete-orphan",
    )

    @property
    def valor_total(self):
        return sum((item.valor_unitario * item.quantidade for item in self.itens), start=0)


class ErpItemOrcamento(db.Model):
    __tablename__ = "erp_itens_orcamento"

    id = db.Column(db.Integer, primary_key=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey("erp_orcamentos.id", ondelete="CASCADE"), nullable=False)
    descricao = db.Column(db.String(300), nullable=False)
    valor_unitario = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    quantidade = db.Column(db.Numeric(10, 2), nullable=False, default=1)
