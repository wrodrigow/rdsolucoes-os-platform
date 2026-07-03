import socket
import traceback
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
        # Flask-Mail 0.10.0 ignora MAIL_TIMEOUT em configure_host(); forçamos
        # o timeout via socket global para evitar travar o worker gunicorn.
        _old = socket.getdefaulttimeout()
        socket.setdefaulttimeout(10)
        try:
            mail.send(msg)
        finally:
            socket.setdefaulttimeout(_old)
        return True
    except Exception as e:
        current_app.logger.error(
            f"[EMAIL] {type(e).__name__} ao enviar para {to}: {e}\n"
            + traceback.format_exc()
        )
        return False


def enviar_confirmacao_compra(order, license_, user):
    """Dispara o e-mail de confirmação de compra com a KEY."""
    try:
        from ..models.download import Download
        from ..models.site_config import SiteConfig
        download = Download.get_ativo()
        suporte_email = SiteConfig.get("site_email_contato") or current_app.config.get("MAIL_USERNAME", "")
        mail_footer = SiteConfig.get("mail_footer") or "RD Soluções — rdsolucoes.eco.br"
        key_obj = license_.key_obj if license_ else None

        return send_email(
            to=user.email,
            subject=f"✅ Sua licença está pronta! Pedido {order.numero_pedido}",
            template="emails/compra_confirmada.html",
            user=user,
            order=order,
            license=license_,
            key=key_obj,
            download=download,
            base_url=current_app.config["BASE_URL"],
            suporte_email=suporte_email,
            mail_footer=mail_footer,
        )
    except Exception as e:
        current_app.logger.error(f"Erro em enviar_confirmacao_compra para {user.email}: {e}")
        return False


def enviar_recuperacao_senha(user, token):
    return send_email(
        to=user.email,
        subject="Recuperação de senha — RD Soluções OS",
        template="emails/recuperar_senha.html",
        user=user,
        token=token,
        base_url=current_app.config["BASE_URL"],
    )
