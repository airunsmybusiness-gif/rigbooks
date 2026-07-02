/** Personal Tax Bridge — pulls corporate dividends/loan data, takes the
 * owner's personal income/deductions, previews the T1 (gross-up, DTC,
 * AMT) and shows the combined corp + personal picture. */
import { Download } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, Card, EmptyState, Field, Input, PageHeader, Select, StatCard,
  Table, Td, Th,
} from "../components/ui";
import { useStore } from "../store";

const INPUT_FIELDS: [string, string][] = [
  ["employment_income", "Employment income (T4, other)"],
  ["other_income", "Other income (rental, self-employed…)"],
  ["interest_income", "Interest & investment income"],
  ["rrsp_deduction", "RRSP deduction"],
  ["other_deductions", "Other deductions"],
];

export default function PersonalTax() {
  const { year } = useStore();
  const [holders, setHolders] = useState<any[]>([]);
  const [sid, setSid] = useState<number | null>(null);
  const [data, setData] = useState<any>(null);
  const [form, setForm] = useState<any>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/api/shareholders").then((r) => {
      const items = r.items ?? r;
      setHolders(items);
      if (items.length && sid === null) setSid(items[0].id);
    });
  }, []);

  const load = useCallback(() => {
    if (sid == null) return;
    api.get(`/api/personal-tax/${sid}/${year}`).then((r) => {
      setData(r);
      setForm(r.inputs);
    });
  }, [sid, year]);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (sid == null) return;
    setSaving(true);
    try {
      const r = await api.put(`/api/personal-tax/${sid}/${year}`, form);
      setData(r);
      setForm(r.inputs);
    } finally { setSaving(false); }
  };

  if (holders.length === 0) {
    return (
      <div className="fade-up">
        <PageHeader title="Personal Tax Bridge" />
        <EmptyState>Add a shareholder first (Dividends & Loans page) —
          the bridge pulls their dividends and loan balance automatically.</EmptyState>
      </div>
    );
  }
  if (!data) return null;

  const t1 = data.t1_preview;
  const inc = t1.income;
  const integ = data.integrated;

  return (
    <div className="fade-up space-y-5">
      <PageHeader title="Personal Tax Bridge"
        sub={`T1 preview for calendar ${year} — corporate figures flow in automatically`}
        action={
          <div className="flex items-center gap-2">
            {data.provisional && <Badge tone="warn">Provisional rates</Badge>}
            <Select value={sid ?? ""} onChange={(e) => setSid(Number(e.target.value))}
              className="!w-auto">
              {holders.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
            </Select>
          </div>
        } />

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Total tax (est.)" value={money(t1.totals.total_tax)}
          tone="bad" sub={`avg rate ${(t1.totals.average_rate * 100).toFixed(1)}%`} />
        <StatCard label="After-tax cash" value={money(t1.totals.after_tax_cash)}
          tone="good" sub={`of ${money(t1.totals.cash_received)} received`} />
        <StatCard label="Marginal rate" value={`${(t1.totals.marginal_rate * 100).toFixed(1)}%`}
          sub="fed + AB combined" />
        <StatCard label="AMT" value={t1.amt.applies ? "Applies" : "Not binding"}
          tone={t1.amt.applies ? "bad" : "good"}
          sub={`AMT calc ${money(t1.amt.amt_tax)}`} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
        <Card title="Personal income & deductions" className="h-fit">
          <div className="space-y-3">
            {INPUT_FIELDS.map(([key, label]) => (
              <Field key={key} label={label}>
                <Input type="number" step="100" value={form[key] ?? 0}
                  onChange={(e) => setForm({ ...form, [key]: Number(e.target.value) })} />
              </Field>
            ))}
            <Button onClick={save} disabled={saving} className="w-full">
              {saving ? "Recalculating…" : "Recalculate preview"}
            </Button>
            <p className="text-xs text-ink-3">
              From the corp (automatic): dividends {money(inc.dividends_actual.non_eligible)}{" "}
              non-eligible + {money(inc.dividends_actual.eligible)} eligible ·
              80.4 imputed interest {money(inc.imputed_interest_80_4)} on a{" "}
              {money(data.loan_balance_dec31)} Dec 31 loan balance.
            </p>
          </div>
        </Card>

        <div className="space-y-5">
          <Card title="T1 preview">
            <Table head={<><Th>Line</Th><Th right>Amount</Th></>}>
              <tr><Td>Employment + other + interest income</Td>
                <Td right>{money(inc.employment + inc.other + inc.interest)}</Td></tr>
              <tr><Td>Taxable dividends (grossed up:
                +{money(inc.gross_up_added)})</Td>
                <Td right>{money(inc.dividends_taxable.eligible + inc.dividends_taxable.non_eligible)}</Td></tr>
              {inc.imputed_interest_80_4 > 0 && (
                <tr><Td>ITA 80.4 imputed interest benefit</Td>
                  <Td right>{money(inc.imputed_interest_80_4)}</Td></tr>
              )}
              <tr><Td>Deductions</Td><Td right>({money(inc.deductions)})</Td></tr>
              <tr className="font-medium"><Td>Taxable income</Td>
                <Td right>{money(inc.taxable_income)}</Td></tr>
              <tr><Td>Federal tax after BPA & dividend tax credit
                ({money(t1.federal.dividend_tax_credit)})</Td>
                <Td right>{money(t1.federal.net)}</Td></tr>
              <tr><Td>Alberta tax after BPA & DTC
                ({money(t1.provincial.dividend_tax_credit)})</Td>
                <Td right>{money(t1.provincial.net)}</Td></tr>
              <tr className="bg-surface-2 font-semibold">
                <Td>Total estimated tax{t1.amt.applies ? " (AMT applies)" : ""}</Td>
                <Td right>{money(t1.totals.total_tax)}</Td></tr>
            </Table>
            <p className="mt-2 text-xs text-ink-3">{t1.notes}</p>
          </Card>

          <Card title="Combined corporate + personal picture">
            <Table head={<><Th>Step</Th><Th right>Amount</Th></>}>
              <tr><Td>Corporate income before tax</Td>
                <Td right>{money(integ.corporate_income_before_tax)}</Td></tr>
              <tr><Td>Corporate tax (estimate)</Td>
                <Td right>({money(integ.corporate_tax_estimate)})</Td></tr>
              <tr><Td>Cash to owner (dividends + other income)</Td>
                <Td right>{money(integ.dividends_to_owner)}</Td></tr>
              <tr><Td>Personal tax (estimate)</Td>
                <Td right>({money(integ.personal_tax_estimate)})</Td></tr>
              <tr className="bg-surface-2 font-semibold">
                <Td>Combined tax — {(integ.combined_effective_rate * 100).toFixed(1)}% of corporate income</Td>
                <Td right>{money(integ.combined_tax)}</Td></tr>
              <tr className="font-semibold text-good">
                <Td>Owner's after-tax cash</Td>
                <Td right>{money(integ.owner_after_tax_cash)}</Td></tr>
            </Table>
            <div className="mt-3 flex justify-end">
              <Button variant="outline" onClick={() =>
                api.download(`/api/reports/accountant-package.zip?year=${year}`,
                  `OilForge_Accountant_Package_${year}.zip`)}>
                <Download size={15} /> Full accountant package (ZIP)
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
