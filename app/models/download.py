from datetime import datetime, timezone
from ..extensions import db


class Download(db.Model):
    __tablename__ = "downloads"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    versao = db.Column(db.String(20), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    nome_arquivo = db.Column(db.String(200), nullable=False)
    tamanho = db.Column(db.String(20), nullable=False, default="—")
    changelog = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    downloads_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    @classmethod
    def get_ativo(cls):
        return cls.query.filter_by(ativo=True).order_by(cls.created_at.desc()).first()

    def __repr__(self):
        return f"<Download {self.versao}>"
