"""Ferramentas online do RD OS: antes e depois, orçamento e ordem de serviço.

A arte de antes e depois é montada no navegador (static/ferramentas/antes-depois.js).
O orçamento e a OS são preenchidos no navegador (static/ferramentas/documentos.js) e o
PDF é montado aqui, em memória, sem guardar nada (services/ferramentas_pdf.py) — assim
a regra do Pro (logotipo, dados da empresa, sem marca d'água) é decidida pelo servidor.
"""
import os
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import (Blueprint, Response, abort, current_app, flash, jsonify, make_response,
                   redirect, render_template, request, send_file, session, url_for)
from flask_login import current_user, login_required, login_user

from ..extensions import csrf, db, limiter
from ..models.ferramentas import FerrListaEspera, FerrMarca, FerrPedidoPro
from ..models.order import Order
from ..models.site_config import SiteConfig
from ..services import ferramentas_service as fs
from ..services.ferramentas_textos import DOCS, IDIOMAS, META_IDIOMA, textos_para

bp = Blueprint("ferramentas", __name__)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,180}\.[A-Za-z]{2,24}$")
NOME_PROIBIDO = re.compile(r"[<>\"`\\{}]|[\x00-\x1f]")   # nome vai para e-mails e para o painel admin
MARCA_MAX_BYTES = 5 * 1024 * 1024       # corpo inteiro do formulário da marca (logo ≤ 4 MB + campos)


# ---------------------------------------------------------------------- apoio
_VERSOES = {}


def versao_estatico(nome):
    """?v= dos arquivos da ferramenta: muda sozinho quando o arquivo muda."""
    if nome not in _VERSOES or current_app.debug:
        caminho = os.path.join(current_app.static_folder, "ferramentas", nome)
        try:
            _VERSOES[nome] = int(os.path.getmtime(caminho))
        except OSError:
            _VERSOES[nome] = 0
    return _VERSOES[nome]


@bp.context_processor
def _contexto_ferramentas():
    # padrões das páginas em português (Pro, retorno, minha marca); as páginas
    # do gerador passam o próprio idioma e estes valores são ignorados
    return {
        "versao_estatico": versao_estatico,
        "tem_pro_atual": fs.tem_pro(current_user),
        "t": textos_para("pt", fs.preco_pro_formatado()),
        "meta_idioma": META_IDIOMA["pt"],
        "idioma": "pt",
        "alternativas": _alternativas(),
        "abas_ferramentas": [
            ("antes-e-depois", "Antes e depois", url_for("ferramentas.antes_depois_pt")),
            ("orcamento", "Orçamento", url_for("ferramentas.orcamento")),
            ("ordem-de-servico", "Ordem de serviço", url_for("ferramentas.ordem_servico")),
        ],
        "aba_atual": None,
        "admin_ferramentas": bool(getattr(current_user, "is_admin", False)),
        "admin_testando_pro": fs.admin_testando_pro(),
    }


def _url_absoluta(endpoint, **valores):
    """URL canônica com o domínio de produção (BASE_URL), não o host da requisição."""
    return current_app.config["BASE_URL"].rstrip("/") + url_for(endpoint, **valores)


def _alternativas():
    return [
        {"idioma": i, "hreflang": META_IDIOMA[i]["hreflang"], "nome": META_IDIOMA[i]["nome"],
         "url": _url_absoluta(META_IDIOMA[i]["endpoint"]), "caminho": url_for(META_IDIOMA[i]["endpoint"])}
        for i in IDIOMAS
    ]


def _registrar(tipo, slug, detalhe=None, order_id=None):
    """Grava a visita/evento no mesmo painel de tráfego dos outros produtos.
    Visitas do próprio admin não entram."""
    if getattr(current_user, "is_admin", False):
        return
    try:
        from ..models.traffic_event import TrafficEvent
        ref = urlparse(request.referrer or "").hostname
        if ref and ref not in (request.host or ""):
            detalhe = f"{detalhe or ''}:ref:{ref}".lstrip(":")
        TrafficEvent.registrar(tipo, request, order_id=order_id, produto="ferramentas", slug=slug, detalhe=detalhe)
    except Exception as e:                      # rastreio nunca derruba a página
        current_app.logger.warning(f"Rastreio das ferramentas falhou: {e}")


