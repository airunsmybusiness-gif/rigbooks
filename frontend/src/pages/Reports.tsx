/** Reports hub: accountant summary, GST34, IFTA quarterly, T4A, audit
 * trail, and CRA-ready exports (PDF / T2125 CSV / full JSON backup). */
import { Download, FileText, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, Card, EmptyState, PageHeader, Select, Table, Td, Th,
} from "../components/ui";
import { useStore } from "../store";

export default function Reports() {
  const { period, year } = useStore();
  const [tab, setTab] = useState<"summary" | "gst" | "ifta" | "t4a" | "audit">("summary");
  return (
    <div className="fade-up space-y-4">
      <PageHeader title="Reports & exports" sub="CRA-ready outputs for filing and your accountant"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() =>
              api.download(`/api/reports/summary.pdf?start=${period.start}&end=${period.end}`,
                `RigBooks_Summary_${year}.pdf`)}>
              <FileText size={15} /> Summary PDF
            </Button>
            <Button variant="outline" onClick={() =>
              api.download(`/api/reports/t2125.csv?start=${period.start}&end=${period.end}`,
                `T2125_RigBooks_${year}.csv`)}>
              <Download size={15} /> T2125 CSV
            </Button>
            <BackupButtons />
          </div>
        } />
      <div className="flex gap-1 overflow-x-auto rounded-xl border border-line bg-surface-1 p-1">
        {([["summary", "Accountant summary"], ["gst", "GST/HST return"],
           ["ifta", "IFTA quarterly"], ["t4a", "T4A (box 048)"],
           ["audit", "Audit trail"]] as const).map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={"whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors " +
              (tab === k ? "bg-accent-soft text-accent" : "text-ink-2 hover:bg-surface-2")}>
            {label}
          </button>
        ))}
      </div>
      {tab === "summary" && <SummaryTab />}
      {tab === "gst" && <GstTab />}
      {tab === "ifta" && <IftaTab />}
      {tab === "t4a" && <T4aTab />}
      {tab === "audit" && <AuditTab />}
    </div>
  );
}

function BackupButtons() {
  const fileRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <Button variant="outline" onClick={() =>
        api.download("/api/reports/backup", `rigbooks_backup_${new Date().toISOString().slice(0, 10)}.json`)}>
        <Download size={15} /> Backup
      </Button>
      <Button variant="outline" onClick={() => fileRef.current?.click()}>
        <Upload size={15} /> Restore
      </Button>
      <input ref={fileRef} type="file" accept=".json" hidden
        onChange={async (e) => {
          const f = e.target.files?.[0];
          if (f && confirm("Restore appends the backup's records to the current books. Continue?")) {
            await api.upload("/api/reports/backup/restore", f);
            window.location.reload();
          }
        }} />
    </>
  );
}

function SummaryTab() {
  const { period } = useStore();
  const [s, setS] = useState<any>(null);
  useEffect(() => {
    api.get(`/api/reports/summary?start=${period.start}&end=${period.end}`).then(setS);
  }, [period]);
  if (!s) return null;
  const rows: [string, number, number?][] = [
    ["Bank statement expenses", s.expenses.bank],
    ["Cash expenses", s.expenses.cash],
    ["Personal account", s.expenses.personal],
    ["Vehicle costs", s.expenses.vehicle],
    ["Fuel", s.expenses.fuel],
    ["Phone (business share)", s.expenses.phone],
    ["Home office", s.expenses.home_office],
    ["Meals & per diem", s.expenses.meals],
    ["Other", s.expenses.other],
  ];
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Where the money went">
        <Table head={<><Th>Source</Th><Th right>Deductible</Th></>}>
          {rows.filter(([, v]) => v > 0).map(([label, v]) => (
            <tr key={label}><Td>{label}</Td><Td right>{money(v)}</Td></tr>
          ))}
          <tr className="bg-surface-2 font-semibold">
            <Td>Total expenses</Td><Td right>{money(s.expenses.total)}</Td>
          </tr>
        </Table>
      </Card>
      <Card title="ITCs by source">
        <Table head={<><Th>Source</Th><Th right>ITC</Th></>}>
          {Object.entries(s.itcs.by_source).map(([k, v]) => (
            <tr key={k}><Td>{k}</Td><Td right>{money(v as number)}</Td></tr>
          ))}
          <tr className="bg-surface-2 font-semibold">
            <Td>Total ITCs</Td><Td right>{money(s.itcs.total)}</Td>
          </tr>
        </Table>
        <p className="mt-3 text-xs text-ink-3">
          Revenue {money(s.revenue.total)} (manual {money(s.revenue.manual)} + bank{" "}
          {money(s.revenue.bank)}) · Net income {money(s.kpis.net_income)} ·
          Business use {s.mileage.business_pct}% over {s.mileage.total_km.toLocaleString()} km
        </p>
      </Card>
    </div>
  );
}

