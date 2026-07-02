/** App shell: sidebar nav, top bar with fiscal-period picker + theme toggle.
 * Collapses to a slide-over below lg for field use. */
import {
  Banknote, BookOpenText, Calendar, ClipboardPen, FileSpreadsheet, Hammer,
  Landmark, LayoutDashboard, LogOut, Menu, Moon, Receipt, Settings2, Sun,
  Truck, UserRound, Wallet, X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { fiscalYear, useStore } from "../store";
import { Button, cx, Select } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/transactions", label: "Bank Import", icon: Landmark },
  { to: "/jobs", label: "Jobs & Field Tickets", icon: Hammer },
  { to: "/field", label: "Field Entry", icon: ClipboardPen },
  { to: "/invoices", label: "Invoices", icon: Receipt },
  { to: "/expenses", label: "Expenses", icon: Wallet },
  { to: "/equipment", label: "Equipment & CCA", icon: Truck },
  { to: "/shareholder", label: "Dividends & Loans", icon: Banknote },
  { to: "/personal-tax", label: "Personal Tax Bridge", icon: UserRound },
  { to: "/reports", label: "Reports & Exports", icon: FileSpreadsheet },
  { to: "/tax-rules", label: "Tax Rules", icon: BookOpenText },
  { to: "/settings", label: "Settings", icon: Settings2 },
];

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <span className="grid size-9 place-items-center rounded-xl bg-accent text-lg text-white">🔥</span>
        <div>
          <p className="text-[15px] font-bold leading-tight text-ink-1">OilForge</p>
          <p className="text-[11px] text-ink-3">corporate oilfield books</p>
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
  const isCustom = !years.some((y) => period.label === `Fiscal ${y}`);
  return (
    <div className="flex items-center gap-2">
      <Calendar size={15} className="hidden text-ink-3 sm:block" />
      <Select value={isCustom ? "custom" : period.label}
        onChange={(e) => {
          const v = e.target.value;
          if (v !== "custom") setPeriod(fiscalYear(Number(v.replace("Fiscal ", ""))));
        }}
        className="!w-auto py-1.5">
        {years.map((y) => <option key={y} value={`Fiscal ${y}`}>Fiscal {y}</option>)}
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
      <aside className="hidden w-60 shrink-0 border-r border-line bg-surface-1 lg:block">
        <Sidebar />
      </aside>
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
