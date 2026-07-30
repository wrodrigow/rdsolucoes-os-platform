from ...extensions import db


class ErpCatalogoItem(db.Model):
    """Catálogo de serviços/itens reutilizáveis pra prefill na hora de
    montar um orçamento."""
    __tablename__ = "erp_catalogo_itens"

    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(300), nullable=False, index=True)
    valor_unitario = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    unidade = db.Column(db.String(20), nullable=False, default="unid")