def _json_ld(idioma, t, canonical, preco):
    """WebApplication + FAQPage. A oferta do Pro só entra onde ele é vendido.

    Sem aggregateRating de propósito: o Google só mostra resultado rico de app
    com avaliações reais. Nunca inventar nota ou avaliação aqui."""
    ofertas = [{"@type": "Offer", "name": t["planos_col_gratis"], "price": "0",
                "priceCurrency": "BRL" if idioma == "pt" else "USD"}]
    if idioma == "pt":
        ofertas.append({"@type": "Offer", "name": "Pro — pagamento único", "price": f"{preco:.2f}",
                        "priceCurrency": "BRL", "url": _url_absoluta("ferramentas.pro")})
    app_ld = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": {"pt": "RD OS — Gerador de Antes e Depois", "es": "RD OS — Creador de Antes y Después",
                 "en": "RD OS — Before & After Photo Maker"}[idioma],
        "url": canonical,
        "description": t["description"],
        "inLanguage": META_IDIOMA[idioma]["hreflang"],
        "applicationCategory": "DesignApplication",
        "operatingSystem": {"pt": "Android, iOS, Windows, macOS (no navegador)",
                            "es": "Android, iOS, Windows, macOS (en el navegador)",
                            "en": "Android, iOS, Windows, macOS (in the browser)"}[idioma],
        "browserRequirements": "Requires JavaScript and a modern browser",
        "isAccessibleForFree": True,
        "offers": ofertas,
        "image": _url_absoluta("static", filename=f"ferramentas/og-antes-depois-{idioma}.jpg"),
        "publisher": {"@type": "Organization", "name": "RD Soluções", "url": "https://rdsolucoes.eco.br/"},
    }
    faq_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "inLanguage": META_IDIOMA[idioma]["hreflang"],
        "mainEntity": [
            {"@type": "Question", "name": p, "acceptedAnswer": {"@type": "Answer", "text": r}}
            for p, r in t["faq"]
        ],
    }
    return [app_ld, faq_ld]


def _marca_para_js():
    """Kit de marca do usuário Pro no formato que o antes-depois.js espera."""
    m = fs.marca_do_usuario(current_user)
    if not m:
        return None
    return m.como_dict(logo_url=_url_logo(m))


def _url_logo(marca):
    """?v= muda por usuário e por troca: o navegador guarda o logo em cache por
    muito tempo, e duas contas no mesmo aparelho não podem ver o logo uma da outra."""
    return url_for("ferramentas.logo", v=f"{marca.user_id[:8]}-{marca.logo_versao or 0}")


def _sem_cache(resp):
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


def _pagamentos_ativos():
    return SiteConfig.get("mp_ativo", "1") == "1"


# ---------------------------------------------------------------------- gerador de antes e depois
def _pagina_antes_depois(idioma):
    t = textos_para(idioma, fs.preco_pro_formatado())
    pro = fs.tem_pro(current_user)
    marca = _marca_para_js() if pro else None
    _registrar("lp_view", "antes-e-depois", idioma)

    cfg = {
        "idioma": idioma,
        "pro": pro,
        "marca": marca,
        "textos": t["js"],
        "rdLogo": url_for("static", filename="ferramentas/rd-icone.png", v=versao_estatico("rd-icone.png")),
        "exemplo": {
            "antes": url_for("static", filename="ferramentas/exemplo-antes.jpg", v=versao_estatico("exemplo-antes.jpg")),
            "depois": url_for("static", filename="ferramentas/exemplo-depois.jpg", v=versao_estatico("exemplo-depois.jpg")),
        },
        "rastreio": {"url": url_for("tracking.evento"), "ativo": not getattr(current_user, "is_admin", False)},
        # quem ainda não é Pro e toca em "Vídeo" vai para a venda (pt) ou para a lista de espera (es/en)
        "urlPro": url_for("ferramentas.pro") if idioma == "pt" else "#pro",
    }
    resp = make_response(render_template(
        "ferramentas/antes_depois.html",
        t=t, idioma=idioma, meta_idioma=META_IDIOMA[idioma], cfg=cfg, pro=pro, marca=marca,
        alternativas=_alternativas(),
        canonical=_url_absoluta(META_IDIOMA[idioma]["endpoint"]),
        og_image=_url_absoluta("static", filename=f"ferramentas/og-antes-depois-{idioma}.jpg"),
        preco=fs.preco_pro(),
        json_ld=_json_ld(idioma, t, _url_absoluta(META_IDIOMA[idioma]["endpoint"]), fs.preco_pro()),
        lista_ok=request.args.get("lista") == "ok",
        lista_erro=request.args.get("lista") == "erro",
        aba_atual="antes-e-depois" if idioma == "pt" else None,
    ))
    # a página muda conforme quem está logado (Pro, marca): não pode ir para cache compartilhado
    return _sem_cache(resp) if current_user.is_authenticated else resp


@bp.route("/antes-e-depois")
def antes_depois_pt():
    return _pagina_antes_depois("pt")


