"""Conversão entre o que o usuário digita/vê (padrão brasileiro) e os tipos
do banco (Decimal, date). Centralizado aqui porque todas as telas da Gestão
recebem valores em R$ 1.234,56 e datas em dd/mm/aaaa ou ISO."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MESES = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def parse_decimal(raw, default="0"):
    """'1.234,56' | '1234,56' | '1234.56' | '1.234' → Decimal.

    Regra para o caso ambíguo (ponto sem vírgula): se o último grupo tem
    exatamente 3 dígitos é separador de milhar ('1.234' → 1234), senão é
    decimal ('1.5' → 1.5).
    """
    if raw is None:
        return Decimal(default)
    txt = str(raw).strip().replace("R$", "").replace(" ", "").replace("\xa0", "")
    if not txt:
        return Decimal(default)

    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif "." in txt:
        ultimo = txt.rsplit(".", 1)[-1]
        if len(ultimo) == 3 and txt.count(".") >= 1:
            txt = txt.replace(".", "")

    try:
        return Decimal(txt).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def parse_data(raw):
    """'2026-07-29' (input type=date) ou '29/07/2026' → date. Vazio → None."""
    if not raw:
        return None
    txt = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(txt[:10], fmt).date()
        except ValueError:
            continue
    return None


def moeda(valor):
    """Decimal/float → 'R$ 1.234,56'."""
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        v = 0.0
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def numero_br(valor, decimais=2):
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        v = 0.0
    return f"{v:,.{decimais}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def data_br(d):
    """date → '29/07/2026'. None → '---'."""
    if not d:
        return "---"
    if isinstance(d, str):
        d = parse_data(d)
        if not d:
            return "---"
    return d.strftime("%d/%m/%Y")


def data_extenso(d):
    """date → '29 de Julho de 2026' (usado no PDF do orçamento)."""
    if not d:
        return ""
    if isinstance(d, str):
        d = parse_data(d)
        if not d:
            return ""
    return f"{d.day} de {MESES[d.month]} de {d.year}"


def quantidade_txt(valor):
    """1 → '1 unid'; 2.5 → '2,5 unid' (formato do PDF do app desktop)."""
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        v = 0.0
    if v == int(v):
        return f"{int(v)} unid"
    return f"{numero_br(v, 3).rstrip('0').rstrip(',')} unid"


def hoje():
    return date.today()
