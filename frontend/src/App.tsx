import { Route, Routes } from "react-router-dom";
import { useEffect } from "react";
import { AnimatedBg, MainHeader, Sidebar } from "./components/ArgusChrome";
import AssistantPage from "./pages/AssistantPage";
import CatalogItemPage from "./pages/CatalogItemPage";
import CatalogPage from "./pages/CatalogPage";
import ContractorPage from "./pages/ContractorPage";
import DocumentPage from "./pages/DocumentPage";
import DocumentValidationPage from "./pages/DocumentValidationPage";
import Home from "./pages/Home";
import SearchPage from "./pages/SearchPage";

export default function App() {
  useEffect(() => {
    document.body.setAttribute("data-mood", "ocean");
    document.body.setAttribute("data-density", "balanced");
  }, []);

  return (
    <>
      <AnimatedBg />
      <div className="app">
        <Sidebar />
        <div className="main">
          <MainHeader />
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
          <div className="m-footer">
            ARGUS catalog-first workspace · поставщики, документы и брифы в одном контуре
          </div>
        </div>
      </div>
    </>
  );
}
