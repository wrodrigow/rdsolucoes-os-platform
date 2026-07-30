"""PDF da Ordem de Serviço — portado de Orcamentos/pdf_os.py (app desktop).
Formulário A4 com alturas de linha fixas em cm; o CNPJ é desenhado direto no
canvas (rodapé nativo) pra não consumir espaço da tabela principal.
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .formatos import data_br
from .pdf_orcamento import logo_flowable

CINZA_BG = colors.HexColor("#D8D8D8")
BORDA = colors.HexColor("#444444")
PRETO = colors.black

MARGIN_LR = 1.0 * cm
MARGIN_TB = 0.9 * cm
CONTENT_H = 29.7 * cm - 2 * MARGIN_TB

C0, C1, C2 = 12.7 * cm, 3.15 * cm, 3.15 * cm

HR = 1.50 * cm   # cabeçalho
H0 = 0.85 * cm   # título
H1 = 1.00 * cm   # empresa / telefone
H2 = 1.00 * cm   # endereço / responsável
H3 = 0.60 * cm   # label "Serviço Executado"
H5 = 0.75 * cm   # data / entrada / saída
H6 = 4.20 * cm   # assinaturas

FIXED = HR + H0 + H1 + H2 + H3 + H5 + H6
# Buffer de 0.5cm: garante que a tabela não extrapola a página com pequenas
# variações de rendering do ReportLab.
H4 = CONTENT_H - FIXED - 0.5 * cm


def _p(texto, size=9.5, align=TA_LEFT, bold=False, color=PRETO):
    font = "Helvetica-Bold" if bold else "Helvetica"
    return Paragraph(texto, ParagraphStyle(
        "_", fontSize=size, fontName=font, alignment=align,
        leading=size * 1.5, textColor=color))


def _mixed(label, valor="", size=9):
    return _p(f"<b>{label}</b>{valor}", size=size)


def gerar_pdf_os(empresa, ordem, orcamento, itens):
    """Devolve um BytesIO posicionado no início, pronto pro send_file."""
    nome = empresa.nome or ""
    cnpj = (empresa.cnpj or "").strip()
    rodape = f"{nome}  |  CNPJ: {cnpj}" if cnpj else nome

    def _footer(canv, doc):
        canv.saveState()
        canv.setFont("Helvetica", 7.5)
        canv.setFillGray(0.35)
        canv.drawCentredString(A4[0] / 2, MARGIN_TB * 0.38, rodape)
        canv.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN_LR, rightMargin=MARGIN_LR,
        topMargin=MARGIN_TB, bottomMargin=MARGIN_TB,
        title=f"Ordem de Serviço {ordem.numero}",
    )

    # ── Cabeçalho (logo + dados da empresa) ──────────────────────────────────
    emp_txt = (f"<b>{nome}</b>  |  {empresa.telefone or ''}  |  "
               f"E-mail: {empresa.email or ''}  |  Site: {empresa.site or ''}")

    hdr = Table([[logo_flowable(empresa, 1.25 * cm, 1.25 * cm), _p(emp_txt, size=7.5)]],
                colWidths=[1.5 * cm, C0 + C1 - 1.5 * cm], rowHeights=[HR - 4])
    hdr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))

    # ── Área de serviço executado ────────────────────────────────────────────
    serv = []
    if (orcamento.descricao_servico or "").strip():
        serv.append(_p(f"<b>Ref.:</b> {orcamento.descricao_servico.strip()}", size=8.5))
        serv.append(Spacer(1, 0.05 * cm))
    for item in itens:
        qtd = float(item.quantidade or 0)
        qtd_txt = f"{int(qtd)}" if qtd == int(qtd) else f"{qtd:g}"
        serv.append(_p(f"• {item.descricao or ''} — {qtd_txt} unid", size=8.5))
    if itens:
        serv.append(Spacer(1, 0.15 * cm))
    if (ordem.observacoes or "").strip():
        serv.append(_p(f"<b>Obs.:</b> {ordem.observacoes.strip()}", size=8.5))
        serv.append(Spacer(1, 0.10 * cm))

    # Linhas em branco pra anotação manual em campo — 20 cabem dentro de H4.
    s_lin = ParagraphStyle("lin", fontSize=8, fontName="Helvetica",
                           leading=17, textColor=colors.HexColor("#BBBBBB"))
    for _ in range(20):
        serv.append(Paragraph("_" * 100, s_lin))

    s_tit = ParagraphStyle("tit", fontSize=13, fontName="Helvetica-Bold",
                           alignment=TA_CENTER, leading=18)
    s_sec = ParagraphStyle("sec", fontSize=10, fontName="Helvetica-Bold", leading=14)

    linhas = [
        [hdr, "", _p(f"<b>OS N°  {ordem.numero}</b>", size=12, align=TA_RIGHT)],
        [Paragraph("ORDEM DE SERVIÇO", s_tit), "", ""],
        [_mixed("Empresa/Condomínio: ", orcamento.cliente_nome or ""),
         _mixed("Telefone: ", orcamento.cliente_telefone or ""), ""],
        [_mixed("Endereço: ", orcamento.cliente_endereco or ""),
         _mixed("Responsável: "), ""],
        [Paragraph("Serviço Executado", s_sec), "", ""],
        [serv, "", ""],
        [_mixed("Data: ", data_br(ordem.data_emissao) if ordem.data_emissao else "___/___/______"),
         _p("<b>Entrada:</b>", size=9), _p("<b>Saída:</b>", size=9)],
        [
            [_p("<b>Equipe:</b>", size=9),
             Spacer(1, 0.3 * cm),
             _p("Ass: ___________________________________________", size=9),
             Spacer(1, 0.25 * cm),
             _p("Ass: ___________________________________________", size=9)],
            [_p("<b>Cliente/Responsável</b>", size=9),
             Spacer(1, 0.7 * cm),
             _p("Ass: _______________________", size=9)],
            "",
        ],
    ]

    main = Table(linhas, colWidths=[C0, C1, C2],
                 rowHeights=[HR, H0, H1, H2, H3, H4, H5, H6])
    main.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.0, BORDA),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDA),

        ("SPAN", (0, 0), (1, 0)),
        ("SPAN", (0, 1), (2, 1)),
        ("SPAN", (1, 2), (2, 2)),
        ("SPAN", (1, 3), (2, 3)),
        ("SPAN", (0, 4), (2, 4)),
        ("SPAN", (0, 5), (2, 5)),
        ("SPAN", (1, 7), (2, 7)),

        ("BACKGROUND", (0, 0), (2, 0), CINZA_BG),
        ("BACKGROUND", (0, 1), (2, 1), CINZA_BG),
        ("BACKGROUND", (0, 4), (2, 4), CINZA_BG),

        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("VALIGN", (0, 0), (2, 0), "MIDDLE"),
        ("VALIGN", (0, 1), (2, 1), "MIDDLE"),
        ("VALIGN", (0, 4), (2, 4), "MIDDLE"),

        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        # Cabeçalho com padding menor pro logo não esticar a linha HR
        ("TOPPADDING", (0, 0), (2, 0), 1),
        ("BOTTOMPADDING", (0, 0), (2, 0), 1),
        ("LEFTPADDING", (0, 1), (2, 1), 0),
        ("RIGHTPADDING", (0, 1), (2, 1), 0),
    ]))

    doc.build([main], onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer
