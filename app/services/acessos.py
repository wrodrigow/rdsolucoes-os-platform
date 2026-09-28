"""Resumo de acessos de todos os sites para o painel admin (página "Acessos").

Lê só a tabela traffic_events, que já recebe as visitas e ações de:
- site RD Soluções e LP de redes (rdsolucoes.eco.br, via beacon: produtos rd_soldas e redes);
- blog (rdsolucoes.eco.br/blog, via beacon: produto blog, slug = artigo);
- ferramentas (rdos.rdsolucoes.eco.br: produto ferramentas, gravado pelo servidor e pelo JS);
- sistema RD OS (/lp grava lp_view; /sistema grava sistema_view, para não misturar com
  o funil da LP de anúncio no painel de Tráfego).

Robôs ficam de fora. As contagens são feitas no banco (GROUP BY); só as visitas
do período atual vêm linha a linha, para montar gráfico, páginas e origens no
fuso de Brasília do mesmo jeito no Postgres (produção) e no SQLite (testes).
"""
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_

from ..extensions import db
from ..models.traffic_event import TrafficEvent

BRT = timezone(timedelta(hours=-3))           # Brasília, sem horário de verão desde 2019
PERIODOS = {"hoje": "Hoje", "7": "7 dias", "30": "30 dias", "90": "90 dias"}
VISITAS = ("lp_view", "sistema_view")          # eventos que contam como visita a uma página
LIMITE_VISITAS = 150_000                        # trava da consulta linha a linha (período atual)

SITES = [
    {"chave": "site", "nome": "Site RD Soluções", "produtos": ("rd_soldas", "redes"),
     "endereco": "rdsolucoes.eco.br"},
    {"chave": "blog", "nome": "Blog", "produtos": ("blog",), "endereco": "rdsolucoes.eco.br/blog"},
    {"chave": "ferramentas", "nome": "Ferramentas", "produtos": ("ferramentas",),
     "endereco": "rdos.rdsolucoes.eco.br"},
    {"chave": "sistema", "nome": "Sistema RD OS", "produtos": ("rd_os",), "endereco": "rdos…/lp e /sistema"},
]
SITE_DO_PRODUTO = {p: s["chave"] for s in SITES for p in s["produtos"]}
PRODUTOS = tuple(SITE_DO_PRODUTO)

# ações que aparecem em cada cartão: (rótulo, eventos somados)
ACOES = {
    "site": [("Cliques no WhatsApp", ("whatsapp_click",)), ("Viram o FAQ", ("faq_view",))],
    "blog": [("Cliques em afiliados", ("click_afiliado",)), ("Cliques para o site", ("click_interno",)),
             ("Cliques no WhatsApp", ("whatsapp_click",))],
    "ferramentas": [("Artes geradas", ("gerou_arte",)), ("PDFs gerados", ("gerou_pdf",)),
                    ("Baixados ou compartilhados", ("baixou", "compartilhou", "baixou_pdf", "compartilhou_pdf")),
                    ("Interesse no Pro", ("clicou_pro", "checkout_start")), ("Códigos resgatados", ("resgatou_codigo",))],
    "sistema": [("Checkouts iniciados", ("checkout_start",)), ("Viram a oferta", ("lp_viu_oferta",))],
}

EVENTOS_LABEL = {
    "lp_view": "Visita", "sistema_view": "Visita", "whatsapp_click": "Clique no WhatsApp", "faq_view": "Viu o FAQ",
    "scroll_50": "Rolou metade", "scroll_100": "Rolou até o fim", "click_afiliado": "Clique em afiliado",
    "click_interno": "Clique para o site", "gerou_arte": "Gerou arte", "gerou_pdf": "Gerou PDF",
    "baixou": "Baixou a arte", "compartilhou": "Compartilhou a arte", "gerou_video": "Gerou vídeo",
    "baixou_pdf": "Baixou o PDF", "compartilhou_pdf": "Compartilhou o PDF", "clicou_pro": "Clicou no Pro",
    "checkout_start": "Abriu o pagamento", "checkout_success": "Pagamento aprovado", "checkout_fail": "Pagamento falhou",
    "resgatou_codigo": "Resgatou código", "pediu_codigo": "Pediu código", "lista_espera": "Lista de espera",
    "lp_viu_oferta": "Viu a oferta", "lp_form_focus": "Começou o formulário", "lp_cta_hero": "Clicou no botão",
    "lp_cta_bar": "Clicou na barra", "lp_whatsapp": "Clique no WhatsApp",
}

