/* Orçamento e ordem de serviço — RD OS Ferramentas.
 *
 * O formulário, a prévia e o rascunho ficam no navegador (localStorage). O PDF
 * é montado no servidor (POST com os dados em JSON) e não fica guardado lá.
 * Configuração em window.RD_DOC = { tipo, pro, marca, urlPdf, urlPro, rastreio }.
 */
(function () {
  'use strict';

  var CFG = window.RD_DOC || {};
  var TIPO = CFG.tipo === 'ordem-de-servico' ? 'ordem-de-servico' : 'orcamento';
  var E_ORC = TIPO === 'orcamento';
  var CHAVE = 'rdos-doc-' + TIPO;
  var CHAVE_NUM = CHAVE + '-ultimo-numero';
  var $ = function (id) { return document.getElementById(id); };
  var form = $('dc-form');
  if (!form) return;

  var brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

  // "1.234,56" | "1234,56" | "1234.56" | "R$ 50" → número
  function numero(txt) {
    var s = String(txt == null ? '' : txt).replace(/R\$|\s| /g, '');
    if (!s) return 0;
    if (s.indexOf(',') >= 0) s = s.replace(/\./g, '').replace(',', '.');
    else if (/\.\d{3}$/.test(s)) s = s.replace(/\./g, '');
    var n = parseFloat(s);
    return isFinite(n) && n > 0 ? n : 0;
  }

  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function escBr(v) { return esc(v).replace(/\n/g, '<br>'); }

  function ler(chave) { try { return localStorage.getItem(chave); } catch (e) { return null; } }
  function gravar(chave, valor) { try { localStorage.setItem(chave, valor); } catch (e) {} }
  function apagar(chave) { try { localStorage.removeItem(chave); } catch (e) {} }

  function avisar(msg) {
    var el = $('dc-aviso');
    if (!el) { alert(msg); return; }
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(avisar.t);
    avisar.t = setTimeout(function () { el.hidden = true; }, 7000);
  }

  function rastrear(tipo, detalhe) {
    var r = CFG.rastreio || {};
    if (!r.ativo || !r.url) return;
    var p = new URLSearchParams({ produto: 'ferramentas', tipo: tipo, slug: TIPO });
    if (detalhe) p.set('detalhe', String(detalhe).slice(0, 300));
    try {
      if (navigator.sendBeacon) navigator.sendBeacon(r.url, p);
      else fetch(r.url, { method: 'POST', body: p, keepalive: true }).catch(function () {});
    } catch (e) {}
  }

  // ------------------------------------------------------------------ itens
  var lista = $('dc-itens');
  var modelo = $('dc-item-modelo');

  function novaLinha(item) {
    var frag = modelo.content.cloneNode(true);
    var linha = frag.querySelector('.item-linha');
    if (item) {
      linha.querySelector('.it-desc').value = item.descricao || '';
      linha.querySelector('.it-qtd').value = item.quantidade || '1';
      linha.querySelector('.it-valor').value = item.valor || '';
    }
    linha.querySelector('.it-remover').addEventListener('click', function () {
      linha.remove();
      if (!lista.children.length) novaLinha();
      atualizar();
    });
    lista.appendChild(linha);
    return linha;
  }

  function itens() {
    return Array.prototype.map.call(lista.querySelectorAll('.item-linha'), function (l) {
      return {
        descricao: l.querySelector('.it-desc').value.trim(),
        quantidade: l.querySelector('.it-qtd').value.trim(),
        valor: l.querySelector('.it-valor').value.trim()
      };
    });
  }

  // ------------------------------------------------------------------ dados
  function dados() {
    var d = {};
    form.querySelectorAll('[data-campo]').forEach(function (el) {
      d[el.getAttribute('data-campo')] = el.type === 'checkbox' ? el.checked : el.value;
    });
    d.itens = itens().filter(function (i) { return i.descricao; });
    return d;
  }

  function totais(d) {
    var pecas = 0;
    d.itens.forEach(function (i) { pecas += (numero(i.quantidade) || (i.quantidade ? 0 : 1)) * numero(i.valor); });
    if (E_ORC) {
      var desc = numero(d.desconto);
      return { subtotal: pecas, desconto: Math.min(desc, pecas), total: Math.max(0, pecas - desc) };
    }
    var mao = numero(d.mao_de_obra);
    return { pecas: pecas, mao: mao, total: pecas + mao };
  }

  // ------------------------------------------------------------------ prévia
  function dataBr(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    return m ? m[3] + '/' + m[2] + '/' + m[1] : '';
  }
  function somarDias(iso, dias) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    if (!m || !dias) return '';
    var dt = new Date(+m[1], +m[2] - 1, +m[3] + dias);
    return ('0' + dt.getDate()).slice(-2) + '/' + ('0' + (dt.getMonth() + 1)).slice(-2) + '/' + dt.getFullYear();
  }

  function par(rotulo, valor) { return valor ? '<p><b>' + esc(rotulo) + ':</b> ' + esc(valor) + '</p>' : ''; }
  function bloco(titulo, texto) { return texto ? '<h4>' + esc(titulo) + '</h4><p>' + escBr(texto) + '</p>' : ''; }

  function renderPrevia() {
    var d = dados(), t = totais(d), m = CFG.pro ? (CFG.marca || {}) : null;
    var cor = m && m.corPrimaria ? m.corPrimaria : '#0c2340';
    var titulo = E_ORC ? 'ORÇAMENTO' : 'ORDEM DE SERVIÇO';
    var h = '<div class="papel-cab" style="border-color:' + esc(cor) + '">';
    if (m) {
      h += '<div class="papel-emp">' + (m.logo ? '<img src="' + esc(m.logo) + '" alt="">' : '') +
        '<div><b>' + esc(m.empresa || 'Nome da sua empresa') + '</b>' +
        (m.cnpj ? '<span>CNPJ/CPF: ' + esc(m.cnpj) + '</span>' : '') +
        '<span>' + esc([m.telefone, m.email].filter(Boolean).join(' · ')) + '</span></div></div>';
    } else {
      h += '<div class="papel-emp gratis"><b>RD OS</b><span>Gerado grátis em rdos.rdsolucoes.eco.br</span></div>';
    }
    h += '<div class="papel-tit"><strong style="color:' + esc(cor) + '">' + titulo + '</strong>' +
      (d.numero ? '<span>Nº ' + esc(d.numero) + '</span>' : '') + '<small>' + esc(dataBr(d.data)) + '</small></div></div>';

    h += '<h4 style="color:' + esc(cor) + '">Cliente</h4>' +
      (d.cliente_nome || d.cliente_telefone || d.cliente_endereco
        ? par('Nome', d.cliente_nome) + par('Telefone', d.cliente_telefone) + par('CPF/CNPJ', d.cliente_documento) +
          par('Endereço', d.cliente_endereco) + (E_ORC ? '' : par('Responsável', d.responsavel))
        : '<p class="vazio">Preencha os dados do cliente</p>');

    if (E_ORC) h += bloco('Serviço', d.descricao);
    else h += bloco('Equipamento / local', d.equipamento) + bloco('Serviço solicitado', d.solicitado) + bloco('Serviço executado', d.executado);

    if (d.itens.length) {
      h += '<table><thead style="background:' + esc(cor) + '"><tr><th>Descrição</th><th>Qtd.</th><th>Total</th></tr></thead><tbody>';
      d.itens.forEach(function (i) {
        var q = numero(i.quantidade) || 1;
        h += '<tr><td>' + esc(i.descricao) + '</td><td>' + esc(String(q).replace('.', ',')) + '</td><td>' + brl.format(q * numero(i.valor)) + '</td></tr>';
      });
      h += '</tbody></table>';
    }
    if (E_ORC) {
      if (t.desconto) h += '<p class="linha-total">Desconto: − ' + brl.format(t.desconto) + '</p>';
      h += '<p class="linha-total forte" style="color:' + esc(cor) + '">Total: ' + brl.format(t.total) + '</p>';
      var validade = somarDias(d.data, parseInt(d.validade_dias, 10) || 0);
      h += (validade || d.prazo || d.pagamento || d.garantia ? '<h4 style="color:' + esc(cor) + '">Condições</h4>' : '') +
        par('Válido até', validade) + par('Prazo', d.prazo) + par('Pagamento', d.pagamento) + par('Garantia', d.garantia);
    } else {
      if (t.mao || t.pecas) h += '<p class="linha-total forte" style="color:' + esc(cor) + '">Total: ' + brl.format(t.total) + '</p>';
      h += par('Entrada', d.entrada) + par('Saída', d.saida) + par('Técnico', d.tecnico) + par('Garantia', d.garantia);
    }
    h += bloco('Observações', d.observacoes);
    if (m && m.condicoes && E_ORC) h += '<div class="papel-cond">' + escBr(m.condicoes) + '</div>';
    h += '<div class="papel-ass"><span>' + (E_ORC ? 'Aprovação do cliente' : 'Técnico responsável') + '</span><span>' +
      (E_ORC ? 'Data' : 'Cliente / responsável') + '</span></div>';
    h += '<p class="papel-rodape">' + (m ? esc([m.empresa, m.cnpj ? 'CNPJ/CPF ' + m.cnpj : '', m.site].filter(Boolean).join(' | '))
      : 'Gerado grátis com RD OS · com o Pro, sai com a sua logomarca') + '</p>';
    if (!m) h += '<span class="papel-selo" aria-hidden="true">RD OS · versão grátis</span>';
    $('dc-previa').innerHTML = h;

    var total = brl.format(t.total);
    $('dc-total').textContent = total;
    var tb = $('dc-total-barra'); if (tb) tb.textContent = total;
    lista.querySelectorAll('.item-linha').forEach(function (l) {
      var q = numero(l.querySelector('.it-qtd').value) || 1;
      l.querySelector('.it-total').textContent = brl.format(q * numero(l.querySelector('.it-valor').value));
    });
  }

  // ------------------------------------------------------------------ rascunho
  var timerRascunho = null;
  function salvarRascunho() {
    clearTimeout(timerRascunho);
    timerRascunho = setTimeout(function () {
      var d = dados();
      d.itens = itens();
      gravar(CHAVE, JSON.stringify(d));
    }, 400);
  }

  function preencher(d) {
    form.querySelectorAll('[data-campo]').forEach(function (el) {
      var k = el.getAttribute('data-campo');
      if (!(k in d)) return;
      if (el.type === 'checkbox') el.checked = !!d[k];
      else el.value = d[k] == null ? '' : d[k];
    });
    lista.innerHTML = '';
    (d.itens && d.itens.length ? d.itens : [null]).forEach(function (i) { novaLinha(i); });
  }

  function hojeIso() {
    var dt = new Date();
    return dt.getFullYear() + '-' + ('0' + (dt.getMonth() + 1)).slice(-2) + '-' + ('0' + dt.getDate()).slice(-2);
  }
  function proximoNumero() {
    var ultimo = parseInt(ler(CHAVE_NUM) || '0', 10) || 0;
    return ('000' + (ultimo + 1)).slice(-4);
  }

  function documentoNovo(manterCliente) {
    var atual = dados();
    var base = { numero: proximoNumero(), data: hojeIso(), itens: [] };
    if (E_ORC) base.validade_dias = atual.validade_dias || '15';
    if (manterCliente) {
      ['prazo', 'pagamento', 'garantia', 'tecnico'].forEach(function (k) { if (atual[k]) base[k] = atual[k]; });
    }
    form.reset();
    preencher(base);
    esconderPronto();
    atualizar();
  }

  // ------------------------------------------------------------------ PDF
  var pdfPronto = null;       // { blob, nome, url }
  function esconderPronto() {
    var box = $('dc-pronto'); if (box) box.hidden = true;
    if (pdfPronto && pdfPronto.url) URL.revokeObjectURL(pdfPronto.url);
    pdfPronto = null;
  }

  function podeCompartilhar(arquivo) {
    try { return !!(navigator.canShare && navigator.canShare({ files: [arquivo] })); } catch (e) { return false; }
  }

  function baixar(blob, nome) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = nome;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
  }

  var gerando = false;
  function gerarPdf() {
    if (gerando) return;
    var d = dados();
    if (!d.cliente_nome && !d.itens.length && !(d.executado || d.solicitado || d.descricao)) {
      avisar('Preencha pelo menos o cliente ou um item antes de gerar o PDF.');
      return;
    }
    var token = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
    gerando = true;
    var botoes = [$('dc-gerar'), $('dc-gerar-barra')];
    botoes.forEach(function (b) { if (b) b.disabled = true; });
    var rotulo = $('dc-gerar-rotulo'); var original = rotulo ? rotulo.textContent : '';
    if (rotulo) rotulo.textContent = 'Gerando o PDF…';
    fetch(CFG.urlPdf, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
      body: JSON.stringify(d)
    }).then(function (r) {
      if (!r.ok) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          var msg = j.erro || (r.status === 400 ? 'A página ficou aberta muito tempo. Recarregue e tente de novo.'
            : r.status === 429 ? 'Muitos PDFs em pouco tempo. Espere um minuto e tente de novo.'
            : 'Não consegui gerar o PDF agora. Tente de novo.');
          throw new Error(msg);
        });
      }
      return r.blob();
    }).then(function (blob) {
      esconderPronto();
      var num = (d.numero || '').replace(/[^0-9A-Za-z-]/g, '');
      var nome = (E_ORC ? 'orcamento' : 'ordem-de-servico') + (num ? '-' + num : '') + '.pdf';
      pdfPronto = { blob: blob, nome: nome, url: URL.createObjectURL(blob) };
      var arquivo = new File([blob], nome, { type: 'application/pdf' });
      var bt = $('dc-compartilhar');
      if (bt) bt.hidden = !podeCompartilhar(arquivo);
      $('dc-pronto').hidden = false;
      $('dc-pronto').scrollIntoView({ behavior: 'smooth', block: 'center' });
      var n = parseInt(num, 10);
      if (n && n > (parseInt(ler(CHAVE_NUM) || '0', 10) || 0)) gravar(CHAVE_NUM, String(n));
    }).catch(function (e) {
      avisar(e.message || 'Não consegui gerar o PDF agora. Tente de novo.');
    }).then(function () {
      gerando = false;
      botoes.forEach(function (b) { if (b) b.disabled = false; });
      if (rotulo) rotulo.textContent = original;
    });
  }

  // ------------------------------------------------------------------ ligações
  function atualizar() { renderPrevia(); salvarRascunho(); }

  form.addEventListener('input', function () { esconderPronto(); atualizar(); });
  form.addEventListener('change', function () { esconderPronto(); atualizar(); });
  $('dc-add-item').addEventListener('click', function () {
    var l = novaLinha();
    l.querySelector('.it-desc').focus();
    atualizar();
  });
  $('dc-gerar').addEventListener('click', gerarPdf);
  var gb = $('dc-gerar-barra'); if (gb) gb.addEventListener('click', gerarPdf);

  $('dc-compartilhar').addEventListener('click', function () {
    if (!pdfPronto) return;
    var arquivo = new File([pdfPronto.blob], pdfPronto.nome, { type: 'application/pdf' });
    navigator.share({ files: [arquivo], title: pdfPronto.nome })
      .then(function () { rastrear('compartilhou_pdf'); })
      .catch(function (e) { if (!e || e.name !== 'AbortError') { baixar(pdfPronto.blob, pdfPronto.nome); rastrear('baixou_pdf', 'share-recusado'); } });
  });
  $('dc-baixar').addEventListener('click', function () {
    if (!pdfPronto) return;
    baixar(pdfPronto.blob, pdfPronto.nome);
    rastrear('baixou_pdf');
  });
  $('dc-abrir').addEventListener('click', function () {
    if (!pdfPronto) return;
    window.open(pdfPronto.url, '_blank', 'noopener');
  });
  $('dc-novo').addEventListener('click', function () { documentoNovo(true); });
  $('dc-limpar').addEventListener('click', function () {
    if (!confirm('Apagar tudo o que foi preenchido neste documento?')) return;
    apagar(CHAVE);
    documentoNovo(false);
  });
  document.querySelectorAll('.js-pro').forEach(function (el) {
    el.addEventListener('click', function () { rastrear('clicou_pro', el.getAttribute('data-origem') || TIPO); });
  });

  // a barra fixa com o total aparece no celular quando o botão principal sai da tela
  var barra = $('dc-barra'), botaoPrincipal = $('dc-gerar');
  if (barra && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (ents) {
      barra.classList.toggle('visivel', !ents[0].isIntersecting);
    }).observe(botaoPrincipal);
  }

  // ------------------------------------------------------------------ início
  var salvo = null;
  try { salvo = JSON.parse(ler(CHAVE) || 'null'); } catch (e) { salvo = null; }
  if (salvo && typeof salvo === 'object') {
    preencher(salvo);
    if (!salvo.data) $('dc-data').value = hojeIso();
  } else {
    preencher({ numero: proximoNumero(), data: hojeIso(), itens: [] });
  }
  renderPrevia();
})();
