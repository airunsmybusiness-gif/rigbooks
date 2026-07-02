/** Reports hub: financial statements, trial balance, GST34, audit trail,
 * exports and (optionally encrypted) backup/restore. */
import { Download, FileText, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, Card, EmptyState, PageHeader, Table, Td, Th,
} from "../components/ui";
import { useStore } from "../store";

export default function Reports() {
  const { period, year } = useStore();
  const [tab, setTab] = useState<"income" | "tb" | "gst" | "audit">("income");
  return (
    <div className="fade-up space-y-4">
      <PageHeader title="Reports & exports" sub="Accountant-ready outputs, audit trail, and backups"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() =>
              api.download(`/api/reports/statements.pdf?start=${period.start}&end=${period.end}`,
                `OilForge_Financials_${year}.pdf`)}>
              <FileText size={15} /> Financials PDF
            </Button>
            <Button variant="outline" onClick={() =>
              api.download(`/api/shareholder/journal.csv?start=${period.start}&end=${period.end}`,
                `OilForge_Journal_${year}.csv`)}>
              <Download size={15} /> Journal CSV
            </Button>
            <BackupButtons />
          </div>
        } />
      <div className="flex gap-1 overflow-x-auto rounded-xl border border-line bg-surface-1 p-1">
        {([["income", "Income statement"], ["tb", "Trial balance"],
           ["gst", "GST/HST return"], ["audit", "Audit trail"]] as const)
          .map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)}
              className={"whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors " +
                (tab === k ? "bg-accent-soft text-accent" : "text-ink-2 hover:bg-surface-2")}>
              {label}
            </button>
          ))}
      </div>
      {tab === "income" && <IncomeTab />}
      {tab === "tb" && <TrialBalanceTab />}
      {tab === "gst" && <GstTab />}
      {tab === "audit" && <AuditTab />}
    </div>
  );
}

function BackupButtons() {
  const fileRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <Button variant="outline" onClick={() => {
        const pw = prompt("Backup password (leave blank for unencrypted JSON):") ?? "";
        const suffix = pw ? `?password=${encodeURIComponent(pw)}` : "";
        api.download(`/api/reports/backup${suffix}`,
          `oilforge_backup_${new Date().toISOString().slice(0, 10)}.${pw ? "ofb" : "json"}`);
      }}>
        <Download size={15} /> Backup
      </Button>
      <Button variant="outline" onClick={() => fileRef.current?.click()}>
        <Upload size={15} /> Restore
      </Button>
      <input ref={fileRef} type="file" accept=".json,.ofb" hidden
        onChange={async (e) => {
          const f = e.target.files?.[0];
          if (!f) return;
          const pw = f.name.endsWith(".ofb")
            ? prompt("Backup password:") ?? "" : "";
          if (confirm("Restore appends the backup's records to the current books. Continue?")) {
            const suffix = pw ? `?password=${encodeURIComponent(pw)}` : "";
            await api.upload(`/api/reports/backup/restore${suffix}`, f);
            window.location.reload();
          }
        }} />
    </>
  );
}

