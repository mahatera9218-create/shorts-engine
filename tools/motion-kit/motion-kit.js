/*!
 * Motion Kit v1.0
 * 웹앱용 모션 프리셋 + 화면 옆 조절 패널. 의존성 없음, 파일 하나.
 *
 * 쓰는 법
 *   <script src="/motion-kit.js"></script>          ← 페이지 맨 아래(또는 Next.js <Script>)
 *   <button data-motion="press">구독</button>       ← 움직일 요소에 속성 추가
 *   주소 뒤에 ?motion 을 붙이거나 Alt+M 을 누르면 조절 패널이 열린다.
 *   배포할 때 패널을 끄려면: <script src="/motion-kit.js" data-panel="off"></script>
 *
 * License: MIT
 */
(function () {
  'use strict';
  if (typeof window === 'undefined' || window.MotionKit) return;

  var VERSION = '1.0.0';
  var SCRIPT = document.currentScript;
  var PANEL_MODE = (SCRIPT && SCRIPT.getAttribute('data-panel')) || 'auto';
  // 북마크로 실행: 프로젝트에 파일이 없으니 패널을 바로 열고, 내보내기는 '라이브러리 없이'가 기본
  var BOOKMARK = !!window.__MK_BM;
  if (BOOKMARK) PANEL_MODE = 'open';

  /* ------------------------------------------------------------------ */
  /* 곡선                                                                */
  /* ------------------------------------------------------------------ */
  var EASES = {
    'ease-out': 'cubic-bezier(.16,1,.3,1)',
    'ease-in-out': 'cubic-bezier(.65,0,.35,1)',
    'ease-in': 'cubic-bezier(.55,0,1,.45)',
    'overshoot': 'cubic-bezier(.34,1.56,.64,1)',
    'anticipation': 'cubic-bezier(.55,-.45,.35,1)',
    'snap': 'cubic-bezier(.2,.8,.2,1)',
    'linear': 'linear'
  };
  var EASE_KR = {
    'ease-out': 'Ease Out · 빠르게 출발, 살살 멈춤',
    'ease-in-out': 'Ease In-Out · 천천히-빠르게-천천히',
    'ease-in': 'Ease In · 천천히 출발 (나갈 때)',
    'overshoot': 'Overshoot · 살짝 넘었다 복귀',
    'anticipation': 'Anticipation · 움츠렸다 출발',
    'snap': 'Snap · 딱 맞춰 멈춤',
    'linear': 'Linear · 일정한 속도'
  };
  function easeCss(e) { return EASES[e] || e || EASES['ease-out']; }

  // JS로 움직이는 효과(숫자·타이핑)용 cubic-bezier 계산
  function easeFn(e) {
    var css = easeCss(e);
    if (css === 'linear') return function (t) { return t; };
    var m = /cubic-bezier\(([^)]+)\)/.exec(css);
    if (!m) return function (t) { return 1 - Math.pow(1 - t, 3); };
    var v = m[1].split(',').map(parseFloat);
    var x1 = v[0], y1 = v[1], x2 = v[2], y2 = v[3];
    function bx(t) { return 3 * x1 * t * (1 - t) * (1 - t) + 3 * x2 * t * t * (1 - t) + t * t * t; }
    function by(t) { return 3 * y1 * t * (1 - t) * (1 - t) + 3 * y2 * t * t * (1 - t) + t * t * t; }
    return function (x) {
      if (x <= 0) return 0; if (x >= 1) return 1;
      var lo = 0, hi = 1, t = x;
      for (var i = 0; i < 24; i++) { var cx = bx(t); if (Math.abs(cx - x) < 1e-4) break; if (cx < x) lo = t; else hi = t; t = (lo + hi) / 2; }
      return by(t);
    };
  }

  /* ------------------------------------------------------------------ */
  /* 프리셋                                                              */
  /* g: appear(나타나기) press(누르기) hover(마우스) loop(반복) scroll   */
  /* k: 키프레임, s: 특수 동작, h: 사람이 읽는 설명(AI 지시문용)          */
  /* ------------------------------------------------------------------ */
  var P = {};
  function def(name, o) { o.name = name; P[name] = o; }
  def('fade',       { g: 'appear', kr: '페이드', d: 300, e: 'ease-out', h: '투명했다가 서서히 보임', k: [{ opacity: 0 }, { opacity: 1 }] });
  def('fade-up',    { g: 'appear', kr: '떠오르기', d: 400, e: 'ease-out', h: '아래에서 16px 올라오며 서서히 보임', k: [{ opacity: 0, transform: 'translateY(16px)' }, { opacity: 1, transform: 'none' }] });
  def('fade-down',  { g: 'appear', kr: '내려오기', d: 400, e: 'ease-out', h: '위에서 16px 내려오며 서서히 보임', k: [{ opacity: 0, transform: 'translateY(-16px)' }, { opacity: 1, transform: 'none' }] });
  def('slide-left', { g: 'appear', kr: '오른쪽에서 들어오기', d: 450, e: 'ease-out', h: '오른쪽 40px 밖에서 미끄러져 들어옴', k: [{ opacity: 0, transform: 'translateX(40px)' }, { opacity: 1, transform: 'none' }] });
  def('slide-right',{ g: 'appear', kr: '왼쪽에서 들어오기', d: 450, e: 'ease-out', h: '왼쪽 40px 밖에서 미끄러져 들어옴', k: [{ opacity: 0, transform: 'translateX(-40px)' }, { opacity: 1, transform: 'none' }] });
  def('scale-in',   { g: 'appear', kr: '커지며 나타나기', d: 350, e: 'ease-out', h: '92% 크기에서 원래 크기로 커지며 보임', k: [{ opacity: 0, transform: 'scale(.92)' }, { opacity: 1, transform: 'none' }] });
  def('pop',        { g: 'appear', kr: '톡 튀어나오기', d: 450, e: 'overshoot', h: '작게 시작해 원래 크기를 살짝 넘었다 돌아옴', k: [{ opacity: 0, transform: 'scale(.5)' }, { opacity: 1, transform: 'none' }] });
  def('blur-in',    { g: 'appear', kr: '흐림에서 선명하게', d: 500, e: 'ease-out', h: '흐릿하게 시작해 선명해짐', k: [{ opacity: 0, filter: 'blur(10px)' }, { opacity: 1, filter: 'blur(0)' }] });
  def('mask-up',    { g: 'appear', kr: '아래부터 드러나기', d: 600, e: 'ease-out', h: '보이지 않는 창이 아래에서 위로 열리며 드러남', k: [{ clipPath: 'inset(100% 0 0 0)' }, { clipPath: 'inset(0 0 0 0)' }] });
  def('wipe-right', { g: 'appear', kr: '와이프', d: 600, e: 'ease-in-out', h: '왼쪽에서 오른쪽으로 쓸며 드러남', k: [{ clipPath: 'inset(0 100% 0 0)' }, { clipPath: 'inset(0 0 0 0)' }] });
  def('iris',       { g: 'appear', kr: '원형으로 열리기', d: 600, e: 'ease-in-out', h: '가운데 원이 커지며 드러남', k: [{ clipPath: 'circle(0% at 50% 50%)' }, { clipPath: 'circle(75% at 50% 50%)' }] });
  def('stagger',    { g: 'appear', kr: '자식 차례로 나타나기', d: 400, e: 'ease-out', gap: 60, s: 'stagger', h: '안에 있는 항목들이 차례로 아래에서 올라오며 보임' });
  def('type-on',    { g: 'appear', kr: '타이핑', d: 1200, e: 'linear', s: 'type', h: '글자가 한 자씩 찍힘' });
  def('count-up',   { g: 'appear', kr: '숫자 올라가기', d: 1200, e: 'ease-out', s: 'count', h: '숫자가 0부터 적힌 값까지 올라감' });

  def('press',      { g: 'press', kr: '눌림', d: 180, e: 'ease-out', h: '95% 크기로 살짝 줄었다 돌아옴', k: [{ transform: 'scale(1)' }, { transform: 'scale(.95)', offset: 0.35 }, { transform: 'scale(1)' }] });
  def('squash',     { g: 'press', kr: '말랑 눌림', d: 450, e: 'ease-out', h: '납작해졌다 길쭉해졌다 돌아오는 말랑한 눌림', k: [{ transform: 'scale(1,1)' }, { transform: 'scale(1.08,.9)', offset: 0.3 }, { transform: 'scale(.97,1.04)', offset: 0.6 }, { transform: 'scale(1,1)' }] });
  def('like-pop',   { g: 'press', kr: '좋아요 팝', d: 450, e: 'ease-out', h: '130%까지 커졌다 살짝 작아졌다 원래 크기', k: [{ transform: 'scale(1)' }, { transform: 'scale(1.3)', offset: 0.4 }, { transform: 'scale(.92)', offset: 0.7 }, { transform: 'scale(1)' }] });
  def('ripple',     { g: 'press', kr: '물결', d: 550, e: 'ease-out', s: 'ripple', h: '누른 자리에서 동그란 물결이 퍼지며 사라짐' });
  def('shake',      { g: 'press', kr: '오류 흔들림', d: 400, e: 'linear', h: '좌우로 3번, 점점 작게 흔들림', k: [{ transform: 'none' }, { transform: 'translateX(-8px)', offset: 0.15 }, { transform: 'translateX(8px)', offset: 0.3 }, { transform: 'translateX(-6px)', offset: 0.45 }, { transform: 'translateX(6px)', offset: 0.6 }, { transform: 'translateX(-3px)', offset: 0.75 }, { transform: 'none' }] });

  def('lift',       { g: 'hover', kr: '떠오르는 호버', d: 200, e: 'ease-out', h: '4px 위로 뜨고 그림자가 짙어짐', k: [{ transform: 'none', boxShadow: '0 0 0 rgba(0,0,0,0)' }, { transform: 'translateY(-4px)', boxShadow: '0 10px 24px rgba(0,0,0,.15)' }] });
  def('grow',       { g: 'hover', kr: '살짝 커지기', d: 200, e: 'ease-out', h: '104% 크기로 커짐', k: [{ transform: 'none' }, { transform: 'scale(1.04)' }] });

  def('pulse',      { g: 'loop', kr: '두근두근', d: 1200, e: 'ease-in-out', alt: true, h: '106% 크기로 커졌다 작아지기를 반복', k: [{ transform: 'scale(1)', opacity: 1 }, { transform: 'scale(1.06)', opacity: 0.85 }] });
  def('float',      { g: 'loop', kr: '둥둥', d: 1800, e: 'ease-in-out', alt: true, h: '6px 위아래로 떠다니기를 반복', k: [{ transform: 'translateY(0)' }, { transform: 'translateY(-6px)' }] });
  def('spin',       { g: 'loop', kr: '회전(로딩)', d: 800, e: 'linear', h: '한 바퀴씩 계속 회전', k: [{ transform: 'rotate(0deg)' }, { transform: 'rotate(360deg)' }] });
  def('wiggle',     { g: 'loop', kr: '흔들흔들(알림)', d: 1600, e: 'ease-in-out', h: '잠깐 좌우로 흔들리고 쉬기를 반복', k: [{ transform: 'rotate(0)' }, { transform: 'rotate(12deg)', offset: 0.06 }, { transform: 'rotate(-10deg)', offset: 0.12 }, { transform: 'rotate(6deg)', offset: 0.18 }, { transform: 'rotate(0)', offset: 0.24 }, { transform: 'rotate(0)' }] });

  def('parallax',   { g: 'scroll', kr: '패럴랙스', d: 0, e: 'linear', s: 'parallax', speed: 0.3, h: '스크롤할 때 다른 내용보다 느리게 움직임' });

  var GROUP_KR = { appear: '나타나기', press: '누르기 반응', hover: '마우스 올리기', loop: '계속 반복', scroll: '스크롤 연동' };
  var DEF_TRIGGER = { appear: 'scroll', press: 'press', hover: 'hover', loop: 'loop', scroll: 'scroll-link' };
  var TRIGGER_KR = { scroll: '화면에 보일 때', load: '페이지 열릴 때', press: '누를 때', hover: '마우스 올릴 때', loop: '계속 반복', 'scroll-link': '스크롤할 때' };
  function triggersFor(p) {
    if (p.s === 'parallax') return ['scroll-link'];
    if (p.s === 'ripple') return ['press'];
    if (p.s) return ['scroll', 'load', 'press'];
    return ['scroll', 'load', 'press', 'hover', 'loop'];
  }

  /* ------------------------------------------------------------------ */
  /* 설정 읽기                                                            */
  /* ------------------------------------------------------------------ */
  var ATTRS = ['data-motion', 'data-motion-trigger', 'data-motion-duration', 'data-motion-delay', 'data-motion-ease', 'data-motion-stagger', 'data-motion-speed', 'data-motion-repeat'];
  function num(v, d) { var n = parseFloat(v); return isFinite(n) ? n : d; }
  function readCfg(el) {
    var p = P[el.getAttribute('data-motion')];
    if (!p) return null;
    var t = el.getAttribute('data-motion-trigger');
    if (triggersFor(p).indexOf(t) < 0) t = DEF_TRIGGER[p.g];
    return {
      p: p, trigger: t,
      duration: num(el.getAttribute('data-motion-duration'), p.d),
      delay: num(el.getAttribute('data-motion-delay'), 0),
      ease: el.getAttribute('data-motion-ease') || p.e,
      gap: num(el.getAttribute('data-motion-stagger'), p.gap || 60),
      speed: num(el.getAttribute('data-motion-speed'), p.speed || 0.3),
      repeat: el.getAttribute('data-motion-repeat') === 'true'
    };
  }

  var mqReduce = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  function reduced() { return !!(mqReduce && mqReduce.matches) && !panelOpen; }

  /* ------------------------------------------------------------------ */
  /* 효과 종류별 동작: prep(첫 장면) · play(재생) · reset(원래대로)       */
  /* ------------------------------------------------------------------ */
  function kfKind(el, c, st) {
    function make(loop) {
      return el.animate(c.p.k, {
        duration: Math.max(1, c.duration), delay: loop ? 0 : c.delay, easing: easeCss(c.ease), fill: 'both',
        iterations: loop ? Infinity : 1, direction: loop && c.p.alt ? 'alternate' : 'normal'
      });
    }
    return {
      prep: function () { if (st.a) st.a.cancel(); st.a = make(false); st.a.pause(); st.a.currentTime = 0; },
      play: function () {
        if (c.trigger === 'loop') { if (st.a) st.a.cancel(); st.a = make(true); return; }
        if (st.a) { st.a.cancel(); }
        var a = st.a = make(false);
        a.onfinish = function () { a.cancel(); if (st.a === a) st.a = null; };
      },
      hoverIn: function () {
        if (!st.a) {
          var a = st.a = make(false); a.pause(); a.currentTime = 0;
          // 되돌아오기가 끝나면 애니메이션을 지워 요소 원래 스타일(그림자 등)로 돌린다
          a.onfinish = function () { if (a.playbackRate < 0) { a.cancel(); if (st.a === a) st.a = null; } };
        }
        st.a.playbackRate = 1; st.a.play();
      },
      hoverOut: function () {
        if (st.a && st.a.currentTime > 0) { st.a.playbackRate = -1; st.a.play(); }
      },
      reset: function () { if (st.a) st.a.cancel(); st.a = null; }
    };
  }

  function staggerKind(el, c, st) {
    var child = [{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'none' }];
    function make() {
      return [].map.call(el.children, function (k, i) {
        return k.animate(child, { duration: c.duration, delay: c.delay + i * c.gap, easing: easeCss(c.ease), fill: 'both' });
      });
    }
    function cancel() { (st.list || []).forEach(function (a) { a.cancel(); }); st.list = null; }
    return {
      prep: function () { cancel(); st.list = make(); st.list.forEach(function (a) { a.pause(); a.currentTime = 0; }); },
      play: function () {
        cancel(); var list = st.list = make();
        if (list.length) list[list.length - 1].onfinish = function () { if (st.list === list) cancel(); };
      },
      reset: cancel
    };
  }

  function typeKind(el, c, st) {
    if (el.__mkText == null) el.__mkText = el.textContent;
    var full = el.__mkText;
    function stop() { if (st.raf) cancelAnimationFrame(st.raf); st.raf = 0; }
    return {
      prep: function () { stop(); el.textContent = ''; },
      play: function () {
        stop(); var t0 = performance.now() + c.delay, f = easeFn(c.ease);
        el.textContent = '';
        (function step(now) {
          var x = (now - t0) / Math.max(1, c.duration);
          if (x < 0) { st.raf = requestAnimationFrame(step); return; }
          el.textContent = full.slice(0, Math.round(full.length * f(Math.min(1, x))));
          if (x < 1) st.raf = requestAnimationFrame(step); else st.raf = 0;
        })(performance.now());
      },
      reset: function () { stop(); el.textContent = full; }
    };
  }

  function countKind(el, c, st) {
    if (el.__mkText == null) el.__mkText = el.textContent;
    var full = el.__mkText;
    var m = /^([\s\S]*?)(-?[\d,]*\.?\d+)([\s\S]*)$/.exec(full);
    function stop() { if (st.raf) cancelAnimationFrame(st.raf); st.raf = 0; }
    if (!m) return { prep: function () {}, play: function () {}, reset: function () {} };
    var pre = m[1], raw = m[2], post = m[3];
    var target = parseFloat(raw.replace(/,/g, ''));
    var dec = (raw.split('.')[1] || '').length, comma = raw.indexOf(',') >= 0;
    function fmt(v) {
      var s = v.toFixed(dec);
      if (comma) { var parts = s.split('.'); parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ','); s = parts.join('.'); }
      return pre + s + post;
    }
    return {
      prep: function () { stop(); el.textContent = fmt(0); },
      play: function () {
        stop(); var t0 = performance.now() + c.delay, f = easeFn(c.ease);
        (function step(now) {
          var x = (now - t0) / Math.max(1, c.duration);
          if (x < 0) { el.textContent = fmt(0); st.raf = requestAnimationFrame(step); return; }
          x = Math.min(1, x); el.textContent = x >= 1 ? full : fmt(target * f(x));
          if (x < 1) st.raf = requestAnimationFrame(step); else st.raf = 0;
        })(performance.now());
      },
      reset: function () { stop(); el.textContent = full; }
    };
  }

  function rippleKind(el, c) {
    return {
      prep: function () {},
      play: function (ev) {
        var cs = getComputedStyle(el);
        if (cs.position === 'static') el.style.position = 'relative';
        if (cs.overflow === 'visible') el.style.overflow = 'hidden';
        var r = el.getBoundingClientRect();
        var x = ev && ev.clientX != null ? ev.clientX - r.left : r.width / 2;
        var y = ev && ev.clientY != null ? ev.clientY - r.top : r.height / 2;
        var size = Math.max(r.width, r.height) * 2.2;
        var dot = document.createElement('span');
        dot.setAttribute('data-motion-ripple', '');
        dot.style.cssText = 'position:absolute;pointer-events:none;border-radius:50%;background:currentColor;opacity:.3;' +
          'left:' + (x - size / 2) + 'px;top:' + (y - size / 2) + 'px;width:' + size + 'px;height:' + size + 'px;';
        el.appendChild(dot);
        var a = dot.animate([{ transform: 'scale(0)', opacity: 0.35 }, { transform: 'scale(1)', opacity: 0 }],
          { duration: c.duration, easing: easeCss(c.ease), fill: 'forwards' });
        a.onfinish = function () { dot.remove(); };
      },
      reset: function () { [].forEach.call(el.querySelectorAll('[data-motion-ripple]'), function (d) { d.remove(); }); }
    };
  }

  function parallaxKind(el, c, st) {
    function update() {
      st.raf = 0;
      var r = el.getBoundingClientRect();
      var off = (r.top + r.height / 2 - window.innerHeight / 2) * -c.speed;
      el.style.transform = 'translate3d(0,' + off.toFixed(1) + 'px,0)';
    }
    function onScroll() { if (!st.raf) st.raf = requestAnimationFrame(update); }
    return {
      prep: function () {},
      play: function () {
        window.addEventListener('scroll', onScroll, { passive: true });
        window.addEventListener('resize', onScroll);
        update();
      },
      reset: function () {
        window.removeEventListener('scroll', onScroll);
        window.removeEventListener('resize', onScroll);
        if (st.raf) cancelAnimationFrame(st.raf);
        el.style.transform = '';
      }
    };
  }

  function kindFor(el, c, st) {
    switch (c.p.s) {
      case 'stagger': return staggerKind(el, c, st);
      case 'type': return typeKind(el, c, st);
      case 'count': return countKind(el, c, st);
      case 'ripple': return rippleKind(el, c, st);
      case 'parallax': return parallaxKind(el, c, st);
      default: return kfKind(el, c, st);
    }
  }

  /* ------------------------------------------------------------------ */
  /* 연결 · 해제                                                          */
  /* ------------------------------------------------------------------ */
  var bound = new Map();
  // 화면에 보일 때: clip-path로 가린 요소는 IntersectionObserver가 못 보므로 위치를 직접 잰다
  var watch = new Set(), checkRaf = 0;
  function check() {
    checkRaf = 0;
    var vh = window.innerHeight || document.documentElement.clientHeight;
    watch.forEach(function (b) {
      var r = b.el.getBoundingClientRect();
      var inView = r.bottom > 0 && r.top < vh * 0.95 && (r.width > 0 || r.height > 0);
      if (inView) {
        if (!b.seen || (b.c.repeat && b.out)) { b.seen = true; b.out = false; b.K.play(); }
        if (!b.c.repeat) watch.delete(b);
      } else if (b.c.repeat && b.seen && !b.out) { b.out = true; b.K.prep(); }
    });
  }
  function queueCheck() { if (!checkRaf) checkRaf = requestAnimationFrame(check); }
  window.addEventListener('scroll', queueCheck, { passive: true, capture: true });
  window.addEventListener('resize', queueCheck);

  function bind(el) {
    unbind(el);
    var c = readCfg(el);
    if (!c || reduced()) return;
    var st = {}, K = kindFor(el, c, st), offs = [];
    function on(type, fn, opt) { el.addEventListener(type, fn, opt); offs.push(function () { el.removeEventListener(type, fn, opt); }); }
    var b = { c: c, K: K, el: el, seen: false };
    switch (c.trigger) {
      case 'load':
        K.prep(); requestAnimationFrame(function () { if (bound.get(el) === b) K.play(); }); break;
      case 'scroll':
        K.prep(); watch.add(b); offs.push(function () { watch.delete(b); }); queueCheck();
        break;
      case 'press':
        on('pointerdown', function (e) { K.play(e); });
        on('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') K.play(); });
        break;
      case 'hover':
        if (K.hoverIn) {
          on('pointerenter', K.hoverIn); on('pointerleave', K.hoverOut);
          on('focus', K.hoverIn); on('blur', K.hoverOut);
        }
        break;
      case 'loop':
      case 'scroll-link':
        K.play(); break;
    }
    b.off = function () { offs.forEach(function (f) { f(); }); K.reset(); };
    bound.set(el, b);
  }
  function unbind(el) { var b = bound.get(el); if (b) { b.off(); bound.delete(el); } }

  // 미리보기: 효과를 한 번 다시 보여 준다
  function play(target) {
    var els = typeof target === 'string' ? document.querySelectorAll(target) : [target];
    [].forEach.call(els, function (el) {
      var b = bound.get(el); if (!b) return;
      var t = b.c.trigger;
      if (t === 'hover' && b.K.hoverIn) { b.K.hoverIn(); setTimeout(b.K.hoverOut, b.c.duration + 400); }
      else if (t === 'loop' || t === 'scroll-link') { /* 이미 움직이는 중 */ }
      else { if (t !== 'press') b.K.prep(); b.K.play(); }
    });
  }

  /* ------------------------------------------------------------------ */
  /* 규칙: 선택자 → 속성                                                  */
  /* ------------------------------------------------------------------ */
  var rules = [];
  var FIELDS = [['trigger', 'data-motion-trigger'], ['duration', 'data-motion-duration'], ['delay', 'data-motion-delay'], ['ease', 'data-motion-ease'], ['stagger', 'data-motion-stagger'], ['speed', 'data-motion-speed'], ['repeat', 'data-motion-repeat']];
  function ruleAttrs(r) {
    var out = {}; if (!r.motion || !P[r.motion]) return out;
    var p = P[r.motion];
    out['data-motion'] = r.motion;
    if (r.trigger && r.trigger !== DEF_TRIGGER[p.g]) out['data-motion-trigger'] = r.trigger;
    if (r.duration != null && +r.duration !== p.d) out['data-motion-duration'] = String(r.duration);
    if (r.delay) out['data-motion-delay'] = String(r.delay);
    if (r.ease && r.ease !== p.e) out['data-motion-ease'] = r.ease;
    if (p.s === 'stagger' && r.stagger != null && +r.stagger !== p.gap) out['data-motion-stagger'] = String(r.stagger);
    if (p.s === 'parallax' && r.speed != null && +r.speed !== p.speed) out['data-motion-speed'] = String(r.speed);
    if (r.repeat) out['data-motion-repeat'] = 'true';
    return out;
  }
  function setAttrs(el, attrs) {
    ATTRS.forEach(function (a) {
      if (attrs[a] == null) { if (el.hasAttribute(a)) el.removeAttribute(a); }
      else if (el.getAttribute(a) !== attrs[a]) el.setAttribute(a, attrs[a]);
    });
  }
  function matchAll(root, sel) {
    var out = [];
    try {
      if (root.nodeType === 1 && root.matches(sel)) out.push(root);
      [].push.apply(out, root.querySelectorAll(sel));
    } catch (e) { /* 잘못된 선택자는 무시 */ }
    return out;
  }
  function applyRules(root) {
    rules.forEach(function (r) {
      var attrs = ruleAttrs(r);
      matchAll(root || document, r.selector).forEach(function (el) { setAttrs(el, attrs); });
    });
  }
  function setRules(list) {
    rules = (list || []).filter(function (r) { return r && r.selector; }).map(function (r) {
      var o = {}; for (var k in r) o[k] = r[k]; if (o.motion == null && o.preset) o.motion = o.preset; return o;
    });
    applyRules(document);
    return rules;
  }

  /* ------------------------------------------------------------------ */
  /* 감시: 새로 생긴 요소·바뀐 속성                                        */
  /* ------------------------------------------------------------------ */
  function scan(root) {
    if (root.nodeType !== 1) return;
    if (root.hasAttribute('data-motion')) bind(root);
    [].forEach.call(root.querySelectorAll('[data-motion]'), bind);
  }
  var mo = new MutationObserver(function (muts) {
    muts.forEach(function (m) {
      if (m.type === 'attributes') {
        var el = m.target;
        if (el.hasAttribute('data-motion')) bind(el); else unbind(el);
      } else {
        m.addedNodes.forEach(function (n) {
          if (n.nodeType !== 1 || n.hasAttribute('data-motion-ripple') || (host && host.contains(n))) return;
          if (rules.length) applyRules(n);
          scan(n);
        });
        m.removedNodes.forEach(function (n) {
          if (n.nodeType !== 1) return;
          bound.forEach(function (b, el) { if (!el.isConnected) unbind(el); });
        });
      }
    });
  });

  function start() {
    applyRules(document);
    scan(document.body);
    mo.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ATTRS });
    if (PANEL_MODE !== 'off') {
      var q = location.search + location.hash;
      if (/[?&#]motion(\b|=|&|$)/.test(q) || PANEL_MODE === 'open') openPanel();
      document.addEventListener('keydown', function (e) {
        if (e.altKey && (e.code === 'KeyM' || e.key === 'm' || e.key === 'M' || e.key === 'µ')) { e.preventDefault(); togglePanel(); }
      });
    }
  }

  /* ------------------------------------------------------------------ */
  /* 조절 패널                                                            */
  /* ------------------------------------------------------------------ */
  var host = null, root = null, panelOpen = false, picking = false, selected = null, exportMode = BOOKMARK ? 'plain' : 'ai';
  var STORE = 'motionkit:rules:' + location.pathname;
  function load() { try { return JSON.parse(localStorage.getItem(STORE) || '[]'); } catch (e) { return []; } }
  function save() { try { localStorage.setItem(STORE, JSON.stringify(rules)); } catch (e) { /* 저장 불가 환경 */ } }

  function cssSel(el) {
    var ok = /^[A-Za-z][\w-]*$/;
    if (el.id && ok.test(el.id)) return '#' + el.id;
    var parts = [], cur = el;
    while (cur && cur.nodeType === 1 && cur !== document.body && cur !== document.documentElement) {
      if (cur.id && ok.test(cur.id)) { parts.unshift('#' + cur.id); break; }
      var part = cur.tagName.toLowerCase();
      var cls = [].filter.call(cur.classList, function (c) {
        return ok.test(c) && c.length < 30 && !/\d{3,}|^(css|sc|jsx|svelte|astro|emotion)-|__|^_/.test(c);
      }).slice(0, 2);
      if (cls.length) part += '.' + cls.join('.');
      var par = cur.parentElement;
      if (par) {
        var tag = cur.tagName;
        var same = [].filter.call(par.children, function (s) { return s.tagName === tag; });
        if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(cur) + 1) + ')';
      }
      parts.unshift(part);
      var s = parts.join(' > ');
      try { if (document.querySelectorAll(s).length === 1) return s; } catch (e) {}
      cur = par;
    }
    return parts.join(' > ') || el.tagName.toLowerCase();
  }
  function describe(el) {
    var tag = el.tagName.toLowerCase();
    var txt = (el.getAttribute('aria-label') || el.getAttribute('alt') || el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
    if (txt.length > 24) txt = txt.slice(0, 24) + '…';
    var kind = { button: '버튼', a: '링크', img: '이미지', h1: '제목', h2: '제목', h3: '제목', p: '문단', li: '목록 항목', ul: '목록', ol: '목록', nav: '메뉴', header: '머리말', footer: '꼬리말', section: '구역', input: '입력칸', svg: '아이콘' }[tag] || tag;
    return kind + (txt ? ' "' + txt + '"' : '');
  }

  var CSS_PANEL = [
    ':host{all:initial}',
    '*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif}',
    '.pnl{position:fixed;top:12px;right:12px;bottom:12px;width:330px;z-index:2147483647;background:#16181F;color:#ECEEF3;border:1px solid #2C303B;border-radius:14px;box-shadow:0 20px 50px rgba(0,0,0,.45);display:flex;flex-direction:column;font-size:13px;line-height:1.45;overflow:hidden}',
    '@media (max-width:640px){.pnl{top:auto;left:0;right:0;bottom:0;width:auto;height:58vh;border-radius:16px 16px 0 0;padding-bottom:env(safe-area-inset-bottom,0px)}}',
    '.pnl.min{height:auto;bottom:auto;top:auto;bottom:12px;width:auto}',
    '@media (max-width:640px){.pnl.min{left:auto;right:12px;bottom:12px;border-radius:999px}}',
    '.hd{display:flex;align-items:center;gap:6px;padding:10px 10px 10px 14px;border-bottom:1px solid #2C303B;flex:none;cursor:move;touch-action:none;user-select:none;-webkit-user-select:none}',
    '.hd button{cursor:pointer}',
    '@media (min-width:641px){.pnl.left{right:auto;left:12px}.pnl.free{right:auto;bottom:auto;height:min(78vh,720px)}.pnl.free.min{height:auto}}',
    '@media (max-width:640px){.side-btn{display:none}}',
    '.pnl.away{visibility:hidden}',
    '.grip{color:#5B6274;font-size:12px;letter-spacing:-2px;margin-right:2px}',
    '.ttl{font-weight:800;font-size:14px;letter-spacing:-.01em;margin-right:auto;display:flex;align-items:center;gap:7px}',
    '.ttl i{width:9px;height:9px;border-radius:3px;background:linear-gradient(135deg,#E8A43C,#EE6A50 50%,#9C7BEE)}',
    '.min .body,.min .pick{display:none}',
    'button{font:inherit;color:inherit;cursor:pointer;border:1px solid #343947;background:#21242D;border-radius:8px;padding:6px 10px}',
    'button:hover{border-color:#5B6274}',
    'button:focus-visible,select:focus-visible,input:focus-visible,textarea:focus-visible{outline:2px solid #5B88F2;outline-offset:1px}',
    'button.on{background:#5B88F2;border-color:#5B88F2;color:#fff}',
    'button.pri{background:#ECEEF3;color:#16181F;border-color:#ECEEF3;font-weight:700}',
    '.body{overflow:auto;padding:12px 14px 16px;display:flex;flex-direction:column;gap:14px;flex:1}',
    '.hint{color:#9AA2B2;font-size:12.5px;margin:0}',
    '.sel{background:#1D2029;border:1px solid #2C303B;border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:6px}',
    '.sel b{font-size:13.5px}',
    '.sel code{font:11px/1.4 ui-monospace,Menlo,Consolas,monospace;color:#9AA2B2;word-break:break-all}',
    '.row{display:flex;gap:6px;flex-wrap:wrap}',
    'label{display:flex;flex-direction:column;gap:5px;font-size:12px;color:#B7BECC}',
    'label.chk{flex-direction:row;align-items:center;gap:8px}',
    'select,input[type=number],textarea{font:inherit;color:#ECEEF3;background:#0F1116;border:1px solid #343947;border-radius:8px;padding:7px 8px;width:100%}',
    '.rng{display:flex;gap:8px;align-items:center}.rng input[type=range]{flex:1;accent-color:#5B88F2}.rng input[type=number]{width:78px}',
    '.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}',
    'h4{margin:0;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#7D8597}',
    'ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}',
    'li{display:flex;align-items:center;gap:6px;background:#1D2029;border:1px solid #2C303B;border-radius:8px;padding:6px 6px 6px 10px;cursor:pointer}',
    'li.cur{border-color:#5B88F2}',
    'li span{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    'li em{font-style:normal;color:#9AA2B2;font-size:11.5px}',
    'li button{padding:2px 8px}',
    'textarea{min-height:150px;font:11.5px/1.5 ui-monospace,Menlo,Consolas,monospace;resize:vertical}',
    '.tabs{display:flex;gap:4px}.tabs button{flex:1;padding:6px 4px;font-size:12px}',
    '.note{font-size:11.5px;color:#7D8597;margin:0}',
    '.box{position:fixed;pointer-events:none;z-index:2147483646;border:2px solid #5B88F2;background:rgba(91,136,242,.12);border-radius:4px;transition:all .06s}',
    '.box.selbox{border-color:#25AD92;background:rgba(37,173,146,.10)}',
    '.box span{position:absolute;left:-2px;top:-20px;background:#5B88F2;color:#fff;font-size:11px;padding:2px 6px;border-radius:4px 4px 4px 0;white-space:nowrap}',
    '.selbox span{background:#25AD92}',
    '.pick{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:2147483647;background:#5B88F2;color:#fff;padding:6px 6px 6px 16px;border-radius:999px;font-weight:700;font-size:13px;box-shadow:0 8px 20px rgba(0,0,0,.3);display:flex;align-items:center;gap:10px;white-space:nowrap}',
    '.pick[hidden]{display:none}',
    '.pick button{background:#fff;color:#2B4FD8;border:0;border-radius:999px;padding:6px 12px;font-weight:700}'
  ].join('\n');

  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    for (var k in (attrs || {})) {
      if (k === 'on') { for (var ev in attrs.on) el.addEventListener(ev, attrs.on[ev]); }
      else if (k === 'text') el.textContent = attrs[k];
      else if (attrs[k] !== false && attrs[k] != null) el.setAttribute(k, attrs[k] === true ? '' : attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c != null) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return el;
  }

  var ui = {};
  function buildPanel() {
    host = document.createElement('motion-kit-panel');
    host.style.cssText = 'all:initial;position:fixed;top:0;left:0;width:0;height:0;z-index:2147483647';
    root = host.attachShadow({ mode: 'open' });
    root.appendChild(h('style', { text: CSS_PANEL }));
    ui.hover = h('div', { class: 'box', hidden: true }, [h('span')]);
    ui.selbox = h('div', { class: 'box selbox', hidden: true }, [h('span', { text: '선택됨' })]);
    ui.pickBar = h('div', { class: 'pick', hidden: true }, ['움직일 요소를 누르세요', h('button', { type: 'button', on: { click: function () { setPicking(false); } } }, ['취소'])]);
    ui.sideBtn = h('button', { type: 'button', class: 'side-btn', title: '패널을 반대쪽으로', 'aria-label': '패널을 반대쪽으로 옮기기', on: { click: function () { dock(!ui.pnl.classList.contains('left')); } } }, ['⇆']);
    ui.pickBtn = h('button', { type: 'button', on: { click: function () { setPicking(!picking); } } }, ['요소 선택']);
    ui.minBtn = h('button', { type: 'button', title: '접기', 'aria-label': '패널 접기', on: { click: function () { ui.pnl.classList.toggle('min'); ui.minBtn.textContent = ui.pnl.classList.contains('min') ? '펼치기' : '접기'; } } }, ['접기']);
    var close = h('button', { type: 'button', 'aria-label': '패널 닫기', on: { click: closePanel } }, ['✕']);
    ui.body = h('div', { class: 'body' });
    ui.pnl = h('div', { class: 'pnl', role: 'dialog', 'aria-label': 'Motion Kit 조절 패널' }, [
      ui.hd = h('div', { class: 'hd', title: '여기를 잡고 끌면 패널이 움직입니다' }, [h('div', { class: 'ttl' }, [h('span', { class: 'grip', 'aria-hidden': 'true', text: '⋮⋮' }), h('i'), 'Motion Kit']), ui.pickBtn, ui.sideBtn, ui.minBtn, close]),
      ui.body
    ]);
    root.appendChild(ui.hover); root.appendChild(ui.selbox); root.appendChild(ui.pickBar); root.appendChild(ui.pnl);
    document.documentElement.appendChild(host);
    dragSetup();
    restorePos();
  }

  function field(labelText, control) { return h('label', {}, [labelText, control]); }
  function rangeField(labelText, value, min, max, step, onInput) {
    var r = h('input', { type: 'range', min: min, max: max, step: step, value: value });
    var n = h('input', { type: 'number', min: min, max: max, step: step, value: value, 'aria-label': labelText });
    r.addEventListener('input', function () { n.value = r.value; onInput(+r.value); });
    n.addEventListener('change', function () { r.value = n.value; onInput(+n.value); });
    return h('label', {}, [labelText, h('div', { class: 'rng' }, [r, n])]);
  }

  function currentRule() {
    if (!selected) return null;
    var sel = cssSel(selected);
    for (var i = 0; i < rules.length; i++) if (rules[i].selector === sel) return rules[i];
    return null;
  }
  function upsert(patch) {
    if (!selected) return;
    var r = currentRule();
    if (!r) { r = { selector: cssSel(selected), desc: describe(selected) }; rules.push(r); }
    for (var k in patch) r[k] = patch[k];
    var p = P[r.motion];
    if (p) {
      if (triggersFor(p).indexOf(r.trigger) < 0) r.trigger = DEF_TRIGGER[p.g];
      if (r.duration == null) r.duration = p.d;
      if (!r.ease) r.ease = p.e;
    }
    applyRules(document); save();
    setTimeout(function () { play(selected); }, 30);
    render();
  }
  function removeRule(r) {
    rules = rules.filter(function (x) { return x !== r; });
    matchAll(document, r.selector).forEach(function (el) { setAttrs(el, {}); });
    save(); render();
  }

  function render() {
    if (!root) return;
    var b = ui.body; b.textContent = '';
    if (!selected) {
      b.appendChild(h('p', { class: 'hint' }, ['위의 ', h('b', { text: '요소 선택' }), '을 누른 뒤 화면에서 움직이고 싶은 버튼·카드·제목을 누르세요. 그다음 여기서 효과와 속도를 고르면 바로 보입니다.']));
    } else {
      var r = currentRule() || {};
      var p = P[r.motion];
      b.appendChild(h('div', { class: 'sel' }, [
        h('b', { text: describe(selected) }),
        h('code', { text: cssSel(selected) }),
        h('div', { class: 'row' }, [
          h('button', { type: 'button', on: { click: function () { if (selected.parentElement && selected.parentElement !== document.body) { selected = selected.parentElement; render(); } } } }, ['↑ 바깥 요소']),
          p ? h('button', { type: 'button', class: 'pri', on: { click: function () { play(selected); } } }, ['▶ 다시 보기']) : null,
          p ? h('button', { type: 'button', on: { click: function () { var cr = currentRule(); if (cr) removeRule(cr); } } }, ['효과 빼기']) : null
        ])
      ]));
      var sel = h('select', { 'aria-label': '효과' });
      sel.appendChild(h('option', { value: '', text: '— 효과 고르기 —' }));
      Object.keys(GROUP_KR).forEach(function (g) {
        var og = h('optgroup', { label: GROUP_KR[g] });
        Object.keys(P).forEach(function (n) { if (P[n].g === g) og.appendChild(h('option', { value: n, text: P[n].kr + '  (' + n + ')' })); });
        sel.appendChild(og);
      });
      sel.value = r.motion || '';
      sel.addEventListener('change', function () {
        var np = P[sel.value];
        if (!np) { var cr = currentRule(); if (cr) removeRule(cr); return; }
        upsert({ motion: sel.value, trigger: DEF_TRIGGER[np.g], duration: np.d, ease: np.e, stagger: np.gap, speed: np.speed });
      });
      b.appendChild(field('효과', sel));
      if (p) {
        b.appendChild(h('p', { class: 'note', text: p.h }));
        var trig = h('select', { 'aria-label': '언제' });
        triggersFor(p).forEach(function (t) { trig.appendChild(h('option', { value: t, text: TRIGGER_KR[t] })); });
        trig.value = r.trigger || DEF_TRIGGER[p.g];
        trig.addEventListener('change', function () { upsert({ trigger: trig.value }); });
        var ease = h('select', { 'aria-label': '속도 곡선' });
        Object.keys(EASES).forEach(function (e) { ease.appendChild(h('option', { value: e, text: EASE_KR[e] })); });
        if (r.ease && !EASES[r.ease]) ease.appendChild(h('option', { value: r.ease, text: r.ease }));
        ease.value = r.ease || p.e;
        ease.addEventListener('change', function () { upsert({ ease: ease.value }); });
        b.appendChild(h('div', { class: 'grid' }, [field('언제', trig), p.s === 'parallax' ? null : field('속도 곡선', ease)]));
        if (p.s === 'parallax') {
          b.appendChild(rangeField('느리게 움직이는 정도 (0.1–0.8)', r.speed != null ? r.speed : p.speed, 0.05, 0.8, 0.05, function (v) { upsert({ speed: v }); }));
        } else {
          b.appendChild(rangeField('길이 (ms) · 1000ms = 1초', r.duration != null ? r.duration : p.d, 50, 3000, 10, function (v) { upsert({ duration: v }); }));
          if (r.trigger !== 'loop') b.appendChild(rangeField('시작 지연 (ms)', r.delay || 0, 0, 2000, 10, function (v) { upsert({ delay: v }); }));
          if (p.s === 'stagger') b.appendChild(rangeField('항목 사이 간격 (ms)', r.stagger != null ? r.stagger : p.gap, 10, 400, 5, function (v) { upsert({ stagger: v }); }));
          if (r.trigger === 'scroll' || (!r.trigger && DEF_TRIGGER[p.g] === 'scroll')) {
            var rep = h('input', { type: 'checkbox' }); rep.checked = !!r.repeat;
            rep.addEventListener('change', function () { upsert({ repeat: rep.checked }); });
            b.appendChild(h('label', { class: 'chk' }, [rep, '화면에 다시 보일 때마다 재생']));
          }
        }
      }
    }

    // 적용한 효과 목록
    var active = rules.filter(function (x) { return P[x.motion]; });
    b.appendChild(h('h4', { text: '적용한 효과 ' + active.length + '개' }));
    if (!active.length) b.appendChild(h('p', { class: 'note', text: '아직 없습니다.' }));
    else {
      var ul = h('ul');
      active.forEach(function (x) {
        var els = matchAll(document, x.selector);
        var li = h('li', { class: selected && els[0] === selected ? 'cur' : null, on: { click: function () { if (els[0]) { selected = els[0]; els[0].scrollIntoView({ block: 'center', behavior: 'smooth' }); render(); } } } }, [
          h('span', { text: (x.desc || x.selector) }), h('em', { text: P[x.motion].kr }),
          h('button', { type: 'button', 'aria-label': '효과 빼기', on: { click: function (e) { e.stopPropagation(); removeRule(x); } } }, ['✕'])
        ]);
        ul.appendChild(li);
      });
      b.appendChild(ul);
    }

    // 내보내기
    b.appendChild(h('h4', { text: '코드로 남기기' }));
    var tabs = h('div', { class: 'tabs' });
    (BOOKMARK ? [['plain', 'AI에게 부탁'], ['ai', 'motion-kit 쓸 때']] : [['ai', 'AI에게 부탁'], ['plain', '라이브러리 없이'], ['code', '규칙 코드']]).forEach(function (t) {
      tabs.appendChild(h('button', { type: 'button', class: exportMode === t[0] ? 'on' : null, on: { click: function () { exportMode = t[0]; render(); } } }, [t[1]]));
    });
    b.appendChild(tabs);
    var ta = h('textarea', { readonly: true, 'aria-label': '내보내기 내용' }); ta.value = exportText(exportMode);
    var copy = h('button', { type: 'button', class: 'pri', on: { click: function () {
      var done = function () { copy.textContent = '복사됨'; setTimeout(function () { copy.textContent = '복사'; }, 1500); };
      var fail = function () { ta.focus(); ta.select(); copy.textContent = '선택됨 · 길게 눌러 복사'; };
      try { navigator.clipboard.writeText(ta.value).then(done, fail); } catch (e) { fail(); }
    } } }, ['복사']);
    b.appendChild(ta);
    b.appendChild(h('div', { class: 'row' }, [copy]));
    b.appendChild(h('p', { class: 'note', text: '여기서 바꾼 것은 이 브라우저에만 임시로 남습니다. 계속 쓰려면 위 내용을 복사해서 AI 코딩 도구에 붙여넣거나 코드에 넣으세요.' }));
  }

  function exportText(mode) {
    var active = rules.filter(function (x) { return P[x.motion]; });
    if (!active.length) return '효과를 하나 이상 적용하면 여기에 내용이 생깁니다.';
    if (mode === 'code') {
      var list = active.map(function (x) {
        var o = { selector: x.selector, motion: x.motion }, a = ruleAttrs(x);
        FIELDS.forEach(function (f) { if (a[f[1]] != null) o[f[0]] = f[0] === 'repeat' ? true : (isNaN(+a[f[1]]) ? a[f[1]] : +a[f[1]]); });
        return '  ' + JSON.stringify(o);
      });
      return '<script src="/motion-kit.js"></script>\n<script>\n  MotionKit.rules([\n' + list.join(',\n') + '\n  ]);\n</script>';
    }
    if (mode === 'plain') {
      return '아래 요소들에 애니메이션을 넣어줘. 라이브러리 없이 지금 프로젝트 방식(CSS 또는 기존 애니메이션 도구)으로 만들고, 휴대폰의 \'동작 줄이기\' 설정(prefers-reduced-motion)이 켜져 있으면 꺼지게 해줘.\n\n' +
        active.map(function (x, i) {
          var p = P[x.motion], parts = [TRIGGER_KR[x.trigger || DEF_TRIGGER[p.g]], '\'' + p.kr + '\' 효과: ' + p.h];
          if (p.s === 'parallax') parts.push('속도 ' + (x.speed != null ? x.speed : p.speed) + '배 느리게');
          else {
            parts.push((x.duration != null ? x.duration : p.d) + 'ms');
            parts.push((x.ease || p.e) + '(' + easeCss(x.ease || p.e) + ')');
            if (x.delay) parts.push(x.delay + 'ms 뒤 시작');
            if (p.s === 'stagger') parts.push('항목 간격 ' + (x.stagger != null ? x.stagger : p.gap) + 'ms');
            if (x.repeat) parts.push('다시 보일 때마다 재생');
          }
          return (i + 1) + '. ' + (x.desc || '') + ' (선택자: ' + x.selector + ')\n   → ' + parts.join(', ');
        }).join('\n');
    }
    return '이 웹앱에 motion-kit.js를 쓰고 있어. 아직 연결 안 돼 있으면 motion-kit.js를 public(정적 파일) 폴더에 넣고 모든 페이지에 불러오게 해줘.\n' +
      '그다음 아래 요소들의 원래 코드(JSX/HTML)에 적힌 data-motion 속성을 그대로 추가해줘. 다른 코드는 바꾸지 마.\n\n' +
      active.map(function (x, i) {
        var a = ruleAttrs(x);
        return (i + 1) + '. ' + (x.desc || '') + '\n   찾는 법: ' + x.selector + '\n   추가: ' + Object.keys(a).map(function (k) { return k + '="' + a[k] + '"'; }).join(' ');
      }).join('\n');
  }

  // 요소 고르기
  function inPanel(t) { return host && (t === host || host.contains(t)); }
  function boxTo(box, el, label) {
    if (!el) { box.hidden = true; return; }
    var r = el.getBoundingClientRect();
    box.hidden = false;
    box.style.left = r.left - 2 + 'px'; box.style.top = r.top - 2 + 'px';
    box.style.width = r.width + 4 + 'px'; box.style.height = r.height + 4 + 'px';
    if (label != null) box.firstChild.textContent = label;
  }
  function onMove(e) { if (picking && !inPanel(e.target)) boxTo(ui.hover, e.target, describe(e.target)); }
  function onPick(e) {
    if (!picking || inPanel(e.target)) return;
    e.preventDefault(); e.stopPropagation();
    if (e.type !== 'click') return;
    selected = e.target; setPicking(false); render();
  }
  function onKey(e) { if (e.key === 'Escape' && picking) setPicking(false); }
  // 패널 옮기기: 머리줄을 잡고 끌기, ⇆ 로 좌우 바꾸기
  var POS = 'motionkit:pos';
  function savePos(o) { try { localStorage.setItem(POS, JSON.stringify(o)); } catch (e) {} }
  function clampPos(x, y) {
    var w = ui.pnl.offsetWidth, hh = ui.hd.offsetHeight;
    return [Math.min(Math.max(0, x), window.innerWidth - Math.min(w, 120)), Math.min(Math.max(0, y), window.innerHeight - hh)];
  }
  function place(x, y) {
    var c = clampPos(x, y);
    ui.pnl.classList.add('free'); ui.pnl.classList.remove('left');
    ui.pnl.style.left = c[0] + 'px'; ui.pnl.style.top = c[1] + 'px';
    return c;
  }
  function dock(left) {
    ui.pnl.classList.remove('free'); ui.pnl.style.left = ''; ui.pnl.style.top = '';
    ui.pnl.classList.toggle('left', left);
    savePos({ side: left ? 'left' : 'right' });
  }
  function restorePos() {
    var o; try { o = JSON.parse(localStorage.getItem(POS) || 'null'); } catch (e) { o = null; }
    if (!o) return;
    if (o.side) dock(o.side === 'left'); else if (o.x != null) place(o.x, o.y);
  }
  function dragSetup() {
    var sx, sy, ox, oy, on = false;
    ui.hd.addEventListener('pointerdown', function (e) {
      if (e.button !== 0 || (e.target.closest && e.target.closest('button'))) return;
      if (window.matchMedia('(max-width:640px)').matches) return;
      var r = ui.pnl.getBoundingClientRect();
      sx = e.clientX; sy = e.clientY; ox = r.left; oy = r.top; on = true;
      ui.hd.setPointerCapture(e.pointerId); e.preventDefault();
    });
    ui.hd.addEventListener('pointermove', function (e) { if (on) place(ox + e.clientX - sx, oy + e.clientY - sy); });
    function end(e) {
      if (!on) return; on = false;
      var r = ui.pnl.getBoundingClientRect();
      if (Math.abs(e.clientX - sx) + Math.abs(e.clientY - sy) > 3) savePos({ x: r.left, y: r.top });
    }
    ui.hd.addEventListener('pointerup', end);
    ui.hd.addEventListener('pointercancel', end);
    window.addEventListener('resize', function () { if (ui.pnl.classList.contains('free')) place(parseFloat(ui.pnl.style.left), parseFloat(ui.pnl.style.top)); });
  }

  function setPicking(on) {
    picking = on;
    ui.pickBtn.classList.toggle('on', on);
    ui.pickBtn.textContent = on ? '선택 중…' : '요소 선택';
    ui.pickBar.hidden = !on;
    // 고르는 동안 패널을 비켜서 뒤에 있는 요소도 누를 수 있게
    ui.pnl.classList.toggle('away', on);
    if (!on) ui.hover.hidden = true;
  }
  var tickRaf = 0;
  function tick() {
    tickRaf = panelOpen ? requestAnimationFrame(tick) : 0;
    if (selected && !selected.isConnected) selected = null;
    boxTo(ui.selbox, selected, null);
  }

  function openPanel() {
    if (panelOpen) return;
    if (!host) buildPanel();
    host.style.display = ''; panelOpen = true;
    var saved = load();
    if (saved.length && !rules.length) setRules(saved);
    document.addEventListener('pointermove', onMove, true);
    document.addEventListener('pointerdown', onPick, true);
    document.addEventListener('click', onPick, true);
    document.addEventListener('keydown', onKey, true);
    render(); tick();
    scan(document.body);
  }
  function closePanel() {
    if (!panelOpen) return;
    setPicking(false); panelOpen = false; host.style.display = 'none';
    document.removeEventListener('pointermove', onMove, true);
    document.removeEventListener('pointerdown', onPick, true);
    document.removeEventListener('click', onPick, true);
    document.removeEventListener('keydown', onKey, true);
  }
  function togglePanel() { if (panelOpen) closePanel(); else openPanel(); }

  /* ------------------------------------------------------------------ */
  /* 공개 API                                                             */
  /* ------------------------------------------------------------------ */
  window.MotionKit = {
    version: VERSION,
    presets: P,
    eases: EASES,
    rules: setRules,
    play: play,
    refresh: function () { applyRules(document); scan(document.body); },
    open: openPanel,
    close: closePanel,
    toggle: togglePanel
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
