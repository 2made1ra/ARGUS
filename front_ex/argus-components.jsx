/* eslint-disable */
const { useState, useEffect, useRef } = React;

// ─── ICON SYSTEM ──────────────────────────────────────────────────────────────
const IC = ({ d, size = 16, strokeWidth = 1.8, ...rest }) =>
<svg width={size} height={size} viewBox="0 0 24 24" fill="none"
stroke="currentColor" strokeWidth={strokeWidth}
strokeLinecap="round" strokeLinejoin="round" {...rest}>
    {Array.isArray(d) ? d.map((p, i) => <path key={i} d={p} />) : <path d={d} />}
  </svg>;


const P = {
  globe: ['M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2z', 'M2 12h20', 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'],
  book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z',
  files: ['M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z', 'M13 2v7h7'],
  clock: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z', 'M12 6v6l4 2'],
  plus: ['M12 5v14', 'M5 12h14'],
  search: ['M21 21l-4.35-4.35', 'M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z'],
  collapse: 'M15 18l-6-6 6-6',
  chevD: 'M6 9l6 6 6-6',
  more: ['M12 12h.01', 'M7 12h.01', 'M17 12h.01'],
  link: ['M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71', 'M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71'],
  export: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M7 10l5 5 5-5', 'M12 15V3'],
  sparkle: 'M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z',
  clip: 'M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48',
  image: ['M21 19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z', 'M8.5 10a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z', 'M21 15l-5-5L5 21'],
  bulb: ['M9 18h6', 'M10 22h4', 'M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z'],
  gear: ['M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z', 'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z'],
  logout: ['M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4', 'M16 17l5-5-5-5', 'M21 12H9'],
  chart: ['M18 20V10', 'M12 20V4', 'M6 20v-6'],
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  brief: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z', 'M14 2v6h6', 'M16 13H8', 'M16 17H8', 'M10 9H8'],
  up: ['M12 19V5', 'M5 12l7-7 7 7'],
  eye: ['M2 12s4-8 10-8 10 8 10 8-4 8-10 8S2 12 2 12z', 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z'],
  edit: ['M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7', 'M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z'],
  plug: ['M12 2v6m4-2h6m0 0v2a2 2 0 0 1-2 2h-2m-8 0H4a2 2 0 0 1-2-2V8m0-4h6M6 18v3m6 0v3m6-3v3M6 18h12', 'M9 22h6']
};

// ─── ANIMATED BACKGROUND ──────────────────────────────────────────────────────
function AnimatedBg() {
  const refs = [useRef(null), useRef(null), useRef(null)];
  const state = useRef({ mx: 0.5, my: 0.5, angle: 0 });

  useEffect(() => {
    const onMove = (e) => {
      state.current.mx = e.clientX / window.innerWidth;
      state.current.my = e.clientY / window.innerHeight;
    };
    window.addEventListener('mousemove', onMove, { passive: true });

    let raf;
    const tick = () => {
      state.current.angle += 0.00055;
      const { mx, my, angle } = state.current;
      const dx = (mx - 0.5) * 55;
      const dy = (my - 0.5) * 38;
      const wx = Math.sin(angle) * 22;
      const wy = Math.cos(angle * 0.73) * 16;

      const t = (i, sx, sy) => `translate(${dx * sx + wx * (i % 2 === 0 ? 1 : -0.7)}px, ${dy * sy + wy * (i < 2 ? 1 : -0.6)}px)`;

      if (refs[0].current) refs[0].current.style.transform = t(0, 0.35, 0.25);
      if (refs[1].current) refs[1].current.style.transform = t(1, -0.28, 0.42);
      if (refs[2].current) refs[2].current.style.transform = t(2, 0.52, -0.33);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener('mousemove', onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div className="bg-layer">
      <div ref={refs[0]} className="blob blob-1" />
      <div ref={refs[1]} className="blob blob-2" />
      <div ref={refs[2]} className="blob blob-3" />
    </div>);

}

// ─── ARGUS ORB – particle nebula + morphing blob ─────────────────────────────
function ArgusOrb({ loading = false }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const t0Ref = useRef(null);
  const loadRef = useRef(loading);
  loadRef.current = loading;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width,H = canvas.height;
    const cx = W / 2,cy = H / 2;
    const BR = W * 0.20; // blob radius
    const PR = W * 0.40; // particle cloud scale
    const NB = 12; // blob bezier control points

    // ── Particle init ──────────────────────────────────────────────────────
    const COUNT = 300;
    const particles = [];
    const rng = () => Math.random();

    for (let i = 0; i < COUNT; i++) {
      const u = rng();
      let r;
      // Bimodal: dense inner shell + sparse outer halo
      if (u < 0.18) r = Math.pow(rng(), 0.6) * 0.38; // core
      else if (u < 0.55) r = 0.38 + rng() * 0.48; // inner shell
      else if (u < 0.80) r = 0.86 + rng() * 0.50; // outer ring
      else r = 1.36 + rng() * 0.70; // halo wisps

      const phi = rng() * Math.PI * 2;
      const theta = Math.acos(rng() * 2 - 1);

      particles.push({
        bx: r * Math.sin(theta) * Math.cos(phi),
        by: r * Math.sin(theta) * Math.sin(phi),
        bz: r * Math.cos(theta),
        r,
        phase: rng() * Math.PI * 2,
        wSpeed: 0.14 + rng() * 0.38,
        size: r < 0.38 ? 0.55 + rng() * 0.9 :
        r < 0.86 ? 0.85 + rng() * 1.3 :
        1.1 + rng() * 1.9
      });
    }

    // ── Blob path helpers ──────────────────────────────────────────────────
    function blobPts(t, lod) {
      const energy = window.ARGUS_ORB_ENERGY || 'medium';
      const energyMap = { low: 0.5, medium: 1.0, high: 1.8 };
      const mult = energyMap[energy] || 1.0;
      const spd = (lod ? 2.1 : 1.0) * mult,amp = (lod ? 1.5 : 1.0) * mult;
      const pts = [];
      for (let i = 0; i < NB; i++) {
        const a = i / NB * Math.PI * 2 - Math.PI / 2;
        const r = BR * (
        1 +
        amp * 0.10 * Math.sin(2 * a + t * 0.55 * spd) +
        amp * 0.08 * Math.sin(3 * a - t * 0.82 * spd) +
        amp * 0.06 * Math.cos(4 * a + t * 0.47 * spd) +
        amp * 0.04 * Math.sin(5 * a - t * 1.10 * spd) + (
        lod ? amp * 0.04 * Math.cos(7 * a + t * 1.85) : 0));

        pts.push({ x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
      }
      return pts;
    }

    function drawBlobPath(pts) {
      const n = pts.length;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const p0 = pts[(i - 1 + n) % n],p1 = pts[i],p2 = pts[(i + 1) % n],p3 = pts[(i + 2) % n];
        const cp1x = p1.x + (p2.x - p0.x) / 6,cp1y = p1.y + (p2.y - p0.y) / 6;
        const cp2x = p2.x - (p3.x - p1.x) / 6,cp2y = p2.y - (p3.y - p1.y) / 6;
        if (i === 0) ctx.moveTo(p1.x, p1.y);
        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
      }
      ctx.closePath();
    }

    // ── Particle colour by depth + distance — LIQUID CHROME ──────────────
    function pColor(r, depthF) {
      let rgb, base;
      if (r < 0.32) {rgb = '238,236,252';base = 0.95;} else
      if (r < 0.68) {rgb = '200,198,228';base = 0.78;} else
      if (r < 1.05) {rgb = '158,156,195';base = 0.60;} else
      if (r < 1.40) {rgb = '120,118,162';base = 0.42;} else
      {rgb = '88,86,130';base = 0.26;}
      const a = Math.min(1, base * (0.32 + 0.68 * depthF));
      return `rgba(${rgb},${a.toFixed(3)})`;
    }

    // ── Draw one particle (dot + soft bloom halo) ──────────────────────────
    function drawParticle(px, py, size, r, depthF) {
      // Bloom halo
      const grad = ctx.createRadialGradient(px, py, 0, px, py, size * 3.2);
      grad.addColorStop(0, pColor(r, depthF * 0.4));
      grad.addColorStop(1, 'rgba(120,118,162,0)');
      ctx.fillStyle = grad;
      ctx.beginPath();ctx.arc(px, py, size * 3.2, 0, Math.PI * 2);ctx.fill();
      // Core dot
      ctx.fillStyle = pColor(r, depthF);
      ctx.beginPath();ctx.arc(px, py, Math.max(0.3, size), 0, Math.PI * 2);ctx.fill();
    }

    // ── Main draw ──────────────────────────────────────────────────────────
    const draw = (ts) => {
      if (!t0Ref.current) t0Ref.current = ts;
      const t = (ts - t0Ref.current) * 0.001;
      const lod = loadRef.current;
      const energy = window.ARGUS_ORB_ENERGY || 'medium';
      const energyMap = { low: 0.6, medium: 1.0, high: 1.6 };
      const energyMult = energyMap[energy] || 1.0;

      ctx.clearRect(0, 0, W, H);

      const floatY = Math.sin(t * 0.75) * 7;
      const rotSpd = (lod ? 0.44 : 0.13) * energyMult;
      const cosA = Math.cos(t * rotSpd);
      const sinA = Math.sin(t * rotSpd);
      const FOV = 3.8;

      // Transform + project all particles
      const xformed = particles.map((p) => {
        const wb = Math.sin(t * p.wSpeed + p.phase) * (lod ? 0.055 : 0.022) * energyMult;
        // Y-axis rotation
        const rx = p.bx * (1 + wb) * cosA + p.bz * sinA;
        const ry = p.by * (1 + wb);
        const rz = -(p.bx * (1 + wb)) * sinA + p.bz * cosA;
        const sc = FOV / (FOV + rz * 0.55);
        return {
          px: cx + rx * PR * sc,
          py: cy + ry * PR * sc + floatY,
          rz, sc,
          r: p.r,
          size: p.size * sc,
          depthF: (rz + 2.3) / 4.6
        };
      });

      // Sort back → front
      xformed.sort((a, b) => a.rz - b.rz);

      const back = xformed.filter((p) => p.rz < -0.05);
      const front = xformed.filter((p) => p.rz >= -0.05);

      // 1. Back particles
      for (const p of back) drawParticle(p.px, p.py, p.size, p.r, p.depthF);

      // 2. Wide ambient nebula glow — chrome
      const nebula = ctx.createRadialGradient(cx, cy + floatY, 0, cx, cy + floatY, BR * 3.0);
      nebula.addColorStop(0, 'rgba(188,186,225,0.26)');
      nebula.addColorStop(0.40, 'rgba(158,156,200,0.10)');
      nebula.addColorStop(0.75, 'rgba(128,126,172,0.04)');
      nebula.addColorStop(1, 'rgba(128,126,172,0)');
      ctx.fillStyle = nebula;
      ctx.beginPath();ctx.arc(cx, cy + floatY, BR * 3.0, 0, Math.PI * 2);ctx.fill();

      // 3. Blob
      ctx.save();
      ctx.translate(0, floatY);
      const pts = blobPts(t, lod);

      drawBlobPath(pts);
      const base = ctx.createRadialGradient(cx - BR * .22, cy - BR * .25, 0, cx, cy, BR * 1.1);
      base.addColorStop(0, '#f2f0ff');
      base.addColorStop(0.18, '#c8c6e0');
      base.addColorStop(0.52, '#9896b8');
      base.addColorStop(0.80, '#7a78a0');
      base.addColorStop(1, '#565478');
      ctx.fillStyle = base;ctx.fill();

      drawBlobPath(pts);
      const shad = ctx.createRadialGradient(cx + BR * .28, cy + BR * .34, 0, cx, cy, BR * .92);
      shad.addColorStop(0, 'rgba(12,10,30,0.60)');
      shad.addColorStop(1, 'rgba(12,10,30,0)');
      ctx.fillStyle = shad;ctx.fill();

      drawBlobPath(pts);
      const sp1 = ctx.createRadialGradient(
        cx - BR * .26 + Math.sin(t * .55) * 2.8, cy - BR * .33 + Math.cos(t * .42) * 2.2, 0,
        cx - BR * .26 + Math.sin(t * .55) * 2.8, cy - BR * .33 + Math.cos(t * .42) * 2.2, BR * .66);
      sp1.addColorStop(0, 'rgba(255,255,255,0.92)');
      sp1.addColorStop(0.28, 'rgba(255,255,255,0.30)');
      sp1.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = sp1;ctx.fill();

      drawBlobPath(pts);
      const sp2 = ctx.createRadialGradient(cx + BR * .32, cy - BR * .38, 0, cx + BR * .32, cy - BR * .38, BR * .12);
      sp2.addColorStop(0, 'rgba(255,255,255,0.46)');sp2.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = sp2;ctx.fill();

      drawBlobPath(pts);
      const rim = ctx.createRadialGradient(cx, cy - BR * .86, 0, cx, cy - BR * .52, BR * .36);
      rim.addColorStop(0, 'rgba(230,228,255,0.55)');rim.addColorStop(1, 'rgba(230,228,255,0)');
      ctx.fillStyle = rim;ctx.fill();

      ctx.restore();

      // 4. Front particles (pass through / in front of blob)
      for (const p of front) drawParticle(p.px, p.py, p.size, p.r, p.depthF);

      // 5. Loading rings
      if (lod) {
        const period = 1900,prog = ts % period / period;
        [0, 0.33, 0.66].forEach((off) => {
          const pp = (prog + off) % 1;
          const rr = BR * (1.18 + pp * 1.25);
          const a = Math.max(0, 0.50 * (1 - pp * 1.44));
          ctx.beginPath();ctx.arc(cx, cy + floatY, rr, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(185,183,220,${a.toFixed(3)})`;
          ctx.lineWidth = 1.4;ctx.stroke();
        });
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => {if (rafRef.current) cancelAnimationFrame(rafRef.current);};
  }, []);

  return (
    <div className="orb-wrap">
      <canvas ref={canvasRef} className="orb-canvas" width={260} height={260} />
      {loading && <div className="orb-dots"><span /><span /><span /></div>}
    </div>);

}

// ─── SIDEBAR ──────────────────────────────────────────────────────────────────
const CHAT_HISTORY = {
  'Сегодня': [
  'Найди площадку на 200 гостей — Екатеринбург',
  'Кейтеринг в бюджет 500K на корпоратив',
  'Список поставщиков звука и света'],

  'Вчера': [
  'Сравни 3 кейтеринга из каталога',
  'Бриф: конференция на 300 человек'],

  '7 дней': [
  'Радиомикрофоны в Екатеринбурге',
  'ТЗ для фотографа мероприятий',
  'Проверь поставщика ИНН 6671234567',
  'Оборудование для презентации',
  'Площадки для team building на природе']

};

const NAV_ITEMS = [
{ id: 'new-chat', label: 'Новая сессия', icon: 'edit', action: 'newChat' },
{ id: 'search', label: 'Поиск', icon: 'search', action: 'openSearch' },
{ id: 'plugins', label: 'Каталог', icon: 'plug', action: null },
{ id: 'automations', label: 'Документы', icon: 'clock', action: null }];


const PINNED_CHATS = [
{ id: 1, title: 'security research', shortcut: '⌘1' },
{ id: 2, title: 'Спроектировать единый чат', shortcut: '⌘2' },
{ id: 3, title: 'LLM роутер тех долг', shortcut: '⌘3' },
{ id: 4, title: 'Расширить router для брифов', shortcut: '⌘4' },
{ id: 5, title: 'Как использовать промпты', shortcut: '⌘5' },
{ id: 6, title: 'Добавить E2E демо на моках', shortcut: '⌘6' },
{ id: 7, title: 'Перейти на LLM API', shortcut: '⌘7' }];


function Sidebar({ activeNav, setActiveNav, activeChat, setActiveChat, onNewChat, onOpenSearch }) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [q, setQ] = useState('');
  const searchInputRef = useRef(null);

  useEffect(() => {
    if (searchOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [searchOpen]);

  const handleNavClick = (item) => {
    if (item.action === 'newChat') {
      onNewChat();
      setActiveNav(item.id);
    } else if (item.action === 'openSearch') {
      setSearchOpen(true);
    } else {
      setActiveNav(item.id);
    }
  };

  const handleSearchClose = () => {
    setSearchOpen(false);
    setQ('');
  };

  return (
    <>
      <aside className="sidebar">
        {/* Header */}
        <div className="s-head">
          <div className="brand">
            <div className="brand-mark">
              <IC d={P.eye} size={15} stroke="#aeacc8" strokeWidth={2.2} />
            </div>
            <span className="brand-name">ARGUS</span>
          </div>
          <button className="icon-btn" aria-label="Свернуть">
            <IC d={P.collapse} size={16} />
          </button>
        </div>

        {/* Nav items */}
        <nav className="s-nav">
          {NAV_ITEMS.map((n) =>
          <button
            key={n.id}
            className={`nav-link${activeNav === n.id ? ' active' : ''}`}
            onClick={() => handleNavClick(n)}>

              <span className="nav-icon"><IC d={P[n.icon]} size={15} /></span>
              <span className="nav-label">{n.label}</span>
            </button>
          )}
        </nav>

        <div className="s-divider" />

        {/* Pinned + History — единый скролл */}
        <div className="s-scroll">
          <div className="s-pinned-label">ИЗБРАННОЕ</div>
          <div className="s-pinned">
            {PINNED_CHATS.map((chat) =>
            <button
              key={chat.id}
              className={`pinned-item${activeChat === `pinned-${chat.id}` ? ' active' : ''}`}
              onClick={() => setActiveChat(`pinned-${chat.id}`)}>

                <span className="pinned-icon"><IC d={P.clip} size={14} /></span>
                <span className="pinned-title">{chat.title}</span>
                <span className="pinned-shortcut">{chat.shortcut}</span>
              </button>
            )}
          </div>

          {/* Chat history */}
          <div className="s-hist">
            {Object.entries(CHAT_HISTORY).map(([period, chats]) =>
            <div className="hist-group" key={period}>
                <span className="hist-label">{period}</span>
                {chats.
              filter((c) => !q || c.toLowerCase().includes(q.toLowerCase())).
              map((c, i) => {
                const id = `${period}-${i}`;
                return (
                  <button
                    key={id}
                    className={`hist-item${activeChat === id ? ' active' : ''}`}
                    onClick={() => setActiveChat(id)}>

                        {c}
                      </button>);

              })}
              </div>
            )}
          </div>
        </div>

        {/* User */}
        <div className="s-user">
          <div className="u-avatar">АМ</div>
          <div className="u-info">
            <div className="u-name">Алексей Морозов</div>
            <div className="u-email">a.morozov@agency.ru</div>
          </div>
          <button className="icon-btn" aria-label="Выйти">
            <IC d={P.logout} size={14} />
          </button>
        </div>
      </aside>

      {/* Search Modal */}
      {searchOpen &&
      <div className="search-modal-overlay" onClick={handleSearchClose}>
          <div className="search-modal" onClick={(e) => e.stopPropagation()}>
            <div className="search-modal-header">
              <IC d={P.search} size={20} style={{ color: '#a1a1aa' }} />
              <input
              ref={searchInputRef}
              type="text"
              placeholder="Search chats..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="search-modal-input" />

              <button className="search-modal-close" onClick={handleSearchClose}>
                <IC d="M18 6l-12 12M6 6l12 12" size={16} />
              </button>
            </div>
            <div className="search-modal-results">
              {q.trim() === '' ?
            <div className="search-empty">Start typing to search...</div> :

            Object.entries(CHAT_HISTORY).
            flatMap(([period, chats]) =>
            chats.
            filter((c) => c.toLowerCase().includes(q.toLowerCase())).
            map((c, i) => ({ c, period, id: `${period}-${i}` }))
            ).
            map((item) =>
            <button
              key={item.id}
              className="search-result-item"
              onClick={() => {
                setActiveChat(item.id);
                handleSearchClose();
              }}>

                      <IC d={P.clock} size={14} style={{ color: '#a1a1aa' }} />
                      <div className="search-result-text">
                        <div className="search-result-title">{item.c}</div>
                        <div className="search-result-period">{item.period}</div>
                      </div>
                    </button>
            )
            }
            </div>
          </div>
        </div>
      }
    </>);

}

// ─── INPUT COMPOSER ───────────────────────────────────────────────────────────
const MODES = [
{
  id: 'catalog',
  label: 'Поиск по каталогу',
  desc: 'Найти поставщиков, площадки, оборудование',
  icon: P.search
},
{
  id: 'brief',
  label: 'Планирование брифа',
  desc: 'Составить план мероприятия шаг за шагом',
  icon: P.brief
}];


function InputComposer({ onSend, loading }) {
  const [val, setVal] = useState('');
  const [mode, setMode] = useState('catalog');
  const taRef = useRef(null);

  const resize = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 180) + 'px';
  };

  const submit = () => {
    const msg = val.trim();
    if (!msg || loading) return;
    setVal('');
    if (taRef.current) taRef.current.style.height = 'auto';
    onSend(msg);
  };

  const activeMode = MODES.find((m) => m.id === mode);

  return (
    <div className="composer-wrap">
      <div className="composer-box composer-row">
        <textarea
          ref={taRef}
          className="composer-ta"
          placeholder={activeMode.desc + '...'}
          value={val}
          rows={1}
          disabled={loading}
          onChange={(e) => {setVal(e.target.value);resize();}}
          onKeyDown={(e) => {if (e.key === 'Enter' && !e.shiftKey) {e.preventDefault();submit();}}} />

        <div className="composer-send-wrap">
          <button
            className="send-btn"
            onClick={submit}
            disabled={!val.trim() || loading}
            aria-label="Отправить">

            <IC d={P.up} size={15} />
          </button>
        </div>
      </div>

      {/* Mode selector */}
      <div className="mode-bar">
        {MODES.map((m) =>
        <button
          key={m.id}
          className={`mode-tab${mode === m.id ? ' mode-tab-active' : ''}`}
          onClick={() => setMode(m.id)}>

            <span className="mode-tab-icon"><IC d={m.icon} size={13} /></span>
            <span className="mode-tab-label">{m.label}</span>
          </button>
        )}
      </div>
    </div>);

}

// ─── QUICK ACTIONS ────────────────────────────────────────────────────────────
const QUICK_ACTIONS = [
{ icon: 'chart', title: 'Синтез каталога', desc: 'Найти поставщиков по категории, городу и бюджету' },
{ icon: 'brief', title: 'Создать бриф', desc: 'Структурированный план мероприятия с позициями' },
{ icon: 'shield', title: 'Проверить поставщика', desc: 'Верификация ИНН, статуса и флагов риска' }];


function QuickActions({ onAction }) {
  return (
    <div className="quick-grid">
      {QUICK_ACTIONS.map((a) =>
      <button className="q-card" key={a.title} onClick={() => onAction(a.title)}>
          <div className="q-icon"><IC d={P[a.icon]} size={22} /></div>
          <div className="q-title">{a.title}</div>
          <div className="q-desc">{a.desc}</div>
        </button>
      )}
    </div>);

}

// ─── CHAT COMPONENTS ─────────────────────────────────────────────────────────
function ChatMessage({ role, content }) {
  return (
    <div className={`msg ${role === 'user' ? 'msg-user' : 'msg-asst'}`}>
      <div className="msg-role">{role === 'user' ? 'Вы' : 'ARGUS'}</div>
      <div className="msg-bubble">{content}</div>
    </div>);

}

function TypingIndicator() {
  return (
    <div className="msg msg-asst">
      <div className="msg-role">ARGUS</div>
      <div className="typing"><span /><span /><span /></div>
    </div>);

}

// ─── EXPORT ───────────────────────────────────────────────────────────────────
Object.assign(window, {
  IC, P,
  AnimatedBg, ArgusOrb,
  Sidebar, InputComposer, QuickActions,
  ChatMessage, TypingIndicator,
  CHAT_HISTORY, QUICK_ACTIONS, NAV_ITEMS, PINNED_CHATS
});
