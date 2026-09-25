"""Textos das páginas das ferramentas em português, espanhol e inglês.

Títulos, descrições e perguntas vêm da pesquisa de palavras-chave feita em
24/09/2026 (autocompletar do Google em cada país). O Pro só é vendido no
Brasil por enquanto (Mercado Pago em reais): em espanhol e inglês a página
oferece a versão grátis e uma lista de espera do Pro.
"""

IDIOMAS = ("pt", "es", "en")

# Códigos usados em <html lang>, hreflang e og:locale, e o caminho de cada versão.
META_IDIOMA = {
    "pt": {"html": "pt-BR", "hreflang": "pt-BR", "og": "pt_BR", "nome": "Português", "endpoint": "ferramentas.antes_depois_pt"},
    "es": {"html": "es", "hreflang": "es", "og": "es_LA", "nome": "Español", "endpoint": "ferramentas.antes_depois_es"},
    "en": {"html": "en", "hreflang": "en", "og": "en_US", "nome": "English", "endpoint": "ferramentas.antes_depois_en"},
}

def textos_para(idioma, preco_fmt):
    """Textos do idioma com o preço atual do Pro no lugar de {preco}
    (o preço fica no SiteConfig ``ferr_pro_preco`` e pode mudar pelo admin)."""
    def trocar(v):
        if isinstance(v, str):
            return v.replace("{preco}", preco_fmt)
        if isinstance(v, dict):
            return {k: trocar(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return type(v)(trocar(x) for x in v)
        return v
    return trocar(TEXTOS[idioma])


TEXTOS = {
    # ------------------------------------------------------------------ português
    "pt": {
        "title": "Montar Foto Antes e Depois Online Grátis | RD OS",
        "description": "Monte o antes e depois do serviço pelo celular, sem instalar app. Grátis. "
                       "Pro por {preco} (pagamento único): sua logomarca, sem marca d'água e com vídeo.",
        "eyebrow": "Ferramenta grátis · funciona no celular",
        "h1": "Monte o Antes e Depois do seu serviço em 1 minuto, direto no celular",
        "lead": "Escolha a foto de antes e a de depois, ajuste o enquadramento e baixe a arte pronta "
                "para o Instagram, o Status do WhatsApp ou para mandar ao cliente.",
        "nav_entrar": "Entrar",
        "nav_marca": "Minha marca",
        "nav_sair": "Sair",
        "nav_pro": "Pro",
        "nav_idioma": "Idioma",
        "nav_ferramenta": "Gerador",
        # ferramenta
        "passo_fotos": "Suas fotos",
        "foto_antes": "Foto do antes",
        "foto_depois": "Foto do depois",
        "trocar_foto": "Trocar",
        "zoom": "Zoom",
        "centralizar": "Centralizar",
        "horizontal": "Horizontal",
        "vertical": "Vertical",
        "inverter": "Inverter antes e depois",
        "passo_formato": "Formato",
        "formatos": [
            ("quadrado", "Quadrado", "Feed 1:1"),
            ("retrato", "Retrato", "Feed 4:5"),
            ("stories", "Stories", "Status 9:16"),
        ],
        "passo_textos": "Textos (opcional)",
        "titulo": "Título",
        "titulo_ph": "Ex.: Solda em contentor de lixo",
        "subtitulo": "Subtítulo",
        "subtitulo_ph": "Ex.: Condomínio em São Bernardo do Campo",
        "rotulo_antes": "Etiqueta do antes",
        "rotulo_depois": "Etiqueta do depois",
        "passo_marca": "Sua marca",
        "cor_primaria": "Cor das faixas",
        "cor_destaque": "Cor de destaque",
        "rodape_marca": "Mostrar minha marca no rodapé",
        "marca_editar": "Trocar logotipo, nome e contato",
        "marca_vazia": "Você ainda não enviou o seu logotipo.",
        "marca_vazia_cta": "Configurar minha marca",
        "baixar": "Baixar imagem",
        "compartilhar": "Compartilhar",
        "video": "Gerar vídeo",
        "video_pro": "Vídeo · Pro",
        "video_compartilhar": "Compartilhar vídeo",
        "video_baixar": "Baixar vídeo",
        "dica": "Dica: arraste cada foto dentro do quadro para enquadrar melhor.",
        "nota_exemplo": "Isto é um exemplo com um serviço real. Toque em “Foto do antes” para montar a sua.",
        "privacidade": "Suas fotos não saem do seu aparelho: a montagem é feita no próprio navegador.",
        "canvas_label": "Prévia da arte de antes e depois",
        # venda do Pro dentro da ferramenta (plano grátis)
        "upsell_titulo": "Tire a marca d'água e coloque a SUA marca",
        "upsell_itens": [
            "Seu logotipo, nome e WhatsApp no rodapé",
            "Sem a marca d'água da RD Soluções",
            "As cores da sua empresa",
            "Vídeo de 7 segundos para Reels e Status",
        ],
        "upsell_preco": "{preco}",
        "upsell_preco_nota": "pagamento único, sem mensalidade",
        "upsell_cta": "Quero o Pro",
        "upsell_ja_tenho": "Já comprei — entrar",
        # seções
        "como_titulo": "Como funciona",
        "como_passos": [
            ("Escolha as duas fotos", "Pegue da galeria ou tire na hora: primeiro a do antes, depois a do depois."),
            ("Ajuste e escolha o formato", "Arraste para enquadrar, use o zoom e escolha feed, retrato ou stories."),
            ("Baixe ou compartilhe", "A arte sai em JPG, pronta para o Instagram, o WhatsApp ou o cliente."),
        ],
        "planos_titulo": "Grátis ou Pro",
        "planos_col_recurso": "Recurso",
        "planos_col_gratis": "Grátis",
        "planos_col_pro": "Pro",
        "planos_linhas": [
            ("Montar antes e depois no celular", True, True),
            ("Formatos para feed, retrato e stories", True, True),
            ("Baixar e compartilhar a imagem", True, True),
            ("Título, subtítulo e etiquetas", True, True),
            ("Sem a marca d'água da RD Soluções", False, True),
            ("Seu logotipo, nome e contato", False, True),
            ("Cores da sua empresa", False, True),
            ("Vídeo para Reels e Status", False, True),
        ],
        "planos_preco_gratis": "R$ 0",
        "planos_preco_pro": "{preco} · pagamento único",
        "planos_cta": "Liberar o Pro por {preco}",
        "planos_garantia": "7 dias para desistir e receber o valor de volta.",
        "profissoes_titulo": "Feito para quem mostra o serviço pronto",
        "profissoes_texto": "Soldadores, pedreiros, pintores, eletricistas, encanadores, higienização de estofados, "
                            "limpeza de caixa d'água, lavagem de telhado, jardinagem, marido de aluguel, "
                            "funilaria, estética automotiva e qualquer serviço em que o resultado aparece na foto.",
        "faq_titulo": "Perguntas frequentes",
        "faq": [
            ("É grátis mesmo?",
             "Sim. Você monta, baixa e compartilha quantas artes quiser sem pagar nada. A versão grátis leva o selo "
             "da RD Soluções sobre as fotos e uma faixa \"Feito grátis com RD OS\" no rodapé. Para trocar pela sua "
             "marca, existe o Pro."),
            ("Preciso instalar algum aplicativo?",
             "Não. Funciona no navegador do celular (Chrome ou Safari) e no computador. É só abrir esta página."),
            ("Quanto custa o Pro? É mensalidade?",
             "O Pro custa {preco}, pagamento único, sem mensalidade. Na compra você recebe um login e cria a sua senha "
             "para usar o Pro sempre que quiser."),
            ("Posso colocar minha logomarca e o meu WhatsApp?",
             "Pode, no Pro. Você envia o logotipo uma vez, escreve o nome da empresa e o contato, e eles entram no "
             "rodapé de todas as artes, com as cores que você escolher."),
            ("Serve para Instagram e WhatsApp?",
             "Sim. O formato quadrado e o retrato servem para o feed do Instagram e do Facebook; o stories serve para "
             "Stories, Reels e Status do WhatsApp. No celular, o botão Compartilhar abre o menu do aparelho para você escolher "
             "o WhatsApp, o Instagram ou outro app. Se ele não aparecer (por exemplo, dentro do navegador do Instagram), "
             "use Baixar imagem."),
            ("O “depois” é feito com inteligência artificial?",
             "Não. A ferramenta só junta as duas fotos reais que você tirou. Ela não inventa nem altera o resultado do serviço."),
            ("Minhas fotos ficam salvas no site?",
             "Não. A arte é montada no seu próprio aparelho e as fotos não são enviadas para o servidor. No Pro, só o "
             "logotipo que você envia fica guardado na sua conta."),
            ("Como tirar uma boa foto de antes e depois?",
             "Fotografe do mesmo lugar e na mesma distância nas duas fotos, com boa luz e o celular na mesma posição "
             "(em pé ou deitado). Mostre o defeito inteiro no antes e o mesmo ponto no depois."),
        ],
        "rodape_texto": "RD OS é um produto da RD Soluções, São Bernardo do Campo – SP.",
        "rodape_termos": "Termos",
        "rodape_privacidade": "Privacidade",
        "rodape_contato": "Contato",
        # usados pelo JavaScript
        "js": {
            "antes": "ANTES",
            "depois": "DEPOIS",
            "exemplo": "EXEMPLO",
            "toqueFoto": "Toque para escolher a foto",
            "feitoCom": "Feito grátis com RD OS",
            "marca": "RD Soluções · rdos.rdsolucoes.eco.br",
            "soImagem": "Escolha um arquivo de imagem (foto).",
            "erroFoto": "Não consegui abrir essa foto. Tente outra ou tire um print dela.",
            "arquivo": "antes-e-depois",
            "tituloCompartilhar": "Antes e depois",
            "semVideo": "Este navegador não grava vídeo. Tente pelo Chrome.",
            "gravando": "Gravando o vídeo…",
            "videoPronto": "Vídeo pronto! Toque em Compartilhar ou Baixar.",
            "videoInterrompido": "A gravação parou porque a página saiu da tela. Grave de novo com ela aberta.",
            "videoArteMudou": "A arte mudou durante a gravação. Grave o vídeo de novo.",
        },
    },

    # ------------------------------------------------------------------ español
    "es": {
        "title": "Collage Antes y Después Online Gratis | Para tus Trabajos",
        "description": "Une la foto del antes y del después de tu trabajo en una sola imagen para Instagram y "
                       "WhatsApp. Gratis, desde el celular, sin instalar apps.",
        "eyebrow": "Herramienta gratis · funciona en el celular",
        "h1": "Crea la foto de Antes y Después de tu trabajo desde el celular",
        "lead": "Elige la foto del antes y la del después, ajusta el encuadre y descarga la imagen lista para "
                "Instagram, los estados de WhatsApp o para enviarla a tu cliente.",
        "nav_entrar": "Entrar",
        "nav_marca": "Mi marca",
        "nav_sair": "Salir",
        "nav_pro": "Pro",
        "nav_idioma": "Idioma",
        "nav_ferramenta": "Herramienta",
        "passo_fotos": "Tus fotos",
        "foto_antes": "Foto del antes",
        "foto_depois": "Foto del después",
        "trocar_foto": "Cambiar",
        "zoom": "Zoom",
        "centralizar": "Centrar",
        "horizontal": "Horizontal",
        "vertical": "Vertical",
        "inverter": "Invertir antes y después",
        "passo_formato": "Formato",
        "formatos": [
            ("quadrado", "Cuadrado", "Feed 1:1"),
            ("retrato", "Vertical", "Feed 4:5"),
            ("stories", "Historias", "Estados 9:16"),
        ],
        "passo_textos": "Textos (opcional)",
        "titulo": "Título",
        "titulo_ph": "Ej.: Soldadura de contenedor de basura",
        "subtitulo": "Subtítulo",
        "subtitulo_ph": "Ej.: Trabajo en un condominio",
        "rotulo_antes": "Etiqueta del antes",
        "rotulo_depois": "Etiqueta del después",
        "passo_marca": "Tu marca",
        "cor_primaria": "Color de las franjas",
        "cor_destaque": "Color de acento",
        "rodape_marca": "Mostrar mi marca abajo",
        "marca_editar": "Cambiar logo, nombre y contacto",
        "marca_vazia": "Todavía no subiste tu logo.",
        "marca_vazia_cta": "Configurar mi marca",
        "baixar": "Descargar imagen",
        "compartilhar": "Compartir",
        "video": "Crear video",
        "video_pro": "Video · Pro",
        "video_compartilhar": "Compartir video",
        "video_baixar": "Descargar video",
        "dica": "Consejo: arrastra cada foto dentro de su cuadro para encuadrarla mejor.",
        "nota_exemplo": "Esto es un ejemplo con un trabajo real. Toca “Foto del antes” para crear la tuya.",
        "privacidade": "Tus fotos no salen de tu teléfono: la imagen se arma en el propio navegador.",
        "canvas_label": "Vista previa de la imagen de antes y después",
        "upsell_titulo": "Pro con TU marca (por ahora solo en Brasil)",
        "upsell_itens": [
            "Tu logo, nombre y WhatsApp en la imagen",
            "Sin la marca de agua",
            "Los colores de tu empresa",
            "Video de 7 segundos para Reels y estados",
        ],
        "espera_texto": "Pro todavía no se vende en tu país. Deja tu e-mail y te avisamos si llega "
                        "(en Brasil es un pago único, sin suscripción).",
        "espera_email": "Tu e-mail",
        "espera_cta": "Avisarme",
        "espera_ok": "¡Listo! Te avisaremos por e-mail si Pro llega a tu país.",
        "espera_erro": "Escribe un e-mail válido.",
        "como_titulo": "Cómo funciona",
        "como_passos": [
            ("Elige las dos fotos", "Desde la galería o con la cámara: primero la del antes, luego la del después."),
            ("Ajusta y elige el formato", "Arrastra para encuadrar, usa el zoom y elige feed, vertical o historias."),
            ("Descarga o comparte", "La imagen sale en JPG, lista para Instagram, WhatsApp o tu cliente."),
        ],
        "planos_titulo": "Gratis o Pro",
        "planos_col_recurso": "Función",
        "planos_col_gratis": "Gratis",
        "planos_col_pro": "Pro (solo Brasil)",
        "planos_linhas": [
            ("Crear antes y después en el celular", True, True),
            ("Formatos para feed, vertical e historias", True, True),
            ("Descargar y compartir la imagen", True, True),
            ("Título, subtítulo y etiquetas", True, True),
            ("Sin sello ni franja de RD OS", False, True),
            ("Tu logo, nombre y contacto", False, True),
            ("Colores de tu empresa", False, True),
            ("Video para Reels y estados", False, True),
        ],
        "planos_preco_gratis": "Gratis",
        "planos_preco_pro": "Pago único",
        "profissoes_titulo": "Para quienes muestran su trabajo terminado",
        "profissoes_texto": "Soldadores, albañiles, pintores, electricistas, plomeros, limpieza de tapizados, "
                            "limpieza de tanques de agua, lavado a presión, jardinería, reparaciones del hogar, "
                            "chapa y pintura, detailing automotriz y cualquier oficio en el que el resultado se ve en la foto.",
        "faq_titulo": "Preguntas frecuentes",
        "faq": [
            ("¿Es gratis?",
             "Sí. Puedes crear, descargar y compartir todas las imágenes que quieras sin pagar. La versión gratis "
             "lleva un sello de RD OS sobre las fotos y una franja con la marca abajo."),
            ("¿Tengo que instalar una app?",
             "No. Funciona en el navegador del celular (Chrome o Safari) y en la computadora. Solo abre esta página."),
            ("¿Cuánto cuesta Pro?",
             "En Brasil, Pro es un pago único, sin suscripción. Por ahora no se vende en otros países; deja tu "
             "e-mail en esta página y te avisamos si llega al tuyo."),
            ("¿Qué incluye Pro?",
             "Tu logo, el nombre de tu empresa y tu contacto en todas las imágenes, sin marca de agua, con los "
             "colores de tu marca, y un video corto para Reels y estados de WhatsApp."),
            ("¿Para qué oficios sirve?",
             "Para cualquier trabajo en el que el resultado se ve en la foto: soldadura, albañilería, pintura, "
             "limpieza, lavado a presión, jardinería, plomería, electricidad, talleres y más."),
            ("¿La herramienta cambia mis fotos o usa IA para el después?",
             "No. Solo une las dos fotos reales que tomaste. No inventa ni modifica el resultado de tu trabajo."),
            ("¿Mis fotos se suben a internet?",
             "No. La imagen se arma en tu propio teléfono y las fotos no se envían a ningún servidor."),
        ],
        "rodape_texto": "RD OS es un producto de RD Soluções, São Bernardo do Campo – SP, Brasil.",
        "rodape_termos": "Términos",
        "rodape_privacidade": "Privacidad",
        "rodape_contato": "Contacto",
        "js": {
            "antes": "ANTES",
            "depois": "DESPUÉS",
            "exemplo": "EJEMPLO",
            "toqueFoto": "Toca para elegir la foto",
            "feitoCom": "Hecho gratis con RD OS",
            "marca": "RD OS · rdos.rdsolucoes.eco.br",
            "soImagem": "Elige un archivo de imagen (foto).",
            "erroFoto": "No pude abrir esa foto. Prueba con otra o haz una captura de pantalla.",
            "arquivo": "antes-y-despues",
            "tituloCompartilhar": "Antes y después",
            "semVideo": "Este navegador no graba video. Prueba con Chrome.",
            "gravando": "Grabando el video…",
            "videoPronto": "¡Video listo! Toca Compartir o Descargar.",
            "videoInterrompido": "La grabación se detuvo porque saliste de la página. Grábalo de nuevo con la página abierta.",
            "videoArteMudou": "La imagen cambió durante la grabación. Graba el video de nuevo.",
        },
    },

    # ------------------------------------------------------------------ english
    "en": {
        "title": "Free Before & After Photo Maker for Contractors | RD OS",
        "description": "Put your before and after job photos side by side for Instagram and Facebook. Free, right "
                       "from your phone. Made for cleaners, pressure washers and contractors.",
        "eyebrow": "Free tool · works on your phone",
        "h1": "Before & After Photo Maker for Contractors and Home Service Pros",
        "lead": "Pick your before and after photos, adjust the framing and download a ready-to-post image for "
                "Instagram, Facebook, WhatsApp or your customer.",
        "nav_entrar": "Log in",
        "nav_marca": "My brand",
        "nav_sair": "Log out",
        "nav_pro": "Pro",
        "nav_idioma": "Language",
        "nav_ferramenta": "Photo maker",
        "passo_fotos": "Your photos",
        "foto_antes": "Before photo",
        "foto_depois": "After photo",
        "trocar_foto": "Change",
        "zoom": "Zoom",
        "centralizar": "Reset",
        "horizontal": "Left / right",
        "vertical": "Up / down",
        "inverter": "Swap before and after",
        "passo_formato": "Format",
        "formatos": [
            ("quadrado", "Square", "Post 1:1"),
            ("retrato", "Portrait", "Post 4:5"),
            ("stories", "Story", "Reels 9:16"),
        ],
        "passo_textos": "Text (optional)",
        "titulo": "Headline",
        "titulo_ph": "E.g.: Driveway pressure washing",
        "subtitulo": "Subheading",
        "subtitulo_ph": "E.g.: Residential job in Austin, TX",
        "rotulo_antes": "Before label",
        "rotulo_depois": "After label",
        "passo_marca": "Your brand",
        "cor_primaria": "Band color",
        "cor_destaque": "Accent color",
        "rodape_marca": "Show my brand at the bottom",
        "marca_editar": "Change logo, name and contact",
        "marca_vazia": "You haven't uploaded your logo yet.",
        "marca_vazia_cta": "Set up my brand",
        "baixar": "Download image",
        "compartilhar": "Share",
        "video": "Make video",
        "video_pro": "Video · Pro",
        "video_compartilhar": "Share video",
        "video_baixar": "Download video",
        "dica": "Tip: drag each photo inside its frame to adjust the framing.",
        "nota_exemplo": "This is an example from a real job. Tap “Before photo” to make yours.",
        "privacidade": "Your photos never leave your device: the image is built right in your browser.",
        "canvas_label": "Before and after image preview",
        "upsell_titulo": "Pro with YOUR brand (Brazil only for now)",
        "upsell_itens": [
            "Your logo, business name and phone on every image",
            "No watermark",
            "Your brand colors",
            "7-second video for Reels, Stories and Shorts",
        ],
        "espera_texto": "Pro isn't available in your country yet. Leave your email and we'll let you know if it "
                        "becomes available (in Brazil it's a one-time payment, no subscription).",
        "espera_email": "Your email",
        "espera_cta": "Notify me",
        "espera_ok": "Done! We'll email you if Pro becomes available in your country.",
        "espera_erro": "Please enter a valid email.",
        "como_titulo": "How it works",
        "como_passos": [
            ("Pick your two photos", "From your camera roll or the camera: first the before, then the after."),
            ("Adjust and pick a format", "Drag to frame, zoom in, and choose square, portrait or story."),
            ("Download or share", "You get a JPG, ready for Instagram, Facebook, WhatsApp or your customer."),
        ],
        "planos_titulo": "Free or Pro",
        "planos_col_recurso": "Feature",
        "planos_col_gratis": "Free",
        "planos_col_pro": "Pro (Brazil only)",
        "planos_linhas": [
            ("Make before & after images on your phone", True, True),
            ("Square, portrait and story formats", True, True),
            ("Download and share the image", True, True),
            ("Headline, subheading and labels", True, True),
            ("No RD OS badge or strip", False, True),
            ("Your logo, business name and contact", False, True),
            ("Your brand colors", False, True),
            ("Video for Reels and Stories", False, True),
        ],
        "planos_preco_gratis": "Free",
        "planos_preco_pro": "One-time payment",
        "profissoes_titulo": "Made for pros who show finished work",
        "profissoes_texto": "Cleaning services, pressure washing, landscaping and lawn care, handymen, painters, "
                            "welders, plumbers, electricians, roofers, junk removal, auto detailing and any job "
                            "where the result shows in the photo.",
        "faq_titulo": "Frequently asked questions",
        "faq": [
            ("Is it really free?",
             "Yes. You can make, download and share as many before & after images as you want. Free images include "
             "an RD OS badge over the photos and a branded strip at the bottom."),
            ("Is Pro a monthly subscription?",
             "No. In Brazil, Pro is a one-time payment. It isn't sold in other countries yet; leave your email on "
             "this page and we'll let you know if it becomes available in yours."),
            ("Can I put my logo, colors and phone number on the image?",
             "With Pro (Brazil only for now): your logo, business name and contact go at the bottom of every image, "
             "in your brand colors, with no RD OS badge."),
            ("Can it make a video for Instagram Reels or Stories?",
             "Only with Pro, which is sold in Brazil only for now: it turns your two photos into a 7-second video "
             "with a before-to-after reveal. Leave your email to hear if it becomes available in your country."),
            ("Do I need to download an app?",
             "No. It runs in your phone's browser (Safari or Chrome) and on a computer. Just open this page."),
            ("Does it create a fake 'after' photo with AI?",
             "No. It only uses the two real photos you took on the job. Customers trust real results."),
            ("Do I need my customer's permission to post photos of their home?",
             "It's good practice to ask first. Avoid showing house numbers, faces or license plates."),
        ],
        "rodape_texto": "RD OS is made by RD Soluções, São Bernardo do Campo, Brazil.",
        "rodape_termos": "Terms",
        "rodape_privacidade": "Privacy",
        "rodape_contato": "Contact",
        "js": {
            "antes": "BEFORE",
            "depois": "AFTER",
            "exemplo": "EXAMPLE",
            "toqueFoto": "Tap to choose a photo",
            "feitoCom": "Made for free with RD OS",
            "marca": "RD OS · rdos.rdsolucoes.eco.br",
            "soImagem": "Please choose an image file (photo).",
            "erroFoto": "Couldn't open that photo. Try another one or take a screenshot of it.",
            "arquivo": "before-and-after",
            "tituloCompartilhar": "Before & after",
            "semVideo": "This browser can't record video. Try Chrome.",
            "gravando": "Recording video…",
            "videoPronto": "Video ready! Tap Share or Download.",
            "videoInterrompido": "Recording stopped because you left the page. Record again with the page open.",
            "videoArteMudou": "The image changed while recording. Please record the video again.",
        },
    },
}
