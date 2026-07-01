/** CRA tax-rules viewer/editor: per-year packs with UI overrides, plus a
 * built-in audit-readiness guide. New year = new JSON pack or edit here. */
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
    const updated = await api.put(`/api/rules/${year}`, patch);
    setRules(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  if (!rules) return null;
  const m = rules.mileage;
  const meals = rules.meals;

  return (
    <div className="fade-up space-y-5">
      <PageHeader title="CRA tax rules"
        sub="Rates the engine applies — update annually when CRA publishes new figures"
        action={
          <div className="flex items-center gap-2">
            {saved && <Badge tone="good">Saved ✓</Badge>}
            {rules.provisional && <Badge tone="warn">Provisional</Badge>}
            <Select value={year} onChange={(e) => setYear(Number(e.target.value))}
              className="!w-auto">
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </Select>
            <Button variant="outline" title="Reset overrides to the packaged rates"
              onClick={async () => {
                setRules(await api.del(`/api/rules/${year}/overrides`));
              }}>
              <RotateCcw size={14} /> Reset
            </Button>
          </div>
        } />

      <p className="rounded-xl bg-surface-1 border border-line px-4 py-3 text-sm text-ink-2">
        {rules.source_notes} Edits here apply immediately to new entries and
        recalculated reports; the shipped rule packs stay untouched. To add a
        future year, drop <code className="text-xs">backend/rigbooks/cra/rules/&lt;year&gt;.json</code> in
        and restart.
      </p>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Vehicle allowance (per-km, tax-free)">
          <div className="grid grid-cols-3 gap-3">
            <Field label={`First ${m.tier1_limit_km.toLocaleString()} km ($/km)`}>
              <Input type="number" step="0.01" value={m.tier1_rate}
                onChange={(e) => save({ mileage: { tier1_rate: Number(e.target.value) } })} />
            </Field>
            <Field label="After ($/km)">
              <Input type="number" step="0.01" value={m.tier2_rate}
                onChange={(e) => save({ mileage: { tier2_rate: Number(e.target.value) } })} />
            </Field>
            <Field label="Territory supplement">
              <Input type="number" step="0.01" value={m.territory_supplement_per_km}
                onChange={(e) => save({ mileage: { territory_supplement_per_km: Number(e.target.value) } })} />
            </Field>
          </div>
        </Card>

        <Card title="Meals & per diem">
          <div className="grid grid-cols-3 gap-3">
            <Field label="Simplified $/meal">
              <Input type="number" step="0.5" value={meals.simplified_rate_per_meal}
                onChange={(e) => save({ meals: { simplified_rate_per_meal: Number(e.target.value) } })} />
            </Field>
            <Field label="Long-haul deductible %">
              <Input type="number" step="1" value={meals.long_haul_deductible_pct * 100}
                onChange={(e) => save({ meals: { long_haul_deductible_pct: Number(e.target.value) / 100 } })} />
            </Field>
            <Field label="Standard deductible %">
              <Input type="number" step="1" value={meals.standard_deductible_pct * 100}
                onChange={(e) => save({ meals: { standard_deductible_pct: Number(e.target.value) / 100 } })} />
            </Field>
          </div>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="GST/HST rates by province">
          <Table head={<><Th>Province</Th><Th right>Rate</Th></>}>
            {Object.entries(rules.gst_hst.rates).map(([prov, rate]) => (
              <tr key={prov}>
                <Td>{prov}</Td>
                <Td right>
                  <input type="number" step="0.01" defaultValue={rate as number}
                    onBlur={(e) => {
                      const v = Number(e.target.value);
                      if (v !== rate) save({ gst_hst: { rates: { [prov]: v } } });
                    }}
                    className="w-20 rounded-lg border border-line bg-surface-2 px-2 py-1 text-right text-sm" />
                </Td>
              </tr>
            ))}
          </Table>
        </Card>

        <Card title="IFTA fuel tax $/L (update quarterly from iftach.org)">
          <Table head={<><Th>Jurisdiction</Th><Th right>$/litre</Th></>}>
            {Object.entries(rules.ifta.fuel_tax_rates_per_litre).map(([j, rate]) => (
              <tr key={j}>
                <Td>{j}</Td>
                <Td right>
                  <input type="number" step="0.0001" defaultValue={rate as number}
                    onBlur={(e) => {
                      const v = Number(e.target.value);
                      if (v !== rate) save({ ifta: { fuel_tax_rates_per_litre: { [j]: v } } });
                    }}
                    className="w-24 rounded-lg border border-line bg-surface-2 px-2 py-1 text-right text-sm" />
                </Td>
              </tr>
            ))}
          </Table>
        </Card>
      </div>

      <Card title="CRA audit-readiness guide">
        <div className="grid gap-4 text-sm text-ink-2 md:grid-cols-2">
          <div>
            <h4 className="mb-1 font-semibold text-ink-1">Receipts</h4>
            <p>Under $30: bank statement is enough. $30–150: keep the receipt.
              Over $150: original receipt required. Meals: receipt + who attended.
              Fuel: receipts + this mileage log.</p>
            <h4 className="mb-1 mt-3 font-semibold text-ink-1">Record keeping</h4>
            <p>Keep all books, receipts and this app's exports for at least{" "}
              <strong>{rules.records_retention_years} years</strong> from the end
              of the tax year. The audit trail here is append-only.</p>
          </div>
          <div>
            <h4 className="mb-1 font-semibold text-ink-1">Mileage log</h4>
            <p>Every business trip: date, origin, destination, purpose, km.
              Business-use % = business km ÷ total km — that percentage applies
              to actual vehicle costs (fuel, repairs, insurance, lease).</p>
            <h4 className="mb-1 mt-3 font-semibold text-ink-1">T4A (box {rules.t4a.box})</h4>
            <p>Fees for services over ${rules.t4a.fee_reporting_threshold} paid
              to contractors (including CCPCs) may require a T4A slip — the
              Reports page lists candidates automatically.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
