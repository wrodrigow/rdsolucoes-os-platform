import ipaddress
from datetime import datetime, timezone
from ..extensions import db


class TrafficEvent(db.Model):
    """Registra eventos do funil de tráfego pago (LP -> checkout -> pagamento)
    para o painel de acompanhamento em tempo real do admin."""
    __tablename__ = "traffic_events"

    # Fonte única de produtos monitorados. Adicionar um produto novo no
    # futuro é só acrescentar uma linha aqui (chave = valor salvo na coluna
    # `produto`, usado também para validar o endpoint público de tracking).
    PRODUTOS = {"rd_os": "RD OS", "rd_soldas": "RD Soldas", "blog": "Blog", "redes": "Certificação de Redes",
                "ferramentas": "Ferramentas online", "serralheria": "Serralheria (Leonardo)"}

    # Quem abre a página sem ser gente: prévia de link do WhatsApp e do Facebook, scripts e
    # navegadores automatizados. TelegramBot, Slackbot, Discordbot, LinkedInBot etc. já caem
    # no "bot" genérico; "linkedin"/"telegram" sozinhos pegariam o navegador interno desses
    # apps, usado por gente de verdade, então ficam de fora.
    MARCAS_DE_ROBO = ("facebookexternalhit", "facebookcatalog", "whatsapp/", "skypeuripreview", "embedly",
                      "curl/", "wget/", "python-requests", "python-urllib", "aiohttp", "go-http-client", "okhttp",
                      "axios/", "node-fetch", "headlesschrome", "phantomjs", "lighthouse", "pagespeed",
                      "crawler", "spider")

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # lp_view | checkout_start | checkout_success | checkout_fail | post_view | click_afiliado | ...
    event_type = db.Column(db.String(30), nullable=False, index=True)
    path = db.Column(db.String(200), nullable=True)
    gclid = db.Column(db.String(300), nullable=True)
    fbclid = db.Column(db.String(300), nullable=True)
    gad_campaignid = db.Column(db.String(50), nullable=True)
    canal = db.Column(db.String(20), nullable=False, default="direto", index=True)  # google_ads | meta_ads | direto
    produto = db.Column(db.String(20), nullable=False, default="rd_os", index=True)  # ver PRODUTOS acima
    is_bot = db.Column(db.Boolean, default=False, nullable=False, index=True)
    device = db.Column(db.String(20), nullable=True)  # mobile | desktop | unknown
    ip = db.Column(db.String(45), nullable=True)
    order_id = db.Column(db.String(36), nullable=True, index=True)
    # slug do post do blog (quando produto="blog") — permite agrupar por artigo.
    slug = db.Column(db.String(200), nullable=True, index=True)
    # contexto extra livre por tipo de evento: URL clicada num click_afiliado/click_interno,
    # nome do produto de afiliado, etc. — não estruturado, só pra exibir no admin.
    detalhe = db.Column(db.String(300), nullable=True)
    # de onde a visita veio, quando o link diz (?o=... ou /p/<parceiro>): "marca-arte",
    # "pdf-orc", "ig-bio", "p:refrig100"... WhatsApp e apps não mandam referrer,
    # então sem isso tudo cai em "direto". Coluna criada em _ensure_schema_upgrades.
    origem = db.Column(db.String(60), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    @staticmethod
    def _parece_gclid_real(gclid):
        """gclid real do Google tem 20+ caracteres alfanuméricos.
        Bots/crawlers de verificação do Ads costumam mandar gclid numérico curto."""
        if not gclid:
            return False
        return len(gclid) >= 20 and not gclid.isdigit()

    # Faixas publicadas pela Cloudflare (https://www.cloudflare.com/ips/, set/2026)
    CLOUDFLARE = ("173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22", "141.101.64.0/18",
                  "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22", "198.41.128.0/17",
                  "162.158.0.0/15", "104.16.0.0/13", "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
                  "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32", "2405:8100::/32",
                  "2a06:98c0::/29", "2c0f:f248::/32")
    _cache_redes = None

    @staticmethod
    def _ip_valido(ip):
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    @classmethod
    def _redes_cloudflare(cls):
        if cls._cache_redes is None:
            cls._cache_redes = tuple(ipaddress.ip_network(r) for r in cls.CLOUDFLARE)
        return cls._cache_redes

    @classmethod
    def _ip_cliente(cls, request):
        """IP real do visitante.

        Por que não usar request.remote_addr: a app já roda com
        ProxyFix(x_for=1), que pega o item MAIS À DIREITA do X-Forwarded-For.
        Na Render existe um hop interno depois da borda, então a cadeia chega
        como "cliente_real, 10.x" e o item da direita é o 10.x — foi isso que
        gravou o mesmo IP de rede interna pra todo visitante e inutilizou a
        deduplicação por IP.

        Também não serve pegar cegamente o primeiro item: esse é o único que o
        cliente consegue forjar mandando o header na mão.

        Solução: varrer a cadeia da direita pra esquerda e devolver o primeiro
        endereço público. Os hops internos (privados) são descartados, e um IP
        forjado à esquerda só seria usado se não houvesse nenhum público real
        depois dele — o que não acontece, porque a borda acrescenta o verdadeiro.
        """
        def publico(ip):
            """Endereço de gente: público e que não seja da Cloudflare. A Render fica
            atrás da Cloudflare, que acrescenta o IP do próprio servidor de borda no
            fim da cadeia; pegar esse IP gravava um endereço diferente a cada
            requisição (e o mesmo para pessoas diferentes)."""
            try:
                end = ipaddress.ip_address(ip)
            except ValueError:
                return False
            return not end.is_private and not any(end in rede for rede in cls._redes_cloudflare())

        xff = request.headers.get("X-Forwarded-For", "") or ""
        partes = [p.strip() for p in xff.split(",") if p.strip()]
        for ip in reversed(partes):
            if publico(ip):
                return ip[:45]

        real = (request.headers.get("X-Real-IP") or "").strip()
        if publico(real):
            return real[:45]
        # A cadeia só tinha a borda da Cloudflare: vale o CF-Connecting-IP, que a própria
        # Cloudflare preenche (só é aceito quando a requisição veio mesmo de uma borda dela).
        veio_da_cloudflare = any(not publico(p) and not ipaddress.ip_address(p).is_private
                                 for p in partes if cls._ip_valido(p))
        cf = (request.headers.get("CF-Connecting-IP") or "").strip()
        if veio_da_cloudflare and publico(cf):
            return cf[:45]
        # nada público (ex.: acesso local/dev): guarda o que houver, só pra não perder o registro
        return ((partes[0] if partes else None) or real or request.remote_addr or "")[:45] or None

    @classmethod
    def _identificar_canal(cls, gclid, fbclid):
        if cls._parece_gclid_real(gclid):
            return "google_ads"
        if fbclid:
            return "meta_ads"
        return "direto"

    @classmethod
    def registrar(cls, event_type, request, order_id=None, produto="rd_os", slug=None, detalhe=None, origem=None):
        gclid = request.args.get("gclid") or request.form.get("gclid")
        fbclid = request.args.get("fbclid") or request.form.get("fbclid")
        gad_campaignid = request.args.get("gad_campaignid")
        order_id = order_id or request.args.get("external_reference")
        ua = request.user_agent.string or ""

        ua_min = ua.lower()
        is_bot = (
            "AdWords-Express" in ua
            or "bot" in ua_min
            or any(m in ua_min for m in cls.MARCAS_DE_ROBO)
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
            fbclid=fbclid,
            gad_campaignid=gad_campaignid,
            canal=cls._identificar_canal(gclid, fbclid),
            produto=produto if produto in cls.PRODUTOS else "rd_os",
            is_bot=is_bot,
            device=device,
            ip=cls._ip_cliente(request),
            order_id=order_id,
            slug=(slug or "")[:200] or None,
            detalhe=(detalhe or "")[:300] or None,
            origem=(origem or "")[:60] or None,
        )
        db.session.add(ev)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return ev
