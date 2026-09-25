"""PDF do orçamento e da ordem de serviço das ferramentas online.

Baseado no layout dos PDFs da Gestão (services/gestao), generalizado para
qualquer profissão. Nada é guardado: o PDF é montado em memória e devolvido.

Grátis: sem identidade do prestador, com a marca RD OS (selo diagonal claro e
rodapé). Pro: logotipo, nome, CNPJ e contato da empresa, cores da marca, sem
marca d'água. A decisão Pro/grátis é do servidor (quem chama passa `marca`
só quando o usuário tem o Pro).
"""
from datetime import timedelta
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from .gestao.formatos import data_br, data_extenso, moeda, numero_br

SITE = "rdos.rdsolucoes.eco.br"
NAVY = colors.HexColor("#0c2340")
LARANJA = colors.HexColor("#c2410c")
CINZA_LINHA = colors.HexColor("#dde4ec")
CINZA_FUNDO = colors.HexColor("#f3f6f9")
CINZA_TEXTO = colors.HexColor("#4b5563")
LARGURA = A4[0] - 3.6 * cm
MAX_PAGINAS = 12


class DocumentoLongo(Exception):
    """Mais de MAX_PAGINAS páginas: a rota responde 413 em vez de prender o servidor."""


def limpo(valor, limite=None):
    """Texto cru (sem escape) só com o que a fonte padrão desenha (Windows-1252)."""
    s = str(valor or "").strip().replace("\u2212", "-")
    if limite:
        s = s[:limite]
    return s.encode("cp1252", "ignore").decode("cp1252")


def txt(valor, limite=None):
    """Texto do usuário vira texto puro dentro do mini-HTML do ReportLab
    (sem isso, um "<" digitado quebra o PDF ou vira marcação)."""
    s = str(valor or "").strip()
    if limite:
        s = s[:limite]
    # A fonte padrão do PDF (Helvetica) só desenha o conjunto Windows-1252:
    # emoji e símbolos fora dele virariam quadradinhos, então saem do PDF.
    s = s.replace("−", "-")
    s = s.encode("cp1252", "ignore").decode("cp1252")
    return escape(s).replace("\n", "<br/>")


def _estilo(nome, **kw):
    base = {"fontName": "Helvetica", "fontSize": 9.5, "leading": 13, "textColor": colors.black}
    base.update(kw)
    return ParagraphStyle(nome, **base)


def _cores(marca):
    if marca is None:
        return NAVY, LARANJA
    try:
        return colors.HexColor(marca.cor_primaria or "#0c2340"), colors.HexColor(marca.cor_destaque or "#f97316")
    except Exception:
        return NAVY, LARANJA


def _logo(marca, lado):
    if marca is None or not marca.logo:
        return None
    try:
        from PIL import Image as PILImage
        with PILImage.open(BytesIO(marca.logo)) as im:
            w, h = im.size
        escala = min(lado / w, lado / h)
        img = Image(BytesIO(marca.logo), width=w * escala, height=h * escala)
        img.hAlign = "LEFT"
        return img
    except Exception:
        return None


def _identidade(marca):
    """Linhas do bloco da empresa (Pro)."""
    linhas = []
    if marca.empresa:
        linhas.append(f'<font size="11"><b>{txt(marca.empresa, 80)}</b></font>')
    if marca.cnpj:
        linhas.append(f"CNPJ/CPF: {txt(marca.cnpj, 30)}")
    contato = "  ·  ".join(x for x in [txt(marca.telefone, 30), txt(marca.email, 120)] if x)
    if contato:
        linhas.append(contato)
    if marca.site:
        linhas.append(txt(str(marca.site).split("?")[0], 120))       # sem o "?igsh=..." de link colado
    if marca.endereco:
        linhas.append(txt(marca.endereco, 200))
    return "<br/>".join(linhas)


