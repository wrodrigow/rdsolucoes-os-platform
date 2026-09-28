"""Ferramentas online do RD OS: antes e depois, orçamento e ordem de serviço.

Plano grátis (com marca d'água RD OS) e Pro por pagamento único ou código de cortesia.

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
    """Quem tem o Pro. Uma linha por usuário; pagamento único, sem vencimento.
    Sem order_id: Pro de cortesia (código de parceiro, ver FerrCodigo)."""
    __tablename__ = "ferr_acessos_pro"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), primary_key=True)
    order_id = db.Column(db.String(36), db.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    liberado_em = db.Column(db.DateTime, default=_agora, nullable=False)


class FerrCodigo(db.Model):
    """Código de cortesia do Pro, um por parceiro (grupo, loja, curso, evento).

    O mesmo código dá o endereço de indicação /p/<codigo> (em minúsculas), que
    grava de onde a visita veio. Limite de usos e validade seguram o prejuízo
    se o código vazar para fora do grupo."""
    __tablename__ = "ferr_codigos"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo = db.Column(db.String(24), nullable=False, unique=True, index=True)   # sempre MAIÚSCULO
    parceiro = db.Column(db.String(80), nullable=False)                           # nome mostrado na página
    limite_usos = db.Column(db.Integer, nullable=False, default=100)
    usos = db.Column(db.Integer, nullable=False, default=0)
    valido_ate = db.Column(db.Date, nullable=True)                                # inclusive; vazio = sem prazo
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, default=_agora, nullable=False)

    @property
    def slug(self):
        return self.codigo.lower()

    def situacao(self, hoje=None):
        """None se o código pode ser usado; senão, o motivo (para a pessoa)."""
        from datetime import date
        hoje = hoje or date.today()
        if not self.ativo:
            return "Esse código foi encerrado."
        if self.valido_ate and hoje > self.valido_ate:
            return "Esse código venceu."
        if self.usos >= self.limite_usos:
            return "Os acessos desse código já acabaram."
        return None


class FerrCodigoUso(db.Model):
    """Quem usou cada código (uma vez por conta)."""
    __tablename__ = "ferr_codigos_usos"
    __table_args__ = (db.UniqueConstraint("codigo_id", "user_id", name="uq_ferr_codigo_uso"),)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_id = db.Column(db.Integer, db.ForeignKey("ferr_codigos.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # WhatsApp só fica guardado se a pessoa aceitou receber novidades
    whatsapp = db.Column(db.String(30), nullable=True)
    aceita_contato = db.Column(db.Boolean, nullable=False, default=False)
    criado_em = db.Column(db.DateTime, default=_agora, nullable=False)


class FerrMarca(db.Model):
    """Identidade visual que o usuário Pro aplica nas artes."""
    __tablename__ = "ferr_marcas"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), primary_key=True)
    empresa = db.Column(db.String(80), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    site = db.Column(db.String(120), nullable=True)          # site ou @instagram
    # usados no cabeçalho do orçamento e da OS (Pro). Colunas criadas em
    # _ensure_schema_upgrades para a tabela que já existe em produção.
    cnpj = db.Column(db.String(30), nullable=True)            # CNPJ ou CPF
    email = db.Column(db.String(120), nullable=True)
    endereco = db.Column(db.String(200), nullable=True)
    condicoes = db.Column(db.Text, nullable=True)            # texto padrão do orçamento
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
