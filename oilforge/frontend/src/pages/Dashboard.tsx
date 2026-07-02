/** Command center: cash position, profitability, GST, shareholder loan &
 * dividends, cash-flow trend, job margins, equipment hours. */
import { useEffect, useState } from "react";
import { api, money } from "../api";
import { CashFlow, EquipmentHours, JobMargins } from "../components/charts";
import { Badge, Card, PageHeader, StatCard } from "../components/ui";
import { useStore } from "../store";

export default function Dashboard() {
  const { period, user } = useStore();
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get(`/api/reports/dashboard?start=${period.start}&end=${period.end}`)
      .then(setD).catch((e) => setError(e.message));
  }, [period]);

  if (error) return <p className="text-sm text-bad">{error}</p>;
  if (!d) return <p className="text-sm text-ink-3">Loading the books…</p>;

  const inc = d.income;
  const shd = d.shareholder;
  const gst = d.gst34;
  const loanTone = shd.loan_balance_total > 0 ? "bad" : "good";

  return (
    <div className="fade-up space-y-5">
      <PageHeader
        title={`Welcome back${user?.name ? ", " + user.name.split(" ")[0] : ""}`}
        sub={`${period.label} · ${d.province} · GST ${Math.round(d.gst_rate * 100)}%`}
        action={d.rules_provisional && (
          <Badge tone="warn">⚠ {d.rules_year} rates provisional — verify in Tax Rules</Badge>
        )} />

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Cash position" value={money(d.kpis.cash_position)}
          tone={d.kpis.cash_position >= 0 ? "good" : "bad"}
          sub="from bank feed" />
        <StatCard label="Revenue (invoiced)" value={money(d.revenue.invoiced)}
          sub={`unbilled work ${money(d.revenue.unbilled_work)}`} />
        <StatCard label="Income before tax" value={money(inc.before_tax)}
          tone={inc.before_tax >= 0 ? "good" : "bad"}
          sub={`after CCA ${money(inc.cca)}`} />
        <StatCard label={gst.owing ? "GST owing" : "GST refund"}
          value={money(Math.abs(gst.line_109_net_tax))}
          tone={gst.owing ? "bad" : "good"} sub="Line 109 net tax" />
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Shareholder loan" value={money(Math.abs(shd.loan_balance_total))}
          tone={loanTone}
          sub={shd.loan_balance_total > 0 ? "owing to corp — ITA 15(2) watch"
            : shd.loan_balance_total < 0 ? "corp owes shareholder" : "cleared"} />
        <StatCard label="Dividends declared" value={money(shd.dividends_declared)}
          sub="this fiscal period" />
        <StatCard label="A/R outstanding" value={money(d.revenue.ar_outstanding)}
          sub={`holdbacks ${money(d.revenue.holdbacks_receivable)}`} />
        <StatCard label="Corporate tax est." value={money(inc.tax_estimate)}
          sub={`${(inc.small_business_rate * 100).toFixed(1)}% small-business rate`} />
      </div>

      <Card title="Monthly cash flow">
        <CashFlow data={d.cash_flow} />
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Job profitability — earned vs costs">
          {d.job_margins.length ? <JobMargins data={d.job_margins} />
            : <p className="text-sm text-ink-3">Add jobs and field entries to see margins.</p>}
        </Card>
        <Card title="Equipment field hours">
          {d.equipment_utilization.some((u: any) => u.hours > 0)
            ? <EquipmentHours data={d.equipment_utilization} />
            : <p className="text-sm text-ink-3">Tag field entries with equipment to track utilization.</p>}
        </Card>
      </div>
    </div>
  );
}
