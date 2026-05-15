import { NavLink } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import type { SVGProps } from "react";

type IconPath = string | string[];

interface IconProps extends Omit<SVGProps<SVGSVGElement>, "d"> {
  d: IconPath;
  size?: number;
  strokeWidth?: number;
}

export const paths = {
  book: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z",
  brief: [
    "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z",
    "M14 2v6h6",
    "M16 13H8",
    "M16 17H8",
    "M10 9H8",
  ],
  chart: ["M18 20V10", "M12 20V4", "M6 20v-6"],
  chevD: "M6 9l6 6 6-6",
  clip: "M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48",
  clock: [
    "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z",
    "M12 6v6l4 2",
  ],
  collapse: "M15 18l-6-6 6-6",
  edit: [
    "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7",
    "M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  ],
  export: [
    "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4",
    "M7 10l5 5 5-5",
    "M12 15V3",
  ],
  eye: [
    "M2 12s4-8 10-8 10 8 10 8-4 8-10 8S2 12 2 12z",
    "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  ],
  files: [
    "M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z",
    "M13 2v7h7",
  ],
  link: [
    "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71",
    "M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71",
  ],
  logout: ["M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4", "M16 17l5-5-5-5", "M21 12H9"],
  more: ["M12 12h.01", "M7 12h.01", "M17 12h.01"],
  plug: [
    "M12 2v6m4-2h6m0 0v2a2 2 0 0 1-2 2h-2m-8 0H4a2 2 0 0 1-2-2V8m0-4h6M6 18v3m6 0v3m6-3v3M6 18h12",
    "M9 22h6",
  ],
  search: ["M21 21l-4.35-4.35", "M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"],
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  up: ["M12 19V5", "M5 12l7-7 7 7"],
};

const chatHistory = {
  Сегодня: [
    "Найди площадку на 200 гостей — Екатеринбург",
    "Кейтеринг в бюджет 500K на корпоратив",
    "Список поставщиков звука и света",
  ],
  Вчера: ["Сравни 3 кейтеринга из каталога", "Бриф: конференция на 300 человек"],
  "7 дней": [
    "Радиомикрофоны в Екатеринбурге",
    "ТЗ для фотографа мероприятий",
    "Проверь поставщика ИНН 6671234567",
    "Оборудование для презентации",
    "Площадки для team building на природе",
  ],
};

const pinnedChats = [
  { id: 1, title: "Каталог поставщиков", shortcut: "⌘1" },
  { id: 2, title: "Корпоратив на 120 гостей", shortcut: "⌘2" },
  { id: 3, title: "Проверка ИНН", shortcut: "⌘3" },
  { id: 4, title: "Финальный бриф", shortcut: "⌘4" },
];

const navItems = [
  { to: "/", label: "Новая сессия", icon: paths.edit },
  { to: "/search", label: "Поиск", icon: paths.search },
  { to: "/catalog", label: "Каталог", icon: paths.plug },
  { to: "/documents/upload", label: "Документы", icon: paths.clock },
];

export function Icon({ d, size = 16, strokeWidth = 1.8, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...rest}
    >
      {Array.isArray(d) ? d.map((path, index) => <path key={index} d={path} />) : <path d={d} />}
    </svg>
  );
}

export function AnimatedBg() {
  const refs = [useRef<HTMLDivElement>(null), useRef<HTMLDivElement>(null), useRef<HTMLDivElement>(null)];
  const state = useRef({ mx: 0.5, my: 0.5, angle: 0 });

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      state.current.mx = event.clientX / window.innerWidth;
      state.current.my = event.clientY / window.innerHeight;
    };
    window.addEventListener("mousemove", onMove, { passive: true });

    let frame = 0;
    const tick = () => {
      state.current.angle += 0.00055;
      const { mx, my, angle } = state.current;
      const dx = (mx - 0.5) * 55;
      const dy = (my - 0.5) * 38;
      const wx = Math.sin(angle) * 22;
      const wy = Math.cos(angle * 0.73) * 16;
      const transform = (index: number, sx: number, sy: number) =>
        `translate(${dx * sx + wx * (index % 2 === 0 ? 1 : -0.7)}px, ${
          dy * sy + wy * (index < 2 ? 1 : -0.6)
        }px)`;

      refs[0].current?.style.setProperty("transform", transform(0, 0.35, 0.25));
      refs[1].current?.style.setProperty("transform", transform(1, -0.28, 0.42));
      refs[2].current?.style.setProperty("transform", transform(2, 0.52, -0.33));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(frame);
    };
  }, [refs]);

  return (
    <div className="bg-layer">
      <div ref={refs[0]} className="blob blob-1" />
      <div ref={refs[1]} className="blob blob-2" />
      <div ref={refs[2]} className="blob blob-3" />
    </div>
  );
}

