/*!
 * edubot-tracker.js — coleta de interações para o EduBot
 *
 * Inclua no HTML do material:
 *
 *   <script src="edubot-tracker.js"
 *           data-endpoint="http://localhost:5010"
 *           data-key="ek_live_..."></script>
 *
 * e marque o que deve ser rastreado:
 *
 *   <button data-edubot-track="botao-teste">Clique</button>
 *   <button class="edubot-track" id="outro-botao">Clique</button>
 *
 * O script envia para POST {endpoint}/api/v1/collect, em lote. Sem dependências;
 * sintaxe ES5 de propósito, para rodar colado em qualquer página (inclusive
 * conteúdo HTML do Canvas) sem etapa de build.
 *
 * Opções (atributo data-* no <script> ou objeto em EduBotTracker.init):
 *
 *   endpoint      URL base do EduBot (obrigatório)
 *   key           chave de coleta, escopo events:write (obrigatório)
 *   userId        id do usuário no sistema de origem, se houver (data-user-id)
 *   debug         true = loga cada evento no console (data-debug="true")
 *   selector      o que conta como rastreável
 *                 (padrão: "[data-edubot-track], .edubot-track")
 *   autoPageView  envia page_view ao iniciar (padrão true)
 *   autoClicks    captura cliques nos elementos rastreáveis (padrão true)
 *   trackTime     envia page_hidden/page_exit com o tempo visível (padrão true)
 *
 * API:
 *   EduBotTracker.init(opcoes)
 *   EduBotTracker.track(tipo, alvo, contexto)   evento manual
 *   EduBotTracker.identify(userId)
 *   EduBotTracker.flush()
 *   EduBotTracker.getVisitorId()
 *
 * Eventos no document, para quem quiser mostrar o status na página:
 *   "edubot-tracker:sent"   detail = {accepted, errors, rejected}
 *   "edubot-tracker:error"  detail = {status, message}
 */
