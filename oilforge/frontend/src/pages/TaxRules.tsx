/** Corporate tax rules viewer/editor: per-year packs with UI overrides. */
import { RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import {
  Badge, Button, Card, Field, Input, PageHeader, Select, Table, Td, Th,
} from "../components/ui";

export default function TaxRules() {
  const [years, setYears] = useState<number[]>([]);
  const [year, setYear] = useState(new Date().getFullYear());
  const [rules, setRules] = useState<any>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.get("/api/rules/years").then(setYears); }, []);
  useEffect(() => { api.get(`/api/rules/${year}`).then(setRules); }, [year]);

  const save = async (patch: any) => {
    setRules(await api.put(`/api/rules/${year}`, patch));
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  if (!rules) return null;
  const ct = rules.corporate_tax;
  const div = rules.dividends;
  const loan = rules.shareholder_loan;

  return (
    <div className="fade-up space-y-5">
      <PageHeader title="Corporate tax rules"
        sub="T2, dividend and CCA parameters the engine applies — update when CRA publishes new figures"
        action={
          <div className="flex items-center gap-2">
            {saved && <Badge tone="good">Saved ✓</Badge>}
            {rules.provisional && <Badge tone="warn">Provisional</Badge>}
            <Select value={year} onChange={(e) => setYear(Number(e.target.value))}
              className="!w-auto">
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </Select>
            <Button variant="outline" title="Reset overrides to packaged rates"
              onClick={async () => setRules(await api.del(`/api/rules/${year}/overrides`))}>
              <RotateCcw size={14} /> Reset
            </Button>
          </div>
        } />

      <p className="rounded-xl border border-line bg-surface-1 px-4 py-3 text-sm text-ink-2">
        {rules.source_notes} New year = drop{" "}
        <code className="text-xs">backend/oilforge/cra/rules/&lt;year&gt;.json</code>{" "}
        in and restart, or edit here (stored as overrides).
      </p>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Corporate tax (T2 estimate inputs)">
          <div className="grid grid-cols-3 gap-3">
            <Field label="Federal small-biz rate">
              <Input type="number" step="0.005" value={ct.federal_small_business_rate}
                onChange={(e) => save({ corporate_tax: { federal_small_business_rate: Number(e.target.value) } })} />
            </Field>
            <Field label="SBD limit ($)">
              <Input type="number" step="10000" value={ct.small_business_limit}
                onChange={(e) => save({ corporate_tax: { small_business_limit: Number(e.target.value) } })} />
            </Field>
            <Field label="AB small-biz rate">
              <Input type="number" step="0.005" value={ct.provincial_rates.AB.small}
                onChange={(e) => save({ corporate_tax: { provincial_rates: { AB: { small: Number(e.target.value) } } } })} />
            </Field>
          </div>
        </Card>

        <Card title="Shareholder loan (ITA 15(2) / 80.4)">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Prescribed rate (update quarterly)">
              <Input type="number" step="0.01" value={loan.prescribed_rate}
                onChange={(e) => save({ shareholder_loan: { prescribed_rate: Number(e.target.value) } })} />
            </Field>
            <Field label="Repayment window (months after FYE)">
              <Input type="number" value={loan.ita_15_2_repayment_months_after_year_end}
                onChange={(e) => save({ shareholder_loan: { ita_15_2_repayment_months_after_year_end: Number(e.target.value) } })} />
            </Field>
          </div>
        </Card>

        <Card title="Dividend gross-up & tax credit">
          <Table head={<><Th>Kind</Th><Th right>Gross-up</Th><Th right>Federal DTC (of taxable)</Th></>}>
            {(["non_eligible", "eligible"] as const).map((kind) => (
              <tr key={kind}>
                <Td className="capitalize">{kind.replace("_", "-")}</Td>
                <Td right>
                  <input type="number" step="0.01" defaultValue={div[kind].gross_up}
                    onBlur={(e) => save({ dividends: { [kind]: { gross_up: Number(e.target.value) } } })}
                    className="w-20 rounded-lg border border-line bg-surface-2 px-2 py-1 text-right text-sm" />
                </Td>
                <Td right>
                  <input type="number" step="0.0001" defaultValue={div[kind].federal_dtc_of_taxable}
                    onBlur={(e) => save({ dividends: { [kind]: { federal_dtc_of_taxable: Number(e.target.value) } } })}
                    className="w-24 rounded-lg border border-line bg-surface-2 px-2 py-1 text-right text-sm" />
                </Td>
              </tr>
            ))}
          </Table>
        </Card>

        <Card title="CCA classes">
          <Table head={<><Th>Class</Th><Th>Description</Th><Th right>Rate</Th></>}>
            {Object.entries(rules.cca.classes).map(([cls, info]: [string, any]) => (
              <tr key={cls}>
                <Td><Badge tone="accent">{cls}</Badge></Td>
                <Td className="text-xs">{info.description}</Td>
                <Td right>
                  <input type="number" step="0.05" defaultValue={info.rate}
                    onBlur={(e) => save({ cca: { classes: { [cls]: { rate: Number(e.target.value) } } } })}
                    className="w-20 rounded-lg border border-line bg-surface-2 px-2 py-1 text-right text-sm" />
                </Td>
              </tr>
            ))}
          </Table>
          <p className="mt-2 text-xs text-ink-3">
            First-year factor on net additions:{" "}
            <input type="number" step="0.5" defaultValue={rules.cca.first_year_multiplier}
              onBlur={(e) => save({ cca: { first_year_multiplier: Number(e.target.value) } })}
              className="w-16 rounded-lg border border-line bg-surface-2 px-2 py-0.5 text-right text-sm" />{" "}
            (1.5 = Accelerated Investment Incentive; 0.5 = plain half-year rule)
          </p>
        </Card>
      </div>

      <Card title="Oilfield deduction notes (CRA)">
        <div className="grid gap-4 text-sm text-ink-2 md:grid-cols-2">
          <div>
            <h4 className="mb-1 font-semibold text-ink-1">Camp & remote sites</h4>
            <p>{rules.oilfield_deductions.camp_allowance_notes}</p>
            <h4 className="mb-1 mt-3 font-semibold text-ink-1">Safety gear</h4>
            <p>{rules.oilfield_deductions.safety_gear_notes}</p>
          </div>
          <div>
            <h4 className="mb-1 font-semibold text-ink-1">Remote travel</h4>
            <p>{rules.oilfield_deductions.remote_work_notes}</p>
            <h4 className="mb-1 mt-3 font-semibold text-ink-1">Records</h4>
            <p>Keep all books, tickets and exports at least{" "}
              {rules.records_retention_years} years. The audit trail in
              Reports is append-only.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
