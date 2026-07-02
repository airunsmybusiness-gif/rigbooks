import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import EquipmentPage from "./pages/Equipment";
import Expenses from "./pages/Expenses";
import Invoices from "./pages/Invoices";
import Jobs from "./pages/Jobs";
import Login from "./pages/Login";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
import ShareholderPage from "./pages/Shareholder";
import TaxRules from "./pages/TaxRules";
import Transactions from "./pages/Transactions";
import { useStore } from "./store";

export default function App() {
  const { user } = useStore();
  if (!user) return <Login />;
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/invoices" element={<Invoices />} />
          <Route path="/expenses" element={<Expenses />} />
          <Route path="/equipment" element={<EquipmentPage />} />
          <Route path="/shareholder" element={<ShareholderPage />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/tax-rules" element={<TaxRules />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
