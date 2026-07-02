/** Corporate expenses — quick entry with job/equipment tagging for costing. */
import { useEffect, useState } from "react";
import { api, money } from "../api";
import CrudPage, { type FieldDef } from "../components/CrudPage";

const CATEGORIES = [
  "Subcontractors", "Fuel & Petroleum", "Equipment Rental",
  "Equipment Repairs & Parts", "Shop Supplies", "Small Tools (<$500)",
  "Safety Gear & PPE", "Camp & Accommodation", "Meals (50%)", "Travel",
  "Insurance - Commercial", "Insurance - Equipment", "WCB Premiums",
  "Professional Fees", "Office & Admin", "Phone & Communications",
  "Software & Subscriptions", "Bank Fees", "Interest & Loan Charges",
  "Utilities - Shop", "Rent - Shop/Yard", "Licenses & Permits",
  "Training & Certifications", "Marketing", "Capital Asset Purchase",
  "Other Operating",
];

export default function Expenses() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [equipment, setEquipment] = useState<any[]>([]);
  useEffect(() => {
    api.get("/api/jobs").then((r) => setJobs(r.items));
    api.get("/api/equipment").then((r) => setEquipment(r.items ?? r));
  }, []);

  const fields: FieldDef[] = [
    { name: "date", label: "Date", type: "date", required: true },
    { name: "amount", label: "Amount ($, GST incl.)", type: "number", step: "0.01", required: true },
    { name: "vendor", label: "Vendor", placeholder: "e.g. NAPA Edmonton" },
    { name: "category", label: "Category", type: "select", options: CATEGORIES },
    { name: "description", label: "Description", span2: true },
    {
      name: "job_id", label: "Job (costing)", type: "select",
      options: [{ value: "", label: "— none —" },
        ...jobs.map((j) => ({ value: String(j.id), label: `${j.number} ${j.title}` }))],
    },
    {
      name: "equipment_id", label: "Equipment", type: "select",
      options: [{ value: "", label: "— none —" },
        ...equipment.map((e) => ({ value: String(e.id), label: e.name }))],
    },
    { name: "receipt_ref", label: "Receipt #", placeholder: "e.g. R-0042" },
  ];

  return (
    <CrudPage title="Expenses"
      sub="ITCs computed from the year's rules — tag a job for per-contract costing"
      path="/api/expenses" fields={fields}
      transform={(f) => ({
        ...f,
        job_id: f.job_id ? Number(f.job_id) : null,
        equipment_id: f.equipment_id ? Number(f.equipment_id) : null,
      })}
      columns={[
        { key: "date", label: "Date" },
        { key: "vendor", label: "Vendor" },
        { key: "category", label: "Category" },
        { key: "description", label: "Description" },
        { key: "amount", label: "Amount", right: true, render: (r) => money(r.amount) },
        { key: "itc", label: "ITC", right: true, render: (r) => money(r.itc) },
        { key: "receipt_ref", label: "Receipt" },
      ]}
      footer={(items) => (
        <div className="flex gap-6 rounded-xl border border-line bg-surface-1 px-4 py-3 text-sm text-ink-2">
          <span>Total: <strong className="text-ink-1">
            {money(items.reduce((s, x) => s + x.amount, 0))}</strong></span>
          <span>ITCs: <strong className="text-ink-1">
            {money(items.reduce((s, x) => s + x.itc, 0))}</strong></span>
        </div>
      )} />
  );
}