def _cabecalho(titulo, numero, data_emissao, marca, cor):
    s_tit = _estilo("tit", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=cor, alignment=TA_RIGHT)
    s_num = _estilo("num", fontName="Helvetica-Bold", fontSize=12, leading=16, alignment=TA_RIGHT)
    s_dir = _estilo("dir", fontSize=9, leading=12.5, alignment=TA_RIGHT, textColor=CINZA_TEXTO)
    s_esq = _estilo("esq", fontSize=8.5, leading=12, textColor=CINZA_TEXTO)
    lado_direito = [Paragraph(titulo, s_tit)]
    if numero:
        lado_direito.append(Paragraph(f"Nº {txt(numero, 20)}", s_num))
    lado_direito.append(Paragraph(f"Emitido em {data_extenso(data_emissao)}", s_dir))
    if marca is not None:
        logo = _logo(marca, 2.6 * cm)
        ident = Paragraph(_identidade(marca), s_esq)
        esquerda = Table([[logo, ident]] if logo else [[ident]],
                         colWidths=[2.9 * cm, 6.3 * cm] if logo else [9.2 * cm])
        esquerda.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                      ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    else:
        esquerda = Paragraph(f'<font color="#0c2340"><b>RD OS</b></font><br/>'
                             f'<font size="7.5">Gerado grátis em {SITE}</font>', s_esq)
    cab = Table([[esquerda, lado_direito]], colWidths=[9.4 * cm, LARGURA - 9.4 * cm])
    cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return [cab, Spacer(1, 0.25 * cm), HRFlowable(width="100%", thickness=2, color=cor), Spacer(1, 0.35 * cm)]


def _secao(titulo, cor):
    # keepWithNext: o título nunca fica sozinho no pé da página
    return Paragraph(titulo, _estilo("sec", fontName="Helvetica-Bold", fontSize=10.5, textColor=cor, spaceAfter=4,
                                     keepWithNext=1))


def _pares(pares, colunas=2):
    """[('Nome', 'João'), ...] → tabela rótulo: valor em 2 colunas, pulando vazios."""
    s = _estilo("par", fontSize=9.5)
    celulas = [Paragraph(f"<b>{r}:</b> {v}", s) for r, v in pares if v]
    if not celulas:
        return None
    linhas = [celulas[i:i + colunas] for i in range(0, len(celulas), colunas)]
    if len(linhas[-1]) < colunas:
        linhas[-1] += [""] * (colunas - len(linhas[-1]))
    t = Table(linhas, colWidths=[LARGURA / colunas] * colunas)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 1),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def _tabela_itens(itens, cor, com_valores=True, desconto=0.0, mostrar_total=True):
    th = _estilo("th", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white)
    th_r = _estilo("thr", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, alignment=TA_RIGHT)
    td = _estilo("td", fontSize=9)
    td_r = _estilo("tdr", fontSize=9, alignment=TA_RIGHT)
    if com_valores:
        dados = [[Paragraph("Descrição", th), Paragraph("Qtd.", th_r), Paragraph("Valor unit.", th_r), Paragraph("Total", th_r)]]
        larguras = [LARGURA - 7.6 * cm, 1.8 * cm, 2.9 * cm, 2.9 * cm]
    else:
        dados = [[Paragraph("Descrição", th), Paragraph("Qtd.", th_r)]]
        larguras = [LARGURA - 2.2 * cm, 2.2 * cm]
    subtotal = 0.0
    for it in itens:
        qtd, unit = it["quantidade"], it["valor"]
        total = qtd * unit
        subtotal += total
        qtd_txt = numero_br(qtd, 3).rstrip("0").rstrip(",") if qtd != int(qtd) else str(int(qtd))
        linha = [Paragraph(txt(it["descricao"], 300), td), Paragraph(qtd_txt, td_r)]
        if com_valores:
            linha += [Paragraph(moeda(unit), td_r), Paragraph(moeda(total), td_r)]
        dados.append(linha)
    n_itens = len(dados)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), cor),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if n_itens > 1:
        estilo.append(("LINEBELOW", (0, 1), (-1, n_itens - 1), 0.4, CINZA_LINHA))
    total_geral = subtotal
    if com_valores and mostrar_total:
        s_l = _estilo("tl", fontSize=9.5, alignment=TA_RIGHT)
        s_lb = _estilo("tlb", fontName="Helvetica-Bold", fontSize=11, alignment=TA_RIGHT, textColor=cor)
        desconto = min(desconto, subtotal)
        if desconto > 0:
            total_geral = subtotal - desconto
            dados.append(["", "", Paragraph("Subtotal", s_l), Paragraph(moeda(subtotal), s_l)])
            dados.append(["", "", Paragraph("Desconto", s_l), Paragraph("- " + moeda(desconto), s_l)])
        dados.append(["", "", Paragraph("<b>Total</b>", s_lb), Paragraph(f"<b>{moeda(total_geral)}</b>", s_lb)])
        estilo.append(("LINEABOVE", (2, n_itens), (-1, n_itens), 1, cor))
    t = Table(dados, colWidths=larguras, repeatRows=1, splitInRow=1)
    t.setStyle(TableStyle(estilo))
    return t, total_geral


