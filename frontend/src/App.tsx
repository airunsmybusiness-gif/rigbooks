import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import {
  ExpensesPage, FuelPage, MealsPage, RevenuePage, TripsPage,
} from "./pages/entityPages";
import FixedCosts from "./pages/FixedCosts";
import Invoices from "./pages/Invoices";
import Login from "./pages/Login";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
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
          <Route path="/revenue" element={<RevenuePage />} />
          <Route path="/invoices" element={<Invoices />} />
          <Route path="/expenses" element={<ExpensesPage />} />
          <Route path="/fuel" element={<FuelPage />} />
          <Route path="/trips" element={<TripsPage />} />
          <Route path="/meals" element={<MealsPage />} />
          <Route path="/fixed-costs" element={<FixedCosts />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/tax-rules" element={<TaxRules />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
