from datetime import datetime, timezone
from ...extensions import db


class ErpCliente(db.Model):
    """Cadastro de clientes do ERP interno (RD Soluções) — distinto dos
    `User` da plataforma de vendas, que são compradores do produto."""
    __tablename__ = "erp_clientes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False, index=True)
    telefone = db.Column(db.String(30))
    email = db.Column(db.String(180))
    cep = db.Column(db.String(12))
    endereco = db.Column(db.String(300))
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