function GstTab() {
  const { period } = useStore();
  const [g, setG] = useState<any>(null);
  useEffect(() => {
    api.get(`/api/reports/gst34?start=${period.start}&end=${period.end}`).then(setG);
  }, [period]);
  if (!g) return null;
  const r = g.gst34;
  return (
    <Card title="Form GST34 working copy">
      {g.rules_provisional && (
        <p className="mb-3"><Badge tone="warn">Provisional rates — verify before filing</Badge></p>
      )}
      <Table head={<><Th>Line</Th><Th>Description</Th><Th right>Amount</Th></>}>
        <tr><Td>101</Td><Td>Sales and other revenue</Td><Td right>{money(r.line_101_sales)}</Td></tr>
        <tr><Td>105</Td><Td>GST/HST collected</Td><Td right>{money(r.line_105_gst_collected)}</Td></tr>
        <tr><Td>108</Td><Td>Input tax credits</Td><Td right>{money(r.line_108_itcs)}</Td></tr>
        <tr className={"font-semibold " + (r.owing ? "text-bad" : "text-good")}>
          <Td>109</Td>
          <Td>{r.owing ? "NET TAX OWING" : "NET TAX REFUND"}</Td>
          <Td right>{money(Math.abs(r.line_109_net_tax))}</Td>
        </tr>
      </Table>
      <p className="mt-3 text-xs text-ink-3">
        Registration is mandatory once worldwide taxable supplies exceed $30,000
        in four consecutive quarters. File through CRA My Business Account.
      </p>
    </Card>
  );
}

function IftaTab() {
  const { year } = useStore();
  const [quarter, setQuarter] = useState(Math.floor(new Date().getMonth() / 3) + 1);
  const [r, setR] = useState<any>(null);
  useEffect(() => {
    api.get(`/api/reports/ifta?year=${year}&quarter=${quarter}`).then(setR);
  }, [year, quarter]);
  if (!r) return null;
  return (
    <Card title={`IFTA — ${year} Q${quarter}`}
      action={
        <Select value={quarter} onChange={(e) => setQuarter(Number(e.target.value))}
          className="!w-auto !py-1">
          {[1, 2, 3, 4].map((q) => <option key={q} value={q}>Q{q}</option>)}
        </Select>
      }>
      <p className="mb-3 text-sm text-ink-3">
        Fleet: {r.total_km.toLocaleString()} km · {r.total_litres.toLocaleString()} L ·{" "}
        {r.fleet_kpl} km/L. {r.rates_note}
      </p>
      {r.lines.length === 0 ? (
        <EmptyState>Log trips (with jurisdictions) and fuel purchases to build the IFTA report.</EmptyState>
      ) : (
        <Table head={<>
          <Th>Jurisdiction</Th><Th right>Distance km</Th><Th right>Fuel purchased L</Th>
          <Th right>Taxable L</Th><Th right>Net taxable L</Th><Th right>Rate $/L</Th><Th right>Net tax</Th>
        </>}>
          {r.lines.map((l: any) => (
            <tr key={l.jurisdiction}>
              <Td><Badge tone="accent">{l.jurisdiction}</Badge></Td>
              <Td right>{l.distance_km.toLocaleString()}</Td>
              <Td right>{l.fuel_purchased_l.toLocaleString()}</Td>
              <Td right>{l.taxable_litres.toLocaleString()}</Td>
              <Td right>{l.net_taxable_litres.toLocaleString()}</Td>
              <Td right>{l.tax_rate.toFixed(4)}</Td>
              <Td right className={l.net_tax > 0 ? "text-bad" : "text-good"}>{money(l.net_tax)}</Td>
            </tr>
          ))}
          <tr className="bg-surface-2 font-semibold">
            <Td>Net tax due</Td><Td right> </Td><Td right> </Td><Td right> </Td>
            <Td right> </Td><Td right> </Td>
            <Td right className={r.net_tax_due > 0 ? "text-bad" : "text-good"}>
              {money(r.net_tax_due)}
            </Td>
          </tr>
        </Table>
      )}
    </Card>
  );
}

function T4aTab() {
  const { year } = useStore();
  const [r, setR] = useState<any>(null);
  useEffect(() => { api.get(`/api/reports/t4a?year=${year}`).then(setR); }, [year]);
  if (!r) return null;
  return (
    <Card title={`T4A candidates — ${year}`}>
      <p className="mb-3 text-sm text-ink-3">{r.notes}</p>
      {r.candidates.length === 0 ? (
        <EmptyState>
          No vendors above the ${r.threshold} threshold. Record professional /
          contractor fees with a vendor name to track them here.
        </EmptyState>
      ) : (
        <Table head={<><Th>Vendor</Th><Th right>Total fees paid</Th><Th right>Slip box</Th></>}>
          {r.candidates.map((c: any) => (
            <tr key={c.vendor}>
              <Td>{c.vendor}</Td>
              <Td right>{money(c.total_fees)}</Td>
              <Td right><Badge>{c.box}</Badge></Td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  );
}

function AuditTab() {
  const [r, setR] = useState<any>(null);
  useEffect(() => { api.get("/api/reports/audit-log").then(setR); }, []);
  if (!r) return null;
  return (
    <Card title={`Audit trail — ${r.total.toLocaleString()} events (append-only, kept forever)`}>
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
    </Card>
  );
}
