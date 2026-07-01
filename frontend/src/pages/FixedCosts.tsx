/** Home office (workspace-in-home, per year) and phone bills. */
import { Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, money } from "../api";
import {
  Button, Card, EmptyState, Field, Input, PageHeader, Table, Td, Th,
} from "../components/ui";
import { useStore } from "../store";

const HO_FIELDS: [string, string][] = [
  ["rent", "Rent or mortgage interest"],
  ["property_tax", "Property tax"],
  ["insurance", "Home insurance"],
  ["electricity", "Electricity"],
  ["gas", "Gas / heating"],
  ["water", "Water"],
  ["internet", "Internet"],
];

function HomeOfficeCard() {
  const { year } = useStore();
  const [ho, setHo] = useState<any>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get(`/api/home-office/${year}`).then(setHo);
  }, [year]);

  const save = async () => {
    const updated = await api.put(`/api/home-office/${year}`, ho);
    setHo(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  if (!ho) return null;
  return (
    <Card title={`Home office — ${year} annual costs`}>
      <p className="mb-4 text-sm text-ink-3">
        CRA: claim the business-use share (office area ÷ home area) of housing
        costs. No ITC on property tax or insurance (GST-exempt).
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {HO_FIELDS.map(([key, label]) => (
          <Field key={key} label={label}>
            <Input type="number" step="50" value={ho[key] ?? 0}
              onChange={(e) => setHo({ ...ho, [key]: Number(e.target.value) })} />
          </Field>
        ))}
        <Field label="Office % of home">
          <Input type="number" min={0} max={50} value={ho.pct}
            onChange={(e) => setHo({ ...ho, pct: Number(e.target.value) })} />
        </Field>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-2">
          Total <strong className="text-ink-1">{money(ho.total)}</strong> ·
          deductible ({ho.pct}%) <strong className="text-ink-1">{money(ho.deductible)}</strong> ·
          ITC <strong className="text-ink-1">{money(ho.itc)}</strong>
        </p>
        <Button onClick={save}>{saved ? "Saved ✓" : "Save"}</Button>
      </div>
    </Card>
  );
}

function PhoneBillsCard() {
  const { period } = useStore();
  const [bills, setBills] = useState<any[]>([]);
  const [form, setForm] = useState({
    owner: "", period_start: period.start, period_end: period.end,
    amount: "", business_pct: 60, notes: "",
  });

  const load = useCallback(() => {
    api.get(`/api/phone-bills?start=${period.start}&end=${period.end}`)
      .then((r) => setBills(r.items));
  }, [period]);
  useEffect(() => { load(); }, [load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/api/phone-bills", { ...form, amount: Number(form.amount) });
    setForm({ ...form, amount: "", notes: "" });
    load();
  };

  return (
    <Card title="Phone bills">
      <p className="mb-4 text-sm text-ink-3">
        CRA: claim only the substantiated business-use portion (50–80% is
        typical). Keep bills and a usage log.
      </p>
      <form onSubmit={add} className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Field label="Whose phone"><Input value={form.owner} required placeholder="e.g. Greg"
          onChange={(e) => setForm({ ...form, owner: e.target.value })} /></Field>
        <Field label="From"><Input type="date" value={form.period_start}
          onChange={(e) => setForm({ ...form, period_start: e.target.value })} /></Field>
        <Field label="To"><Input type="date" value={form.period_end}
          onChange={(e) => setForm({ ...form, period_end: e.target.value })} /></Field>
        <Field label="Amount ($)"><Input type="number" step="0.01" required value={form.amount}
          onChange={(e) => setForm({ ...form, amount: e.target.value })} /></Field>
        <Field label="Business %"><Input type="number" min={0} max={100} value={form.business_pct}
          onChange={(e) => setForm({ ...form, business_pct: Number(e.target.value) })} /></Field>
        <div className="flex items-end">
          <Button type="submit" className="w-full"><Plus size={15} /> Add</Button>
        </div>
      </form>
      {bills.length === 0 ? (
        <EmptyState>No phone bills in this period.</EmptyState>
      ) : (
        <Table head={<>
          <Th>Owner</Th><Th>Period</Th><Th right>Amount</Th><Th right>Biz %</Th>
          <Th right>Deductible</Th><Th right> </Th>
        </>}>
          {bills.map((b) => (
            <tr key={b.id} className="hover:bg-surface-2">
              <Td>{b.owner}</Td>
              <Td>{b.period_start} → {b.period_end}</Td>
              <Td right>{money(b.amount)}</Td>
              <Td right>{b.business_pct}%</Td>
              <Td right>{money(b.amount * b.business_pct / 100)}</Td>
              <Td right>
                <button className="rounded-lg p-1.5 text-ink-3 hover:text-bad" title="Delete"
                  onClick={async () => {
                    if (confirm("Delete this bill?")) {
                      await api.del(`/api/phone-bills/${b.id}`); load();
                    }
                  }}><Trash2 size={14} /></button>
              </Td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  );
}

export default function FixedCosts() {
  return (
    <div className="fade-up space-y-5">
      <PageHeader title="Home office & phone"
        sub="Recurring mixed-use costs claimed at their business percentage" />
      <HomeOfficeCard />
      <PhoneBillsCard />
    </div>
  );
}
