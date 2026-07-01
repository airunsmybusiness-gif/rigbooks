/** Business profile, shareholders, invoice numbering. */
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
    await Promise.all([
      api.put("/api/settings/business", { value: settings.business }),
      api.put("/api/settings/shareholders", { value: settings.shareholders }),
      api.put("/api/settings/invoice", { value: settings.invoice }),
    ]);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  if (!settings) return null;
  const b = settings.business;
  const inv = settings.invoice;

  return (
    <div className="fade-up space-y-5">
      <PageHeader title="Settings" sub="Business profile, ownership and invoice preferences"
        action={<Button onClick={save}>{saved ? "Saved ✓" : "Save all"}</Button>} />

      <Card title="Business">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Field label="Business name" className="col-span-2">
            <Input value={b.name}
              onChange={(e) => setSettings({ ...settings, business: { ...b, name: e.target.value } })} />
          </Field>
          <Field label="Province (GST/HST)">
            <Select value={b.province}
              onChange={(e) => setSettings({ ...settings, business: { ...b, province: e.target.value } })}>
              {PROVINCES.map((p) => <option key={p}>{p}</option>)}
            </Select>
          </Field>
          <Field label="GST number">
            <Input value={b.gst_number} placeholder="123456789 RT0001"
              onChange={(e) => setSettings({ ...settings, business: { ...b, gst_number: e.target.value } })} />
          </Field>
        </div>
      </Card>

      <Card title="Shareholders">
        <div className="space-y-2">
          {settings.shareholders.map((sh: any, i: number) => (
            <div key={i} className="grid grid-cols-[1fr_120px] gap-3">
              <Field label={`Shareholder ${i + 1}`}>
                <Input value={sh.name} onChange={(e) => {
                  const next = [...settings.shareholders];
                  next[i] = { ...sh, name: e.target.value };
                  setSettings({ ...settings, shareholders: next });
                }} />
              </Field>
              <Field label="Ownership %">
                <Input type="number" min={0} max={100} value={sh.pct} onChange={(e) => {
                  const next = [...settings.shareholders];
                  next[i] = { ...sh, pct: Number(e.target.value) };
                  setSettings({ ...settings, shareholders: next });
                }} />
              </Field>
            </div>
          ))}
          <p className="text-xs text-ink-3">
            Total: {settings.shareholders.reduce((s: number, x: any) => s + x.pct, 0)}%
            — ITA 15(2): shareholder loans must be repaid within one year of the
            corporation's year-end or they become taxable income.
          </p>
        </div>
      </Card>

      <Card title="Invoicing">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Field label="Number prefix">
            <Input value={inv.prefix}
              onChange={(e) => setSettings({ ...settings, invoice: { ...inv, prefix: e.target.value } })} />
          </Field>
          <Field label="Next number">
            <Input type="number" value={inv.next_number}
              onChange={(e) => setSettings({ ...settings, invoice: { ...inv, next_number: Number(e.target.value) } })} />
          </Field>
          <Field label="Terms" className="col-span-2">
            <Input value={inv.terms}
              onChange={(e) => setSettings({ ...settings, invoice: { ...inv, terms: e.target.value } })} />
          </Field>
        </div>
      </Card>
    </div>
  );
}
