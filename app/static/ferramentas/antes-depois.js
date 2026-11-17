/* Gerador de antes e depois — RD OS Ferramentas.
 *
 * Tudo roda no navegador: as fotos nunca são enviadas para o servidor.
 * Configuração vem do template em window.RD_FERR:
 *   { idioma, pro, marca: {empresa, telefone, site, corPrimaria, corDestaque, logo} | null,
 *     textos: {...}, rdLogo, exemplo: {antes, depois} | null, rastreio: {url, ativo}, urlPro }
 *
 * A página abre com um par de fotos de exemplo (serviço real da RD Soluções)
 * para mostrar o resultado antes de a pessoa escolher as dela. Enquanto o
 * exemplo está na tela, baixar/compartilhar ficam desligados.
 */
(function () {
  'use strict';

  var CFG = window.RD_FERR || {};
  var T = CFG.textos || {};
  var PRO = !!CFG.pro;
  var MARCA = CFG.marca || null;

  var FORMATOS = {
    quadrado: { w: 1080, h: 1080, modo: 'lado' },
    retrato: { w: 1080, h: 1350, modo: 'lado' },
    stories: { w: 1080, h: 1920, modo: 'pilha' }
  };
  var VERMELHO = '#c83939';
  var VERDE = '#1a8a4c';
  var FONTE_TIT = '"Poppins", "Segoe UI", Arial, sans-serif';
  var FONTE_TXT = '"Inter", "Segoe UI", Arial, sans-serif';
  // endereço curto da arte grátis: grava de onde a visita veio (routes/ferramentas.gratis)
  var SITE = T.site || 'rdos.rdsolucoes.eco.br/gratis';

  var estado = {
    fotos: { antes: null, depois: null },
    ajuste: { antes: { z: 1, x: 0, y: 0 }, depois: { z: 1, x: 0, y: 0 } },
    formato: 'quadrado',
    titulo: '',
    subtitulo: '',
    rotulos: { antes: T.antes || 'ANTES', depois: T.depois || 'DEPOIS' },
    cores: {
      primaria: (PRO && MARCA && MARCA.corPrimaria) || '#0c2340',
      destaque: (PRO && MARCA && MARCA.corDestaque) || '#f97316'
    },
    rodapeMarca: true,
    exemplo: false,   // true enquanto as fotos de exemplo estão na tela
    logo: null,       // logotipo do usuário Pro
    rdLogo: null      // logo da RD (marca d'água do plano grátis)
  };

  var $ = function (id) { return document.getElementById(id); };
  var canvas = $('ad-canvas');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');

  // ------------------------------------------------------------------ rastreio
  var jaGerou = false;
  function rastrear(tipo, detalhe) {
    var r = CFG.rastreio || {};
    if (!r.ativo || !r.url) return;
    var p = new URLSearchParams({ produto: 'ferramentas', tipo: tipo, slug: 'antes-e-depois' });
    p.set('detalhe', String((CFG.idioma || '') + (detalhe ? ':' + detalhe : '')).slice(0, 300));
    try {
      if (navigator.sendBeacon) navigator.sendBeacon(r.url, p);
      else fetch(r.url, { method: 'POST', body: p, keepalive: true }).catch(function () {});
    } catch (e) {}
  }

  function avisar(msg) {
    var el = $('ad-aviso');
    if (!el) { alert(msg); return; }
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(avisar.t);
    avisar.t = setTimeout(function () { el.hidden = true; }, 6000);
  }

  function avisoAoVoltar(msg) {
    if (!document.hidden) { avisar(msg); return; }
    document.addEventListener('visibilitychange', function mostrar() {
      if (document.hidden) return;
      document.removeEventListener('visibilitychange', mostrar);
      avisar(msg);
    });
  }

  // ------------------------------------------------------------------ imagens
  function carregarImagem(src) {
    return new Promise(function (ok, erro) {
      var img = new Image();
      img.onload = function () { ok(img); };
      img.onerror = erro;
      img.src = src;
    });
  }

  // <img> já aplica a rotação EXIF nos navegadores atuais. Foto muito grande é
  // reduzida para 2400 px para não estourar a memória do celular.
  function carregarArquivo(arquivo) {
    var url = URL.createObjectURL(arquivo);
    return carregarImagem(url).then(function (img) {
      var lado = Math.max(img.naturalWidth, img.naturalHeight);
      if (lado <= 2400) return img;
      var s = 2400 / lado;
      var c = document.createElement('canvas');
      c.width = Math.round(img.naturalWidth * s);
      c.height = Math.round(img.naturalHeight * s);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      return c;
    });
  }
  function largura(img) { return img.naturalWidth || img.width; }
  function altura(img) { return img.naturalHeight || img.height; }

  // ------------------------------------------------------------------ layout
  function temRodape() {
    if (!PRO) return true;                       // grátis: faixa com a marca RD
    if (!estado.rodapeMarca || !MARCA) return false;
    return !!(estado.logo || MARCA.empresa || MARCA.telefone || MARCA.site);
  }

  function calcularLayout(fmt) {
    var W = fmt.w, H = fmt.h;
    var escala = W / 1080;
    var temTitulo = !!(estado.titulo || estado.subtitulo);
    var topo = temTitulo ? Math.round((fmt.modo === 'pilha' ? 230 : estado.subtitulo ? 170 : 130) * escala) : 0;
    var rodape = temRodape() ? Math.round((fmt.modo === 'pilha' ? 200 : 140) * escala) : 0;
    var gap = Math.round(10 * escala);
    var area = { x: 0, y: topo, w: W, h: H - topo - rodape };
    var a, d;
    if (fmt.modo === 'lado') {
      var lw = Math.floor((area.w - gap) / 2);
      a = { x: 0, y: area.y, w: lw, h: area.h };
      d = { x: lw + gap, y: area.y, w: area.w - lw - gap, h: area.h };
    } else {
      var lh = Math.floor((area.h - gap) / 2);
      a = { x: 0, y: area.y, w: area.w, h: lh };
      d = { x: 0, y: area.y + lh + gap, w: area.w, h: area.h - lh - gap };
    }
    return { W: W, H: H, e: escala, topo: topo, rodape: rodape, gap: gap, area: area, antes: a, depois: d, modo: fmt.modo };
  }

  // ------------------------------------------------------------------ desenho
  function fotoCobrindo(c, img, r, aj) {
    var s = Math.max(r.w / largura(img), r.h / altura(img)) * aj.z;
    var dw = largura(img) * s, dh = altura(img) * s;
    var dx = r.x - (dw - r.w) * (0.5 + aj.x / 2);
    var dy = r.y - (dh - r.h) * (0.5 + aj.y / 2);
    c.save();
    c.beginPath(); c.rect(r.x, r.y, r.w, r.h); c.clip();
    c.drawImage(img, dx, dy, dw, dh);
    c.restore();
  }

  function textoAjustado(c, texto, maxW, tamanho, peso, fonte) {
    var t = tamanho;
    c.font = peso + ' ' + t + 'px ' + fonte;
    while (c.measureText(texto).width > maxW && t > 12) {
      t -= 2;
      c.font = peso + ' ' + t + 'px ' + fonte;
    }
    return t;
  }

  function retanguloArredondado(c, x, y, w, h, r) {
    c.beginPath();
    c.moveTo(x + r, y);
    c.arcTo(x + w, y, x + w, y + h, r);
    c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r);
    c.arcTo(x, y, x + w, y, r);
    c.closePath();
  }

  function pilula(c, x, y, texto, cor, e) {
    var tam = Math.round(40 * e);
    c.font = '700 ' + tam + 'px ' + FONTE_TIT;
    var padX = Math.round(24 * e), h = Math.round(tam * 1.5);
    var w = c.measureText(texto).width + padX * 2;
    c.fillStyle = cor;
    retanguloArredondado(c, x, y, w, h, h / 2);
    c.fill();
    c.fillStyle = '#fff';
    c.textBaseline = 'middle';
    c.fillText(texto, x + padX, y + h / 2 + 1);
    c.textBaseline = 'alphabetic';
  }

  function vazio(c, r, rotulo, e) {
    c.fillStyle = '#e8edf2';
    c.fillRect(r.x, r.y, r.w, r.h);
    c.strokeStyle = '#b8c4d0';
    c.lineWidth = Math.max(2, 3 * e);
    c.setLineDash([14 * e, 10 * e]);
    c.strokeRect(r.x + 18 * e, r.y + 18 * e, r.w - 36 * e, r.h - 36 * e);
    c.setLineDash([]);
    c.fillStyle = '#5d6d7e';
    c.textAlign = 'center';
    var tam = textoAjustado(c, T.toqueFoto || 'Toque para escolher a foto', r.w - 60 * e, Math.round(34 * e), '600', FONTE_TXT);
    c.fillText(T.toqueFoto || 'Toque para escolher a foto', r.x + r.w / 2, r.y + r.h / 2);
    c.font = '700 ' + Math.round(tam * 1.3) + 'px ' + FONTE_TIT;
    c.fillText(rotulo, r.x + r.w / 2, r.y + r.h / 2 - tam * 1.6);
    c.textAlign = 'left';
  }

  function desenharCabecalho(c, L) {
    if (!L.topo) return;
    var faixa = Math.round(6 * L.e);                 // linha de destaque embaixo
    c.fillStyle = estado.cores.primaria;
    c.fillRect(0, 0, L.W, L.topo);
    c.fillStyle = estado.cores.destaque;
    c.fillRect(0, L.topo - faixa, L.W, faixa);
    var interno = L.topo - faixa, maxW = L.W - 80 * L.e;
    var tt = estado.titulo ? textoAjustado(c, estado.titulo, maxW, Math.round((L.modo === 'pilha' ? 72 : 60) * L.e), '700', FONTE_TIT) : 0;
    var ts = estado.subtitulo ? textoAjustado(c, estado.subtitulo, maxW, Math.round((L.modo === 'pilha' ? 40 : 32) * L.e), '500', FONTE_TXT) : 0;
    var entre = tt && ts ? Math.round(12 * L.e) : 0;
    var topoBloco = (interno - (tt + entre + ts)) / 2;
    c.textAlign = 'center';
    c.fillStyle = '#fff';
    if (tt) {
      c.font = '700 ' + tt + 'px ' + FONTE_TIT;
      c.fillText(estado.titulo, L.W / 2, topoBloco + tt * 0.82);
    }
    if (ts) {
      c.globalAlpha = 0.85;
      c.font = '500 ' + ts + 'px ' + FONTE_TXT;
      c.fillText(estado.subtitulo, L.W / 2, topoBloco + tt + entre + ts * 0.82);
      c.globalAlpha = 1;
    }
    c.textAlign = 'left';
  }

  function desenharRodape(c, L) {
    if (!L.rodape) return;
    var y0 = L.H - L.rodape;
    c.fillStyle = estado.cores.primaria;
    c.fillRect(0, y0, L.W, L.rodape);
    c.fillStyle = estado.cores.destaque;
    c.fillRect(0, y0, L.W, Math.round(6 * L.e));
    var pad = Math.round(40 * L.e);
    var meio = y0 + L.rodape / 2 + Math.round(3 * L.e);

    if (!PRO) {
      // plano grátis: faixa do RD OS, com o endereço curto grande o bastante para ler no celular
      var x = pad;
      if (estado.rdLogo) {
        var lh = L.rodape * 0.5, lw = lh * largura(estado.rdLogo) / altura(estado.rdLogo);
        c.drawImage(estado.rdLogo, x, meio - lh / 2, lw, lh);
        x += lw + Math.round(22 * L.e);
      }
      c.fillStyle = '#fff';
      var t1 = T.feitoCom || 'Feito grátis com RD OS';
      var t2 = SITE;
      var tam = textoAjustado(c, t1, L.W - x - pad, Math.round(34 * L.e), '700', FONTE_TIT);
      c.fillText(t1, x, meio - tam * 0.15);
      var tam2 = textoAjustado(c, t2, L.W - x - pad, Math.round(tam * 0.95), '600', FONTE_TXT);
      c.fillStyle = estado.cores.destaque;
      c.fillText(t2, x, meio + tam * 0.2 + tam2 * 0.85);
      return;
    }

    // Pro: identidade do usuário
    var xl = pad;
    if (estado.logo) {
      var h = L.rodape * 0.62, w = Math.min(h * largura(estado.logo) / altura(estado.logo), L.W * 0.38);
      h = w * altura(estado.logo) / largura(estado.logo);
      c.drawImage(estado.logo, xl, meio - h / 2, w, h);
      xl += w + Math.round(24 * L.e);
    }
    var linhas = [];
    if (MARCA.empresa) linhas.push({ t: MARCA.empresa, peso: '700', f: FONTE_TIT, cor: '#fff', tam: 38 });
    var contato = [MARCA.telefone, MARCA.site].filter(Boolean).join('  ·  ');
    if (contato) linhas.push({ t: contato, peso: '500', f: FONTE_TXT, cor: estado.cores.destaque, tam: 30 });
    if (!linhas.length) return;
    c.textAlign = 'right';
    var xr = L.W - pad, maxW = xr - xl;
    var alturas = linhas.map(function (ln) { return textoAjustado(c, ln.t, maxW, Math.round(ln.tam * L.e), ln.peso, ln.f); });
    var total = alturas.reduce(function (s, v) { return s + v * 1.25; }, 0);
    var y = meio - total / 2 + alturas[0] * 0.95;
    linhas.forEach(function (ln, i) {
      c.font = ln.peso + ' ' + alturas[i] + 'px ' + ln.f;
      c.fillStyle = ln.cor;
      c.fillText(ln.t, xr, y);
      y += alturas[i] * 1.25 + (i === 0 ? 4 * L.e : 0);
    });
    c.textAlign = 'left';
  }

  // Marca d'água do plano grátis: selo sobre as fotos, cruzando a divisória.
  // Fica em cima das fotos de propósito — é o que o Pro remove.
  function desenharMarcaDagua(c, L) {
    if (PRO) return;
    var texto = T.marca || ('RD OS · ' + SITE);
    var tam = Math.round(26 * L.e);
    c.font = '600 ' + tam + 'px ' + FONTE_TXT;
    var logoH = estado.rdLogo ? tam * 1.6 : 0;
    var logoW = estado.rdLogo ? logoH * largura(estado.rdLogo) / altura(estado.rdLogo) : 0;
    var padX = Math.round(20 * L.e), h = Math.round(Math.max(tam, logoH) + 22 * L.e);
    var w = c.measureText(texto).width + padX * 2 + (logoW ? logoW + 12 * L.e : 0);
    var x = (L.W - w) / 2;
    var y = L.area.y + L.area.h - h - Math.round(26 * L.e);
    if (L.modo === 'pilha') y = L.depois.y - h / 2 - L.gap / 2;
    c.globalAlpha = 0.82;
    c.fillStyle = '#0c2340';
    retanguloArredondado(c, x, y, w, h, h / 2);
    c.fill();
    c.globalAlpha = 1;
    var xt = x + padX;
    if (estado.rdLogo) {
      c.drawImage(estado.rdLogo, xt, y + (h - logoH) / 2, logoW, logoH);
      xt += logoW + 12 * L.e;
    }
    c.fillStyle = '#fff';
    c.textBaseline = 'middle';
    c.fillText(texto, xt, y + h / 2 + 1);
    c.textBaseline = 'alphabetic';
  }

  function seloExemplo(c, L) {
    var texto = T.exemplo || 'EXEMPLO';
    var tam = Math.round(30 * L.e);
    c.font = '700 ' + tam + 'px ' + FONTE_TIT;
    var padX = Math.round(22 * L.e), h = Math.round(tam * 1.6);
    var w = c.measureText(texto).width + padX * 2;
    var x = (L.W - w) / 2, y = L.area.y + L.area.h / 2 - h / 2;
    c.fillStyle = '#ffffff';
    retanguloArredondado(c, x, y, w, h, Math.round(8 * L.e));
    c.fill();
    c.fillStyle = '#0c2340';
    c.textBaseline = 'middle';
    c.fillText(texto, x + padX, y + h / 2 + 1);
    c.textBaseline = 'alphabetic';
  }

  function desenhar(c, fmt) {
    var L = calcularLayout(fmt);
    c.canvas.width = L.W;
    c.canvas.height = L.H;
    c.fillStyle = estado.cores.destaque;              // aparece na divisória entre as fotos
    c.fillRect(0, 0, L.W, L.H);
    ['antes', 'depois'].forEach(function (lado) {
      var r = L[lado];
      if (estado.fotos[lado]) fotoCobrindo(c, estado.fotos[lado], r, estado.ajuste[lado]);
      else vazio(c, r, estado.rotulos[lado], L.e);
    });
    var m = Math.round(26 * L.e);
    if (estado.fotos.antes) pilula(c, L.antes.x + m, L.antes.y + m, estado.rotulos.antes, VERMELHO, L.e);
    if (estado.fotos.depois) pilula(c, L.depois.x + m, L.depois.y + m, estado.rotulos.depois, VERDE, L.e);
    desenharCabecalho(c, L);
    desenharRodape(c, L);
    if (estado.fotos.antes || estado.fotos.depois) desenharMarcaDagua(c, L);
    if (estado.exemplo) seloExemplo(c, L);
    return L;
  }

  var layoutAtual = null;
  var agendado = false;
  // O celular só deixa abrir o compartilhamento logo depois do toque. Por isso a
  // imagem final fica pronta de antemão, a cada mudança, e o botão usa a pronta.
  var versaoArte = 0;
  var imagemPronta = null;          // { v, blob }
  var timerImagem = null;
  function prepararImagem() {
    clearTimeout(timerImagem);
    imagemPronta = null;
    if (estado.exemplo || !(estado.fotos.antes && estado.fotos.depois)) return;
    var v = versaoArte;
    timerImagem = setTimeout(function () {
      gerarBlob().then(function (blob) { if (v === versaoArte && blob) imagemPronta = { v: v, blob: blob }; });
    }, 350);
  }
  function renderizar() {
    if (agendado) return;
    agendado = true;
    var feito = false;
    function executar() {
      if (feito) return;
      feito = true;
      agendado = false;
      layoutAtual = desenhar(ctx, FORMATOS[estado.formato]);
      versaoArte++;
      atualizarBotoes();
      prepararImagem();
      if (!jaGerou && !estado.exemplo && estado.fotos.antes && estado.fotos.depois) {
        jaGerou = true;
        rastrear('gerou_arte', estado.formato);
      }
    }
    requestAnimationFrame(executar);
    setTimeout(executar, 150);   // aba em segundo plano não dispara requestAnimationFrame
  }

  // ------------------------------------------------------------------ interface
  function arteNaTelaPronta() { return !!(estado.fotos.antes && estado.fotos.depois) && !estado.exemplo; }

  function atualizarBotoes() {
    var pronto = arteNaTelaPronta();
    ['ad-baixar', 'ad-compartilhar'].forEach(function (id) {
      var b = $(id);
      if (b) b.disabled = !pronto;
    });
    // o vídeo também sai só com as artes guardadas, mesmo com a tela vazia
    var bv = $('ad-video');
    if (bv) bv.disabled = gravando || !(pronto || (PRO && guardadas.length));
    atualizarSerie();
    var dica = $('ad-dica');
    if (dica) dica.hidden = !pronto;
    ['antes', 'depois'].forEach(function (lado) {
      var bloco = $('ad-ajuste-' + lado);
      if (bloco) bloco.hidden = !estado.fotos[lado] || estado.exemplo;
    });
    // com foto da pessoa, arrastar no quadro enquadra a foto (e não rola a página)
    canvas.classList.toggle('arrastavel', !estado.exemplo && !!(estado.fotos.antes || estado.fotos.depois));
    if (videoPronto && !gravando) {
      videoPronto = null;
      var cxv = $('ad-video-pronto'); if (cxv) cxv.hidden = true;
    }
    var nota = $('ad-nota-exemplo');
    if (nota) nota.hidden = !estado.exemplo;
    var trocar = $('ad-trocar');
    if (trocar) trocar.disabled = estado.exemplo || !(estado.fotos.antes || estado.fotos.depois);
  }

  function sincronizarSliders() {
    ['antes', 'depois'].forEach(function (lado) {
      var aj = estado.ajuste[lado];
      var z = $('ad-zoom-' + lado), x = $('ad-x-' + lado), y = $('ad-y-' + lado);
      if (z) z.value = aj.z;
      if (x) x.value = aj.x;
      if (y) y.value = aj.y;
    });
  }

  function escolherFoto(lado) {
    var input = $('ad-arquivo-' + lado);
    if (input) input.click();
  }

  function aoEscolher(lado, input) {
    var arq = input.files && input.files[0];
    if (!arq) return;
    if (arq.type && !/^image\//.test(arq.type)) { avisar(T.soImagem || 'Escolha um arquivo de imagem.'); input.value = ''; return; }
    carregarArquivo(arq).then(function (img) {
      if (estado.exemplo) {                 // primeira foto da pessoa: sai o exemplo inteiro
        estado.exemplo = false;
        estado.fotos = { antes: null, depois: null };
        estado.ajuste = { antes: { z: 1, x: 0, y: 0 }, depois: { z: 1, x: 0, y: 0 } };
      }
      estado.fotos[lado] = img;
      estado.ajuste[lado] = { z: 1, x: 0, y: 0 };
      sincronizarSliders();
      var mini = $('ad-mini-' + lado);
      if (mini) {
        mini.style.backgroundImage = 'url(' + (img.src || img.toDataURL('image/jpeg', 0.6)) + ')';
        mini.classList.add('tem');
      }
      renderizar();
    }).catch(function () { avisar(T.erroFoto || 'Não consegui abrir essa foto.'); });
    input.value = '';
  }

  // arrastar a foto dentro do seu quadro para ajustar o enquadramento
  var arraste = null;
  function pontoNoCanvas(ev) {
    var r = canvas.getBoundingClientRect();
    return { x: (ev.clientX - r.left) * canvas.width / r.width, y: (ev.clientY - r.top) * canvas.height / r.height };
  }
  function ladoNoPonto(p) {
    if (!layoutAtual) return null;
    var dentro = function (q) { return p.x >= q.x && p.x <= q.x + q.w && p.y >= q.y && p.y <= q.y + q.h; };
    if (dentro(layoutAtual.antes)) return 'antes';
    if (dentro(layoutAtual.depois)) return 'depois';
    return null;
  }
  // Escolher a foto fica no "click": no celular o seletor de arquivos só abre
  // com um toque completo (no pointerdown o primeiro toque falha e rolar a
  // página por cima do quadro abriria a galeria sem querer).
  var ultimoMoveu = false;
  canvas.addEventListener('click', function (ev) {
    if (ultimoMoveu) { ultimoMoveu = false; return; }      // fim de um arraste, não um toque
    var lado = ladoNoPonto(pontoNoCanvas(ev));
    if (lado && (!estado.fotos[lado] || estado.exemplo)) escolherFoto(lado);
  });
  canvas.addEventListener('pointerdown', function (ev) {
    if (arraste || ev.button > 0) return;      // segundo dedo (pinça) ou botão direito
    ultimoMoveu = false;
    var p = pontoNoCanvas(ev), lado = ladoNoPonto(p);
    if (!lado || !estado.fotos[lado] || estado.exemplo) return;
    arraste = { lado: lado, x: p.x, y: p.y, moveu: false, id: ev.pointerId };
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener('pointermove', function (ev) {
    if (!arraste || ev.pointerId !== arraste.id) return;
    var p = pontoNoCanvas(ev);
    var img = estado.fotos[arraste.lado], r = layoutAtual[arraste.lado], aj = estado.ajuste[arraste.lado];
    var s = Math.max(r.w / largura(img), r.h / altura(img)) * aj.z;
    var exX = largura(img) * s - r.w, exY = altura(img) * s - r.h;
    if (exX > 1) aj.x = Math.max(-1, Math.min(1, aj.x - 2 * (p.x - arraste.x) / exX));
    if (exY > 1) aj.y = Math.max(-1, Math.min(1, aj.y - 2 * (p.y - arraste.y) / exY));
    if (Math.abs(p.x - arraste.x) + Math.abs(p.y - arraste.y) > 4) arraste.moveu = true;
    arraste.x = p.x; arraste.y = p.y;
    sincronizarSliders();
    renderizar();
  });
  function fimArraste(ev) {
    if (arraste && ev.pointerId === arraste.id) { ultimoMoveu = arraste.moveu; arraste = null; }
  }
  canvas.addEventListener('pointerup', fimArraste);
  canvas.addEventListener('pointercancel', fimArraste);

  // ------------------------------------------------------------------ saída
  function nomeArquivo(ext) { return (T.arquivo || 'antes-e-depois') + '.' + ext; }

  function gerarBlob() {
    var c = document.createElement('canvas').getContext('2d');
    desenhar(c, FORMATOS[estado.formato]);
    return new Promise(function (ok) { c.canvas.toBlob(ok, 'image/jpeg', 0.92); });
  }

  function baixarBlob(blob, nome) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = nome;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
  }

  function compartilharOuBaixar(blob, nome, tipo) {
    var arquivo = new File([blob], nome, { type: blob.type });
    if (navigator.canShare && navigator.canShare({ files: [arquivo] })) {
      return navigator.share({ files: [arquivo], title: T.tituloCompartilhar || 'Antes e depois' })
        .then(function () { rastrear('compartilhou', tipo); })
        .catch(function (e) {
          if (e && e.name === 'AbortError') return;      // a pessoa fechou a janela
          baixarBlob(blob, nome);
          rastrear('baixou', tipo + ':share-recusado');
        });
    }
    baixarBlob(blob, nome);
    rastrear('baixou', tipo + ':sem-share');
  }

  // ------------------------------------------------------------------ vídeo (Pro)
  function melhorFormatoVideo() {
    if (!window.MediaRecorder) return null;
    var tipos = ['video/mp4;codecs=avc1.42E01E', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm'];
    for (var i = 0; i < tipos.length; i++) if (MediaRecorder.isTypeSupported(tipos[i])) return tipos[i];
    return null;
  }

  // Linha do tempo de cada arte no vídeo: antes parado · cortina revela o depois · depois parado · arte final.
  // Com uma arte só, fica como sempre foi (7 s). Com várias, cada uma é mais curta, para o vídeo de até
  // 10 artes caber no Status do WhatsApp (10 × 5,5 s = 55 s).
  var LINHA_UMA = { antes: 1.5, cortina: 1.1, depois: 1.4, arte: 3, fade: 0.5 };
  var LINHA_VARIAS = { antes: 1.2, cortina: 1.0, depois: 1.0, arte: 2.3, fade: 0.4 };
  function duracaoLinha(L) { return L.antes + L.cortina + L.depois + L.arte; }

  // Desenha o quadro do tempo t (em segundos) de uma arte do vídeo (seg). "anterior" é a arte que veio
  // antes no mesmo vídeo: a arte final dela se dissolve no "antes" desta, nos primeiros instantes.
  function quadroVideo(c, fmt, t, seg, L, anterior) {
    var W = fmt.w, H = fmt.h, e = W / 1080;
    var tela = { x: 0, y: 0, w: W, h: H };
    var s = seg.snap;
    var t1 = L.antes, t2 = L.antes + L.cortina, t3 = t2 + L.depois;
    c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
    var m = Math.round(40 * e);
    if (t < t3) {
      fotoCobrindo(c, s.fotos.antes, tela, { z: 1, x: s.ajuste.antes.x, y: s.ajuste.antes.y });
      var corte = t < t1 ? 0 : t > t2 ? W : W * easing((t - t1) / L.cortina);
      if (corte > 0) {
        c.save(); c.beginPath(); c.rect(0, 0, corte, H); c.clip();
        fotoCobrindo(c, s.fotos.depois, tela, { z: 1, x: s.ajuste.depois.x, y: s.ajuste.depois.y });
        c.restore();
        if (corte < W) { c.fillStyle = s.cores.destaque; c.fillRect(corte - 5 * e, 0, 10 * e, H); }
      }
      var meio = t1 + L.cortina / 2;
      pilula(c, m, m, t < meio ? s.rotulos.antes : s.rotulos.depois, t < meio ? VERMELHO : VERDE, e * 1.25);
      if (anterior && t < L.fade) {
        c.globalAlpha = 1 - t / L.fade;
        c.drawImage(anterior.arte, 0, 0);
        c.globalAlpha = 1;
      }
    } else {
      c.globalAlpha = Math.min(1, (t - t3) / L.fade);
      c.drawImage(seg.arte, 0, 0);
      c.globalAlpha = 1;
    }
  }
  function easing(x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }

  function copiaAjuste(a) { return { z: a.z, x: a.x, y: a.y }; }

  // Tudo o que define uma arte (menos o formato, que é o do vídeo, e a marca, que é a da conta).
  function copiaDaTela() {
    return {
      fotos: { antes: estado.fotos.antes, depois: estado.fotos.depois },
      ajuste: { antes: copiaAjuste(estado.ajuste.antes), depois: copiaAjuste(estado.ajuste.depois) },
      titulo: estado.titulo,
      subtitulo: estado.subtitulo,
      rotulos: { antes: estado.rotulos.antes, depois: estado.rotulos.depois },
      cores: { primaria: estado.cores.primaria, destaque: estado.cores.destaque },
      rodapeMarca: estado.rodapeMarca
    };
  }

  // Desenha uma arte guardada com as funções de sempre: põe os dados dela no lugar dos da tela durante
  // a chamada (que é síncrona) e devolve tudo como estava.
  var CHAVES_ARTE = ['fotos', 'ajuste', 'titulo', 'subtitulo', 'rotulos', 'cores', 'rodapeMarca'];
  function comArte(snap, fn) {
    var salvo = { exemplo: estado.exemplo };
    CHAVES_ARTE.forEach(function (k) { salvo[k] = estado[k]; estado[k] = snap[k]; });
    estado.exemplo = false;
    try { return fn(); } finally {
      CHAVES_ARTE.forEach(function (k) { estado[k] = salvo[k]; });
      estado.exemplo = salvo.exemplo;
    }
  }

  function imagemDoBlob(blob) {
    var url = URL.createObjectURL(blob);
    return carregarImagem(url).then(function (img) { URL.revokeObjectURL(url); return img; },
                                    function (e) { URL.revokeObjectURL(url); throw e; });
  }
  function abrirFoto(blob) {
    if (window.createImageBitmap) return createImageBitmap(blob).catch(function () { return imagemDoBlob(blob); });
    return imagemDoBlob(blob);
  }

  // Deixa uma arte pronta para entrar no vídeo: abre as fotos (se for guardada) e desenha a arte final
  // no formato do vídeo. Só a arte que está tocando, a anterior e a próxima ficam na memória.
  function prepararSegmento(item, fmt) {
    var fotos = item.snap ? Promise.resolve(null) : Promise.all([abrirFoto(item.antes), abrirFoto(item.depois)]);
    return fotos.then(function (par) {
      var snap = item.snap || {
        fotos: { antes: par[0], depois: par[1] }, ajuste: item.ajuste, titulo: item.titulo, subtitulo: item.subtitulo,
        rotulos: item.rotulos, cores: item.cores, rodapeMarca: item.rodapeMarca
      };
      var c = document.createElement('canvas').getContext('2d');
      comArte(snap, function () { desenhar(c, fmt); });
      return { snap: snap, arte: c.canvas, abertas: !item.snap };
    });
  }
  function liberarSegmento(seg) {
    if (!seg || seg.liberado) return;
    seg.liberado = true;
    if (seg.abertas) {
      ['antes', 'depois'].forEach(function (l) { var f = seg.snap.fotos[l]; if (f && f.close) f.close(); });
    }
    seg.arte.width = 0; seg.arte.height = 0;
  }

  // O vídeo junta, nesta ordem, as artes guardadas e a que está na tela (se tiver as duas fotos e
  // ainda couber no limite: com {MAX_ARTES} guardadas, a da tela fica de fora e a página avisa).
  function artesDoVideo() {
    var lista = guardadas.slice();
    if (arteNaTelaPronta() && lista.length < MAX_ARTES) lista.push({ snap: copiaDaTela() });
    return lista;
  }

  function gerarVideo(botao) {
    var tipo = melhorFormatoVideo();
    if (!tipo || !canvas.captureStream) { avisar(T.semVideo || 'Este navegador não grava vídeo. Tente no Chrome.'); return; }
    if (gravando) return;
    var lista = artesDoVideo();
    if (!lista.length) return;
    if (lista.length > MAX_ARTES) {
      avisar(texto(T.limiteVideo || 'O vídeo junta até {max} artes. Tire alguma da lista.', { max: MAX_ARTES }));
      return;
    }
    var fmt = FORMATOS[estado.formato];
    var L = lista.length > 1 ? LINHA_VARIAS : LINHA_UMA;
    var rotulo = $('ad-video-rotulo') || botao;
    gravando = true;
    videoPronto = null;
    var cxAntiga = $('ad-video-pronto'); if (cxAntiga) cxAntiga.hidden = true;
    atualizarBotoes();
    rotulo.textContent = T.gravando || 'Gravando…';
    prepararSegmento(lista[0], fmt).then(function (primeiro) {
      gravar(lista, fmt, L, primeiro, tipo, rotulo);
    }).catch(function () {
      gravando = false;
      atualizarBotoes();
      avisar(T.erroVideo || 'Não consegui montar o vídeo. Tente de novo.');
    });
  }

  function gravar(lista, fmt, L, primeiro, tipo, rotulo) {
    var duracao = duracaoLinha(L);
    var c = document.createElement('canvas');
    c.width = fmt.w; c.height = fmt.h;
    // o Safari só grava canvas que está na página: fica anexado, invisível, durante a gravação
    c.style.cssText = 'position:fixed;left:-99999px;top:0;width:10px;height:10px;opacity:0;pointer-events:none';
    document.body.appendChild(c);
    var cx = c.getContext('2d');
    var atual = primeiro, anterior = null, proximo = null, indice = 0, falhou = false;
    function prepararProximo() {
      proximo = null;
      if (indice + 1 >= lista.length) return;
      var alvo = indice + 1;
      prepararSegmento(lista[alvo], fmt).then(function (s) {
        if (alvo === indice + 1 && gravando) proximo = s; else liberarSegmento(s);
      }).catch(function () { falhou = true; });
    }
    quadroVideo(cx, fmt, 0, atual, L, null);
    var stream = c.captureStream(30);
    var gravador = new MediaRecorder(stream, { mimeType: tipo, videoBitsPerSecond: 6000000 });
    var pedacos = [];
    gravador.ondataavailable = function (ev) { if (ev.data && ev.data.size) pedacos.push(ev.data); };
    var abortado = false;
    function aoSairDaTela() {
      // em segundo plano o navegador para de desenhar e o vídeo sairia cortado
      if (document.hidden && gravador.state === 'recording') { abortado = true; gravador.stop(); }
    }
    document.addEventListener('visibilitychange', aoSairDaTela);
    gravador.onstop = function () {
      gravando = false;
      c.remove();
      stream.getTracks().forEach(function (tr) { tr.stop(); });
      document.removeEventListener('visibilitychange', aoSairDaTela);
      liberarSegmento(anterior); liberarSegmento(atual); liberarSegmento(proximo);
      atualizarBotoes();                    // devolve o rótulo e libera os botões
      if (abortado) { avisoAoVoltar(T.videoInterrompido || 'A gravação parou porque a página saiu da tela. Grave de novo com ela aberta.'); return; }
      if (falhou) { avisar(T.erroVideo || 'Não consegui montar o vídeo. Tente de novo.'); return; }
      var blob = new Blob(pedacos, { type: tipo.split(';')[0] });
      var ext = tipo.indexOf('mp4') >= 0 ? 'mp4' : 'webm';
      rastrear('gerou_video', estado.formato + ':' + ext + ':' + lista.length);
      mostrarVideoPronto(blob, nomeArquivo(ext));
    };
    var inicio = null;
    function passo(ts) {
      if (gravador.state !== 'recording') return;   // gravação interrompida
      if (inicio === null) inicio = ts;
      var t = Math.max(0, (ts - inicio) / 1000);
      if (t >= duracao) {
        if (indice >= lista.length - 1 || falhou) {
          quadroVideo(cx, fmt, duracao, atual, L, anterior);
          gravador.stop();
          return;
        }
        if (proximo) {                       // passa para a próxima arte
          liberarSegmento(anterior);
          anterior = atual; atual = proximo; indice++;
          inicio = ts; t = 0;
          prepararProximo();
        } else {
          t = duracao;                       // a próxima ainda está abrindo: segura a arte final
        }
      }
      quadroVideo(cx, fmt, t, atual, L, anterior);
      proximoQuadro(passo);
    }
    gravador.start(250);
    prepararProximo();
    proximoQuadro(passo);
  }

  // Próximo quadro do vídeo: requestAnimationFrame quando a tela está desenhando; se ele não vier
  // (janela coberta por outra, por exemplo), o temporizador garante que a gravação ande e termine.
  function proximoQuadro(fn) {
    var feito = false;
    function uma() { if (feito) return; feito = true; fn(performance.now()); }
    requestAnimationFrame(uma);
    setTimeout(uma, 33);              // ~30 quadros por segundo, o mesmo do captureStream
  }

  // O vídeo leva 7 s para gravar: depois disso o toque original já "venceu" e o
  // celular não abre o compartilhamento sozinho. A pessoa toca de novo aqui.
  var videoPronto = null;
  var gravando = false;
  function mostrarVideoPronto(blob, nome) {
    videoPronto = { blob: blob, nome: nome };
    var caixa = $('ad-video-pronto');
    if (!caixa) { baixarBlob(blob, nome); return; }
    var btShare = $('ad-video-compartilhar');
    var pode = false;
    try { pode = !!(navigator.canShare && navigator.canShare({ files: [new File([blob], nome, { type: blob.type })] })); } catch (e) {}
    if (btShare) btShare.hidden = !pode;
    caixa.hidden = false;
    avisar(T.videoPronto || 'Vídeo pronto!');
  }

  // ------------------------------------------------------------------ várias artes num vídeo (Pro)
  // A pessoa guarda cada antes e depois do mesmo cliente e grava um vídeo só com todos. As artes guardadas
  // ficam no próprio aparelho (IndexedDB), não vão para o servidor: sobrevivem a recarregar a página (no
  // celular, abrir a câmera às vezes recarrega a aba) até a pessoa tirar ou começar outro cliente.
  var MAX_ARTES = 10;
  var guardadas = [];        // [{ id, antes: Blob, depois: Blob, mini: Blob, miniUrl, ajuste, titulo, subtitulo, rotulos, cores, rodapeMarca }]
  var banco = null;          // IndexedDB; sem ele (aba anônima de alguns navegadores) a lista vive só na memória
  var idMemoria = -1;        // ids negativos = artes que não foram para o banco
  var guardando = false;
  var geracao = 0;           // muda a cada "começar outro cliente": um guardar atrasado não entra na lista nova
  var BANCO = 'rdos-antes-depois', LOJA = 'artes';

  function texto(modelo, valores) {
    return String(modelo || '').replace(/\{(\w+)\}/g, function (m, k) { return valores[k] != null ? valores[k] : m; });
  }

  function abrirBanco() {
    return new Promise(function (ok) {
      if (!window.indexedDB) { ok(null); return; }
      var req;
      try { req = indexedDB.open(BANCO, 1); } catch (e) { ok(null); return; }
      req.onupgradeneeded = function () { req.result.createObjectStore(LOJA, { keyPath: 'id', autoIncrement: true }); };
      req.onsuccess = function () { ok(req.result); };
      req.onerror = function () { ok(null); };
      req.onblocked = function () { ok(null); };
    });
  }

  // Blob vira ArrayBuffer antes de ir ao banco: versões antigas do Safari falham ao guardar Blob.
  function lerBuffer(blob) {
    if (blob.arrayBuffer) return blob.arrayBuffer();
    return new Promise(function (ok, erro) {
      var r = new FileReader();
      r.onload = function () { ok(r.result); };
      r.onerror = function () { erro(r.error); };
      r.readAsArrayBuffer(blob);
    });
  }

  function gravarNoBanco(item) {
    if (!banco) return Promise.resolve(idMemoria--);
    function tentar(b) {
      return new Promise(function (ok, erro) {
        var t, req;
        try {
          t = banco.transaction(LOJA, 'readwrite');
          req = t.objectStore(LOJA).add({
            antes: b[0], depois: b[1], mini: b[2], tipo: 'image/jpeg', ajuste: item.ajuste, titulo: item.titulo,
            subtitulo: item.subtitulo, rotulos: item.rotulos, cores: item.cores, rodapeMarca: item.rodapeMarca, criado: item.criado
          });
        } catch (e) { erro(e); return; }
        t.oncomplete = function () { ok(req.result); };
        t.onerror = t.onabort = function () { erro(t.error); };
      });
    }
    return Promise.all([lerBuffer(item.antes), lerBuffer(item.depois), lerBuffer(item.mini)]).then(function (b) {
      return tentar(b).catch(function () {
        // no iPhone a conexão com o banco cai quando a página vai para o fundo: reabre e tenta mais uma vez
        return abrirBanco().then(function (novo) {
          if (!novo) throw new Error('sem banco');
          banco = novo;
          return tentar(b);
        });
      });
    }).catch(function () { return idMemoria--; });   // banco cheio ou recusado: fica só na memória (e a página avisa)
  }

  function apagarDoBanco(id) {
    if (!banco || id < 0) return;
    try { banco.transaction(LOJA, 'readwrite').objectStore(LOJA)['delete'](id); } catch (e) {}
  }

  function carregarGuardadas() {
    return abrirBanco().then(function (b) {
      banco = b;
      if (!b) return [];
      return new Promise(function (ok) {
        var regs = [];
        try {
          var req = b.transaction(LOJA, 'readonly').objectStore(LOJA).openCursor();
          req.onsuccess = function () {
            var cur = req.result;
            if (cur) { regs.push(cur.value); cur['continue'](); } else ok(regs);
          };
          req.onerror = function () { ok(regs); };
        } catch (e) { ok(regs); }
      });
    }).then(function (regs) {
      regs.forEach(function (r) {
        if (!r || !r.antes || !r.depois || !r.ajuste) return;
        var tipo = r.tipo || 'image/jpeg';
        var item = {
          id: r.id, antes: new Blob([r.antes], { type: tipo }), depois: new Blob([r.depois], { type: tipo }),
          mini: new Blob([r.mini || r.depois], { type: tipo }), ajuste: r.ajuste, titulo: r.titulo || '',
          subtitulo: r.subtitulo || '', rotulos: r.rotulos || { antes: T.antes || 'ANTES', depois: T.depois || 'DEPOIS' },
          cores: r.cores || { primaria: estado.cores.primaria, destaque: estado.cores.destaque },
          rodapeMarca: r.rodapeMarca !== false
        };
        item.miniUrl = URL.createObjectURL(item.mini);
        guardadas.push(item);
      });
    }).catch(function () {}).then(desenharLista);
  }

  function canvasParaBlob(c, qualidade) {
    return new Promise(function (ok, erro) {
      c.toBlob(function (b) { if (b) ok(b); else erro(new Error('toBlob')); }, 'image/jpeg', qualidade);
    });
  }

  // a foto guardada é reduzida a 1920 px: basta para o vídeo e não pesa no aparelho
  function fotoParaBlob(img) {
    var w = largura(img), h = altura(img), s = Math.min(1, 1920 / Math.max(w, h));
    var c = document.createElement('canvas');
    c.width = Math.round(w * s); c.height = Math.round(h * s);
    var cx = c.getContext('2d');
    if (!cx) throw new Error('canvas');     // memória de canvas esgotada (iPhone): cai no aviso de erro
    cx.drawImage(img, 0, 0, c.width, c.height);
    function soltar() { c.width = 0; c.height = 0; }   // devolve a memória do canvas na hora
    return canvasParaBlob(c, 0.9).then(function (b) { soltar(); return b; }, function (e) { soltar(); throw e; });
  }

  function miniatura(snap) {
    var a = document.createElement('canvas').getContext('2d');
    if (!a) throw new Error('canvas');
    comArte(snap, function () { desenhar(a, FORMATOS[estado.formato]); });
    var m = document.createElement('canvas');
    m.width = 200; m.height = Math.round(a.canvas.height * 200 / a.canvas.width);
    var mx = m.getContext('2d');
    if (!mx) { a.canvas.width = 0; throw new Error('canvas'); }
    mx.drawImage(a.canvas, 0, 0, m.width, m.height);
    a.canvas.width = 0;
    return canvasParaBlob(m, 0.8);
  }

  function limparArteDaTela() {
    estado.fotos = { antes: null, depois: null };
    estado.ajuste = { antes: { z: 1, x: 0, y: 0 }, depois: { z: 1, x: 0, y: 0 } };
    sincronizarSliders();
    ['antes', 'depois'].forEach(function (lado) {
      var mini = $('ad-mini-' + lado);
      if (mini) { mini.style.backgroundImage = ''; mini.classList.remove('tem'); }
    });
    renderizar();
  }

  function guardarArte() {
    if (guardando || gravando || !arteNaTelaPronta()) return;
    if (guardadas.length >= MAX_ARTES) {
      avisar(texto(T.serieCheia || 'O vídeo junta até {max} artes.', { max: MAX_ARTES }));
      return;
    }
    guardando = true;
    var minhaGeracao = geracao;
    atualizarBotoes();
    var snap = copiaDaTela();
    // dentro de uma promessa: um erro já no desenho (memória de canvas no iPhone) também cai no catch
    Promise.resolve().then(function () {
      return Promise.all([fotoParaBlob(snap.fotos.antes), fotoParaBlob(snap.fotos.depois), miniatura(snap)]);
    }).then(function (r) {
      var item = {
        antes: r[0], depois: r[1], mini: r[2], ajuste: snap.ajuste, titulo: snap.titulo, subtitulo: snap.subtitulo,
        rotulos: snap.rotulos, cores: snap.cores, rodapeMarca: snap.rodapeMarca, criado: Date.now()
      };
      return gravarNoBanco(item).then(function (id) { item.id = id; return item; });
    }).then(function (item) {
      guardando = false;
      if (minhaGeracao !== geracao) {        // a pessoa começou outro cliente no meio do guardar
        apagarDoBanco(item.id);
        atualizarBotoes();
        return;
      }
      item.miniUrl = URL.createObjectURL(item.mini);
      guardadas.push(item);
      rastrear('guardou_arte', String(guardadas.length));
      limparArteDaTela();                    // a tela fica livre para o próximo antes e depois
      desenharLista();
      var n = guardadas.length, msg;
      if (item.id < 0) msg = T.arteSoNaMemoria || 'Arte {n} guardada só enquanto esta página estiver aberta. Gere o vídeo antes de fechar ou recarregar a página.';
      else if (n >= MAX_ARTES) msg = T.arteGuardadaUltima || 'Arte {n} guardada. O vídeo chegou ao máximo de {max} artes: agora é só gerar.';
      else msg = T.arteGuardada || 'Arte {n} guardada. Escolha as fotos do próximo antes e depois.';
      avisar(texto(msg, { n: n, max: MAX_ARTES }));
    }).catch(function () {
      guardando = false;
      atualizarBotoes();
      avisar(T.erroGuardar || 'Não consegui guardar esta arte. Tente de novo.');
    });
  }

  function tirarArte(id) {
    if (gravando || guardando) return;
    for (var i = 0; i < guardadas.length; i++) {
      if (guardadas[i].id !== id) continue;
      if (!window.confirm(texto(T.confirmaTirar || 'Tirar a arte {n} do vídeo?', { n: i + 1 }))) return;
      URL.revokeObjectURL(guardadas[i].miniUrl);
      guardadas.splice(i, 1);
      apagarDoBanco(id);
      desenharLista();
      return;
    }
  }

  function comecarOutroCliente() {
    if (gravando || guardando || !guardadas.length) return;
    if (!window.confirm(T.confirmaLimpar || 'Apagar as artes guardadas e começar outro cliente?')) return;
    geracao++;
    guardadas.forEach(function (it) { URL.revokeObjectURL(it.miniUrl); });
    guardadas = [];
    if (banco) { try { banco.transaction(LOJA, 'readwrite').objectStore(LOJA).clear(); } catch (e) {} }
    desenharLista();
  }

  function desenharLista() {
    var ol = $('ad-serie-lista');
    if (ol) {
      ol.textContent = '';
      guardadas.forEach(function (item, i) {
        var li = document.createElement('li');
        var img = document.createElement('img');
        img.src = item.miniUrl;
        img.alt = texto(T.arteN || 'Arte {n}', { n: i + 1 });
        var num = document.createElement('span');
        num.className = 'ordem';
        num.textContent = String(i + 1);
        num.setAttribute('aria-hidden', 'true');
        var bt = document.createElement('button');
        bt.type = 'button';
        bt.className = 'tirar';
        bt.textContent = '×';
        bt.setAttribute('aria-label', texto(T.tirarArte || 'Tirar a arte {n} do vídeo', { n: i + 1 }));
        bt.addEventListener('click', function () { tirarArte(item.id); });
        li.appendChild(img); li.appendChild(num); li.appendChild(bt);
        ol.appendChild(li);
      });
      ol.hidden = !guardadas.length;
    }
    atualizarBotoes();
  }

  // estado dos botões e do texto da caixa "várias artes" (chamado por atualizarBotoes)
  var rotuloVideoPadrao = ($('ad-video-rotulo') || {}).textContent || '';
  function atualizarSerie() {
    var pronto = arteNaTelaPronta();
    var n = guardadas.length;
    var cheia = n >= MAX_ARTES;
    var total = n + (pronto && !cheia ? 1 : 0);   // igual a artesDoVideo()
    var rotulo = $('ad-video-rotulo');
    if (rotulo && !gravando) {
      rotulo.textContent = PRO && total > 1 ? texto(T.videoVarias || 'Gerar vídeo com {n} artes', { n: total }) : rotuloVideoPadrao;
    }
    if (!$('ad-serie')) return;
    var bg = $('ad-guardar');
    if (bg) bg.disabled = guardando || gravando || !pronto || cheia;
    var bl = $('ad-serie-limpar');
    if (bl) { bl.hidden = !n; bl.disabled = gravando || guardando; }
    var ol = $('ad-serie-lista');
    if (ol) ol.querySelectorAll('.tirar').forEach(function (b) { b.disabled = gravando || guardando; });
    var info = $('ad-serie-info');
    if (info) {
      if (!n) info.textContent = T.serieVazia || info.textContent;
      else {
        var partes = [];
        if (n === 1) {
          partes.push(T.serieUma || '1 arte guardada.');
          partes.push(pronto ? (T.serieComTelaUma || 'O vídeo junta esta e a que está na tela, nesta ordem.')
                             : (T.serieSemTelaUma || 'O vídeo sai só com ela.'));
        } else {
          partes.push(texto(T.serieVarias || '{n} artes guardadas.', { n: n }));
          partes.push(pronto && !cheia ? (T.serieComTela || 'O vídeo junta estas e a que está na tela, nesta ordem.')
                                       : (T.serieSemTela || 'O vídeo junta estas, nesta ordem.'));
        }
        if (cheia) {
          partes.push(texto(pronto ? (T.serieCheiaTela || 'A arte da tela fica de fora: o vídeo junta até {max} artes.')
                                   : (T.serieCheia || 'O vídeo junta até {max} artes.'), { max: MAX_ARTES }));
        }
        info.textContent = partes.join(' ');
      }
    }
  }

  // ------------------------------------------------------------------ ligações
  function ligar(id, evento, fn) { var el = $(id); if (el) el.addEventListener(evento, fn); }

  ['antes', 'depois'].forEach(function (lado) {
    ligar('ad-escolher-' + lado, 'click', function () { escolherFoto(lado); });
    ligar('ad-arquivo-' + lado, 'change', function (ev) { aoEscolher(lado, ev.target); });
    ligar('ad-zoom-' + lado, 'input', function (ev) { estado.ajuste[lado].z = parseFloat(ev.target.value) || 1; renderizar(); });
    ligar('ad-x-' + lado, 'input', function (ev) { estado.ajuste[lado].x = parseFloat(ev.target.value) || 0; renderizar(); });
    ligar('ad-y-' + lado, 'input', function (ev) { estado.ajuste[lado].y = parseFloat(ev.target.value) || 0; renderizar(); });
    ligar('ad-centralizar-' + lado, 'click', function () {
      estado.ajuste[lado] = { z: 1, x: 0, y: 0 };
      sincronizarSliders();
      renderizar();
    });
  });

  ligar('ad-trocar', 'click', function () {
    if (estado.exemplo) return;
    var f = estado.fotos, a = estado.ajuste;
    estado.fotos = { antes: f.depois, depois: f.antes };
    estado.ajuste = { antes: a.depois, depois: a.antes };
    sincronizarSliders();
    var ma = $('ad-mini-antes'), md = $('ad-mini-depois');
    if (ma && md) {
      var bg = ma.style.backgroundImage; ma.style.backgroundImage = md.style.backgroundImage; md.style.backgroundImage = bg;
      var ta = ma.classList.contains('tem'), td = md.classList.contains('tem');
      ma.classList.toggle('tem', td); md.classList.toggle('tem', ta);
    }
    renderizar();
  });

  document.querySelectorAll('input[name="ad-formato"]').forEach(function (r) {
    r.addEventListener('change', function () { if (r.checked) { estado.formato = r.value; renderizar(); } });
  });
  ligar('ad-titulo', 'input', function (ev) { estado.titulo = ev.target.value.slice(0, 60); renderizar(); });
  ligar('ad-subtitulo', 'input', function (ev) { estado.subtitulo = ev.target.value.slice(0, 80); renderizar(); });
  ligar('ad-rotulo-antes', 'input', function (ev) { estado.rotulos.antes = (ev.target.value || T.antes || 'ANTES').slice(0, 16); renderizar(); });
  ligar('ad-rotulo-depois', 'input', function (ev) { estado.rotulos.depois = (ev.target.value || T.depois || 'DEPOIS').slice(0, 16); renderizar(); });

  if (PRO) {
    ligar('ad-cor-primaria', 'input', function (ev) { estado.cores.primaria = ev.target.value; renderizar(); });
    ligar('ad-cor-destaque', 'input', function (ev) { estado.cores.destaque = ev.target.value; renderizar(); });
    ligar('ad-rodape-marca', 'change', function (ev) { estado.rodapeMarca = ev.target.checked; renderizar(); });
  }

  ligar('ad-baixar', 'click', function () {
    gerarBlob().then(function (blob) { baixarBlob(blob, nomeArquivo('jpg')); rastrear('baixou', estado.formato); });
  });
  ligar('ad-compartilhar', 'click', function () {
    if (imagemPronta && imagemPronta.v === versaoArte) {
      compartilharOuBaixar(imagemPronta.blob, nomeArquivo('jpg'), 'imagem');
      return;
    }
    gerarBlob().then(function (blob) { compartilharOuBaixar(blob, nomeArquivo('jpg'), 'imagem'); });
  });
  ligar('ad-video-compartilhar', 'click', function () {
    if (videoPronto) compartilharOuBaixar(videoPronto.blob, videoPronto.nome, 'video');
  });
  ligar('ad-video-baixar', 'click', function () {
    if (!videoPronto) return;
    baixarBlob(videoPronto.blob, videoPronto.nome);
    rastrear('baixou', 'video');
  });
  ligar('ad-video', 'click', function (ev) {
    if (!PRO) { rastrear('clicou_pro', 'video'); window.location.href = CFG.urlPro; return; }
    gerarVideo(ev.currentTarget);
  });
  if (PRO) {
    ligar('ad-guardar', 'click', guardarArte);
    ligar('ad-serie-limpar', 'click', comecarOutroCliente);
  }
  document.querySelectorAll('.js-pro').forEach(function (el) {
    el.addEventListener('click', function () { rastrear('clicou_pro', el.getAttribute('data-origem') || ''); });
  });

  // ------------------------------------------------------------------ início
  // sem compartilhamento de arquivo (a maioria dos computadores): fica só o Baixar
  (function () {
    var b = $('ad-compartilhar');
    if (!b) return;
    var pode = false;
    try { pode = !!(navigator.canShare && navigator.canShare({ files: [new File([''], 'x.jpg', { type: 'image/jpeg' })] })); } catch (e) {}
    var baixar = $('ad-baixar');
    if (!pode) {
      b.hidden = true;
      if (baixar) baixar.classList.add('largo');
    } else if (baixar && window.matchMedia && matchMedia('(pointer: coarse)').matches) {
      // celular/tablet: no iPhone o Baixar vai para o app Arquivos, não para a galeria
      b.classList.replace('secundario', 'principal');
      baixar.classList.replace('principal', 'secundario');
      b.parentNode.insertBefore(b, baixar);
    }
  })();

  var esperas = [];
  if (CFG.rdLogo) esperas.push(carregarImagem(CFG.rdLogo).then(function (i) { estado.rdLogo = i; }).catch(function () {}));
  if (CFG.exemplo && CFG.exemplo.antes && CFG.exemplo.depois) {
    esperas.push(Promise.all([carregarImagem(CFG.exemplo.antes), carregarImagem(CFG.exemplo.depois)]).then(function (par) {
      if (estado.fotos.antes || estado.fotos.depois) return;   // a pessoa já escolheu uma foto
      estado.fotos = { antes: par[0], depois: par[1] };
      estado.exemplo = true;
    }).catch(function () {}));
  }
  if (PRO && MARCA && MARCA.logo) esperas.push(carregarImagem(MARCA.logo).then(function (i) { estado.logo = i; }).catch(function () {}));
  if (document.fonts && document.fonts.load) {
    esperas.push(document.fonts.load('700 40px Poppins').catch(function () {}));
    esperas.push(document.fonts.load('600 30px Inter').catch(function () {}));
  }
  if (PRO && $('ad-serie')) esperas.push(carregarGuardadas());
  renderizar();
  Promise.all(esperas).then(renderizar);
})();
