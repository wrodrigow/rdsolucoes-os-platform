"""Parser de extratos bancários (Banco Inter e C6 Bank) — portado de
Orcamentos/pages/extrato_parser.py.

Diferenças da versão desktop:
  - aceita file-like object (o upload do navegador, direto da memória) além de
    caminho — o pdfplumber suporta os dois, então nada toca o disco. Isso é o
    que faz funcionar no Render, cujo disco é efêmero;
  - a senha do extrato C6 sai do código-fonte e vem de config/env.

Retorna sempre (transacoes, saldo_final):
  transacoes  : lista de dicts {data, descricao, tipo, valor, categoria}
  saldo_final : float do saldo lido no PDF, ou None se não encontrado
"""
import re

import pdfplumber

MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3,
    "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}

# Auto-categorização por palavra-chave (mais específico primeiro)
_REGRAS = [
    (["PEDAGIO", "AUTOPISTA", "AUTOBAN", "RODOANEL", "AUTO BAN", "EIXO SP",
      "C6TAG", "CONCESSIONARIA SPMAR", "P6 RIBEIRAO", "TAG RODOVIA",
      "TAG ADICIONAL", "MENSALIDADE C6TAG", "SEGURO TAG", "BARUERI BRA",
      "ITAQUAQUECETUBA", "CONCESSIONARIA", "SPMAR"], "Pedágio"),
    (["FROGPAY*AUTO", "POSTODGT", "AUTO POSTO", "POSTO "], "Combustível"),
    (["SIMPLES NACIONAL", "DARF", "TRIBUTOS FEDERAIS", "CONVENIO SIMPLES",
      "PGTO FAT CARTAO C6", "PGTO FAT CARTAO", "IOF CHEQUE", "JUROS CHEQUE",
      "INSS"], "Imposto"),
    (["FACEBOOK", "INSTAGRAM", "GOOGLE BRASIL", "PAGHIPER", "PAGARME",
      "PAGARME PAGAMENTOS"], "Marketing"),
    (["PORTO SEGURO CARTOES", "SUPERMED", "PLANO DE SAUDE",
      "SEGURO TAG RODOVIA"], "Seguro"),
    (["RESTAURANTE", "LANCHONETE", " BAR ", "CANTINHO", "ADEGA", "TABACARIA",
      "BURGUER", "SUSHI", "PIZZARIA", "VITAL LANCHONETE",
      "VITAL RESTAURANTE"], "Alimentação"),
    (["CIAFER", "QUEOPS", "ROCHA DEPOSITO", "PARAFUSOS", "ELASTOBOR",
      "FERREIRAS", "ACEDO", "MATERIAIS PARA CO", "HRDE"], "Insumos"),
    (["CONTABILIDADE GARCIA", "V C GARCIA", "CONTABILIDADE",
      "GARCIA SERVICOS", "GARCIA"], "Serviços"),
    (["CLARO", "GOOGLE BRASIL INTERNET", "FLOW HORTOLANDIA"], "Serviços"),
]

# Prefixos de tipo no extrato C6 → direção do lançamento
_C6_TIPOS = [
    ("Débito de Cartão", "Saída"),
    ("Outros gastos", "Saída"),
    ("Entrada PIX", "Entrada"),
    ("Saída PIX", "Saída"),
    ("Pagamento", "Saída"),
    ("Entradas", "Entrada"),
    ("Saída", "Saída"),
    ("Entrada", "Entrada"),
]

_INTER_RUIDO = [
    "SAC:", "Ouvidoria:", "Deficiência", "Fale com a gente",
    "CPF/CNPJ:", "Solicitado em:", "Saldo total",
    "Saldo disponível", "Saldo bloqueado",
    "(bloqueado", "Valor Saldo por transação",
]

_C6_RUIDO = [
    "Extrato exportado", "RD SOLUCOES", "Agência:", "Período",
    "Saldo do dia", "Cheque Especial", "Data Data",
    "Tipo Descrição", "lançamento contábil",
    "Sem lançamentos", "Extrato",
]


def _parse_money(texto):
    limpo = re.sub(r"[R$\s]", "", str(texto)).strip().replace(".", "").replace(",", ".")
    try:
        return abs(float(limpo))
    except ValueError:
        return 0.0


def auto_categorize(descricao):
    desc = descricao.upper()
    for palavras, categoria in _REGRAS:
        if any(p in desc for p in palavras):
            return categoria
    return ""


