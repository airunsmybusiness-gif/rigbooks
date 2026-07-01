/** Config-driven entity pages built on CrudPage: revenue, expenses,
 * fuel, trips, meals. */
import { useEffect, useState } from "react";
import { api, money } from "../api";
import CrudPage, { type FieldDef } from "../components/CrudPage";
import { Badge } from "../components/ui";

const sum = (items: any[], f: (x: any) => number) =>
  items.reduce((s, x) => s + f(x), 0);

function TotalsBar({ entries }: { entries: [string, number][] }) {
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-1 rounded-xl border border-line bg-surface-1 px-4 py-3 text-sm">
      {entries.map(([label, v]) => (
        <span key={label} className="text-ink-2">
          {label}: <strong className="tabular-nums text-ink-1">{money(v)}</strong>
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- Revenue

export function RevenuePage() {
  const fields: FieldDef[] = [
    { name: "date", label: "Date", type: "date", required: true },
    { name: "amount", label: "Amount ($)", type: "number", step: "0.01", required: true },
    { name: "client", label: "Client", placeholder: "e.g. Long Run Exploration" },
    { name: "job", label: "Job / service", placeholder: "e.g. Hotshot to Redwater" },
    { name: "gst_included", label: "GST included in amount", type: "checkbox", defaultValue: true },
    { name: "notes", label: "Notes", placeholder: "e.g. ticket #1234" },
  ];
  return (
    <CrudPage title="Revenue" sub="Hauling tickets, oilfield jobs, consulting — GST is split out automatically"
      path="/api/revenue" fields={fields}
      columns={[
        { key: "date", label: "Date" },
        { key: "client", label: "Client" },
        { key: "job", label: "Job" },
        { key: "amount", label: "Amount", right: true, render: (r) => money(r.amount) },
        { key: "gst_amount", label: "GST", right: true, render: (r) => money(r.gst_amount) },
      ]}
      footer={(items) => (
        <TotalsBar entries={[
          ["Total revenue", sum(items, (r) => r.amount)],
          ["GST collected", sum(items, (r) => r.gst_amount)],
        ]} />
      )} />
  );
}

// ---------------------------------------------------------------- Expenses

const EXPENSE_CATEGORIES = [
  "Fuel & Petroleum", "Vehicle Repairs", "Vehicle - Loan/Lease Payment",
  "Vehicle - Insurance", "Vehicle - Registration", "Equipment & Tools",
  "Safety Gear & PPE", "Meals (50%)", "Meals - Long Haul (80%)",
  "Professional Fees", "Office Supplies", "Phone & Communications", "Internet",
  "Training & Certifications", "Software & Subscriptions",
  "Travel & Accommodations", "Insurance", "Rent - Work Accommodation",
  "Utilities", "Bank Fees", "Other Business",
];

export function ExpensesPage() {
  const fields: FieldDef[] = [
    { name: "date", label: "Date", type: "date", required: true },
    { name: "amount", label: "Amount ($)", type: "number", step: "0.01", required: true },
    { name: "description", label: "Description", placeholder: "e.g. New tires", span2: true },
    { name: "category", label: "Category", type: "select", options: EXPENSE_CATEGORIES },
    {
      name: "source", label: "Paid with", type: "select",
      options: [
        { value: "cash", label: "Cash / debit" },
        { value: "personal", label: "Personal account (reimbursable)" },
        { value: "vehicle", label: "Vehicle cost (mixed use)" },
        { value: "other", label: "Other" },
      ],
    },
    { name: "vendor", label: "Vendor", placeholder: "for T4A tracking" },
    { name: "paid_by", label: "Paid by", placeholder: "e.g. Greg" },
    { name: "business_pct", label: "Business use %", type: "number", defaultValue: 100 },
    { name: "receipt_ref", label: "Receipt # / link", placeholder: "e.g. R-001" },
  ];
  return (
    <CrudPage title="Expenses"
      sub="Cash, personal-account and vehicle costs — ITC is computed from the year's CRA rules"
      path="/api/expenses" fields={fields}
      columns={[
        { key: "date", label: "Date" },
        { key: "description", label: "Description" },
        { key: "category", label: "Category" },
        { key: "source", label: "Source", render: (r) => <Badge>{r.source}</Badge> },
        { key: "business_pct", label: "Biz %", right: true },
        { key: "amount", label: "Amount", right: true, render: (r) => money(r.amount) },
        { key: "itc", label: "ITC", right: true, render: (r) => money(r.itc) },
        { key: "receipt_ref", label: "Receipt" },
      ]}
      footer={(items) => (
        <TotalsBar entries={[
          ["Total", sum(items, (r) => r.amount)],
          ["Deductible", sum(items, (r) => r.amount * r.business_pct / 100)],
          ["ITCs", sum(items, (r) => r.itc)],
        ]} />
      )} />
  );
}

// -------------------------------------------------------------------- Fuel

const JURISDICTIONS = ["AB", "BC", "SK", "MB", "ON", "QC", "NB", "NS", "PE",
  "NL", "YT", "NT", "MT", "ND", "SD", "WA", "ID"];

export function FuelPage() {
  const fields: FieldDef[] = [
    { name: "date", label: "Date", type: "date", required: true },
    { name: "amount", label: "Amount ($)", type: "number", step: "0.01", required: true },
    { name: "litres", label: "Litres", type: "number", step: "0.1", required: true },
    { name: "jurisdiction", label: "Province / state", type: "select", options: JURISDICTIONS },
    { name: "vendor", label: "Vendor", placeholder: "e.g. Flying J Nisku" },
    { name: "fuel_type", label: "Fuel", type: "select", options: ["diesel", "gasoline", "DEF"] },
    { name: "receipt_ref", label: "Receipt #", placeholder: "e.g. R-101" },
  ];
  return (
    <CrudPage title="Fuel purchases"
      sub="100% business use — litres and jurisdiction feed the IFTA quarterly report"
      path="/api/fuel" fields={fields}
      columns={[
        { key: "date", label: "Date" },
        { key: "vendor", label: "Vendor" },
        { key: "jurisdiction", label: "Juris.", render: (r) => <Badge tone="accent">{r.jurisdiction}</Badge> },
        { key: "litres", label: "Litres", right: true },
        { key: "amount", label: "Amount", right: true, render: (r) => money(r.amount) },
        { key: "itc", label: "ITC", right: true, render: (r) => money(r.itc) },
      ]}
      footer={(items) => (
        <TotalsBar entries={[
          ["Total fuel", sum(items, (r) => r.amount)],
          ["ITCs", sum(items, (r) => r.itc)],
        ]} />
      )} />
  );
}

// ------------------------------------------------------------------- Trips

export function TripsPage() {
  const fields: FieldDef[] = [
    { name: "date", label: "Date", type: "date", required: true },
    { name: "purpose", label: "Purpose", placeholder: "e.g. Haul to Redwater" },
    { name: "origin", label: "From", placeholder: "e.g. Edmonton" },
    { name: "destination", label: "To", placeholder: "e.g. Fort McMurray" },
    { name: "odometer_start", label: "Odometer start", type: "number", step: "1" },
    { name: "odometer_end", label: "Odometer end", type: "number", step: "1" },
    { name: "business_km", label: "Business km", type: "number", step: "0.1", required: true },
    { name: "revenue_amount", label: "Ticket value ($, optional)", type: "number", step: "0.01" },
  ];
  return (
    <CrudPage title="Trips & mileage log"
      sub="CRA logbook: date, destination, purpose, odometer — drives business-use % and IFTA distance"
      path="/api/trips" fields={fields}
      transform={(f) => ({
        ...f,
        odometer_start: f.odometer_start === "" ? null : f.odometer_start,
        odometer_end: f.odometer_end === "" ? null : f.odometer_end,
        revenue_amount: f.revenue_amount === "" ? 0 : f.revenue_amount,
      })}
      columns={[
        { key: "date", label: "Date" },
        { key: "route", label: "Route", render: (r) => `${r.origin} → ${r.destination}` },
        { key: "purpose", label: "Purpose" },
        { key: "business_km", label: "Biz km", right: true },
        { key: "total_km", label: "Total km", right: true },
      ]}
      footer={(items) => {
        const biz = sum(items, (r) => r.business_km);
        const total = sum(items, (r) => r.total_km);
        return (
          <div className="flex flex-wrap gap-x-6 gap-y-1 rounded-xl border border-line bg-surface-1 px-4 py-3 text-sm text-ink-2">
            <span>Business km: <strong className="text-ink-1">{biz.toLocaleString()}</strong></span>
            <span>Total km: <strong className="text-ink-1">{total.toLocaleString()}</strong></span>
            <span>Business use: <strong className="text-ink-1">
              {total ? Math.min(100, (biz / total) * 100).toFixed(1) : 0}%</strong></span>
          </div>
        );
      }} />
  );
}

// ------------------------------------------------------------------- Meals

export function MealsPage() {
  const [rates, setRates] = useState<any>(null);
  useEffect(() => {
    api.get(`/api/rules/${new Date().getFullYear()}`).then((r) => setRates(r.meals))
      .catch(() => {});
  }, []);
  const fields: FieldDef[] = [
    { name: "date", label: "Date", type: "date", required: true },
    {
      name: "method", label: "Method", type: "select",
      options: [
        { value: "simplified", label: "Simplified (flat rate/meal)" },
        { value: "detailed", label: "Detailed (receipts)" },
      ],
    },
    { name: "meals_count", label: "Meals (simplified)", type: "number", defaultValue: 3 },
    { name: "amount", label: "Amount $ (detailed)", type: "number", step: "0.01", defaultValue: 0 },
    { name: "long_haul", label: "Long-haul trip (80% deductible)", type: "checkbox", defaultValue: true },
    { name: "location", label: "Location", placeholder: "e.g. Fort McMurray" },
    { name: "receipt_ref", label: "Receipt #", placeholder: "detailed method" },
  ];
  return (
    <div>
      {rates && (
        <p className="mb-3 rounded-xl bg-accent-soft/60 px-4 py-2 text-sm text-ink-2">
          CRA simplified rate: <strong>${rates.simplified_rate_per_meal}/meal</strong>, max{" "}
          {rates.max_meals_per_day}/day · long-haul drivers deduct{" "}
          <strong>{rates.long_haul_deductible_pct * 100}%</strong> (others{" "}
          {rates.standard_deductible_pct * 100}%). Long-haul = trips ≥{" "}
          {rates.long_haul_min_distance_km} km away for {rates.long_haul_min_hours_away}+ hours.
        </p>
      )}
      <CrudPage title="Meals & per diem"
        sub="Simplified TL2-style flat rate or detailed receipts — long-haul 80% rule applied automatically"
        path="/api/meals" fields={fields}
        columns={[
          { key: "date", label: "Date" },
          { key: "location", label: "Location" },
          { key: "method", label: "Method", render: (r) => <Badge>{r.method}</Badge> },
          { key: "meals_count", label: "Meals", right: true },
          { key: "amount", label: "Receipts", right: true, render: (r) => r.amount ? money(r.amount) : "—" },
          {
            key: "long_haul", label: "Rate",
            render: (r) => <Badge tone={r.long_haul ? "good" : "neutral"}>
              {r.long_haul ? "80%" : "50%"}</Badge>,
          },
        ]} />
    </div>
  );
}
