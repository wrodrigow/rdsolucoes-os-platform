from datetime import datetime, timezone
from ..extensions import db


class TrafficEvent(db.Model):
    """Registra eventos do funil de tráfego pago (LP -> checkout -> pagamento)
    para o painel de acompanhamento em tempo real do admin."""
    __tablename__ = "traffic_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # lp_view | checkout_start | checkout_success | checkout_fail
    event_type = db.Column(db.String(30), nullable=False, index=True)
    path = db.Column(db.String(200), nullable=True)
    gclid = db.Column(db.String(300), nullable=True)
    gad_campaignid = db.Column(db.String(50), nullable=True)
    is_bot = db.Column(db.Boolean, default=False, nullable=False, index=True)
    device = db.Column(db.String(20), nullable=True)  # mobile | desktop | unknown
    ip = db.Column(db.String(45), nullable=True)
    order_id = db.Column(db.String(36), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    @staticmethod
    def _parece_gclid_real(gclid):
        """gclid real do Google tem 20+ caracteres alfanuméricos.
        Bots/crawlers de verificação do Ads costumam mandar gclid numérico curto."""
        if not gclid:
            return False
        return len(gclid) >= 20 and not gclid.isdigit()

    @classmethod
    def registrar(cls, event_type, request, order_id=None):
        gclid = request.args.get("gclid") or request.form.get("gclid")
        gad_campaignid = request.args.get("gad_campaignid")
        order_id = order_id or request.args.get("external_reference")
        ua = request.user_agent.string or ""

        is_bot = (
            "AdWords-Express" in ua
            or "bot" in ua.lower()
            or (gclid is not None and not cls._parece_gclid_real(gclid))
        )
        if "Mobile" in ua:
            device = "mobile"
        elif ua:
            device = "desktop"
        else:
            device = "unknown"

        ev = cls(
            event_type=event_type,
            path=request.path,
            gclid=gclid,
            gad_campaignid=gad_campaignid,
            is_bot=is_bot,
            device=device,
            ip=request.remote_addr,
            order_id=order_id,
        )
        db.session.add(ev)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return ev
