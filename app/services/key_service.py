from datetime import datetime, timezone
from ..extensions import db
from ..models.key import Key
from ..models.license import License
from ..models.download import Download


def assign_key(order):
    """
    Seleciona uma KEY disponível, associa ao pedido e cria a licença.
    Retorna a License criada ou lança exceção se não houver keys.
    Usa SELECT FOR UPDATE para evitar race conditions.
    """
    key = Key.get_disponivel()
    if not key:
        raise RuntimeError("Nenhuma KEY disponível. Contate o suporte.")

    now = datetime.now(timezone.utc)
    key.status = "vendida"
    key.order_id = order.id
    key.user_id = order.user_id
    key.data_venda = now

    versao_atual = Download.get_ativo()
    versao = versao_atual.versao if versao_atual else "v1.19"

    license_ = License(
        user_id=order.user_id,
        order_id=order.id,
        key_id=key.id,
        tipo="vitalicia",
        status="ativa",
        versao_liberada=versao,
    )
    db.session.add(license_)
    db.session.commit()
    return license_


def get_license_for_user(user_id):
    """Retorna a licença mais recente e ativa do usuário."""
    return (
        License.query
        .filter_by(user_id=user_id, status="ativa")
        .order_by(License.created_at.desc())
        .first()
    )
