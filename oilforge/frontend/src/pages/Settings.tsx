/** Corporate profile and numbering preferences. */
import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Card, Field, Input, PageHeader, Select } from "../components/ui";

const PROVINCES = ["AB", "BC", "SK", "MB", "ON", "QC", "NB", "NS", "PE", "NL",
  "YT", "NT", "NU"];

export default function Settings() {
  const [settings, setSettings] = useState<any>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.get("/api/settings").then(setSettings); }, []);

  const save = async () => {
    await Promise.all(Object.entries(settings).map(([k, v]) =>
      api.put(`/api/settings/${k}`, { value: v })));
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  if (!settings) return null;
  const b = settings.business;
  const inv = settings.invoice;
  const job = settings.job;

  return (
    <div className="fade-up space-y-5">
      <PageHeader title="Settings" sub="Corporate profile and document numbering"
        action={<Button onClick={save}>{saved ? "Saved ✓" : "Save all"}</Button>} />

      <Card title="Corporation">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Field label="Legal name" className="col-span-2">
            <Input value={b.name}
              onChange={(e) => setSettings({ ...settings, business: { ...b, name: e.target.value } })} />
          </Field>
          <Field label="Province">
            <Select value={b.province}
              onChange={(e) => setSettings({ ...settings, business: { ...b, province: e.target.value } })}>
              {PROVINCES.map((p) => <option key={p}>{p}</option>)}
            </Select>
          </Field>
          <Field label="Fiscal year end (MM-DD)">
            <Input value={b.fiscal_year_end} placeholder="12-31"
              onChange={(e) => setSettings({ ...settings, business: { ...b, fiscal_year_end: e.target.value } })} />
          </Field>
          <Field label="GST number">
            <Input value={b.gst_number} placeholder="123456789 RT0001"
              onChange={(e) => setSettings({ ...settings, business: { ...b, gst_number: e.target.value } })} />
          </Field>
          <Field label="Business number (BN)">
            <Input value={b.bn} placeholder="123456789"
              onChange={(e) => setSettings({ ...settings, business: { ...b, bn: e.target.value } })} />
          </Field>
        </div>
      </Card>

      <Card title="Document numbering">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Field label="Invoice prefix">
            <Input value={inv.prefix}
              onChange={(e) => setSettings({ ...settings, invoice: { ...inv, prefix: e.target.value } })} />
          </Field>
          <Field label="Next invoice #">
            <Input type="number" value={inv.next_number}
              onChange={(e) => setSettings({ ...settings, invoice: { ...inv, next_number: Number(e.target.value) } })} />
          </Field>
          <Field label="Job prefix">
            <Input value={job.prefix}
              onChange={(e) => setSettings({ ...settings, job: { ...job, prefix: e.target.value } })} />
          </Field>
          <Field label="Next job #">
            <Input type="number" value={job.next_number}
              onChange={(e) => setSettings({ ...settings, job: { ...job, next_number: Number(e.target.value) } })} />
          </Field>
          <Field label="Invoice terms" className="col-span-2">
            <Input value={inv.terms}
              onChange={(e) => setSettings({ ...settings, invoice: { ...inv, terms: e.target.value } })} />
          </Field>
        </div>
      </Card>
    </div>
  );
}