PAGINAS_FERRAMENTAS = {
    "ferramentas": "Página das ferramentas", "antes-e-depois": "Antes e depois", "orcamento": "Orçamento",
    "ordem-de-servico": "Ordem de serviço", "pro": "Venda do Pro", "pro-codigo": "Resgate de código",
}

ORIGENS_LINK = {
    "marca": "Marca d'água da arte", "marca-es": "Marca d'água da arte (es)", "marca-en": "Marca d'água da arte (en)",
    "pdf-orc": "PDF de orçamento", "pdf-os": "PDF de ordem de serviço", "raiz": "Digitou o endereço",
}
REF_RE = re.compile(r"ref:([A-Za-z0-9.\-]+)")
INTERNO = "Dentro dos próprios sites"


def _para_brt(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:                      # o banco devolve sem fuso (UTC)
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRT)


def _naive(dt):
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def janela(periodo, agora=None):
    """(início, fim, início_anterior, fim_anterior, por_hora), em UTC.

    O período anterior tem sempre o mesmo tempo decorrido do atual: "hoje" às 10h
    compara com ontem até as 10h; "7 dias" às 10h compara com os 7 dias anteriores
    até as 10h do dia equivalente (sem isso, de manhã aparecia uma queda que não houve)."""
    agora = (agora or datetime.now(timezone.utc)).astimezone(BRT)
    meia_noite = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    dias = 1 if periodo == "hoje" else int(periodo)
    inicio = meia_noite - timedelta(days=dias - 1)
    anterior = inicio - timedelta(days=dias)
    fim_anterior = agora - timedelta(days=dias)
    utc = timezone.utc
    return (inicio.astimezone(utc), agora.astimezone(utc), anterior.astimezone(utc),
            fim_anterior.astimezone(utc), periodo == "hoje")


def _host_amigavel(host):
    h = (host or "").lower()
    if h.startswith("www."):
        h = h[4:]
    if not h:
        return None
    if h in ("rdsolucoes.eco.br", "rdos.rdsolucoes.eco.br", "rdsolucoes-os-platform.onrender.com", "localhost"):
        return INTERNO
    if "youtube" in h:                                   # antes do Google: com.google.android.youtube
        return "YouTube"
    if h in ("com.google.android.gm", "mail.google.com") or "mail." in h or "outlook" in h:
        return "E-mail"
    if "googlequicksearchbox" in h:
        return "Google (app)"
    if h.startswith("google.") or ".google." in h:
        return "Google"
    if "facebook" in h or h.startswith("fb.") or h in ("lm.facebook.com", "l.facebook.com"):
        return "Facebook"
    if "instagram" in h:
        return "Instagram"
    if "bing." in h:
        return "Bing"
    if "chatgpt" in h or "openai" in h:
        return "ChatGPT"
    if "whatsapp" in h:
        return "WhatsApp"
    if "linkedin" in h or h == "lnkd.in":
        return "LinkedIn"
    return h