def parse_inter(origem):
    """Extrato do Banco Inter. `origem` = caminho ou file-like object.
    O saldo final vem do último "Saldo do dia:" encontrado no PDF."""
    transacoes = []
    data_atual = None
    saldo_final = None

    with pdfplumber.open(origem) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            for linha in texto.split("\n"):
                linha = linha.strip()
                if not linha:
                    continue

                # 1. Cabeçalho de dia: "1 de Janeiro de 2025 Saldo do dia: R$ ..."
                cab = re.match(r"^(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", linha, re.IGNORECASE)
                if cab:
                    dia = int(cab.group(1))
                    mes_txt = (cab.group(2).lower()
                               .replace("ã", "a").replace("â", "a")
                               .replace("ê", "e").replace("ç", "c")
                               .replace("é", "e").replace("ó", "o"))
                    ano = int(cab.group(3))
                    mes = MESES_PT.get(mes_txt, 0)
                    if mes > 0:
                        data_atual = f"{ano}-{mes:02d}-{dia:02d}"
                    saldo = re.search(r"Saldo\s+do\s+dia:\s*R\$\s*([\d.]+,\d{2})", linha, re.IGNORECASE)
                    if saldo:
                        saldo_final = _parse_money(saldo.group(1))
                    continue

                if any(r in linha for r in _INTER_RUIDO):
                    continue
                if not data_atual:
                    continue

                # 2. Transação: precisa de pelo menos 2 valores (valor + saldo corrente)
                valores = re.findall(r"-?R\$\s*[\d.]+,\d{2}", linha)
                if len(valores) < 2:
                    continue

                bruto = valores[-2]  # penúltimo = valor da transação
                valor = _parse_money(bruto)
                if valor <= 0:
                    continue

                tipo = "Saída" if bruto.strip().startswith("-") else "Entrada"

                pos_saldo = linha.rfind(valores[-1])
                pos_valor = linha.rfind(valores[-2], 0, pos_saldo)
                desc = linha[:pos_valor].strip() if pos_valor > 0 else linha[:pos_saldo].strip()

                desc = re.sub(
                    r"^(Compra no debito|Pix recebido|Pix enviado"
                    r"|Boleto de cobranca recebido|Pagamento efetuado"
                    r"|Pagamento de Convenio|Pagamento):?\s*",
                    "", desc, flags=re.IGNORECASE).strip().strip('"').strip()
                desc = re.sub(r"^Cp\s*:\s*[\d-]*-?\s*", "", desc, flags=re.IGNORECASE)
                desc = re.sub(r"^No estabelecimento\s+", "", desc, flags=re.IGNORECASE)
                desc = re.sub(r"\s+[A-Z\s]+(?:BRA|ARG|USA)\s*$", "", desc).strip()

                if not desc or re.match(r"^[\d/]+$", desc):
                    desc = f"Boleto {desc}".strip()

                # Fallback: se não achou cabeçalho com saldo, usa o saldo corrente
                if saldo_final is None and not valores[-1].strip().startswith("-"):
                    saldo_final = _parse_money(valores[-1])

                desc = " ".join(desc.split())
                transacoes.append({
                    "data": data_atual,
                    "descricao": desc[:200],
                    "tipo": tipo,
                    "valor": valor,
                    "categoria": auto_categorize(desc),
                })

    return transacoes, saldo_final


def parse_c6(origem, password=None):
    """Extrato do C6 Bank (PDF protegido por senha). `origem` = caminho ou
    file-like object; `password` vem da configuração da aplicação."""
    transacoes = []
    ano_atual = None
    mes_atual = None
    saldo_final = None

    with pdfplumber.open(origem, password=password) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            for linha in texto.split("\n"):
                linha = linha.strip()
                if not linha:
                    continue

                # 1. Cabeçalho de mês: "Janeiro 2025 ( 01/01/2025 - 31/01/2025 ) ..."
                cab = re.match(r"^(\w+)\s+(\d{4})\s*\(", linha, re.IGNORECASE)
                if cab:
                    periodo = re.search(r"\(\s*(\d{2})/(\d{2})/(\d{4})", linha)
                    if periodo:
                        ano_atual = int(periodo.group(3))
                        mes_atual = int(periodo.group(2))
                    else:
                        ano_atual = int(cab.group(2))
                        mes_txt = (cab.group(1).lower()
                                   .replace("ã", "a").replace("ç", "c")
                                   .replace("é", "e").replace("ê", "e")
                                   .replace("ó", "o").replace("ô", "o"))
                        mes_atual = MESES_PT.get(mes_txt, mes_atual or 1)
                    continue

                # Saldo do dia é lido antes do filtro de ruído (o último vale)
                if "Saldo do dia" in linha:
                    saldo = re.search(r"R\$\s*([\d.]+,\d{2})", linha)
                    if saldo:
                        saldo_final = _parse_money(saldo.group(1))
                    continue

                if any(r in linha for r in _C6_RUIDO):
                    continue
                if ano_atual is None:
                    continue

                # 2. Transação: "DD/MM DD/MM Tipo Descrição Valor"
                tx = re.match(r"^(\d{2})/(\d{2})\s+\d{2}/\d{2}\s+(.+)", linha)
                if not tx:
                    continue

                dia = int(tx.group(1))
                mes = int(tx.group(2))
                resto = tx.group(3).strip()

                # Vira o ano quando o extrato cruza dezembro/janeiro
                ano = ano_atual
                if mes_atual and mes != mes_atual:
                    diff = mes - mes_atual
                    if diff > 6:
                        ano = ano_atual - 1
                    elif diff < -6:
                        ano = ano_atual + 1

                valor_match = re.search(r"(-?R\$\s*[\d.]+,\d{2})\s*$", resto)
                if not valor_match:
                    continue

                bruto = valor_match.group(1)
                valor = _parse_money(bruto)
                if valor <= 0:
                    continue

                tipo = "Saída" if bruto.strip().startswith("-") else "Entrada"
                desc = resto[:valor_match.start()].strip()
                for prefixo, direcao in _C6_TIPOS:
                    if desc.startswith(prefixo):
                        tipo = direcao
                        desc = desc[len(prefixo):].strip()
                        break

                desc = re.sub(
                    r"^(Pix recebido de|Pix enviado para|Pix recebido|Pix enviado)\s*",
                    "", desc, flags=re.IGNORECASE).strip()
                if not desc:
                    desc = resto[:valor_match.start()].strip()

                desc = " ".join(desc.split())
                transacoes.append({
                    "data": f"{ano}-{mes:02d}-{dia:02d}",
                    "descricao": desc[:200],
                    "tipo": tipo,
                    "valor": valor,
                    "categoria": auto_categorize(desc),
                })

    return transacoes, saldo_final


def chave_dedupe(descricao):
    """Chave de deduplicação: maiúsculas, espaços colapsados, 60 caracteres —
    mesma regra do app desktop, pra reconhecer o que já foi importado antes."""
    return " ".join(str(descricao or "").strip().upper().split())[:60]