@bp.route("/es/antes-y-despues")
def antes_depois_es():
    return _pagina_antes_depois("es")


@bp.route("/en/before-and-after")
def antes_depois_en():
    return _pagina_antes_depois("en")


@bp.route("/ferramentas/")
def inicio_barra():
    return redirect(url_for("ferramentas.inicio"), code=301)


@bp.route("/ferramentas")
def inicio():
    """Página única com as três ferramentas."""
    _registrar("lp_view", "ferramentas", "pt")
    d = DOCS["hub"]
    resp = make_response(render_template(
        "ferramentas/hub.html", d=d, preco_fmt=fs.preco_pro_formatado(),
        canonical=_url_absoluta("ferramentas.inicio"),
        og_image=_url_absoluta("static", filename="ferramentas/og-antes-depois-pt.jpg"),
        json_ld=_json_ld_doc(d, _url_absoluta("ferramentas.inicio"), "Ferramentas para prestador de serviço"),
        aba_atual=None,
    ))
    return _sem_cache(resp) if current_user.is_authenticated else resp


# ---------------------------------------------------------------------- orçamento e ordem de serviço
LIMITE_ITENS = 60
LIMITE_LINHAS = 40            # por campo de texto: quebras de linha viram páginas no PDF
PADRAO_NUMERO = re.compile(r"[0-9][0-9.,]*")


def _json_ld_doc(d, url, nome):
    ofertas = [{"@type": "Offer", "name": "Grátis", "price": "0", "priceCurrency": "BRL"},
               {"@type": "Offer", "name": "Pro — pagamento único", "price": f"{fs.preco_pro():.2f}",
                "priceCurrency": "BRL", "url": _url_absoluta("ferramentas.pro")}]
    return [
        {"@context": "https://schema.org", "@type": "WebApplication", "name": f"RD OS — {nome}", "url": url,
         "description": d["description"], "inLanguage": "pt-BR", "applicationCategory": "BusinessApplication",
         "operatingSystem": "Android, iOS, Windows, macOS (no navegador)", "isAccessibleForFree": True,
         "offers": ofertas, "publisher": {"@type": "Organization", "name": "RD Soluções", "url": "https://rdsolucoes.eco.br/"}},
        {"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": "pt-BR",
         "mainEntity": [{"@type": "Question", "name": p, "acceptedAnswer": {"@type": "Answer", "text": r}}
                        for p, r in d["faq"]]},
    ]


def _marca_doc():
    """Dados da empresa para a prévia do documento (só Pro)."""
    m = fs.marca_do_usuario(current_user)
    if not m:
        return {}
    return {"empresa": m.empresa or "", "cnpj": m.cnpj or "", "telefone": m.telefone or "", "email": m.email or "",
            "site": m.site or "", "endereco": m.endereco or "", "condicoes": m.condicoes or "",
            "corPrimaria": m.cor_primaria or "#0c2340", "corDestaque": m.cor_destaque or "#f97316",
            "logo": _url_logo(m) if m.logo else None}


def _pagina_documento(tipo):
    d = DOCS[tipo]
    pro = fs.tem_pro(current_user)
    _registrar("lp_view", tipo, "pt")
    endpoint = "ferramentas.orcamento" if tipo == "orcamento" else "ferramentas.ordem_servico"
    cfg = {
        "tipo": tipo,
        "pro": pro,
        "marca": _marca_doc() if pro else None,
        "urlPdf": url_for("ferramentas.documento_pdf", tipo=tipo),
        "urlToken": url_for("ferramentas.token_csrf"),
        "urlPro": url_for("ferramentas.pro"),
        "rastreio": {"url": url_for("tracking.evento"), "ativo": not getattr(current_user, "is_admin", False)},
    }
    resp = make_response(render_template(
        "ferramentas/documento.html", d=d, tipo=tipo, cfg=cfg, pro=pro, preco_fmt=fs.preco_pro_formatado(),
        canonical=_url_absoluta(endpoint),
        og_image=_url_absoluta("static", filename="ferramentas/og-antes-depois-pt.jpg"),
        json_ld=_json_ld_doc(d, _url_absoluta(endpoint), d["nome"]),
        aba_atual=tipo, alternativas=None,
    ))
    return _sem_cache(resp) if current_user.is_authenticated else resp


@bp.route("/orcamento")
def orcamento():
    return _pagina_documento("orcamento")


@bp.route("/ordem-de-servico")
def ordem_servico():
    return _pagina_documento("ordem-de-servico")


