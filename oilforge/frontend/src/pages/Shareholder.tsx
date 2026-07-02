/** Dividends & shareholder loans — the compensation workflow for an
 * owner who takes no payroll: draws accumulate on the loan, the year-end
 * dividend clears it, T5 figures and journal entries go to the accountant. */
import { Download, FileText, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select,
  StatCard, Table, Td, Th,
} from "../components/ui";
import { useStore } from "../store";

export default function ShareholderPage() {
  const { year, period } = useStore();
  const [overview, setOverview] = useState<any>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [ledger, setLedger] = useState<any>(null);
  const [addingTxn, setAddingTxn] = useState(false);
  const [declaring, setDeclaring] = useState(false);
  const [addingHolder, setAddingHolder] = useState(false);

  const load = useCallback(() => {
    api.get(`/api/shareholder/overview?year=${year}`).then((o) => {
      setOverview(o);
      if (o.shareholders.length && selected === null) {
        setSelected(o.shareholders[0].shareholder.id);
      }
    });
  }, [year, selected]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (selected != null) {
      api.get(`/api/shareholder/${selected}/ledger`).then(setLedger);
    }
  }, [selected, overview]);

  if (!overview) return null;
  const holders = overview.shareholders;
  const current = holders.find((h: any) => h.shareholder.id === selected);

  return (
    <div className="fade-up space-y-5">
      <PageHeader title="Dividends & shareholder loans"
        sub="No payroll: draws build the loan through the year; dividends clear it at year-end"
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setAddingHolder(true)}>
              <Plus size={15} /> Shareholder
            </Button>
            <Button variant="outline" onClick={() => setAddingTxn(true)}
              disabled={!holders.length}>
              <Plus size={15} /> Loan entry
            </Button>
            <Button onClick={() => setDeclaring(true)} disabled={!holders.length}>
              <FileText size={15} /> Declare dividend
            </Button>
          </div>
        } />

      {holders.length === 0 ? (
        <EmptyState>Add the shareholder(s) of the corporation to start
          tracking draws and dividends.</EmptyState>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {holders.map((h: any) => (
              <button key={h.shareholder.id}
                onClick={() => setSelected(h.shareholder.id)}
                className={"rounded-xl border px-4 py-2 text-sm font-medium transition-colors " +
                  (selected === h.shareholder.id
                    ? "border-accent bg-accent-soft text-accent"
                    : "border-line bg-surface-1 text-ink-2 hover:bg-surface-2")}>
                {h.shareholder.name} · {h.shareholder.ownership_pct}%
              </button>
            ))}
          </div>

          {current && (
            <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
              <StatCard label="Loan balance"
                value={money(Math.abs(current.loan_balance))}
                tone={current.loan_balance > 0 ? "bad" : "good"}
                sub={current.loan_balance > 0 ? "shareholder owes corp"
                  : current.loan_balance < 0 ? "corp owes shareholder" : "cleared"} />
              <StatCard label={`Dividends ${year}`}
                value={money(current.dividends_ytd)}
                sub={`non-eligible ${money(current.dividends_by_kind.non_eligible)}`} />
              <StatCard label="ITA 15(2)"
                value={current.assessment.owing_to_corp ? "Exposure" : "Clear"}
                tone={current.assessment.owing_to_corp ? "bad" : "good"}
                sub={current.assessment.owing_to_corp
                  ? "repay or declare within 1 yr of FYE" : "no repayment required"} />
              <StatCard label="80.4 imputed interest"
                value={money(current.assessment.annual_imputed_interest_80_4)}
                sub={`prescribed rate ${(current.assessment.prescribed_rate * 100).toFixed(0)}%`} />
            </div>
          )}

          {current?.assessment.owing_to_corp && (
            <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-700 dark:text-amber-400">
              ⚠ {current.assessment.repayment_deadline_note}
            </p>
          )}

          <Card title="Loan ledger — running balance"
            action={
              <div className="flex gap-2">
                <Button variant="ghost" onClick={() =>
                  api.download(`/api/shareholder/journal.csv?start=${period.start}&end=${period.end}`,
                    `OilForge_Journal_${year}.csv`)}>
                  <Download size={14} /> Journal CSV
                </Button>
                <Button variant="ghost" onClick={() => selected != null &&
                  api.download(`/api/reports/dividend-register/${selected}.pdf?year=${year}`,
                    `Dividends_${year}.pdf`)}>
                  <Download size={14} /> Dividend PDF
                </Button>
              </div>
            }>
            {!ledger || ledger.rows.length === 0 ? (
              <EmptyState>No activity yet. Post bank withdrawals from Bank
                Import, or add a loan entry.</EmptyState>
            ) : (
              <Table head={<>
                <Th>Date</Th><Th>Entry</Th><Th>Memo</Th><Th right>Amount</Th>
                <Th right>Effect</Th><Th right>Balance</Th>
              </>}>
                {ledger.rows.map((r: any, i: number) => (
                  <tr key={`${r.source}-${r.id}-${i}`}>
                    <Td>{r.date}</Td>
                    <Td>
                      <Badge tone={r.signed > 0 ? "warn" : "good"}>{r.label}</Badge>
                    </Td>
                    <Td className="max-w-[28ch] truncate text-xs">{r.memo}</Td>
                    <Td right>{money(r.amount)}</Td>
                    <Td right className={r.signed > 0 ? "text-bad" : "text-good"}>
                      {r.signed > 0 ? "+" : "−"}{money(Math.abs(r.signed))}
                    </Td>
                    <Td right className="font-semibold">{money(r.balance)}</Td>
                  </tr>
                ))}
              </Table>
            )}
          </Card>

          {selected != null && <T5Card shareholderId={selected} year={year} />}
          {selected != null && <YearlyCard shareholderId={selected} />}
          {current?.assessment.owing_to_corp && selected != null && (
            <PlannerCard shareholderId={selected} />
          )}
        </>
      )}

      {addingHolder && (
        <HolderModal onClose={() => setAddingHolder(false)}
          onSaved={() => { setAddingHolder(false); load(); }} />
      )}
      {addingTxn && (
        <TxnModal holders={holders} defaultId={selected}
          onClose={() => setAddingTxn(false)}
          onSaved={() => { setAddingTxn(false); load(); }} />
      )}
      {declaring && (
        <DividendModal holders={holders} defaultId={selected}
          balance={current?.loan_balance ?? 0}
          onClose={() => setDeclaring(false)}
          onSaved={() => { setDeclaring(false); load(); }} />
      )}
    </div>
  );
}

