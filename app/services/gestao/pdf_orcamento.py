"""PDF do Orçamento — portado de Orcamentos/pdf_gen.py (app desktop),
mantendo o mesmo layout aprovado. Diferenças da versão desktop:
  - escreve num BytesIO (pra devolver via send_file) em vez de num caminho;
  - recebe os models SQLAlchemy em vez de dicts do sqlite3;
  - o logo vem do banco (ErpEmpresa.logo_blob) com fallback pro estático.
"""
import os
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from .formatos import data_extenso, data_br, moeda, quantidade_txt

AZUL = colors.HexColor("#1a5fa8")
CINZA_LINHA = colors.HexColor("#dde4ec")
CINZA_COND = colors.HexColor("#f0f4f8")

CONDICOES = [
    "✔  O reparo é realizado no endereço do cliente, sem necessidade de deslocamento para outro local.",
    "✔  O contentor deve estar <b>vazio e lavado</b> para que o reparo seja executado com qualidade e segurança.",
    "✔  É necessária uma tomada de energia elétrica disponível a <b>pelo menos 30 metros</b> do local de reparo, fornecida pelo condomínio.",
    "✔  Garantir <b>acesso de veículo próximo ao local</b> do reparo, em razão da quantidade de ferramentas e equipamentos utilizados.",
]


def logo_flowable(empresa, largura, altura):
    """Logo do banco (bytes) ou o padrão do projeto. Nunca levanta erro —
    se a imagem estiver corrompida, o PDF sai sem logo em vez de falhar."""
    fonte = None
    if empresa is not None and getattr(empresa, "logo_blob", None):
        fonte = BytesIO(empresa.logo_blob)
    else:
        padrao = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "static", "img", "logo.png",
        )
        if os.path.exists(padrao):
            fonte = padrao
    if fonte is None:
        return Paragraph("", ParagraphStyle("vazio"))
    try:
        img = Image(fonte, width=largura, height=altura)
        img.hAlign = "LEFT"
        return img
    except Exception:
        return Paragraph("", ParagraphStyle("vazio"))


