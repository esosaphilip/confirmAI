import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import VerifyPage from "./pages/VerifyPage";
import RulesPage from "./pages/RulesPage";
import RunPage from "./pages/RunPage";
import HistoryPage from "./pages/HistoryPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<VerifyPage />} />
        <Route path="/rules" element={<RulesPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/runs/:runId" element={<RunPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
