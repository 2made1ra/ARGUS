/* eslint-disable */
const { useState, useEffect, useRef } = React;

// ─── MOCK DATA ────────────────────────────────────────────────────────────────
const MOCK = {
  search:
`Анализирую каталог...\n\nНашёл 12 позиций по вашему запросу. Топ-3 по совпадению:\n\n1. Аудио Профи — радиомикрофоны Shure, ₽ 2 500/день\n2. СаундМакс — комплект PA + мониторы, ₽ 18 000/день\n3. ЕкбАудио — свет + звук полный пакет, ₽ 24 000/день\n\nПоказать детальные карточки или добавить кандидатов в бриф?`,

  brief:
`Черновик брифа готов:\n\nТип: Корпоратив\nГостей: 120 чел.\nГород: Екатеринбург\nНужны: площадка, кейтеринг, звук, свет\n\nУточните даты и бюджет — начну поиск площадок и поставщиков.`,

  verify:
`Проверяю контрагента...\n\n✓ ИНН подтверждён в ЕГРЮЛ\n✓ Статус: Действующий\n✓ Дата регистрации: 14.03.2018\n✓ Флаги рисков: не обнаружены\n\nПоставщик верифицирован, можно включать в бриф.`,

  default:
`Понял ваш запрос. Обрабатываю...\n\nДля поиска поставщиков уточните категорию услуги и город. Для брифа — формат события и количество гостей. Для проверки — укажите ИНН или название компании.`,
};

function getMock(msg) {
  const m = msg.toLowerCase();
  if (/найд|поиск|постав|подрядч|микроф|звук|площадк|свет|аренд|каталог/.test(m)) return MOCK.search;
  if (/бриф|меропри|корпор|план|организ|конфер|событ|гостей/.test(m))              return MOCK.brief;
  if (/провер|верифик|инн|контраг|статус|огрн/.test(m))                            return MOCK.verify;
  return MOCK.default;
}

// ─── MAIN HEADER ──────────────────────────────────────────────────────────────
function MainHeader() {
  return (
    <div className="m-hdr">
      <div className="m-hdr-l">
        <button className="model-pill">
          <span className="model-dot" />
          ARGUS Assistant
          <IC d={P.chevD} size={13} />
        </button>
      </div>
      <div className="m-hdr-r">
        <button className="h-ico-btn" aria-label="Меню"><IC d={P.more} size={16} /></button>
        <button className="h-ico-btn" aria-label="Ссылка"><IC d={P.link} size={15} /></button>
        <button className="h-btn">
          <IC d={P.export} size={14} />
          Экспорт
        </button>
        <button className="h-btn primary">PRO</button>
      </div>
    </div>
  );
}

// ─── EMPTY STATE ──────────────────────────────────────────────────────────────
function EmptyState({ loading, onSend }) {
  return (
    <div className="empty-area">
      <ArgusOrb loading={loading} />
      <div className="greeting-name">Привет!</div>
      <div className="greeting-q">Чем могу помочь?</div>
      <InputComposer onSend={onSend} loading={loading} />
    </div>
  );
}

// ─── CHAT AREA ────────────────────────────────────────────────────────────────
function ChatArea({ messages, loading, onSend }) {
  const threadRef = useRef(null);

  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, loading]);

  return (
    <div className="chat-area">
      <div className="chat-thread" ref={threadRef}>
        {messages.map((m, i) => (
          <ChatMessage key={i} role={m.role} content={m.content} />
        ))}
        {loading && <TypingIndicator />}
      </div>
      <InputComposer onSend={onSend} loading={loading} />
    </div>
  );
}

// ─── APP ──────────────────────────────────────────────────────────────────────
function App() {
  const [messages, setMessages]     = useState([]);
  const [loading, setLoading]       = useState(false);
  const [activeNav, setActiveNav]   = useState('new-chat');
  const [activeChat, setActiveChat] = useState(null);

  async function handleSend(msg) {
    setMessages(prev => [...prev, { role: 'user', content: msg }]);
    setLoading(true);
    const delay = 1200 + Math.random() * 900;
    await new Promise(r => setTimeout(r, delay));
    setMessages(prev => [...prev, { role: 'assistant', content: getMock(msg) }]);
    setLoading(false);
  }

  function handleNewChat() {
    setMessages([]);
    setActiveChat(null);
  }

  const hasChat = messages.length > 0 || loading;

  return (
    <>
      <AnimatedBg />
      <div className="app">
        <Sidebar
          activeNav={activeNav}
          setActiveNav={setActiveNav}
          activeChat={activeChat}
          setActiveChat={setActiveChat}
          onNewChat={handleNewChat}
        />
        <main className="main">
          {hasChat
            ? <ChatArea messages={messages} loading={loading} onSend={handleSend} />
            : <EmptyState loading={loading} onSend={handleSend} />
          }

          <div className="m-footer">
            Присоединяйтесь к сообществу ARGUS —&nbsp;
            <a href="#">свяжитесь с нами</a>
          </div>
        </main>
      </div>
    </>
  );
}

// ─── RENDER ───────────────────────────────────────────────────────────────────
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
