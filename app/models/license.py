import uuid
from datetime import datetime, timezone
from ..extensions import db


class License(db.Model):
    __tablename__ = "licenses"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    order_id = db.Column(db.String(36), db.ForeignKey("orders.id"), nullable=False, unique=True)
    key_id = db.Column(db.Integer, db.ForeignKey("keys.id"), nullable=False, unique=True)

    tipo = db.Column(db.String(30), nullable=False, default="vitalicia")

    # ativa | suspensa | cancelada
    status = db.Column(db.String(20), nullable=False, default="ativa", index=True)

    versao_liberada = db.Column(db.String(20), nullable=False, default="v1.19")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    key_obj = db.relationship("Key", backref="license", uselist=False)

    def status_label(self):
        labels = {
            "ativa": ("ATIVA", "success"),
            "suspensa": ("SUSPENSA", "warning"),
            "cancelada": ("CANCELADA", "danger"),
        }
        return labels.get(self.status, (self.status.upper(), "secondary"))

    def __repr__(self):
        return f"<License {self.id} [{self.status}]>"