(function (window, document) {
  'use strict';

  if (window.EduBotTracker && window.EduBotTracker.version) {
    return;
  }

  var VERSION = '0.1.0';
  var BATCH_SIZE = 20;          // o servidor aceita até 50 por requisição
  var FLUSH_MS = 3000;          // lote a cada 3 s enquanto houver fila
  var MAX_QUEUE = 500;          // teto de memória se o servidor ficar fora do ar
  var MAX_BACKOFF_MS = 60000;
  var VISITOR_STORAGE = 'edubot_visitor_id';

  var cfg = {
    endpoint: '',
    key: '',
    userId: null,
    debug: false,
    selector: '[data-edubot-track], .edubot-track',
    autoPageView: true,
    autoClicks: true,
    trackTime: true
  };

  var started = false;
  var queue = [];
  var timer = null;
  var sending = false;
  var backoffMs = FLUSH_MS;
  var visitorId = null;
  var sessionId = null;
  var pageStart = 0;
  var visibleMs = 0;
  var visibleSince = null;
  var exitSent = false;

  // -------------------------------------------------------------------------
  // utilitários
  // -------------------------------------------------------------------------
  function log() {
    if (cfg.debug && window.console) {
      var args = Array.prototype.slice.call(arguments);
      args.unshift('[EduBotTracker]');
      window.console.log.apply(window.console, args);
    }
  }

  function warn(msg) {
    // Erro de configuração aparece mesmo sem debug: chave errada não pode
    // falhar em silêncio.
    if (window.console) { window.console.warn('[EduBotTracker] ' + msg); }
  }

  function now() { return new Date().getTime(); }

  function randomId() {
    var bytes = null;
    try {
      bytes = new Uint8Array(16);
      window.crypto.getRandomValues(bytes);
    } catch (e) {
      bytes = null;
    }
    var out = '';
    for (var i = 0; i < 16; i++) {
      var b = bytes ? bytes[i] : Math.floor(Math.random() * 256);
      out += (b < 16 ? '0' : '') + b.toString(16);
    }
    return out;
  }

  // Dentro de iframe de outro domínio (Canvas) o navegador pode bloquear o
  // storage: o acesso LANÇA exceção. Sem storage o visitante vira um por
  // carregamento — perde-se a continuidade, não o rastreio.
  function storageGet(name) {
    try { return window.localStorage.getItem(name); } catch (e) { return null; }
  }

  function storageSet(name, value) {
    try { window.localStorage.setItem(name, value); } catch (e) { /* sem storage */ }
  }

  function emit(name, detail) {
    try {
      var ev;
      if (typeof window.CustomEvent === 'function') {
        ev = new window.CustomEvent(name, { detail: detail });
      } else {
        ev = document.createEvent('CustomEvent');
        ev.initCustomEvent(name, false, false, detail);
      }
      document.dispatchEvent(ev);
    } catch (e) { /* nada a fazer */ }
  }

  function clip(value, size) {
    if (value === null || value === undefined) { return null; }
    var text = String(value).replace(/\s+/g, ' ').replace(/^\s+|\s+$/g, '');
    return text ? text.slice(0, size) : null;
  }

  function closest(el, selector) {
    while (el && el.nodeType === 1) {
      var matches = el.matches || el.msMatchesSelector || el.webkitMatchesSelector;
      if (matches && matches.call(el, selector)) { return el; }
      el = el.parentNode;
    }
    return null;
  }

  function collectUrl() {
    return cfg.endpoint.replace(/\/+$/, '') + '/api/v1/collect';
  }

  // -------------------------------------------------------------------------
  // fila e envio
  // -------------------------------------------------------------------------
  function enqueue(type, target, context) {
    if (!started) {
      warn('evento "' + type + '" ignorado: chame EduBotTracker.init() antes.');
      return;
    }
    var ev = {
      type: type,
      target: clip(target, 120),
      context: context || null,
      occurred_at: new Date().toISOString()
    };
    queue.push(ev);
    if (queue.length > MAX_QUEUE) { queue.splice(0, queue.length - MAX_QUEUE); }
    log('evento', ev);
    if (queue.length >= BATCH_SIZE) { flush(); } else { schedule(FLUSH_MS); }
  }

  function schedule(ms) {
    if (timer) { return; }
    timer = window.setTimeout(function () {
      timer = null;
      flush();
    }, ms);
  }

  function body(events) {
    return JSON.stringify({
      key: cfg.key,
      visitor_id: visitorId,
      session_id: sessionId,
      user_id: cfg.userId,
      page_url: window.location.href,
      page_title: document.title,
      tracker_version: VERSION,
      events: events
    });
  }

  // Content-Type text/plain e a chave no corpo: é uma "simple request" (sem
  // preflight de CORS) e é o único formato que o sendBeacon consegue mandar.
  function flush() {
    if (!started || sending || !queue.length) { return; }
    if (!window.fetch) {
      warn('navegador sem fetch(): eventos não enviados.');
      return;
    }
    sending = true;
    var batch = queue.splice(0, BATCH_SIZE);
    window.fetch(collectUrl(), {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
      body: body(batch),
      mode: 'cors',
      credentials: 'omit'
    }).then(function (resp) {
      return resp.text().then(function (text) {
        var data = null;
        try { data = JSON.parse(text); } catch (e) { data = null; }
        return { status: resp.status, data: data };
      });
    }).then(function (res) {
      sending = false;
      if (res.status >= 200 && res.status < 300) {
        backoffMs = FLUSH_MS;
        log('enviado', res.data);
        emit('edubot-tracker:sent', res.data || {});
        if (res.data && res.data.errors) {
          warn(res.data.errors + ' evento(s) rejeitado(s): ' + JSON.stringify(res.data.rejected));
        }
        if (queue.length) { schedule(FLUSH_MS); }
        return;
      }
      var message = (res.data && res.data.error) || ('HTTP ' + res.status);
      if (res.status === 429 || res.status >= 500) {
        // Transitório: devolve o lote para a fila e tenta de novo mais tarde.
        retry(batch, res.status, message);
      } else {
        // 400/401/403/413: reenviar não vai mudar nada — descarta e avisa.
        warn('lote descartado (' + res.status + '): ' + message);
        emit('edubot-tracker:error', { status: res.status, message: message });
        if (queue.length) { schedule(FLUSH_MS); }
      }
    }, function (err) {
      sending = false;
      retry(batch, 0, (err && err.message) || 'falha de rede');
    });
  }

  function retry(batch, status, message) {
    queue = batch.concat(queue);
    if (queue.length > MAX_QUEUE) { queue.splice(0, queue.length - MAX_QUEUE); }
    backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
    warn('envio falhou (' + message + '); nova tentativa em ' + Math.round(backoffMs / 1000) + ' s.');
    emit('edubot-tracker:error', { status: status, message: message });
    schedule(backoffMs);
  }

  // Página fechando: não dá para esperar resposta. sendBeacon entrega mesmo
  // depois do unload; fetch com keepalive é o plano B.
  function flushOnExit() {
    if (!started || !queue.length) { return; }
    while (queue.length) {
      var batch = queue.splice(0, BATCH_SIZE);
      var payload = body(batch);
      var ok = false;
      if (window.navigator.sendBeacon) {
        try {
          ok = window.navigator.sendBeacon(collectUrl(),
            new Blob([payload], { type: 'text/plain;charset=UTF-8' }));
        } catch (e) { ok = false; }
      }
      if (!ok && window.fetch) {
        try {
          window.fetch(collectUrl(), {
            method: 'POST', body: payload, keepalive: true, mode: 'cors',
            credentials: 'omit', headers: { 'Content-Type': 'text/plain;charset=UTF-8' }
          });
          ok = true;
        } catch (e2) { ok = false; }
      }
      if (!ok) {
        queue = batch.concat(queue);
        return;
      }
    }
  }

  // -------------------------------------------------------------------------
  // captura automática
  // -------------------------------------------------------------------------
  function targetName(el) {
    return el.getAttribute('data-edubot-track') ||
      el.id ||
      el.getAttribute('name') ||
      clip(el.textContent, 60) ||
      el.tagName.toLowerCase();
  }

  function clickContext(el) {
    var ctx = { tag: el.tagName.toLowerCase() };
    var text = clip(el.textContent, 80);
    if (text) { ctx.text = text; }
    if (el.getAttribute('href')) { ctx.href = clip(el.getAttribute('href'), 300); }
    if (el.value !== undefined && el.value !== '' && el.type !== 'password') {
      ctx.value = clip(el.value, 120);
    }
    // Contexto extra declarado no HTML: data-edubot-context='{"questao": 3}'
    var extra = el.getAttribute('data-edubot-context');
    if (extra) {
      try {
        var parsed = JSON.parse(extra);
        for (var k in parsed) {
          if (Object.prototype.hasOwnProperty.call(parsed, k)) { ctx[k] = parsed[k]; }
        }
      } catch (e) {
        warn('data-edubot-context não é JSON válido em ' + targetName(el));
      }
    }
    return ctx;
  }

  function onClick(e) {
    var el = closest(e.target, cfg.selector);
    if (!el) { return; }
    enqueue('click', targetName(el), clickContext(el));
    // Link que sai da página: manda já, senão o lote morre com a navegação.
    if (el.tagName === 'A' && el.getAttribute('href') && el.target !== '_blank') {
      flushOnExit();
    }
  }

  function visibleSeconds() {
    var total = visibleMs + (visibleSince !== null ? now() - visibleSince : 0);
    return Math.round(total / 1000);
  }

  function onVisibility() {
    if (document.visibilityState === 'hidden') {
      if (visibleSince !== null) {
        visibleMs += now() - visibleSince;
        visibleSince = null;
      }
      // No celular a aba pode morrer sem nunca disparar pagehide: este é o
      // último momento garantido para mandar o que ficou na fila. Se o
      // pagehide já veio (o Chrome dispara antes, ao fechar), o page_exit já
      // levou o tempo — um page_hidden depois dele seria só ruído.
      if (!exitSent) {
        enqueue('page_hidden', null, { visible_seconds: visibleSeconds() });
      }
      flushOnExit();
    } else if (visibleSince === null) {
      visibleSince = now();
    }
  }

  function onPageHide() {
    if (exitSent) { return; }
    exitSent = true;
    enqueue('page_exit', null, {
      visible_seconds: visibleSeconds(),
      total_seconds: Math.round((now() - pageStart) / 1000)
    });
    flushOnExit();
  }

  // -------------------------------------------------------------------------
  // API pública
  // -------------------------------------------------------------------------
  function init(options) {
    if (started) {
      warn('init() chamado de novo; ignorando.');
      return;
    }
    options = options || {};
    for (var k in options) {
      if (Object.prototype.hasOwnProperty.call(options, k) && options[k] !== undefined) {
        cfg[k] = options[k];
      }
    }
    if (!cfg.endpoint || !cfg.key) {
      warn('faltam endpoint e/ou key — rastreio desligado.');
      return;
    }

    visitorId = storageGet(VISITOR_STORAGE);
    if (!visitorId || !/^[A-Za-z0-9_-]{8,64}$/.test(visitorId)) {
      visitorId = randomId();
      storageSet(VISITOR_STORAGE, visitorId);
    }
    sessionId = randomId();
    pageStart = now();
    visibleSince = document.visibilityState === 'hidden' ? null : now();
    started = true;
    log('iniciado', { endpoint: cfg.endpoint, visitor_id: visitorId, session_id: sessionId });

    if (cfg.autoClicks) {
      // Fase de captura: o clique é registrado mesmo que a página faça
      // stopPropagation no próprio botão.
      document.addEventListener('click', onClick, true);
    }
    if (cfg.trackTime) {
      document.addEventListener('visibilitychange', onVisibility);
      window.addEventListener('pagehide', onPageHide);
    }
    if (cfg.autoPageView) {
      enqueue('page_view', null, {
        referrer: clip(document.referrer, 300),
        language: window.navigator.language || null,
        viewport: window.innerWidth + 'x' + window.innerHeight,
        in_iframe: window.self !== window.top
      });
    }
  }

  function track(type, target, context) {
    enqueue(type, target, context);
  }

  function identify(userId) {
    cfg.userId = userId ? String(userId) : null;
    log('identify', cfg.userId);
  }

  window.EduBotTracker = {
    version: VERSION,
    init: init,
    track: track,
    identify: identify,
    flush: flush,
    getVisitorId: function () { return visitorId; }
  };

  // Auto-inicialização pelos atributos do próprio <script>.
  var script = document.currentScript;
  if (script && script.getAttribute('data-key') && script.getAttribute('data-auto') !== 'false') {
    var opts = {
      endpoint: script.getAttribute('data-endpoint') || '',
      key: script.getAttribute('data-key'),
      userId: script.getAttribute('data-user-id') || null,
      debug: script.getAttribute('data-debug') === 'true'
    };
    if (script.getAttribute('data-selector')) { opts.selector = script.getAttribute('data-selector'); }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () { init(opts); });
    } else {
      init(opts);
    }
  }
})(window, document);
