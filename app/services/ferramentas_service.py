"""Regras do plano Pro das ferramentas online."""
import io

from flask import current_app

from ..extensions import db
from ..models.ferramentas import FerrAcessoPro, FerrMarca, FerrPedidoPro
from ..models.site_config import SiteConfig

PRODUTO_PRO_NOME = "RD OS Ferramentas Pro — acesso vitalício"
LOGO_MAX_BYTES = 4 * 1024 * 1024      # arquivo enviado
LOGO_MAX_LADO = 600                   # px, depois de normalizado
LOGO_MAX_PIXELS = 16_000_000          # 16 Mpx: acima disso a imagem é recusada antes de decodificar


def preco_pro() -> float:
    return float(SiteConfig.get("ferr_pro_preco", "10.00"))


def preco_pro_formatado() -> str:
    """R$ 10 / R$ 12,90 — sem centavos quando o valor é redondo."""
    v = preco_pro()
    if abs(v - round(v)) < 0.005:
        return f"R$ {int(round(v))}"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def eh_pedido_pro(order) -> bool:
    return db.session.get(FerrPedidoPro, order.id) is not None


def tem_pro(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_admin", False):
        # Administrador vê a versão grátis, igual a qualquer visitante, e só
        # vê o Pro quando liga o modo de teste (evita achar que o grátis
        # "libera" recursos do Pro).
        return admin_testando_pro()
    return db.session.get(FerrAcessoPro, user.id) is not None


def admin_testando_pro() -> bool:
    from flask import has_request_context, session
    return bool(has_request_context() and session.get("ferr_admin_pro"))


def liberar_pro(order):
    """Libera o Pro para o dono do pedido. Idempotente: o Mercado Pago pode
    reenviar o mesmo aviso de pagamento várias vezes."""
    acesso = db.session.get(FerrAcessoPro, order.user_id)
    if acesso is None:
        acesso = FerrAcessoPro(user_id=order.user_id, order_id=order.id)
        db.session.add(acesso)
        db.session.commit()
    return acesso


def revogar_pro(order):
    """Tira o Pro liberado por este pedido (reembolso ou estorno). A marca
    salva fica guardada: se a pessoa comprar de novo, não precisa refazer."""
    acesso = db.session.get(FerrAcessoPro, order.user_id)
    if acesso is not None and acesso.order_id == order.id:
        db.session.delete(acesso)
        db.session.commit()
        return True
    return False


def marca_do_usuario(user, criar=False):
    marca = db.session.get(FerrMarca, user.id)
    if marca is None and criar:
        marca = FerrMarca(user_id=user.id)
        db.session.add(marca)
    return marca


def normalizar_logo(arquivo) -> bytes:
    """Recebe o upload do logo e devolve um PNG limpo, no máximo 600 px.

    Reabrir e regravar com o Pillow descarta metadados e qualquer conteúdo que
    não seja imagem; o PNG mantém a transparência de logos recortados.
    Levanta ValueError com mensagem para o usuário se o arquivo não servir.
    """
    from PIL import Image, UnidentifiedImageError

    dados = arquivo.read(LOGO_MAX_BYTES + 1)
    if not dados:
        raise ValueError("Escolha uma imagem para o logotipo.")
    if len(dados) > LOGO_MAX_BYTES:
        raise ValueError("O logotipo pode ter no máximo 4 MB.")

    import warnings
    try:
        with warnings.catch_warnings():
            # aviso de "bomba de descompressão" vira erro: um PNG de poucos KB
            # pode ter dezenas de megapixels e estourar a memória do servidor
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(dados)) as teste:
                if teste.format not in ("PNG", "JPEG", "WEBP"):
                    raise ValueError("Use um logotipo em PNG, JPG ou WEBP.")
                if teste.width * teste.height > LOGO_MAX_PIXELS:
                    raise ValueError("Esse logotipo é grande demais. Envie uma imagem de até 4000 x 4000 pixels.")
                teste.verify()                   # detecta arquivo corrompido/forjado
            img = Image.open(io.BytesIO(dados))
            if img.format == "JPEG":
                img.draft("RGB", (LOGO_MAX_LADO * 2, LOGO_MAX_LADO * 2))   # decodifica já reduzido
            if img.mode in ("P", "PA", "1", "L", "LA"):
                # paleta/1 bit seriam reduzidos por "vizinho mais próximo" (borda serrilhada);
                # convertido antes, o LANCZOS suaviza. Memória limitada pelos 16 Mpx.
                img = img.convert("RGBA")
            img.thumbnail((LOGO_MAX_LADO, LOGO_MAX_LADO), Image.LANCZOS)   # reduz antes de converter
            img = img.convert("RGBA")          # dentro do try: arquivo truncado vira mensagem, não erro 500
    except ValueError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning,
            OSError, SyntaxError):
        raise ValueError("Não consegui ler essa imagem. Tente um PNG ou JPG.")

    saida = io.BytesIO()
    img.save(saida, "PNG", optimize=True)
    current_app.logger.info(f"Logo normalizado: {img.size[0]}x{img.size[1]}, {saida.tell() // 1024} KB")
    return saida.getvalue()


def cor_valida(valor, padrao):
    """Aceita só #rrggbb — o valor vai para dentro do CSS/canvas."""
    valor = (valor or "").strip()
    if len(valor) == 7 and valor[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in valor[1:]):
        return valor.lower()
    return padrao
