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
  var SITE = 'rdos.rdsolucoes.eco.br';

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
      // plano grátis: faixa da RD Soluções
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
      c.font = '500 ' + Math.round(tam * 0.8) + 'px ' + FONTE_TXT;
      c.fillStyle = estado.cores.destaque;
      c.fillText(t2, x, meio + tam * 0.95);
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
    var texto = T.marca || ('RD Soluções · ' + SITE);
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
  function atualizarBotoes() {
    var pronto = !!(estado.fotos.antes && estado.fotos.depois) && !estado.exemplo;
    ['ad-baixar', 'ad-compartilhar', 'ad-video'].forEach(function (id) {
      var b = $(id);
      if (b) b.disabled = !pronto || (id === 'ad-video' && gravando);
    });
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

  // 0–1,5 s antes · 1,5–2,6 s cortina revela o depois · 2,6–4 s depois · 4–7 s arte final
  function quadroVideo(c, fmt, t, arteFinal) {
    var W = fmt.w, H = fmt.h, e = W / 1080;
    var tela = { x: 0, y: 0, w: W, h: H };
    c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
    var m = Math.round(40 * e);
    if (t < 4) {
      fotoCobrindo(c, estado.fotos.antes, tela, { z: 1, x: estado.ajuste.antes.x, y: estado.ajuste.antes.y });
      var corte = t < 1.5 ? 0 : t > 2.6 ? W : W * easing((t - 1.5) / 1.1);
      if (corte > 0) {
        c.save(); c.beginPath(); c.rect(0, 0, corte, H); c.clip();
        fotoCobrindo(c, estado.fotos.depois, tela, { z: 1, x: estado.ajuste.depois.x, y: estado.ajuste.depois.y });
        c.restore();
        if (corte < W) { c.fillStyle = estado.cores.destaque; c.fillRect(corte - 5 * e, 0, 10 * e, H); }
      }
      pilula(c, m, m, t < 2.05 ? estado.rotulos.antes : estado.rotulos.depois, t < 2.05 ? VERMELHO : VERDE, e * 1.25);
    } else {
      c.globalAlpha = Math.min(1, (t - 4) / 0.5);
      c.drawImage(arteFinal, 0, 0);
      c.globalAlpha = 1;
    }
  }
  function easing(x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }

  function gerarVideo(botao) {
    var tipo = melhorFormatoVideo();
    if (!tipo || !canvas.captureStream) { avisar(T.semVideo || 'Este navegador não grava vídeo. Tente no Chrome.'); return; }
    var fmt = FORMATOS[estado.formato];
    var arte = document.createElement('canvas').getContext('2d');
    desenhar(arte, fmt);
    var c = document.createElement('canvas');
    c.width = fmt.w; c.height = fmt.h;
    // o Safari só grava canvas que está na página: fica anexado, invisível, durante a gravação
    c.style.cssText = 'position:fixed;left:-99999px;top:0;width:10px;height:10px;opacity:0;pointer-events:none';
    document.body.appendChild(c);
    var cx = c.getContext('2d');
    quadroVideo(cx, fmt, 0, arte.canvas);
    var stream = c.captureStream(30);
    var gravador = new MediaRecorder(stream, { mimeType: tipo, videoBitsPerSecond: 6000000 });
    var pedacos = [];
    gravador.ondataavailable = function (ev) { if (ev.data && ev.data.size) pedacos.push(ev.data); };
    var versaoInicio = versaoArte;
    videoPronto = null;
    var cxAntiga = $('ad-video-pronto'); if (cxAntiga) cxAntiga.hidden = true;
    var rotulo = $('ad-video-rotulo') || botao;
    var textoOriginal = rotulo.textContent;
    botao.disabled = true;
    rotulo.textContent = T.gravando || 'Gravando…';
    var abortado = false;
    function aoSairDaTela() {
      // em segundo plano o navegador para de desenhar e o vídeo sairia cortado
      if (document.hidden && gravador.state === 'recording') { abortado = true; gravador.stop(); }
    }
    document.addEventListener('visibilitychange', aoSairDaTela);
    gravador.onstop = function () {
      gravando = false;
      c.remove();
      document.removeEventListener('visibilitychange', aoSairDaTela);
      botao.disabled = false;
      rotulo.textContent = textoOriginal;
      if (abortado) { avisoAoVoltar(T.videoInterrompido || 'A gravação parou porque a página saiu da tela. Grave de novo com ela aberta.'); return; }
      if (versaoArte !== versaoInicio) { avisar(T.videoArteMudou || 'A arte mudou durante a gravação. Grave o vídeo de novo.'); return; }
      var blob = new Blob(pedacos, { type: tipo.split(';')[0] });
      var ext = tipo.indexOf('mp4') >= 0 ? 'mp4' : 'webm';
      rastrear('gerou_video', estado.formato + ':' + ext);
      mostrarVideoPronto(blob, nomeArquivo(ext));
    };
    gravando = true;
    var inicio = null, duracao = 7;
    function passo(ts) {
      if (gravador.state !== 'recording') return;   // gravação interrompida
      if (inicio === null) inicio = ts;
      var t = (ts - inicio) / 1000;
      quadroVideo(cx, fmt, Math.min(t, duracao), arte.canvas);
      if (t < duracao) requestAnimationFrame(passo);
      else gravador.stop();
    }
    gravador.start(250);
    requestAnimationFrame(passo);
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
  renderizar();
  Promise.all(esperas).then(renderizar);
})();
