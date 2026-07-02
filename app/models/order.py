import uuid
from datetime import datetime, timezone
from ..extensions import db


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    numero_pedido = db.Column(db.String(20), unique=True, nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)

    # Produto
    produto_nome = db.Column(db.String(200), nullable=False, default="RD Soluções OS — Licença Vitalícia")
    valor = db.Column(db.Numeric(10, 2), nullable=False, default=297.00)

    # Status: pending | approved | cancelled | refunded | in_process
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)

    # Mercado Pago
    mp_preference_id = db.Column(db.String(100), nullable=True)
    mp_payment_id = db.Column(db.String(50), nullable=True, index=True)
    mp_status = db.Column(db.String(30), nullable=True)
    mp_payment_method = db.Column(db.String(50), nullable=True)
    mp_payment_type = db.Column(db.String(30), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    approved_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relacionamentos
    license = db.relationship("License", backref="order", uselist=False, cascade="all, delete-orphan")
    key = db.relationship("Key", backref="order", uselist=False)

    @staticmethod
    def gerar_numero():
        from ..extensions import db
        import random
        prefix = "RD"
        ts = datetime.now(timezone.utc).strftime("%y%m%d")
        suffix = f"{random.randint(1000, 9999)}"
        return f"{prefix}{ts}{suffix}"

    def valor_formatado(self):
        return f"R$ {float(self.valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def status_label(self):
        labels = {
            "pending": ("Aguardando Pagamento", "warning"),
            "approved": ("Aprovado", "success"),
            "in_process": ("Em Processamento", "info"),
            "cancelled": ("Cancelado", "danger"),
            "refunded": ("Reembolsado", "secondary"),
        }
        text, cls = labels.get(self.status, (self.status, "secondary"))
        return f'<span class="adm-badge adm-badge-{cls}">{text}</span>'

    def __repr__(self):
        return f"<Order {self.numero_pedido}>"
