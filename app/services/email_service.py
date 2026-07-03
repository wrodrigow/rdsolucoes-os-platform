import socket
import traceback
from flask import current_app, render_template
from flask_mail import Message
from ..extensions import mail


def send_email(to, subject, template, **kwargs):
    """Envia e-mail via Resend API (se RESEND_API_KEY estiver definida) ou SMTP."""
    try:
        html_body = render_template(template, **kwargs)
        api_key = current_app.config.get("RESEND_API_KEY", "")
        if api_key:
            return _send_via_resend(api_key, to, subject, html_body)
        return _send_via_smtp(to, subject, html_body)
    except Exception as e:
        current_app.logger.error(
            f"[EMAIL] {type(e).__name__} ao enviar para {to}: {e}\n"
            + traceback.format_exc()
        )
        return False


def _send_via_resend(api_key, to, subject, html_body):
    import resend
    resend.api_key = api_key
    sender = current_app.config.get("MAIL_DEFAULT_SENDER", "")
    params = {
        "from": sender,
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "html": html_body,
    }
    response = resend.Emails.send(params)
    if response.get("id"):
        return True
    current_app.logger.error(f"[EMAIL/Resend] resposta inesperada: {response}")
    return False


def _send_via_smtp(to, subject, html_body):
    # Flask-Mail 0.10 ignora MAIL_TIMEOUT em configure_host(); usamos
    # socket.setdefaulttimeout para não travar o worker gunicorn.
    msg = Message(
        subject=subject,
        recipients=[to] if isinstance(to, str) else to,
        html=html_body,
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
    )
    _old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(10)
    try:
        mail.send(msg)
    finally:
        socket.setdefaulttimeout(_old)
    return True


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
    from ..models.site_config import SiteConfig
    base_url = current_app.config["BASE_URL"]
    reset_url = f"{base_url}/auth/nova-senha/{token}"
    mail_footer = SiteConfig.get("mail_footer") or "RD Soluções — rdsolucoes.eco.br"
    return send_email(
        to=user.email,
        subject="Recuperação de senha — RD Soluções OS",
        template="emails/recuperar_senha.html",
        user=user,
        token=token,
        reset_url=reset_url,
        base_url=base_url,
        mail_footer=mail_footer,
    )
