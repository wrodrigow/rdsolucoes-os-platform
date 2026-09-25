from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()
migrate = Migrate()
def _chave_limite():
    """IP real do visitante para os limites de requisição. Na Render o
    remote_addr é o hop interno (10.x), igual para todo mundo: sem isto, um
    limite "15 por hora" valeria para o site inteiro."""
    try:
        from flask import request
        from .models.traffic_event import TrafficEvent
        ip = TrafficEvent._ip_cliente(request) or get_remote_address()
        if ip and ":" in ip:
            # operadoras entregam um /64 inteiro por cliente: girar o final do
            # endereço não pode render um limite novo
            import ipaddress
            ip = str(ipaddress.ip_network(ip + "/64", strict=False))
        return ip
    except Exception:
        return get_remote_address()


limiter = Limiter(key_func=_chave_limite, default_limits=[], storage_uri="memory://")