def _texto(dados, chave, limite, linhas=LIMITE_LINHAS):
    valor = dados.get(chave)
    s = valor.strip() if isinstance(valor, str) else ""
    s = re.sub(r"\r\n?", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    partes = s.split("\n")
    if len(partes) > linhas:                    # o que passar do limite vira uma linha só
        s = "\n".join(partes[:linhas - 1] + [" ".join(p for p in partes[linhas - 1:] if p.strip())])
    return s[:limite]


def numero_br(valor):
    """Mesma regra do documentos.js: pega o primeiro número ("3 m²" → 3,
    "R$ 1.234,56" → 1234.56, "50 reais" → 50). Vazio ou inválido → None."""
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        v = float(valor)
    else:
        m = PADRAO_NUMERO.search(str(valor).replace("\u00a0", " "))
        if not m:
            return None
        s = m.group(0)
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        elif re.search(r"\.\d{3}$", s):
            s = s.replace(".", "")
        inicio = re.match(r"\d+(?:\.\d+)?", s)          # como o parseFloat do JS: "1.5.6" → 1.5
        if not inicio:
            return None
        v = float(inicio.group(0))
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def _numero(valor, minimo=0.0, maximo=1e8, padrao=0.0, casas=2):
    """Arredonda "meio para cima", igual ao documentos.js (0,125 → 0,13)."""
    from decimal import ROUND_HALF_UP, Decimal
    v = numero_br(valor)
    if v is None:
        v = padrao
    v = max(minimo, min(maximo, v))
    return float(Decimal(repr(v)).quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP))


def _dados_documento(tipo, dados):
    """Valida o que veio do formulário. Tudo com limite de tamanho: o texto vai
    para dentro do PDF e o servidor é pequeno."""
    from ..services.gestao.formatos import parse_data
    from datetime import date
    itens = []
    brutos = dados.get("itens")
    for bruto in (brutos if isinstance(brutos, list) else [])[:LIMITE_ITENS]:
        if not isinstance(bruto, dict):
            continue
        descricao = _texto(bruto, "descricao", 300, linhas=6)
        if not descricao:
            continue
        qtd_bruta = bruto.get("quantidade")
        vazia = qtd_bruta is None or (isinstance(qtd_bruta, str) and not qtd_bruta.strip())
        itens.append({"descricao": descricao,
                      # vazia = 1 (igual à tela); zero fica zero
                      "quantidade": 1.0 if vazia else _numero(qtd_bruta, 0.0, 1e6, 0.0, casas=3),
                      "valor": _numero(bruto.get("valor"))})
    data = parse_data(dados.get("data")) if isinstance(dados.get("data"), str) else None
    if data is None or not (2000 <= data.year <= 2100):
        data = date.today()
    comum = {
        "numero": _texto(dados, "numero", 20, linhas=1),
        "data": data,
        "cliente_nome": _texto(dados, "cliente_nome", 120),
        "cliente_telefone": _texto(dados, "cliente_telefone", 40),
        "cliente_documento": _texto(dados, "cliente_documento", 30),
        "cliente_endereco": _texto(dados, "cliente_endereco", 200),
        "garantia": _texto(dados, "garantia", 120),
        "observacoes": _texto(dados, "observacoes", 2000),
        "itens": itens,
    }
    if tipo == "orcamento":
        validade = int(_numero(dados.get("validade_dias"), 0, 365, 0, casas=0))
        comum.update({
            "descricao": _texto(dados, "descricao", 2000),
            "desconto": _numero(dados.get("desconto")),
            "validade_dias": max(0, min(365, validade)),
            "prazo": _texto(dados, "prazo", 120),
            "pagamento": _texto(dados, "pagamento", 200),
        })
    else:
        comum.update({
            "responsavel": _texto(dados, "responsavel", 120),
            "equipamento": _texto(dados, "equipamento", 3000),
            "solicitado": _texto(dados, "solicitado", 3000),
            "executado": _texto(dados, "executado", 3000),
            "mao_de_obra": _numero(dados.get("mao_de_obra")),
            "entrada": _texto(dados, "entrada", 40),
            "saida": _texto(dados, "saida", 40),
            "tecnico": _texto(dados, "tecnico", 120),
            "linhas_manuais": bool(dados.get("linhas_manuais")),
        })
    return comum