def origem_da_visita(ev, parceiros):
    """De onde veio: anúncio do Google > origem do link (?o=, /p/) > site que mandou (referrer)."""
    if ev["canal"] == "google_ads":
        return "Google Ads"
    origem = ev["origem"]
    if origem:
        if origem.startswith("p:"):
            return f"Parceiro: {parceiros.get(origem, origem[2:].upper())}"
        return ORIGENS_LINK.get(origem, f"Link com ?o={origem}")
    if ev["canal"] == "meta_ads":
        # fbclid vem em TODO clique saído do Facebook/Instagram (post orgânico e bio também), não só de anúncio
        return "Facebook ou Instagram"
    m = REF_RE.search(ev["detalhe"] or "")
    return (_host_amigavel(m.group(1)) if m else None) or "Direto ou sem informação"


def pagina_da_visita(ev, titulos_blog):
    produto, slug = ev["produto"], ev["slug"]
    if produto == "rd_soldas":
        return "Loja" if slug == "loja" else ("Início" if not slug else str(slug)[:80])
    if produto == "redes":
        return "LP Certificação de redes"
    if produto == "blog":
        return titulos_blog.get(slug) or (str(slug)[:80] if slug else "Blog")
    if produto == "ferramentas":
        nome = PAGINAS_FERRAMENTAS.get(slug or "", "Outras páginas")
        if slug == "antes-e-depois":
            idioma = (ev["detalhe"] or "").split(":", 1)[0]
            if idioma in ("es", "en"):
                nome += f" ({idioma})"
        return nome
    if produto == "rd_os":
        return "/sistema (venda do desktop)" if slug == "sistema" else "LP do sistema (/lp)"
    return str(slug or ev.get("path") or produto)[:80]


def _base(inicio, fim, fim_inclusivo=True):
    q = TrafficEvent.query.filter(TrafficEvent.created_at >= _naive(inicio), TrafficEvent.is_bot == False,  # noqa: E712
                                  TrafficEvent.produto.in_(PRODUTOS))
    return q.filter(TrafficEvent.created_at <= _naive(fim) if fim_inclusivo else TrafficEvent.created_at < _naive(fim))


def _contagens(inicio, fim, fim_inclusivo=True):
    """{site: Counter(event_type)} e {site: nº de IPs distintos nas visitas}."""
    q = _base(inicio, fim, fim_inclusivo)
    cont = {s["chave"]: Counter() for s in SITES}
    for produto, tipo, n in (q.with_entities(TrafficEvent.produto, TrafficEvent.event_type, func.count(TrafficEvent.id))
                             .group_by(TrafficEvent.produto, TrafficEvent.event_type)):
        cont[SITE_DO_PRODUTO[produto]][tipo] += n
    ips = defaultdict(set)
    for produto, ip in (q.filter(TrafficEvent.event_type.in_(VISITAS), TrafficEvent.ip.isnot(None))
                        .with_entities(TrafficEvent.produto, TrafficEvent.ip).distinct()):
        ips[SITE_DO_PRODUTO[produto]].add(ip)
    return cont, {k: len(v) for k, v in ips.items()}


def _evento(linha):
    return {"quando": _para_brt(linha.created_at), "produto": linha.produto, "tipo": linha.event_type,
            "slug": linha.slug, "ip": linha.ip, "device": linha.device, "detalhe": linha.detalhe,
            "origem": linha.origem, "canal": linha.canal or "direto", "path": linha.path,
            "site": SITE_DO_PRODUTO.get(linha.produto)}


COLUNAS = (TrafficEvent.created_at, TrafficEvent.produto, TrafficEvent.event_type, TrafficEvent.slug, TrafficEvent.ip,
           TrafficEvent.device, TrafficEvent.detalhe, TrafficEvent.origem, TrafficEvent.canal, TrafficEvent.path)