def gerar_pdf_orcamento(empresa, orcamento, itens):
    """Devolve um BytesIO posicionado no início, pronto pro send_file."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"Orçamento {orcamento.numero}",
    )
    story = []

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    empresa_info = Paragraph(
        f"""<para align="right">
        <font size="18" color="#1a5fa8"><b>Orçamento</b></font>
        <font size="18" color="#1a5fa8"><b>  N&#176; {orcamento.numero}</b></font><br/>
        <font size="9"><b>{empresa.nome or ''}</b></font><br/>
        <font size="8">{empresa.email or ''}</font><br/>
        <font size="8">{empresa.site or ''}</font><br/>
        <font size="8">{empresa.telefone or ''}</font>
        </para>""",
        ParagraphStyle("emp", leading=13),
    )

    header = Table([[logo_flowable(empresa, 2.6 * cm, 2.6 * cm), empresa_info]],
                   colWidths=[3.2 * cm, 13.6 * cm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(header)
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=CINZA_LINHA))
    story.append(Spacer(1, 0.3 * cm))

    # ── Data de emissão / situação ───────────────────────────────────────────
    s_valor = ParagraphStyle("valor", fontSize=9, fontName="Helvetica")
    info = Table([[
        Paragraph(f"<b>Data Emissão:</b> {data_extenso(orcamento.data_emissao)}", s_valor),
        Paragraph(f"<b>Situação do Orçamento:</b> {orcamento.situacao or ''}", s_valor),
    ]], colWidths=[8.4 * cm, 8.4 * cm])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(info)
    story.append(Spacer(1, 0.35 * cm))

    if (orcamento.descricao_servico or "").strip():
        story.append(Paragraph(orcamento.descricao_servico.strip(),
                               ParagraphStyle("desc", fontSize=10, leading=13)))
        story.append(Spacer(1, 0.3 * cm))

    # ── Dados do cliente (snapshot gravado no orçamento) ─────────────────────
    story.append(Paragraph("Dados do Cliente", ParagraphStyle(
        "secao", fontSize=10, fontName="Helvetica-Bold", spaceAfter=4)))
    story.append(Table([[
        Paragraph(f"<b>Nome:</b> {orcamento.cliente_nome or ''}", s_valor),
        Paragraph(f"<b>Telefone:</b> {orcamento.cliente_telefone or ''}", s_valor),
    ]], colWidths=[8.4 * cm, 8.4 * cm]))
    story.append(Paragraph(f"<b>Endereço:</b> {orcamento.cliente_endereco or ''}",
                           ParagraphStyle("end", fontSize=9, spaceBefore=4)))
    story.append(Spacer(1, 0.4 * cm))

    # ── Itens ────────────────────────────────────────────────────────────────
    th = ParagraphStyle("th", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white)
    th_r = ParagraphStyle("thr", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_RIGHT)
    td = ParagraphStyle("td", fontSize=9, fontName="Helvetica")
    td_r = ParagraphStyle("tdr", fontSize=9, fontName="Helvetica", alignment=TA_RIGHT)

    dados = [[
        Paragraph("Descrição", th),
        Paragraph("Valor Unitário", th_r),
        Paragraph("Quantidade", th_r),
        Paragraph("Total", th_r),
    ]]

    total_geral = 0.0
    for item in itens:
        qtd = float(item.quantidade or 0)
        unit = float(item.valor_unitario or 0)
        total = qtd * unit
        total_geral += total
        dados.append([
            Paragraph(item.descricao or "", td),
            Paragraph(moeda(unit), td_r),
            Paragraph(quantidade_txt(qtd), td_r),
            Paragraph(moeda(total), td_r),
        ])

    linha_total = len(dados)
    dados.append([
        "", "",
        Paragraph("Total Geral", ParagraphStyle("totl", fontSize=9.5, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph(moeda(total_geral), ParagraphStyle("totv", fontSize=9.5, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
    ])

    tabela = Table(dados, colWidths=[8.0 * cm, 3.2 * cm, 3.0 * cm, 2.6 * cm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, AZUL),
        ("LINEBELOW", (0, 1), (-1, linha_total - 1), 0.4, CINZA_LINHA),
        ("LINEABOVE", (0, linha_total), (-1, linha_total), 1, AZUL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 0.5 * cm))

    # ── Outras informações ───────────────────────────────────────────────────
    story.append(Paragraph("Outras Informações", ParagraphStyle(
        "secao2", fontSize=10, fontName="Helvetica-Bold", spaceAfter=6)))

    linhas = []
    if orcamento.validade:
        linhas.append(f"<b>Orçamento válido até:</b> {data_br(orcamento.validade)}")
    if orcamento.garantia:
        linhas.append(f"<b>Garantia até:</b> {data_br(orcamento.garantia)}")
    if orcamento.forma_pagamento:
        linhas.append(f"<b>Forma de Pagamento:</b> {orcamento.forma_pagamento}")
    for linha in linhas:
        story.append(Paragraph(linha, ParagraphStyle("outra", fontSize=9.5, spaceAfter=4)))

    if (orcamento.observacoes or "").strip():
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(orcamento.observacoes.strip(),
                               ParagraphStyle("obs", fontSize=9, leading=12)))

    # ── Condições de atendimento ─────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    s_cond = ParagraphStyle("cond", fontSize=8.5, fontName="Helvetica", leading=13, leftIndent=4)
    itens_cond = [[Paragraph("Condições de Atendimento", ParagraphStyle(
        "condTitulo", fontSize=9.5, fontName="Helvetica-Bold", textColor=AZUL, spaceAfter=4))]]
    itens_cond += [[Paragraph(c, s_cond)] for c in CONDICOES]

    cond = Table(itens_cond, colWidths=[17.6 * cm])
    cond.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CINZA_COND),
        ("BOX", (0, 0), (-1, -1), 0.5, AZUL),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, AZUL),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(cond)

    doc.build(story)
    buffer.seek(0)
    return buffer