@bp.route("/ferramentas/<tipo>/pdf", methods=["POST"])
@limiter.limit("60 per hour;10 per minute")
def documento_pdf(tipo):
    """Monta o PDF do orçamento ou da OS. O token CSRF vem no cabeçalho X-CSRFToken."""
    if tipo not in ("orcamento", "ordem-de-servico"):
        abort(404)
    if request.content_length is None or request.content_length > 200_000:
        return jsonify({"erro": "Documento grande demais."}), 413
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"erro": "Não recebi os dados do documento. Recarregue a página e tente de novo."}), 400

    from ..services.ferramentas_pdf import gerar_orcamento, gerar_ordem_servico
    pro = fs.tem_pro(current_user)
    marca = fs.marca_do_usuario(current_user) if pro else None
    if pro and marca is None:
        from ..models.ferramentas import FerrMarca
        marca = FerrMarca(user_id=current_user.id)          # Pro sem marca salva: sem marca d'água, cabeçalho vazio
    d = _dados_documento(tipo, dados)
    from ..services.ferramentas_pdf import DocumentoLongo
    try:
        pdf = (gerar_orcamento if tipo == "orcamento" else gerar_ordem_servico)(d, marca)
    except DocumentoLongo:
        return jsonify({"erro": "O documento ficou longo demais (mais de 12 páginas). Divida em dois ou encurte os textos."}), 413
    except Exception as e:
        current_app.logger.error(f"PDF de {tipo} falhou: {e}")
        return jsonify({"erro": "Não consegui montar o PDF. Confira os campos e tente de novo."}), 500

    _registrar("gerou_pdf", tipo, "pro" if pro else "gratis")
    base_nome = "orcamento" if tipo == "orcamento" else "ordem-de-servico"
    numero = re.sub(r"[^0-9A-Za-z-]", "", d["numero"])[:20]
    resp = send_file(pdf, mimetype="application/pdf", as_attachment=False,
                     download_name=f"{base_nome}{'-' + numero if numero else ''}.pdf")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.route("/ferramentas/token")
@limiter.limit("60 per hour")
def token_csrf():
    """Token CSRF novo, pedido pelo documentos.js antes de gerar o PDF (a OS
    costuma ficar aberta durante todo o atendimento, e o token vence em 1 h)."""
    from flask_wtf.csrf import generate_csrf
    resp = jsonify({"token": generate_csrf()})
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------------- modo de teste do administrador
@bp.route("/ferramentas/admin/modo")
@login_required
def admin_modo():
    """Administrador alterna entre ver a versão grátis (padrão) e testar o Pro."""
    if not getattr(current_user, "is_admin", False):
        abort(404)
    if request.args.get("pro") == "1":
        session["ferr_admin_pro"] = True
    else:
        session.pop("ferr_admin_pro", None)
    from .auth import _next_seguro
    return redirect(_next_seguro(request.args.get("volta")) or url_for("ferramentas.inicio"))


# ---------------------------------------------------------------------- venda do Pro (só Brasil)
@bp.route("/ferramentas/pro")
def pro():
    _registrar("lp_view", "pro", "pt")
    resp = make_response(render_template(
        "ferramentas/pro.html",
        t=textos_para("pt", fs.preco_pro_formatado()),
        ja_tem=fs.tem_pro(current_user),
        preco_fmt=fs.preco_pro_formatado(),
        preco=fs.preco_pro(),
        pagamentos_ativos=_pagamentos_ativos(),
        alternativas=_alternativas(),
        canonical=_url_absoluta("ferramentas.pro"),
        og_image=_url_absoluta("static", filename="ferramentas/og-antes-depois-pt.jpg"),
    ))
    return _sem_cache(resp) if current_user.is_authenticated else resp


@bp.route("/ferramentas/pro/comprar", methods=["POST"])
@limiter.limit("15 per hour;5 per minute")
def comprar():
    """Checkout do Pro: pede só nome e e-mail (ou usa a conta logada) e manda
    para o Mercado Pago. A conta é criada na hora, com senha aleatória; a pessoa
    cria a senha dela ao voltar do pagamento ou pelo link do e-mail."""
    from ..models.user import User

    if not _pagamentos_ativos():
        flash("As vendas estão pausadas por alguns minutos. Tente de novo daqui a pouco.", "warning")
        return redirect(url_for("ferramentas.pro"))

    if current_user.is_authenticated:
        if fs.tem_pro(current_user):
            flash("Você já tem o Pro. É só configurar a sua marca.", "success")
            return redirect(url_for("ferramentas.minha_marca"))
        user = current_user._get_current_object()
    else:
        nome = (request.form.get("nome") or "").strip()[:120]
        email = (request.form.get("email") or "").strip().lower()[:180]
        telefone = (request.form.get("whatsapp") or "").strip()[:30]
        if len(nome) < 3 or NOME_PROIBIDO.search(nome):
            flash("Escreva o seu nome (só letras, números e pontuação comum).", "danger")
            return redirect(url_for("ferramentas.pro") + "#comprar")
        if not EMAIL_RE.match(email):
            flash("Escreva um e-mail válido: é nele que chega o seu acesso.", "danger")
            return redirect(url_for("ferramentas.pro") + "#comprar")

        user = User.query.filter_by(email=email).first()
        if user and fs.tem_pro(user):
            flash("Esse e-mail já tem o Pro. Entre com a sua senha.", "info")
            return redirect(url_for("auth.login", next=url_for("ferramentas.minha_marca")))
        if not user:
            user = User(nome=nome, email=email, telefone=telefone)
            user.set_senha(secrets.token_urlsafe(32))
            db.session.add(user)
            db.session.commit()
            # conta criada agora, neste navegador: ao voltar do pagamento aprovado
            # a pessoa pode criar a senha ali mesmo, sem esperar o e-mail
            session["ferr_conta_nova"] = user.id

    preco = fs.preco_pro()
    # Reaproveita o pedido pendente só se foi criado neste mesmo navegador e com o
    # mesmo preço (a pessoa voltou do Mercado Pago sem pagar). Pedido de outro
    # navegador nunca é reaproveitado: a sessão que o criou poderia depois criar a
    # senha da conta de quem pagou.
    order = None
    anterior = db.session.get(Order, session.get("ferr_pedido")) if session.get("ferr_pedido") else None
    if (anterior and anterior.user_id == user.id and anterior.status == "pending"
            and fs.eh_pedido_pro(anterior) and abs(float(anterior.valor) - preco) < 0.005):
        order = anterior
    if not order:
        order = Order(numero_pedido=Order.gerar_numero(), user_id=user.id,
                      produto_nome=fs.PRODUTO_PRO_NOME, valor=preco, status="pending")
        db.session.add(order)
        db.session.flush()
        db.session.add(FerrPedidoPro(order_id=order.id))
    db.session.commit()
    session["ferr_pedido"] = order.id

    try:
        from ..services.payment_service import criar_preferencia
        preference = criar_preferencia(
            order, user,
            item_id="rdos-ferramentas-pro",
            descricao="Acesso vitalício ao Pro do gerador de antes e depois — pagamento único",
            retorno="/ferramentas/pro",
            descritor="RD OS PRO",
            parcelas=1,
            # boleto custa mais de um terço de uma venda de R$ 10 e demora dias
            tipos_excluidos=("ticket", "atm"),
        )
        order.mp_preference_id = preference.get("id")
        db.session.commit()
        init_point = preference.get("init_point") or preference.get("sandbox_init_point")
        if not init_point:
            raise RuntimeError("init_point não retornado pelo Mercado Pago.")
    except Exception as e:
        current_app.logger.error(f"Erro ao criar preferência MP (Pro ferramentas): {e}")
        flash("Não consegui abrir o pagamento agora. Tente de novo em instantes.", "danger")
        return redirect(url_for("ferramentas.pro") + "#comprar")

    _registrar("checkout_start", "pro", "pt", order_id=order.id)
    return redirect(init_point)


def _mascarar_email(email):
    nome, _, dominio = (email or "").partition("@")
    return (nome[:1] + "•••@" + dominio) if dominio else ""


def _pode_criar_senha_aqui(order):
    """Criar a senha na página de retorno só vale para a conta criada neste mesmo
    navegador, no checkout deste pedido, que ainda não tem senha própria.
    reset_token vazio = a senha já foi criada (pelo link do e-mail ou aqui)."""
    return bool(
        order and order.status == "approved"
        and not current_user.is_authenticated
        and session.get("ferr_pedido") == order.id
        and session.get("ferr_conta_nova") == order.user_id
        and order.user and order.user.ultimo_login is None
        and order.user.reset_token
        and _dentro_da_validade(order.user.reset_token_exp)
    )


def _dentro_da_validade(exp):
    if exp is None:
        return False
    if exp.tzinfo is None:                   # o banco devolve sem fuso (UTC)
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > datetime.now(timezone.utc)


