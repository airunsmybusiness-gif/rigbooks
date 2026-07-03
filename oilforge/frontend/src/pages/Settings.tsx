/** Corporate profile, numbering preferences, and the migration wizard. */
import { CheckCircle2, Download, Loader2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Badge, Button, Card, Field, Input, PageHeader, Select } from "../components/ui";

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

      <MigrationWizard />

      <Card title="Data security">
        <p className="text-sm text-ink-2">
          Backups encrypt with a password (Reports → Backup). For at-rest
          database encryption, put <code className="text-xs">~/.oilforge</code>{" "}
          on an encrypted volume (BitLocker / FileVault / LUKS) or swap SQLite
          for SQLCipher — see the README's <em>Data security</em> section for
          the exact steps. Everything stays offline either way.
        </p>
      </Card>
    </div>
  );
}

const WIZARD_STEPS: { kind: string; label: string; hint: string }[] = [
  { kind: "clients", label: "1 · Clients", hint: "who you bill" },
  { kind: "equipment", label: "2 · Equipment", hint: "assets + CCA class + acquired date" },
  { kind: "jobs", label: "3 · Jobs", hint: "old work orders (clients auto-created)" },
  { kind: "bank_transactions", label: "4 · Bank history", hint: "prior-year statements, auto-classified" },
  { kind: "expenses", label: "5 · Expenses", hint: "cash/receipt expenses, ITCs recomputed" },
  { kind: "shareholder_history", label: "6 · Shareholder loan", hint: "draws & contributions (opening balance = first rows)" },
  { kind: "dividends", label: "7 · Dividends", hint: "past declarations for T5 history" },
];

function MigrationWizard() {
  const [results, setResults] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [pendingKind, setPendingKind] = useState("");

  const upload = async (kind: string, file: File) => {
    setBusy(kind);
    try {
      const r = await api.upload(`/api/import/${kind}`, file);
      setResults((x) => ({ ...x, [kind]: r }));
    } catch (e: any) {
      setResults((x) => ({ ...x, [kind]: { error: e.message } }));
    } finally { setBusy(""); }
  };

  return (
    <Card title="Migration wizard — bring in historical data">
      <p className="mb-4 text-sm text-ink-3">
        Moving from the old Streamlit books or spreadsheets? Work top to
        bottom: download each template, fill it from your old records
        (first data row shows the expected format), upload. Imports are
        additive and bank rows are duplicate-safe, so re-running is fine.
      </p>
      <div className="space-y-2">
        {WIZARD_STEPS.map(({ kind, label, hint }) => {
          const r = results[kind];
          return (
            <div key={kind}
              className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2">
              <span className="min-w-40 text-sm font-medium text-ink-1">{label}</span>
              <span className="flex-1 text-xs text-ink-3">{hint}</span>
              <Button variant="ghost" className="!py-1" onClick={() =>
                api.download(`/api/import/template/${kind}`, `oilforge_${kind}_template.csv`)}>
                <Download size={13} /> Template
              </Button>
              <Button variant="outline" className="!py-1" disabled={busy !== ""}
                onClick={() => { setPendingKind(kind); fileRef.current?.click(); }}>
                {busy === kind
                  ? <><Loader2 size={13} className="animate-spin" /> Importing…</>
                  : <><Upload size={13} /> Upload</>}
              </Button>
              {r && !r.error && (
                <Badge tone="good">
                  <CheckCircle2 size={11} />&nbsp;{r.created} imported
                  {r.errors?.length ? ` · ${r.errors.length} errors` : ""}
                </Badge>
              )}
              {r?.error && <Badge tone="bad">{r.error}</Badge>}
            </div>
          );
        })}
      </div>
      <input ref={fileRef} type="file" accept=".csv" hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f && pendingKind) upload(pendingKind, f);
          e.target.value = "";
        }} />
      {Object.values(results).some((r: any) => r?.errors?.length > 0) && (
        <div className="mt-3 rounded-xl bg-bad/10 p-3 text-xs text-bad">
          {Object.entries(results).flatMap(([k, r]: [string, any]) =>
            (r.errors ?? []).map((e: any, i: number) => (
              <p key={`${k}-${i}`}>{k} row {e.row}: {e.error}</p>
            )))}
        </div>
      )}
    </Card>
  );
}
