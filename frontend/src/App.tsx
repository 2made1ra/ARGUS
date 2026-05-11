import { NavLink, Route, Routes } from "react-router-dom";
import AssistantPage from "./pages/AssistantPage";
import CatalogItemPage from "./pages/CatalogItemPage";
import CatalogPage from "./pages/CatalogPage";
import ContractorPage from "./pages/ContractorPage";
import DocumentPage from "./pages/DocumentPage";
import DocumentValidationPage from "./pages/DocumentValidationPage";
import Home from "./pages/Home";
import SearchPage from "./pages/SearchPage";

const navItems = [
  { to: "/", label: "Ассистент", glyph: "01" },
  { to: "/catalog", label: "Каталог", glyph: "02" },
  { to: "/search", label: "Документы", glyph: "03" },
  { to: "/documents/upload", label: "Загрузка", glyph: "04" },
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
        <Route path="/" element={<AssistantPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/catalog/items/:id" element={<CatalogItemPage />} />
        <Route path="/documents/upload" element={<Home />} />
        <Route path="/contractors/:id" element={<ContractorPage />} />
        <Route path="/documents/:id/validate" element={<DocumentValidationPage />} />
        <Route path="/documents/:id" element={<DocumentPage />} />
      </Routes>
    </div>
  );
}