@bp.route("/ferramentas/pro/<situacao>")
@limiter.limit("30 per minute")
def retorno(situacao):
    """Volta do Mercado Pago (sucesso, pendente ou falha)."""
    if situacao not in ("sucesso", "pendente", "falha"):
        abort(404)
    order_id = request.args.get("external_reference") or session.get("ferr_pedido")
    order = db.session.get(Order, order_id) if order_id else None
    if order and not fs.eh_pedido_pro(order):
        order = None

    # Não espera o webhook: confere o pagamento direto no Mercado Pago. É idempotente
    # e usa o external_reference que vem do próprio Mercado Pago, não o da URL.
    payment_id = request.args.get("payment_id") or request.args.get("collection_id") or ""
    if order and order.status != "approved" and situacao != "falha" and payment_id.isdigit():
        try:
            from .payment import _processar_pagamento
            _processar_pagamento(payment_id)
            db.session.refresh(order)
        except Exception as e:
            current_app.logger.error(f"Conferência do pagamento {payment_id} no retorno falhou: {e}")

    aprovado = bool(order and order.status == "approved")
    if situacao == "sucesso" and aprovado:
        _registrar("checkout_success", "pro", "pt", order_id=order.id)
    elif situacao == "falha":
        _registrar("checkout_fail", "pro", "pt", order_id=order.id if order else None)

    resp = make_response(render_template(
        "ferramentas/pro_retorno.html",
        situacao=situacao, order=order, aprovado=aprovado,
        email_mascarado=_mascarar_email(order.user.email) if order and order.user else "",
        pode_criar_senha=_pode_criar_senha_aqui(order),
        e_dono=bool(order and current_user.is_authenticated and current_user.id == order.user_id),
        ja_tem_senha=bool(order and order.user and order.user.ultimo_login is not None),
    ))
    return _sem_cache(resp)


@bp.route("/ferramentas/pro/criar-senha", methods=["POST"])
@limiter.limit("10 per hour")
def criar_senha():
    order_id = session.get("ferr_pedido")
    order = db.session.get(Order, order_id) if order_id else None
    if not _pode_criar_senha_aqui(order):
        flash("Use o link que enviamos por e-mail para criar a sua senha.", "warning")
        return redirect(url_for("auth.login", next=url_for("ferramentas.minha_marca")))

    senha = request.form.get("senha", "")
    if len(senha) < 8:
        flash("A senha precisa ter pelo menos 8 caracteres.", "danger")
        return redirect(url_for("ferramentas.retorno", situacao="sucesso", external_reference=order.id))
    if senha != request.form.get("senha2", ""):
        flash("As duas senhas não são iguais.", "danger")
        return redirect(url_for("ferramentas.retorno", situacao="sucesso", external_reference=order.id))

    user = order.user
    user.set_senha(senha)
    user.reset_token = None
    user.reset_token_exp = None
    user.ultimo_login = datetime.now(timezone.utc)
    db.session.commit()
    session.pop("ferr_conta_nova", None)
    session.pop("ferr_pedido", None)
    login_user(user, remember=True)
    flash("Senha criada. Agora envie o seu logotipo e escolha as suas cores.", "success")
    return redirect(url_for("ferramentas.minha_marca"))


# ---------------------------------------------------------------------- marca do usuário Pro
@bp.route("/ferramentas/minha-marca", methods=["GET", "POST"])
@csrf.exempt          # validado à mão, depois de recusar corpo grande (ver abaixo)
@limiter.limit("30 per hour", methods=["POST"])
@login_required
def minha_marca():
    if not fs.tem_pro(current_user):
        flash("A marca própria faz parte do Pro.", "info")
        return redirect(url_for("ferramentas.pro"))

    marca = fs.marca_do_usuario(current_user)

    if request.method == "POST":
        # O limite geral do site é 500 MB (downloads do desktop). Aqui o corpo é
        # recusado antes de ser lido; só depois o token CSRF é conferido.
        if request.content_length is None or request.content_length > MARCA_MAX_BYTES:
            flash("O logotipo pode ter no máximo 4 MB.", "danger")
            return redirect(url_for("ferramentas.minha_marca"))
        from flask_wtf.csrf import ValidationError, validate_csrf
        try:
            validate_csrf(request.form.get("csrf_token"))
        except ValidationError:
            flash("A página ficou aberta por muito tempo. Tente salvar de novo.", "warning")
            return redirect(url_for("ferramentas.minha_marca"))

        if marca is None:
            marca = fs.marca_do_usuario(current_user, criar=True)
        marca.empresa = (request.form.get("empresa") or "").strip()[:80] or None
        marca.telefone = (request.form.get("telefone") or "").strip()[:30] or None
        marca.site = (request.form.get("site") or "").strip()[:120] or None
        marca.cnpj = (request.form.get("cnpj") or "").strip()[:30] or None
        marca.email = (request.form.get("email") or "").strip()[:120] or None
        marca.endereco = (request.form.get("endereco") or "").strip()[:200] or None
        marca.condicoes = (request.form.get("condicoes") or "").strip()[:3000] or None
        marca.cor_primaria = fs.cor_valida(request.form.get("cor_primaria"), marca.cor_primaria or "#0c2340")
        marca.cor_destaque = fs.cor_valida(request.form.get("cor_destaque"), marca.cor_destaque or "#f97316")

        arquivo = request.files.get("logo")
        if arquivo and arquivo.filename:
            try:
                marca.logo = fs.normalizar_logo(arquivo)
            except ValueError as e:
                db.session.commit()          # nome, contato e cores ficam salvos
                flash(f"{e} O nome, o contato e as cores foram salvos.", "danger")
                return redirect(url_for("ferramentas.minha_marca"))
            marca.logo_versao = (marca.logo_versao or 0) + 1
        elif request.form.get("remover_logo") == "1" and marca.logo:
            marca.logo = None
            marca.logo_versao = (marca.logo_versao or 0) + 1

        db.session.commit()
        flash("Marca salva. Ela já aparece nas suas artes.", "success")
        return redirect(url_for("ferramentas.minha_marca"))

    resp = make_response(render_template(
        "ferramentas/minha_marca.html",
        marca=marca,
        logo_url=_url_logo(marca) if marca and marca.logo else None,
        cor_primaria=(marca.cor_primaria if marca else None) or "#0c2340",
        cor_destaque=(marca.cor_destaque if marca else None) or "#f97316",
    ))
    return _sem_cache(resp)