function T5Card({ shareholderId, year }: { shareholderId: number; year: number }) {
  const [t5, setT5] = useState<any>(null);
  useEffect(() => {
    api.get(`/api/shareholder/${shareholderId}/t5?year=${year}`).then(setT5);
  }, [shareholderId, year]);
  if (!t5) return null;
  const rows = [
    ["Non-eligible (boxes 10 / 11 / 12)", t5.kinds.non_eligible],
    ["Eligible (boxes 24 / 25 / 26)", t5.kinds.eligible],
  ] as const;
  return (
    <Card title={`T5 slip figures — ${year} calendar year`}>
      <Table head={<>
        <Th>Dividend type</Th><Th right>Actual</Th>
        <Th right>Taxable (grossed up)</Th><Th right>Dividend tax credit</Th>
      </>}>
        {rows.map(([label, k]) => (
          <tr key={label}>
            <Td>{label}</Td>
            <Td right>{money(k.actual)}</Td>
            <Td right>{money(k.taxable)}</Td>
            <Td right>{money(k.dtc)}</Td>
          </tr>
        ))}
      </Table>
      <p className="mt-2 text-xs text-ink-3">
        Filing deadline: {t5.filing_deadline}. Non-eligible is the normal kind
        for income taxed at the small-business rate — confirm eligible
        designations (GRIP) with your accountant.
      </p>
    </Card>
  );
}

function YearlyCard({ shareholderId }: { shareholderId: number }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    api.get(`/api/shareholder/${shareholderId}/yearly`).then(setData);
  }, [shareholderId]);
  if (!data || !data.years?.length) return null;
  return (
    <Card title="Multi-year history — balance at each fiscal year-end">
      <Table head={<>
        <Th>Year</Th><Th right>Balance at FYE</Th><Th>15(2) deadline</Th>
        <Th>Status</Th><Th right>Dividends</Th>
      </>}>
        {data.years.map((y: any) => (
          <tr key={y.year}>
            <Td>{y.year}</Td>
            <Td right>{money(y.balance_at_fye)}</Td>
            <Td className="text-xs">{y.repayment_deadline}</Td>
            <Td>{y.ita_15_2_ok
              ? <Badge tone="good">clear</Badge>
              : <Badge tone="bad">15(2) risk</Badge>}</Td>
            <Td right>{money((y.dividends.eligible ?? 0) + (y.dividends.non_eligible ?? 0))}</Td>
          </tr>
        ))}
      </Table>
    </Card>
  );
}

function PlannerCard({ shareholderId }: { shareholderId: number }) {
  const [plan, setPlan] = useState<any>(null);
  useEffect(() => {
    api.get(`/api/shareholder/${shareholderId}/repayment-plan`).then(setPlan);
  }, [shareholderId]);
  if (!plan || plan.balance <= 0) return null;
  return (
    <Card title="Repayment planner — clearing the loan before the ITA 15(2) deadline">
      <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-ink-3">Deadline</p>
          <p className="font-semibold">{plan.repayment_deadline}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-ink-3">Monthly to clear</p>
          <p className="font-semibold">{money(plan.monthly_repayment_to_clear)}
            <span className="text-xs text-ink-3"> × {plan.months_remaining} mo</span></p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-ink-3">Dividend to clear now</p>
          <p className="font-semibold">{money(plan.dividend_to_clear_now)}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-ink-3">80.4 interest if held</p>
          <p className="font-semibold">{money(plan.estimated_80_4_interest_if_held_to_deadline)}</p>
        </div>
      </div>
      <ul className="mt-3 list-inside list-disc text-xs text-ink-3">
        {plan.options.map((o: string) => <li key={o}>{o}</li>)}
      </ul>
    </Card>
  );
}

