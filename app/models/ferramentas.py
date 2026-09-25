"""Ferramentas online do RD OS (antes e depois; depois orçamento e OS).

Plano grátis (com marca d'água RD Soluções) e Pro por pagamento único.

Tudo em tabelas próprias com prefixo ``ferr_``: o projeto não tem Alembic e
``create_all`` não altera tabelas existentes, então nada aqui mexe em
``users`` nem em ``orders`` — só aponta para elas.
"""
from datetime import datetime, timezone

from ..extensions import db


def _agora():
    return datetime.now(timezone.utc)


class FerrPedidoPro(db.Model):
    """Marca um pedido como compra do Pro das ferramentas.

    O webhook do Mercado Pago consulta esta tabela para decidir se libera o Pro
    ou uma licença do RD OS desktop — sem ela, todo pagamento aprovado recebia
    uma chave do desktop.
    """
    __tablename__ = "ferr_pedidos_pro"

    # CASCADE: se um pedido de teste/abandonado for apagado, a marcação vai junto
    order_id = db.Column(db.String(36), db.ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True)
    created_at = db.Column(db.DateTime, default=_agora, nullable=False)


class FerrAcessoPro(db.Model):
    """Quem tem o Pro. Uma linha por usuário; pagamento único, sem vencimento."""
    __tablename__ = "ferr_acessos_pro"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), primary_key=True)
    order_id = db.Column(db.String(36), db.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    liberado_em = db.Column(db.DateTime, default=_agora, nullable=False)


class FerrMarca(db.Model):
    """Identidade visual que o usuário Pro aplica nas artes."""
    __tablename__ = "ferr_marcas"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), primary_key=True)
    empresa = db.Column(db.String(80), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    site = db.Column(db.String(120), nullable=True)          # site ou @instagram
    cor_primaria = db.Column(db.String(7), nullable=False, default="#0c2340")
    cor_destaque = db.Column(db.String(7), nullable=False, default="#f97316")
    # Logo já normalizado pelo servidor: PNG, no máximo 600 px no lado maior.
    # Fica no banco porque o disco da Render é apagado a cada deploy.
    logo = db.Column(db.LargeBinary, nullable=True)
    logo_versao = db.Column(db.Integer, nullable=False, default=0)   # muda a URL a cada troca (cache)
    atualizado_em = db.Column(db.DateTime, default=_agora, onupdate=_agora, nullable=False)

    def como_dict(self, logo_url=None):
        return {
            "empresa": self.empresa or "",
            "telefone": self.telefone or "",
            "site": self.site or "",
            "corPrimaria": self.cor_primaria,
            "corDestaque": self.cor_destaque,
            "logo": logo_url if self.logo else None,
        }


class FerrListaEspera(db.Model):
    """E-mails de quem quer o Pro em países onde ainda não vendemos (es/en)."""
    __tablename__ = "ferr_lista_espera"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(180), nullable=False, index=True)
    idioma = db.Column(db.String(5), nullable=False)
    created_at = db.Column(db.DateTime, default=_agora, nullable=False)