@bp.route("/ferramentas/marca/logo.png")
@login_required
def logo():
    """Logo do próprio usuário logado (nunca de outra pessoa: não há id na URL)."""
    m = fs.marca_do_usuario(current_user)
    if not m or not m.logo:
        abort(404)
    resp = Response(m.logo, mimetype="image/png")
    # a URL muda a cada troca (?v=), então pode ficar em cache no navegador
    resp.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return resp


# ---------------------------------------------------------------------- sair, termos, erros, cache
@bp.route("/ferramentas/sair")
def sair():
    """Sai e volta ao gerador no mesmo idioma (o /auth/logout leva à página do desktop)."""
    from flask_login import logout_user
    idioma = request.args.get("idioma")
    logout_user()
    return redirect(url_for(META_IDIOMA.get(idioma, META_IDIOMA["pt"])["endpoint"]))


@bp.route("/ferramentas/termos")
def termos():
    return render_template("ferramentas/termos.html", preco_fmt=fs.preco_pro_formatado(),
                           canonical=_url_absoluta("ferramentas.termos"))


from flask_wtf.csrf import CSRFError  # noqa: E402


@bp.errorhandler(CSRFError)
def _csrf_vencido(e):
    """Página aberta por muito tempo (token vencido): volta ao formulário com um
    aviso, em vez da página crua "400 Bad Request" em inglês."""
    ep = request.endpoint or ""
    if ep == "ferramentas.documento_pdf":        # pedido do JavaScript: responde em JSON
        return jsonify({"erro": "A página ficou aberta por muito tempo. Recarregue a página e gere o PDF de novo "
                                "(o que você preencheu continua salvo)."}), 400
    if ep == "ferramentas.lista_espera":
        idioma = request.form.get("idioma") if request.form.get("idioma") in ("es", "en") else "en"
        return redirect(url_for(META_IDIOMA[idioma]["endpoint"]) + "?lista=erro#pro")
    flash("A página ficou aberta por muito tempo. Tente de novo.", "warning")
    if ep == "ferramentas.criar_senha":
        return redirect(url_for("ferramentas.retorno", situacao="sucesso"))
    if ep == "ferramentas.comprar":
        return redirect(url_for("ferramentas.pro") + "#comprar")
    return redirect(url_for("ferramentas.antes_depois_pt"))


@bp.after_app_request
def _cache_estaticos(resp):
    # arquivos da ferramenta pedidos com ?v= (muda quando o arquivo muda) podem
    # ficar em cache por um ano; sem isso o celular revalida tudo a cada visita
    if request.path.startswith("/static/ferramentas/") and request.args.get("v") and resp.status_code == 200:
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


# ---------------------------------------------------------------------- lista de espera (es/en)
@bp.route("/ferramentas/lista-espera", methods=["POST"])
@limiter.limit("10 per hour")
def lista_espera():
    idioma = request.form.get("idioma")
    if idioma not in ("es", "en"):
        idioma = "en"
    destino = url_for(META_IDIOMA[idioma]["endpoint"])
    email = (request.form.get("email") or "").strip().lower()[:180]
    if not EMAIL_RE.match(email):
        return redirect(destino + "?lista=erro#pro")
    if not FerrListaEspera.query.filter_by(email=email, idioma=idioma).first():
        db.session.add(FerrListaEspera(email=email, idioma=idioma))
        db.session.commit()
    _registrar("lista_espera", "antes-e-depois", idioma)
    return redirect(destino + "?lista=ok#pro")