def _rodape_e_selo(marca, identificacao=""):
    """Desenha em toda página: rodapé (com o nº do documento) e, no grátis, o selo diagonal."""
    def desenhar(canv, doc):
        if doc.page > MAX_PAGINAS:
            raise DocumentoLongo()
        canv.saveState()
        largura, altura = A4
        if marca is None:
            canv.setFillColor(colors.HexColor("#0c2340"))
            canv.setFillAlpha(0.06)
            canv.setFont("Helvetica-Bold", 54)
            canv.translate(largura / 2, altura / 2)
            canv.rotate(35)
            canv.drawCentredString(0, 0, "RD OS · versão grátis")
            canv.rotate(-35)
            canv.translate(-largura / 2, -altura / 2)
            canv.setFillAlpha(1)
            texto = f"Gerado grátis com RD OS · {SITE} · com o Pro, sai com a sua logomarca"
        else:
            site = limpo(marca.site, 120).split("?")[0]
            partes = [limpo(marca.empresa, 80), f"CNPJ/CPF {limpo(marca.cnpj, 30)}" if marca.cnpj else "", site]
            texto = "  |  ".join(p for p in partes if p)
        pagina = f"{identificacao} · pág. {doc.page}" if identificacao else f"pág. {doc.page}"
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(CINZA_TEXTO)
        esquerda, direita = 1.8 * cm, largura - 1.8 * cm
        espaco = direita - esquerda - stringWidth(pagina, "Helvetica", 7.5) - 12
        while texto and stringWidth(texto, "Helvetica", 7.5) > espaco:     # nunca invade o "pág. N"
            texto = texto[:-2].rstrip() + "…"
        canv.drawString(esquerda, 0.8 * cm, texto)
        canv.drawRightString(direita, 0.8 * cm, pagina)
        canv.restoreState()
    return desenhar


def _doc(buffer, titulo):
    return SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                             topMargin=1.4 * cm, bottomMargin=1.6 * cm, title=titulo, author="RD OS")


def _assinaturas(esquerda, direita):
    """Duas linhas de assinatura separadas (coluna do meio vazia)."""
    s = _estilo("ass", fontSize=9, alignment=TA_CENTER, textColor=CINZA_TEXTO)
    meio = 1.6 * cm
    lado = (LARGURA - meio) / 2
    t = Table([["", "", ""], [Paragraph(esquerda, s), "", Paragraph(direita, s)]],
              colWidths=[lado, meio, lado], rowHeights=[1.3 * cm, None])
    t.setStyle(TableStyle([("LINEABOVE", (0, 1), (0, 1), 0.6, colors.black),
                           ("LINEABOVE", (2, 1), (2, 1), 0.6, colors.black)]))
    return t


