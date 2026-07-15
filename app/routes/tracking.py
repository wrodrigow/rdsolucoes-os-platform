from flask import Blueprint, request
from ..extensions import csrf, limiter
from ..models.traffic_event import TrafficEvent

bp = Blueprint("tracking", __name__)

# Origens externas autorizadas a mandar eventos pra cá (sites estáticos fora
# do domínio do próprio Flask, ex.: rdsolucoes.eco.br). Isolado deste
# blueprint só — não mexe no CSP nem nos headers globais da app.
ORIGENS_PERMITIDAS = {
    "https://rdsolucoes.eco.br",
    "https://www.rdsolucoes.eco.br",
}

# Whitelist fechada de eventos aceitos por produto externo (mesmo espírito
# de LP_EVENTOS_PERMITIDOS em routes/main.py, mas aqui é por produto porque
# cada site tem seu próprio funil de conversão).
# "lp_view" é o tipo universal de "visitou a página" — reaproveitado do
# funil do RD OS (routes/admin.py:trafego_dados) para que a visita apareça
# no mesmo gráfico/funil sem precisar duplicar a lógica de agregação por
# tipo de evento. O produto é o que diferencia uma visita de outra.
EVENTOS_PERMITIDOS = {
    "rd_soldas": {
        "lp_view", "whatsapp_click", "scroll_50", "scroll_100", "faq_view",
    },
    "blog": {
        # lp_view = visualização de página (mesmo nome universal, pra reaproveitar
        # o gráfico/funil de 24h já pronto no admin sem duplicar lógica).
        "lp_view", "whatsapp_click", "scroll_50", "scroll_100",
        "click_afiliado", "click_interno",
    },
}


@bp.after_request
def _cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in ORIGENS_PERMITIDAS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    return response


@bp.route("/evento", methods=["POST", "OPTIONS"])
@csrf.exempt  # beacon anônimo via sendBeacon — não carrega token CSRF
@limiter.limit("60 per minute")
def evento():
    """Endpoint público de tracking para sites externos ao Flask (ex.: o
    site estático do RD Soldas). Isolado das rotas de main.py/checkout.py
    que sustentam o funil de vendas do RD OS — qualquer alteração aqui não
    afeta o funcionamento delas."""
    if request.method == "OPTIONS":
        return "", 204

    produto = (request.form.get("produto") or "").strip()
    tipo = (request.form.get("tipo") or "").strip()

    if produto not in EVENTOS_PERMITIDOS or tipo not in EVENTOS_PERMITIDOS[produto]:
        return "", 204

    slug = (request.form.get("slug") or "").strip()
    detalhe = (request.form.get("detalhe") or "").strip()
    TrafficEvent.registrar(tipo, request, produto=produto, slug=slug or None, detalhe=detalhe or None)
    return "", 204
