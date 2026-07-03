/** Tax Optimizer: deduction scanner findings, T2 Schedule 1 working paper,
 * personal tax bridge (corporate → T1), GRIP tracking. */
import { AlertTriangle, Info, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, Card, EmptyState, Input, PageHeader, StatCard, Table, Td, Th,
} from "../components/ui";
import { useStore } from "../store";

const SEV: Record<string, { tone: any; label: string }> = {
  action: { tone: "bad", label: "Action" },
  review: { tone: "warn", label: "Review" },
  info: { tone: "neutral", label: "Idea" },
};

export default function TaxOptimizer() {
  const { period, year } = useStore();
  const [opt, setOpt] = useState<any>(null);
  const [s1, setS1] = useState<any>(null);
  const [grip, setGrip] = useState<Record<string, number>>({});
  const [gripDraft, setGripDraft] = useState("");

  useEffect(() => {
    const range = `start=${period.start}&end=${period.end}`;
    api.get(`/api/tax/optimizer?${range}`).then(setOpt);
    api.get(`/api/tax/schedule1?${range}`).then(setS1);
    api.get("/api/tax/grip").then((g) => {
      setGrip(g);
      setGripDraft(String(g[String(year)] ?? ""));
    });
  }, [period, year]);

  if (!opt) return <p className="text-sm text-ink-3">Scanning the books…</p>;

  return (
    <div className="fade-up space-y-5">
      <PageHeader title="Tax Optimizer"
        sub="Every legitimate claim found, every exposure flagged — before the accountant sees the books" />

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Action items" value={String(opt.counts.action)}
          tone={opt.counts.action ? "bad" : "good"}
          sub="money or compliance at stake" />
        <StatCard label="Review items" value={String(opt.counts.review)}
          sub="judgment calls for the accountant" />
        <StatCard label="Ideas" value={String(opt.counts.info)}
          sub="claimable categories with no activity" />
        <StatCard label="Flagged amounts" value={money(opt.flagged_total)}
          sub="total across findings" />
      </div>

      <Card title="Findings">
        {opt.findings.length === 0 ? (
          <EmptyState>Nothing flagged — the books look filing-ready.</EmptyState>
        ) : (
          <div className="space-y-2.5">
            {opt.findings.map((f: any, i: number) => (
              <div key={i}
                className="flex flex-wrap items-start gap-3 rounded-xl border border-line bg-surface-2 px-4 py-3">
                <Badge tone={SEV[f.severity].tone}>
                  {f.severity === "action" ? <AlertTriangle size={11} />
                    : f.severity === "review" ? <Search size={11} /> : <Info size={11} />}
                  &nbsp;{SEV[f.severity].label}
                </Badge>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-ink-1">
                    {f.title}
                    {f.amount != null && (
                      <span className="ml-2 tabular-nums text-accent">{money(f.amount)}</span>
                    )}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-3">{f.detail}</p>
                  {f.action && <p className="mt-0.5 text-xs text-accent">→ {f.action}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        {s1 && (
          <Card title="T2 Schedule 1 — book to tax">
            <Table head={<><Th>Line</Th><Th right>Amount</Th></>}>
              {s1.lines.map((l: any, i: number) => (
                <tr key={i} className={i === s1.lines.length - 1 ? "bg-surface-2 font-semibold" : ""}>
                  <Td>{l.line}</Td>
                  <Td right>{money(l.amount)}</Td>
                </tr>
              ))}
            </Table>
            <p className="mt-2 text-xs text-ink-3">
              {s1.notes} Corporate tax estimate on this base:{" "}
              <strong>{money(s1.corporate_tax_estimate)}</strong>.
            </p>
          </Card>
        )}

        <div className="space-y-5">
          <Card title={`GRIP balance — ${year}`}>
            <p className="mb-3 text-sm text-ink-3">
              General Rate Income Pool caps how much can be paid as{" "}
              <em>eligible</em> dividends. Enter the balance from the
              accountant's T2 Schedule 53; declarations above it get flagged.
            </p>
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Input type="number" step="100" value={gripDraft}
                  placeholder="0"
                  onChange={(e) => setGripDraft(e.target.value)} />
              </div>
              <Button onClick={async () => {
                const g = await api.put("/api/tax/grip",
                  { [String(year)]: Number(gripDraft || 0) });
                setGrip(g);
              }}>Save</Button>
            </div>
            <p className="mt-2 text-xs text-ink-3">
              Saved: {money(Number(grip[String(year)] ?? 0))}
            </p>
          </Card>

          <Card title="Personal tax (T1) preview">
            <p className="text-sm text-ink-2">
              The <a href="/personal-tax" className="font-medium text-accent underline">
              Personal Tax Bridge</a> page runs the full owner-side estimate:
              dividends through the federal + Alberta brackets with both
              dividend tax credits, employment/other income, RRSP deductions,
              the simplified AMT check, and the combined corporate + personal
              effective rate. If family members are shareholders, dividends to
              anyone not active in the business fall under TOSI — plan with
              the accountant.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
