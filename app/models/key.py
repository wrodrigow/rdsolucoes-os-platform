from datetime import datetime, timezone
from ..extensions import db


class Key(db.Model):
    __tablename__ = "keys"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(25), unique=True, nullable=False, index=True)

    # disponivel | vendida | reservada
    status = db.Column(db.String(20), nullable=False, default="disponivel", index=True)

    # Vínculos (preenchidos após venda)
    order_id = db.Column(db.String(36), db.ForeignKey("orders.id"), nullable=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

    data_venda = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    @classmethod
    def get_disponivel(cls):
        return cls.query.filter_by(status="disponivel").with_for_update().first()

    @classmethod
    def total_disponiveis(cls):
        return cls.query.filter_by(status="disponivel").count()

    @classmethod
    def total_vendidas(cls):
        return cls.query.filter_by(status="vendida").count()

    def __repr__(self):
        return f"<Key {self.key} [{self.status}]>"