def resumo(periodo="7", agora=None):
    if periodo not in PERIODOS:
        periodo = "7"
    agora_utc = agora or datetime.now(timezone.utc)
    inicio, fim, inicio_ant, fim_ant, por_hora = janela(periodo, agora_utc)

    from ..models.blog import BlogArticle
    from ..models.ferramentas import FerrCodigo, FerrPedidoPro
    from ..models.order import Order
    titulos_blog = {s: t for s, t in db.session.query(BlogArticle.slug, BlogArticle.title)}
    parceiros = {"p:" + c.codigo.lower(): c.parceiro for c in FerrCodigo.query.all()}
    nomes = {s["chave"]: s["nome"] for s in SITES}

    # ------------------------------------------------ contagens (no banco)
    cont, unicos = _contagens(inicio, fim)
    cont_ant, unicos_ant = _contagens(inicio_ant, fim_ant, fim_inclusivo=False)
    robos = (TrafficEvent.query.filter(TrafficEvent.created_at >= _naive(inicio), TrafficEvent.created_at <= _naive(fim),
                                       TrafficEvent.is_bot == True).count())  # noqa: E712

    # ------------------------------------------------ visitas do período, linha a linha (mais novas primeiro no LIMIT)
    linhas = (_base(inicio, fim).filter(TrafficEvent.event_type.in_(VISITAS)).with_entities(*COLUNAS)
              .order_by(TrafficEvent.created_at.desc()).limit(LIMITE_VISITAS).all())
    truncado = len(linhas) >= LIMITE_VISITAS
    visitas = [_evento(l) for l in reversed(linhas)]

    ini_brt = inicio.astimezone(BRT)
    if por_hora:
        rotulos = [f"{h:02d}h" for h in range(0, fim.astimezone(BRT).hour + 1)]
        chave_balde = lambda d: f"{d.hour:02d}h"
    else:
        dias = (fim.astimezone(BRT).date() - ini_brt.date()).days + 1
        rotulos = [(ini_brt.date() + timedelta(days=i)).strftime("%d/%m") for i in range(dias)]
        chave_balde = lambda d: d.strftime("%d/%m")

    serie = {s["chave"]: dict.fromkeys(rotulos, 0) for s in SITES}
    paginas, origens, dispositivos = Counter(), Counter(), Counter()
    entradas_vistas = set()
    for ev in visitas:
        s = ev["site"]
        b = chave_balde(ev["quando"])
        if b in serie[s]:
            serie[s][b] += 1
        paginas[(s, pagina_da_visita(ev, titulos_blog))] += 1
        dispositivos[ev["device"] or "unknown"] += 1
        # origem só na página de entrada (1ª visita da pessoa naquele site no dia): a navegação
        # interna das ferramentas não manda referrer e viraria "direto"
        chave_entrada = (ev["ip"], s, ev["quando"].date()) if ev["ip"] else None
        if chave_entrada and chave_entrada in entradas_vistas:
            continue
        if chave_entrada:
            entradas_vistas.add(chave_entrada)
        origem = origem_da_visita(ev, parceiros)
        if origem != INTERNO:
            origens[origem] += 1

    def variacao(atual, antes):
        if not antes:
            return None                          # sem base para comparar (não é "+100%")
        return round((atual - antes) / antes * 100)

    cartoes = []
    for s in SITES:
        k = s["chave"]
        v_atual = sum(cont[k][t] for t in VISITAS)
        v_antes = sum(cont_ant[k][t] for t in VISITAS)
        cartoes.append({
            "chave": k, "nome": s["nome"], "endereco": s["endereco"],
            "visitas": v_atual, "visitas_ant": v_antes, "variacao": variacao(v_atual, v_antes),
            "unicos": unicos.get(k, 0), "unicos_ant": unicos_ant.get(k, 0),
            "acoes": [{"rotulo": r, "valor": sum(cont[k][e] for e in evs),
                       "anterior": sum(cont_ant[k][e] for e in evs)} for r, evs in ACOES[k]],
            "serie": list(serie[k].values()),
        })

    # ------------------------------------------------ ferramentas por página (no banco; slugs estranhos em "Outras")
    ferr = defaultdict(Counter)
    for slug, tipo, n in (_base(inicio, fim).filter(TrafficEvent.produto == "ferramentas")
                          .with_entities(TrafficEvent.slug, TrafficEvent.event_type, func.count(TrafficEvent.id))
                          .group_by(TrafficEvent.slug, TrafficEvent.event_type)):
        ferr[slug if slug in PAGINAS_FERRAMENTAS else "_outras"][tipo] += n
    ferramentas = []
    for slug in list(PAGINAS_FERRAMENTAS) + ["_outras"]:
        c = ferr.get(slug)
        if not c:
            continue
        ferramentas.append({
            "pagina": PAGINAS_FERRAMENTAS.get(slug, "Outras páginas"), "visitas": sum(c[t] for t in VISITAS),
            "artes": c["gerou_arte"], "pdfs": c["gerou_pdf"],
            "saidas": c["baixou"] + c["compartilhou"] + c["baixou_pdf"] + c["compartilhou_pdf"],
            "pro": c["clicou_pro"] + c["checkout_start"], "codigos": c["resgatou_codigo"],
        })

    # ------------------------------------------------ vendas aprovadas no período (sem a "venda simulada" do admin)
    pro_ids = {o for (o,) in db.session.query(FerrPedidoPro.order_id)}
    vendas = {"pro": 0, "desktop": 0, "receita": 0.0}
    for o in (Order.query.filter(Order.status == "approved", Order.approved_at >= _naive(inicio),
                                 Order.approved_at <= _naive(fim),
                                 or_(Order.mp_payment_id.is_(None), Order.mp_payment_id != "SIMULADO"))):
        vendas["pro" if o.id in pro_ids else "desktop"] += 1
        vendas["receita"] += float(o.valor or 0)

    # ------------------------------------------------ agora: últimos 30 minutos, independente do período
    corte = agora_utc - timedelta(minutes=30)
    recentes = [_evento(l) for l in _base(corte, agora_utc).with_entities(*COLUNAS).limit(5000)]
    agora_paginas = Counter((nomes[ev["site"]], pagina_da_visita(ev, titulos_blog))
                            for ev in recentes if ev["tipo"] in VISITAS)

    ultimos = [_evento(l) for l in _base(inicio, fim).with_entities(*COLUNAS)
               .order_by(TrafficEvent.created_at.desc()).limit(40)]

    total_origens = sum(origens.values()) or 1
    total_disp = sum(dispositivos.values()) or 1
    return {
        "periodo": periodo, "periodo_nome": PERIODOS[periodo], "por_hora": por_hora,
        "comparacao": "ontem até esta hora" if por_hora else f"{PERIODOS[periodo]} anteriores até a mesma hora",
        "rotulos": rotulos, "cartoes": cartoes, "vendas": vendas, "ferramentas": ferramentas,
        "top_paginas": [{"site": nomes[s], "pagina": p, "visitas": n} for (s, p), n in paginas.most_common(20)],
        "top_origens": [{"origem": o, "visitas": n, "pct": round(n / total_origens * 100)} for o, n in origens.most_common(15)],
        "agora": {"pessoas": len({ev["ip"] for ev in recentes if ev["ip"]}),
                  "paginas": [{"site": s, "pagina": p, "visitas": n} for (s, p), n in agora_paginas.most_common(8)]},
        "dispositivos": {"celular": round(dispositivos["mobile"] / total_disp * 100),
                         "computador": round(dispositivos["desktop"] / total_disp * 100)},
        "ultimos": [{
            "hora": ev["quando"].strftime("%d/%m %H:%M") if ev["quando"] else "—", "site": nomes[ev["site"]],
            "pagina": pagina_da_visita(ev, titulos_blog), "evento": EVENTOS_LABEL.get(ev["tipo"], ev["tipo"]),
            "dispositivo": {"mobile": "Celular", "desktop": "Computador"}.get(ev["device"], "—"),
            "origem": origem_da_visita(ev, parceiros) if ev["tipo"] in VISITAS else "",
        } for ev in ultimos],
        "robos": robos, "atualizado_em": agora_utc.astimezone(BRT).strftime("%H:%M:%S"), "truncado": truncado,
    }
