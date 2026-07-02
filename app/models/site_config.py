from ..extensions import db


class SiteConfig(db.Model):
    __tablename__ = "site_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chave = db.Column(db.String(80), unique=True, nullable=False, index=True)
    valor = db.Column(db.Text, nullable=True)

    @classmethod
    def get(cls, chave, default=None):
        obj = cls.query.filter_by(chave=chave).first()
        return obj.valor if obj else default

    @classmethod
    def set(cls, chave, valor):
        obj = cls.query.filter_by(chave=chave).first()
        if obj:
            obj.valor = valor
        else:
            obj = cls(chave=chave, valor=valor)
            db.session.add(obj)
        db.session.commit()

    @classmethod
    def set_if_missing(cls, chave, valor):
        if not cls.query.filter_by(chave=chave).first():
            db.session.add(cls(chave=chave, valor=valor))
            db.session.commit()

    @classmethod
    def get_all(cls):
        return {c.chave: c.valor for c in cls.query.all()}

    def __repr__(self):
        return f"<SiteConfig {self.chave}={self.valor}>"