# ---------------------------------------------------------------------- orçamento
def gerar_orcamento(d, marca=None):
    """d: dicionário já validado pela rota (ver routes/ferramentas._dados_documento)."""
    cor, destaque = _cores(marca)
    buffer = BytesIO()
    doc = _doc(buffer, f"Orçamento {d['numero']}".strip())
    s = _estilo("corpo", fontSize=9.5, leading=13.5)
    story = _cabecalho("ORÇAMENTO", d["numero"], d["data"], marca, cor)

    pares = _pares([("Nome", txt(d["cliente_nome"], 120)), ("Telefone", txt(d["cliente_telefone"], 40)),
                    ("CPF/CNPJ", txt(d["cliente_documento"], 30)), ("Endereço", txt(d["cliente_endereco"], 200))])
    if pares:
        story.append(_secao("Cliente", cor))
        story.append(pares)
        story.append(Spacer(1, 0.3 * cm))

    if d["descricao"]:
        story.append(_secao("Serviço", cor))
        story.append(Paragraph(txt(d["descricao"], 2000), s))
        story.append(Spacer(1, 0.3 * cm))

    if d["itens"]:
        tabela, total = _tabela_itens(d["itens"], cor, com_valores=True, desconto=d["desconto"])
        story.append(tabela)
        story.append(Spacer(1, 0.45 * cm))

    validade = f"{data_br(d['data'] + timedelta(days=d['validade_dias']))} ({d['validade_dias']} dias)" if d["validade_dias"] else ""
    condicoes = _pares([("Validade do orçamento", validade), ("Prazo de execução", txt(d["prazo"], 120)),
                        ("Forma de pagamento", txt(d["pagamento"], 200)), ("Garantia", txt(d["garantia"], 120))], colunas=1)
    if condicoes:
        story.append(_secao("Condições", cor))
        story.append(condicoes)
        story.append(Spacer(1, 0.2 * cm))

    if d["observacoes"]:
        story.append(_secao("Observações", cor))
        story.append(Paragraph(txt(d["observacoes"], 2000), s))
        story.append(Spacer(1, 0.3 * cm))

    if marca is not None and (marca.condicoes or "").strip():
        caixa = Table([[Paragraph(txt(marca.condicoes, 3000), _estilo("cond", fontSize=8.5, leading=12))]],
                      colWidths=[LARGURA], splitInRow=1)
        caixa.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CINZA_FUNDO),
                                   ("BOX", (0, 0), (-1, -1), 0.5, cor),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                   ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story.append(caixa)
        story.append(Spacer(1, 0.3 * cm))

    story.append(Spacer(1, 0.6 * cm))
    story.append(KeepTogether([_assinaturas("Aprovação do cliente", "Data: ____/____/________")]))
    ident = f"Orçamento {limpo(d['numero'], 20)}".strip()
    doc.build(story, onFirstPage=_rodape_e_selo(marca, ident), onLaterPages=_rodape_e_selo(marca, ident))
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------- ordem de serviço
def gerar_ordem_servico(d, marca=None):
    cor, destaque = _cores(marca)
    buffer = BytesIO()
    doc = _doc(buffer, f"Ordem de Serviço {d['numero']}".strip())
    s = _estilo("corpo", fontSize=9.5, leading=13.5)
    story = _cabecalho("ORDEM DE SERVIÇO", d["numero"], d["data"], marca, cor)

    pares = _pares([("Nome", txt(d["cliente_nome"], 120)), ("Telefone", txt(d["cliente_telefone"], 40)),
                    ("Responsável no local", txt(d["responsavel"], 120)), ("CPF/CNPJ", txt(d["cliente_documento"], 30)),
                    ("Endereço", txt(d["cliente_endereco"], 200))])
    if pares:
        story.append(_secao("Cliente", cor))
        story.append(pares)
        story.append(Spacer(1, 0.3 * cm))

    blocos = [("Equipamento / local", d["equipamento"]), ("Serviço solicitado / defeito relatado", d["solicitado"]),
              ("Serviço executado", d["executado"])]
    for titulo, conteudo in blocos:
        if conteudo:
            story.append(_secao(titulo, cor))
            story.append(Paragraph(txt(conteudo, 3000), s))
            story.append(Spacer(1, 0.3 * cm))

    if d["itens"]:
        story.append(_secao("Peças e materiais", cor))
        com_valores = any(it["valor"] for it in d["itens"])
        tabela, _ = _tabela_itens(d["itens"], cor, com_valores=com_valores, mostrar_total=False)
        story.append(tabela)
        story.append(Spacer(1, 0.35 * cm))

    valores = []
    if d["mao_de_obra"]:
        valores.append(("Mão de obra", moeda(d["mao_de_obra"])))
    pecas = sum(it["quantidade"] * it["valor"] for it in d["itens"])
    if pecas:
        valores.append(("Peças e materiais", moeda(pecas)))
    if valores:
        valores.append(("<b>Total</b>", f"<b>{moeda(d['mao_de_obra'] + pecas)}</b>"))
        s_r = _estilo("vr", fontSize=9.5, alignment=TA_RIGHT)
        t = Table([[Paragraph(r, s_r), Paragraph(v, s_r)] for r, v in valores],
                  colWidths=[LARGURA - 3.4 * cm, 3.4 * cm])
        t.setStyle(TableStyle([("LINEABOVE", (0, len(valores) - 1), (-1, len(valores) - 1), 1, cor),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
        story.append(t)
        story.append(Spacer(1, 0.35 * cm))

    info = _pares([("Entrada", txt(d["entrada"], 40)), ("Saída", txt(d["saida"], 40)),
                   ("Técnico responsável", txt(d["tecnico"], 120)), ("Garantia", txt(d["garantia"], 120))])
    if info:
        story.append(info)
        story.append(Spacer(1, 0.2 * cm))

    if d["observacoes"]:
        story.append(_secao("Observações", cor))
        story.append(Paragraph(txt(d["observacoes"], 2000), s))
        story.append(Spacer(1, 0.3 * cm))

    if d["linhas_manuais"]:
        story.append(_secao("Anotações", cor))
        for _ in range(5):
            story.append(Spacer(1, 0.55 * cm))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#bbbbbb")))
        story.append(Spacer(1, 0.3 * cm))

    story.append(Spacer(1, 0.6 * cm))
    story.append(KeepTogether([_assinaturas("Técnico responsável", "Cliente / responsável")]))
    ident = f"OS {limpo(d['numero'], 20)}".strip()
    doc.build(story, onFirstPage=_rodape_e_selo(marca, ident), onLaterPages=_rodape_e_selo(marca, ident))
    buffer.seek(0)
    return buffer