export function ArgusOrb({ loading = false }: { loading?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number | undefined>(undefined);
  const startRef = useRef<number | undefined>(undefined);
  const loadingRef = useRef(loading);
  loadingRef.current = loading;

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return undefined;

    const width = canvas.width;
    const height = canvas.height;
    const cx = width / 2;
    const cy = height / 2;
    const blobRadius = width * 0.2;
    const particleRadius = width * 0.4;
    const pointsCount = 12;
    const particles = Array.from({ length: 300 }, () => {
      const bucket = Math.random();
      const radius =
        bucket < 0.18
          ? Math.pow(Math.random(), 0.6) * 0.38
          : bucket < 0.55
            ? 0.38 + Math.random() * 0.48
            : bucket < 0.8
              ? 0.86 + Math.random() * 0.5
              : 1.36 + Math.random() * 0.7;
      const phi = Math.random() * Math.PI * 2;
      const theta = Math.acos(Math.random() * 2 - 1);
      return {
        bx: radius * Math.sin(theta) * Math.cos(phi),
        by: radius * Math.sin(theta) * Math.sin(phi),
        bz: radius * Math.cos(theta),
        radius,
        phase: Math.random() * Math.PI * 2,
        speed: 0.14 + Math.random() * 0.38,
        size: radius < 0.38 ? 0.55 + Math.random() * 0.9 : radius < 0.86 ? 0.85 + Math.random() * 1.3 : 1.1 + Math.random() * 1.9,
      };
    });

    const drawBlobPath = (points: Array<{ x: number; y: number }>) => {
      ctx.beginPath();
      for (let index = 0; index < points.length; index += 1) {
        const p0 = points[(index - 1 + points.length) % points.length];
        const p1 = points[index];
        const p2 = points[(index + 1) % points.length];
        const p3 = points[(index + 2) % points.length];
        const cp1x = p1.x + (p2.x - p0.x) / 6;
        const cp1y = p1.y + (p2.y - p0.y) / 6;
        const cp2x = p2.x - (p3.x - p1.x) / 6;
        const cp2y = p2.y - (p3.y - p1.y) / 6;
        if (index === 0) ctx.moveTo(p1.x, p1.y);
        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
      }
      ctx.closePath();
    };

    const blobPoints = (time: number, energized: boolean) => {
      const speed = energized ? 2.1 : 1;
      const amp = energized ? 1.5 : 1;
      return Array.from({ length: pointsCount }, (_, index) => {
        const angle = (index / pointsCount) * Math.PI * 2 - Math.PI / 2;
        const radius =
          blobRadius *
          (1 +
            amp * 0.1 * Math.sin(2 * angle + time * 0.55 * speed) +
            amp * 0.08 * Math.sin(3 * angle - time * 0.82 * speed) +
            amp * 0.06 * Math.cos(4 * angle + time * 0.47 * speed));
        return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
      });
    };

    const particleColor = (radius: number, depth: number) => {
      const [rgb, base] =
        radius < 0.32
          ? ["238,236,252", 0.95]
          : radius < 0.68
            ? ["200,198,228", 0.78]
            : radius < 1.05
              ? ["158,156,195", 0.6]
              : radius < 1.4
                ? ["120,118,162", 0.42]
                : ["88,86,130", 0.26];
      return `rgba(${rgb},${Math.min(1, base * (0.32 + 0.68 * depth)).toFixed(3)})`;
    };

    const drawParticle = (x: number, y: number, size: number, radius: number, depth: number) => {
      const glow = ctx.createRadialGradient(x, y, 0, x, y, size * 3.2);
      glow.addColorStop(0, particleColor(radius, depth * 0.4));
      glow.addColorStop(1, "rgba(120,118,162,0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(x, y, size * 3.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = particleColor(radius, depth);
      ctx.beginPath();
      ctx.arc(x, y, Math.max(0.3, size), 0, Math.PI * 2);
      ctx.fill();
    };

    const draw = (timestamp: number) => {
      startRef.current ??= timestamp;
      const time = (timestamp - startRef.current) * 0.001;
      const energized = loadingRef.current;
      ctx.clearRect(0, 0, width, height);

      const floatY = Math.sin(time * 0.75) * 7;
      const cosA = Math.cos(time * (energized ? 0.44 : 0.13));
      const sinA = Math.sin(time * (energized ? 0.44 : 0.13));

      const transformed = particles
        .map((particle) => {
          const wobble = Math.sin(time * particle.speed + particle.phase) * (energized ? 0.055 : 0.022);
          const rx = particle.bx * (1 + wobble) * cosA + particle.bz * sinA;
          const ry = particle.by * (1 + wobble);
          const rz = -(particle.bx * (1 + wobble)) * sinA + particle.bz * cosA;
          const scale = 3.8 / (3.8 + rz * 0.55);
          return {
            x: cx + rx * particleRadius * scale,
            y: cy + ry * particleRadius * scale + floatY,
            rz,
            radius: particle.radius,
            size: particle.size * scale,
            depth: (rz + 2.3) / 4.6,
          };
        })
        .sort((a, b) => a.rz - b.rz);

      transformed.filter((particle) => particle.rz < -0.05).forEach((particle) => drawParticle(particle.x, particle.y, particle.size, particle.radius, particle.depth));

      const nebula = ctx.createRadialGradient(cx, cy + floatY, 0, cx, cy + floatY, blobRadius * 3);
      nebula.addColorStop(0, "rgba(188,186,225,0.26)");
      nebula.addColorStop(0.4, "rgba(158,156,200,0.10)");
      nebula.addColorStop(1, "rgba(128,126,172,0)");
      ctx.fillStyle = nebula;
      ctx.beginPath();
      ctx.arc(cx, cy + floatY, blobRadius * 3, 0, Math.PI * 2);
      ctx.fill();

      ctx.save();
      ctx.translate(0, floatY);
      const points = blobPoints(time, energized);
      drawBlobPath(points);
      const base = ctx.createRadialGradient(cx - blobRadius * 0.22, cy - blobRadius * 0.25, 0, cx, cy, blobRadius * 1.1);
      base.addColorStop(0, "#f2f0ff");
      base.addColorStop(0.18, "#c8c6e0");
      base.addColorStop(0.52, "#9896b8");
      base.addColorStop(0.8, "#7a78a0");
      base.addColorStop(1, "#565478");
      ctx.fillStyle = base;
      ctx.fill();

      drawBlobPath(points);
      const shine = ctx.createRadialGradient(cx - blobRadius * 0.26, cy - blobRadius * 0.33, 0, cx - blobRadius * 0.26, cy - blobRadius * 0.33, blobRadius * 0.66);
      shine.addColorStop(0, "rgba(255,255,255,0.92)");
      shine.addColorStop(0.28, "rgba(255,255,255,0.30)");
      shine.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = shine;
      ctx.fill();
      ctx.restore();

      transformed.filter((particle) => particle.rz >= -0.05).forEach((particle) => drawParticle(particle.x, particle.y, particle.size, particle.radius, particle.depth));

      if (energized) {
        [0, 0.33, 0.66].forEach((offset) => {
          const progress = ((timestamp % 1900) / 1900 + offset) % 1;
          ctx.beginPath();
          ctx.arc(cx, cy + floatY, blobRadius * (1.18 + progress * 1.25), 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(185,183,220,${Math.max(0, 0.5 * (1 - progress * 1.44)).toFixed(3)})`;
          ctx.lineWidth = 1.4;
          ctx.stroke();
        });
      }

      frameRef.current = requestAnimationFrame(draw);
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => {
      if (frameRef.current !== undefined) cancelAnimationFrame(frameRef.current);
    };
  }, []);

  return (
    <div className="orb-wrap">
      <canvas ref={canvasRef} className="orb-canvas" width={260} height={260} />
      {loading && (
        <div className="orb-dots">
          <span />
          <span />
          <span />
        </div>
      )}
    </div>
  );
}

export function Sidebar() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeChat, setActiveChat] = useState<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (searchOpen) searchInputRef.current?.focus();
  }, [searchOpen]);

  const results = Object.entries(chatHistory).flatMap(([period, chats]) =>
    chats
      .filter((chat) => chat.toLowerCase().includes(query.toLowerCase()))
      .map((chat, index) => ({ id: `${period}-${index}`, period, chat })),
  );

  return (
    <>
      <aside className="sidebar">
        <div className="s-head">
          <div className="brand">
            <div className="brand-mark">
              <Icon d={paths.eye} size={15} stroke="#aeacc8" strokeWidth={2.2} />
            </div>
            <span className="brand-name">ARGUS</span>
          </div>
          <button className="icon-btn" aria-label="Свернуть">
            <Icon d={paths.collapse} size={16} />
          </button>
        </div>

        <nav className="s-nav" aria-label="Основная навигация">
          {navItems.map((item) =>
            item.to === "/search" ? (
              <button key={item.to} className="nav-link" type="button" onClick={() => setSearchOpen(true)}>
                <span className="nav-icon">
                  <Icon d={item.icon} size={15} />
                </span>
                <span className="nav-label">{item.label}</span>
              </button>
            ) : (
              <NavLink key={item.to} to={item.to} end={item.to === "/"} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
                <span className="nav-icon">
                  <Icon d={item.icon} size={15} />
                </span>
                <span className="nav-label">{item.label}</span>
              </NavLink>
            ),
          )}
        </nav>

        <div className="s-divider" />

        <div className="s-scroll">
          <div className="s-pinned-label">Избранное</div>
          <div className="s-pinned">
            {pinnedChats.map((chat) => (
              <button key={chat.id} className={`pinned-item${activeChat === `pinned-${chat.id}` ? " active" : ""}`} type="button" onClick={() => setActiveChat(`pinned-${chat.id}`)}>
                <span className="pinned-icon">
                  <Icon d={paths.clip} size={14} />
                </span>
                <span className="pinned-title">{chat.title}</span>
                <span className="pinned-shortcut">{chat.shortcut}</span>
              </button>
            ))}
          </div>

          <div className="s-hist">
            {Object.entries(chatHistory).map(([period, chats]) => (
              <div className="hist-group" key={period}>
                <span className="hist-label">{period}</span>
                {chats.map((chat, index) => {
                  const id = `${period}-${index}`;
                  return (
                    <button key={id} className={`hist-item${activeChat === id ? " active" : ""}`} type="button" onClick={() => setActiveChat(id)}>
                      {chat}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

        <div className="s-user">
          <div className="u-avatar">AM</div>
          <div className="u-info">
            <div className="u-name">Agency Manager</div>
            <div className="u-email">argus@event-agency.local</div>
          </div>
          <button className="icon-btn" aria-label="Выйти">
            <Icon d={paths.logout} size={14} />
          </button>
        </div>
      </aside>

      {searchOpen && (
        <div className="search-modal-overlay" onClick={() => setSearchOpen(false)}>
          <div className="search-modal" onClick={(event) => event.stopPropagation()}>
            <div className="search-modal-header">
              <Icon d={paths.search} size={20} />
              <input ref={searchInputRef} className="search-modal-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search chats..." />
              <button className="search-modal-close" type="button" onClick={() => setSearchOpen(false)} aria-label="Закрыть поиск">
                <Icon d="M18 6l-12 12M6 6l12 12" size={16} />
              </button>
            </div>
            <div className="search-modal-results">
              {query.trim() === "" ? (
                <div className="search-empty">Start typing to search...</div>
              ) : (
                results.map((item) => (
                  <button key={item.id} className="search-result-item" type="button" onClick={() => setActiveChat(item.id)}>
                    <Icon d={paths.clock} size={14} />
                    <div className="search-result-text">
                      <div className="search-result-title">{item.chat}</div>
                      <div className="search-result-period">{item.period}</div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export function MainHeader() {
  return (
    <div className="m-hdr">
      <div className="m-hdr-l">
        <button className="model-pill" type="button">
          <span className="model-dot" />
          ARGUS Assistant
          <Icon d={paths.chevD} size={13} />
        </button>
      </div>
      <div className="m-hdr-r">
        <button className="h-ico-btn" aria-label="Меню" type="button">
          <Icon d={paths.more} size={16} />
        </button>
        <button className="h-ico-btn" aria-label="Ссылка" type="button">
          <Icon d={paths.link} size={15} />
        </button>
        <button className="h-btn" type="button">
          <Icon d={paths.export} size={14} />
          Экспорт
        </button>
        <button className="h-btn primary" type="button">
          PRO
        </button>
      </div>
    </div>
  );
}

export const composerModes = [
  {
    id: "catalog",
    label: "Поиск по каталогу",
    desc: "Найти поставщиков, площадки, оборудование",
    icon: paths.search,
  },
  {
    id: "brief",
    label: "Планирование брифа",
    desc: "Составить план мероприятия шаг за шагом",
    icon: paths.brief,
  },
] as const;