function HolderModal({ onClose, onSaved }: any) {
  const [form, setForm] = useState({ name: "", email: "", ownership_pct: 100 });
  return (
    <Modal title="Add shareholder" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Name"><Input value={form.name} required
          onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Email"><Input value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Ownership %"><Input type="number" value={form.ownership_pct}
            onChange={(e) => setForm({ ...form, ownership_pct: Number(e.target.value) })} /></Field>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={async () => {
            await api.post("/api/shareholders", form); onSaved();
          }}>Save</Button>
        </div>
      </div>
    </Modal>
  );
}

const TXN_TYPES = [
  { value: "withdrawal", label: "Owner withdrawal (increases loan)" },
  { value: "personal_expense", label: "Personal expense paid by corp" },
  { value: "contribution", label: "Contribution to corp" },
  { value: "corp_expense_paid_personally", label: "Corp expense paid personally" },
  { value: "loan_repayment", label: "Loan repayment" },
];

function TxnModal({ holders, defaultId, onClose, onSaved }: any) {
  const [form, setForm] = useState<any>({
    shareholder_id: defaultId ?? holders[0]?.shareholder.id,
    date: new Date().toISOString().slice(0, 10),
    type: "withdrawal", amount: "", memo: "",
  });
  const [error, setError] = useState("");
  return (
    <Modal title="Shareholder loan entry" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Shareholder">
          <Select value={form.shareholder_id}
            onChange={(e) => setForm({ ...form, shareholder_id: Number(e.target.value) })}>
            {holders.map((h: any) =>
              <option key={h.shareholder.id} value={h.shareholder.id}>{h.shareholder.name}</option>)}
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date"><Input type="date" value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
          <Field label="Amount ($)"><Input type="number" step="0.01" value={form.amount} required
            onChange={(e) => setForm({ ...form, amount: e.target.value })} /></Field>
        </div>
        <Field label="Type">
          <Select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            {TXN_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </Select>
        </Field>
        <Field label="Memo"><Input value={form.memo} placeholder="e.g. e-transfer to personal chequing"
          onChange={(e) => setForm({ ...form, memo: e.target.value })} /></Field>
        {error && <p className="text-sm text-bad">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={async () => {
            try {
              await api.post("/api/shareholder-txns",
                { ...form, amount: Number(form.amount) });
              onSaved();
            } catch (e: any) { setError(e.message); }
          }}>Add entry</Button>
        </div>
      </div>
    </Modal>
  );
}

function DividendModal({ holders, defaultId, balance, onClose, onSaved }: any) {
  const [form, setForm] = useState<any>({
    shareholder_id: defaultId ?? holders[0]?.shareholder.id,
    date: new Date().toISOString().slice(0, 10),
    amount: balance > 0 ? balance : "",
    kind: "non_eligible", settlement: "loan", resolution_ref: "",
  });
  const [error, setError] = useState("");
  return (
    <Modal title="Declare dividend" onClose={onClose}>
      <p className="mb-3 text-sm text-ink-3">
        Record the directors' resolution. Settling “against loan” is the usual
        year-end cleanup for owner draws{balance > 0 &&
          <> — the current balance is <strong>{money(balance)}</strong></>}.
      </p>
      <div className="space-y-3">
        <Field label="Shareholder">
          <Select value={form.shareholder_id}
            onChange={(e) => setForm({ ...form, shareholder_id: Number(e.target.value) })}>
            {holders.map((h: any) =>
              <option key={h.shareholder.id} value={h.shareholder.id}>{h.shareholder.name}</option>)}
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date declared"><Input type="date" value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
          <Field label="Amount ($)"><Input type="number" step="0.01" value={form.amount} required
            onChange={(e) => setForm({ ...form, amount: e.target.value })} /></Field>
          <Field label="Kind">
            <Select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              <option value="non_eligible">Non-eligible (typical CCPC)</option>
              <option value="eligible">Eligible (requires GRIP)</option>
            </Select>
          </Field>
          <Field label="Settlement">
            <Select value={form.settlement}
              onChange={(e) => setForm({ ...form, settlement: e.target.value })}>
              <option value="loan">Apply against shareholder loan</option>
              <option value="cash">Paid in cash</option>
            </Select>
          </Field>
        </div>
        <Field label="Resolution reference">
          <Input value={form.resolution_ref} placeholder="e.g. RES-2026-01"
            onChange={(e) => setForm({ ...form, resolution_ref: e.target.value })} />
        </Field>
        {error && <p className="text-sm text-bad">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={async () => {
            try {
              await api.post("/api/dividends", { ...form, amount: Number(form.amount) });
              onSaved();
            } catch (e: any) { setError(e.message); }
          }}>Declare</Button>
        </div>
      </div>
    </Modal>
  );
}
