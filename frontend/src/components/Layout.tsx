/** App shell: sidebar navigation, top bar with period picker + theme toggle.
 * Mobile-first: sidebar collapses to a slide-over below lg. */
import {
  BadgeDollarSign, BookOpenText, Calendar, FileSpreadsheet, Fuel, Landmark,
  LayoutDashboard, LogOut, Menu, Moon, Receipt, Route, ScrollText, Settings2,
  Sun, UtensilsCrossed, Wallet, X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { taxYear, useStore } from "../store";
import { Button, cx, Select } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/transactions", label: "Bank Import", icon: Landmark },
  { to: "/revenue", label: "Revenue", icon: BadgeDollarSign },
  { to: "/invoices", label: "Invoices", icon: Receipt },
  { to: "/expenses", label: "Expenses", icon: Wallet },
  { to: "/fuel", label: "Fuel & IFTA", icon: Fuel },
  { to: "/trips", label: "Trips & Mileage", icon: Route },
  { to: "/meals", label: "Meals & Per Diem", icon: UtensilsCrossed },
  { to: "/fixed-costs", label: "Home Office & Phone", icon: ScrollText },
  { to: "/reports", label: "Reports & Exports", icon: FileSpreadsheet },
  { to: "/tax-rules", label: "CRA Tax Rules", icon: BookOpenText },
  { to: "/settings", label: "Settings", icon: Settings2 },
];

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <span className="grid size-9 place-items-center rounded-xl bg-accent text-lg text-white">🛻</span>
        <div>
          <p className="text-[15px] font-bold leading-tight text-ink-1">RigBooks</p>
          <p className="text-[11px] text-ink-3">CRA-ready bookkeeping</p>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === "/"} onClick={onNavigate}
            className={({ isActive }) => cx(
              "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-accent-soft text-accent"
                : "text-ink-2 hover:bg-surface-2 hover:text-ink-1")}>
            <Icon size={17} strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

function PeriodPicker() {
  const { period, setPeriod } = useStore();
  const thisYear = new Date().getFullYear();
  const years = Array.from({ length: 7 }, (_, i) => thisYear + 1 - i);
  const isCustom = !years.some((y) => period.label === `Tax year ${y}`);
  return (
    <div className="flex items-center gap-2">
      <Calendar size={15} className="hidden text-ink-3 sm:block" />
      <Select
        value={isCustom ? "custom" : period.label}
        onChange={(e) => {
          const v = e.target.value;
          if (v !== "custom") setPeriod(taxYear(Number(v.replace("Tax year ", ""))));
        }}
        className="!w-auto py-1.5">
        {years.map((y) => <option key={y} value={`Tax year ${y}`}>Tax year {y}</option>)}
        {isCustom && <option value="custom">{period.label}</option>}
      </Select>
      <input type="date" value={period.start} aria-label="Period start"
        onChange={(e) => setPeriod({ ...period, start: e.target.value, label: "Custom range" })}
        className="hidden rounded-xl border border-line bg-surface-2 px-2 py-1.5 text-xs text-ink-2 md:block" />
      <input type="date" value={period.end} aria-label="Period end"
        onChange={(e) => setPeriod({ ...period, end: e.target.value, label: "Custom range" })}
        className="hidden rounded-xl border border-line bg-surface-2 px-2 py-1.5 text-xs text-ink-2 md:block" />
    </div>
  );
}

export default function Layout() {
  const { dark, toggleDark, logout, user } = useStore();
  const [open, setOpen] = useState(false);
  return (
    <div className="flex h-full">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-line bg-surface-1 lg:block">
        <Sidebar />
      </aside>
      {/* Mobile slide-over */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-surface-1 shadow-xl">
            <button className="absolute right-3 top-4 text-ink-2" onClick={() => setOpen(false)}
              aria-label="Close menu"><X size={20} /></button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-line bg-surface-1/90 px-4 py-2.5 backdrop-blur">
          <div className="flex items-center gap-2">
            <button className="rounded-lg p-1.5 text-ink-2 hover:bg-surface-2 lg:hidden"
              onClick={() => setOpen(true)} aria-label="Open menu">
              <Menu size={20} />
            </button>
            <PeriodPicker />
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" onClick={toggleDark}
              title={dark ? "Switch to light mode" : "Switch to dark mode"}>
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </Button>
            <span className="hidden max-w-[16ch] truncate text-xs text-ink-3 sm:block">
              {user?.name}
            </span>
            <Button variant="ghost" onClick={logout} title="Sign out">
              <LogOut size={17} />
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
