import { NavLink, Route, Routes } from "react-router-dom";
import CatalogPage from "./pages/CatalogPage";
import ContractorPage from "./pages/ContractorPage";
import DocumentPage from "./pages/DocumentPage";
import DocumentValidationPage from "./pages/DocumentValidationPage";
import Home from "./pages/Home";
import SearchPage from "./pages/SearchPage";

const navItems = [
  { to: "/", label: "Загрузка", glyph: "01" },
  { to: "/search", label: "AI-поиск", glyph: "02" },
  { to: "/catalog", label: "Каталог", glyph: "03" },
];

export default function App() {
  return (
    <div className="app-shell">
      <aside className="side-rail">
        <div className="brand-lockup">
          <div className="brand-mark">V</div>
          <div>
            <strong>VIZIER</strong>
            <span>ARGUS intelligence</span>
          </div>
        </div>
        <nav className="side-nav" aria-label="Основная навигация">
          {navItems.map((item) => (
            <NavLink
              className={({ isActive }) =>
                `side-nav__item${isActive ? " side-nav__item--active" : ""}`
              }
              end={item.to === "/"}
              key={item.to}
              to={item.to}
            >
              <span>{item.glyph}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/contractors/:id" element={<ContractorPage />} />
        <Route path="/documents/:id/validate" element={<DocumentValidationPage />} />
        <Route path="/documents/:id" element={<DocumentPage />} />
      </Routes>
    </div>
  );
}
