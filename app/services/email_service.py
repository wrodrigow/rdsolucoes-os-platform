import re
import socket
import traceback
from flask import current_app, render_template
from flask_mail import Message
from ..extensions import mail


def _html_to_text(html):
    """Converte HTML em plain-text limpo para versão alternativa do e-mail."""
    t = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    t = re.sub(r'<(?:p|div|tr|li)[^>]*>', '\n', t, flags=re.IGNORECASE)
    t = re.sub(r'</(?:p|div|tr|li)>', '\n', t, flags=re.IGNORECASE)
    t = re.sub(r'<h[1-6][^>]*>', '\n\n', t, flags=re.IGNORECASE)
    t = re.sub(r'</h[1-6]>', '\n', t, flags=re.IGNORECASE)
    t = re.sub(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'\2 (\1)', t, flags=re.IGNORECASE | re.DOTALL)
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ').replace('&#39;', "'")
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def send_email(to, subject, template, **kwargs):
    """Envia e-mail via Resend API (se RESEND_API_KEY estiver definida) ou SMTP."""
    try:
        html_body = render_template(template, **kwargs)
        text_body = _html_to_text(html_body)
        api_key = current_app.config.get("RESEND_API_KEY", "")
        if api_key:
            return _send_via_resend(api_key, to, subject, html_body, text_body)
        return _send_via_smtp(to, subject, html_body, text_body)
    except Exception as e:
        current_app.logger.error(
            f"[EMAIL] {type(e).__name__} ao enviar para {to}: {e}\n"
            + traceback.format_exc()
        )
        return False


def _send_via_resend(api_key, to, subject, html_body, text_body):
    import resend
    resend.api_key = api_key
    sender = current_app.config.get("MAIL_DEFAULT_SENDER", "")
    params = {
        "from": sender,
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }
    response = resend.Emails.send(params)
    if response.get("id"):
        return True
    current_app.logger.error(f"[EMAIL/Resend] resposta inesperada: {response}")
    return False


def _send_via_smtp(to, subject, html_body, text_body):
    # Flask-Mail 0.10 ignora MAIL_TIMEOUT em configure_host(); usamos
    # socket.setdefaulttimeout para não travar o worker gunicorn.
    msg = Message(
        subject=subject,
        recipients=[to] if isinstance(to, str) else to,
        html=html_body,
        body=text_body,
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