function IncomeTab() {
  const { period } = useStore();
  const [s, setS] = useState<any>(null);
  useEffect(() => {
    api.get(`/api/reports/statements?start=${period.start}&end=${period.end}`)
      .then((r) => setS(r.summary));
  }, [period]);
  if (!s) return null;
  const inc = s.income;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Income statement (fiscal period)">
        <Table head={<><Th>Line</Th><Th right>Amount</Th></>}>
          <tr><Td>Revenue (invoiced)</Td><Td right>{money(s.revenue.invoiced)}</Td></tr>
          <tr><Td>Operating expenses</Td><Td right>({money(s.expenses.total)})</Td></tr>
          <tr className="font-medium"><Td>EBITDA</Td><Td right>{money(inc.ebitda)}</Td></tr>
          <tr><Td>CCA (max available)</Td><Td right>({money(inc.cca)})</Td></tr>
          <tr className="font-medium"><Td>Income before tax</Td><Td right>{money(inc.before_tax)}</Td></tr>
          <tr><Td>Corporate tax estimate
            ({(inc.small_business_rate * 100).toFixed(1)}%)</Td>
            <Td right>({money(inc.tax_estimate)})</Td></tr>
          <tr className="bg-surface-2 font-semibold">
            <Td>Estimated after-tax income</Td><Td right>{money(inc.after_tax_estimate)}</Td></tr>
        </Table>
      </Card>
      <Card title="Expenses by category">
        <Table head={<><Th>Category</Th><Th right>Amount</Th></>}>
          {Object.entries(s.expenses.by_category).map(([cat, amt]) => (
            <tr key={cat}><Td>{cat}</Td><Td right>{money(amt as number)}</Td></tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}

function TrialBalanceTab() {
  const { period } = useStore();
  const [tb, setTb] = useState<any>(null);
  useEffect(() => {
    api.get(`/api/reports/statements?start=${period.start}&end=${period.end}`)
      .then((r) => setTb(r.trial_balance));
  }, [period]);
  if (!tb) return null;
  return (
    <Card title="Derived trial balance">
      <Table head={<><Th>Account</Th><Th right>Debit</Th><Th right>Credit</Th></>}>
        {tb.rows.map((r: any) => (
          <tr key={r.account}>
            <Td>{r.account}</Td>
            <Td right>{r.debit ? money(r.debit) : ""}</Td>
            <Td right>{r.credit ? money(r.credit) : ""}</Td>
          </tr>
        ))}
        <tr className="bg-surface-2 font-semibold">
          <Td>Totals</Td>
          <Td right>{money(tb.total_debits)}</Td>
          <Td right>{money(tb.total_credits)}</Td>
        </tr>
      </Table>
      <p className="mt-2 text-xs text-ink-3">{tb.note}</p>
    </Card>
  );
}

function GstTab() {
  const { period } = useStore();
  const [s, setS] = useState<any>(null);
  useEffect(() => {
    api.get(`/api/reports/statements?start=${period.start}&end=${period.end}`)
      .then((r) => setS(r.summary));
  }, [period]);
  if (!s) return null;
  const g = s.gst34;
  return (
    <Card title="Form GST34 working copy">
      {s.rules_provisional && (
        <p className="mb-3"><Badge tone="warn">Provisional rates — verify before filing</Badge></p>
      )}
      <Table head={<><Th>Line</Th><Th>Description</Th><Th right>Amount</Th></>}>
        <tr><Td>101</Td><Td>Sales and other revenue</Td><Td right>{money(g.line_101_sales)}</Td></tr>
        <tr><Td>105</Td><Td>GST/HST collected</Td><Td right>{money(g.line_105_gst_collected)}</Td></tr>
        <tr><Td>108</Td><Td>Input tax credits</Td><Td right>{money(g.line_108_itcs)}</Td></tr>
        <tr className={"font-semibold " + (g.owing ? "text-bad" : "text-good")}>
          <Td>109</Td><Td>{g.owing ? "NET TAX OWING" : "NET TAX REFUND"}</Td>
          <Td right>{money(Math.abs(g.line_109_net_tax))}</Td>
        </tr>
      </Table>
    </Card>
  );
}

function AuditTab() {
  const [r, setR] = useState<any>(null);
  useEffect(() => { api.get("/api/reports/audit-log").then(setR); }, []);
  if (!r) return null;
  return (
    <Card title={`Audit trail — ${r.total.toLocaleString()} events (append-only)`}>
      {r.items.length === 0 ? <EmptyState>No events yet.</EmptyState> : (
        <Table head={<><Th>When (UTC)</Th><Th>User</Th><Th>Action</Th><Th>Entity</Th><Th>Ref</Th></>}>
          {r.items.map((a: any) => (
            <tr key={a.id}>
              <Td className="whitespace-nowrap text-xs">{a.ts.replace("T", " ").slice(0, 19)}</Td>
              <Td className="text-xs">{a.user}</Td>
              <Td><Badge tone={a.action === "delete" ? "bad" : "neutral"}>{a.action}</Badge></Td>
              <Td>{a.entity}</Td>
              <Td>{a.entity_id}</Td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  );
}
