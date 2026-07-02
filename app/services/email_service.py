from flask import current_app, render_template
from flask_mail import Message
from ..extensions import mail


def send_email(to, subject, template, **kwargs):
    """Envia um e-mail HTML usando o template fornecido."""
    try:
        html_body = render_template(template, **kwargs)
        msg = Message(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            html=html_body,
            sender=current_app.config["MAIL_DEFAULT_SENDER"],
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Erro ao enviar e-mail para {to}: {e}")
        return False


def enviar_confirmacao_compra(order, license_, user):
    """Dispara o e-mail de confirmação de compra com a KEY."""
    from ..models.download import Download
    download = Download.get_ativo()

    return send_email(
        to=user.email,
        subject=f"✅ Sua licença está pronta! Pedido {order.numero_pedido}",
        template="emails/compra_confirmada.html",
        user=user,
        order=order,
        license=license_,
        key=license_.key_obj,
        download=download,
        base_url=current_app.config["BASE_URL"],
    )


def enviar_recuperacao_senha(user, token):
    return send_email(
        to=user.email,
        subject="Recuperação de senha — RD Soluções OS",
        template="emails/recuperar_senha.html",
        user=user,
        token=token,
        base_url=current_app.config["BASE_URL"],
    )
