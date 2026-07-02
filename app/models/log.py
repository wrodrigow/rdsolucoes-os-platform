from datetime import datetime, timezone
from ..extensions import db


class Log(db.Model):
    __tablename__ = "logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    acao = db.Column(db.String(100), nullable=False, index=True)
    detalhes = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    @classmethod
    def registrar(cls, acao, detalhes=None, user_id=None, ip=None, user_agent=None):
        from ..extensions import db
        log = cls(acao=acao, detalhes=detalhes, user_id=user_id, ip=ip, user_agent=user_agent)
        db.session.add(log)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    def __repr__(self):
        return f"<Log {self.acao} {self.created_at}>"
