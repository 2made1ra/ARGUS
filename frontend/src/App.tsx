import { Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import ContractorPage from "./pages/ContractorPage";
import DocumentPage from "./pages/DocumentPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/contractors/:id" element={<ContractorPage />} />
      <Route path="/documents/:id" element={<DocumentPage />} />
    </Routes>
  );
}
