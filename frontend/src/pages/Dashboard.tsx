/** Home dashboard: KPI tiles, monthly P&L, profit-per-km, expense mix,
 * GST position — the daily-driver view. */
import { useEffect, useState } from "react";
import { api, money } from "../api";
import { ExpenseBreakdown, MonthlyPnL, ProfitPerKm } from "../components/charts";
import { Badge, Card, PageHeader, StatCard } from "../components/ui";
import { useStore } from "../store";

export default function Dashboard() {
  const { period, user } = useStore();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get(`/api/reports/dashboard?start=${period.start}&end=${period.end}`)
      .then(setData).catch((e) => setError(e.message));
  }, [period]);

  if (error) return <p className="text-sm text-bad">{error}</p>;
  if (!data) return <p className="text-sm text-ink-3">Loading your books…</p>;

  const net = data.kpis.net_income;
  const gst = data.gst34;
  const categories = Object.entries(data.expenses.by_category)
    .map(([category, amount]) => ({ category, amount: amount as number }));

  return (
    <div className="fade-up space-y-5">
      <PageHeader
        title={`Welcome back${user?.name ? ", " + user.name.split(" ")[0] : ""}`}
        sub={`${period.label} · ${data.province} · GST ${Math.round(data.gst_rate * 100)}%`}
        action={data.rules_provisional && (
          <Badge tone="warn">⚠ {data.rules_year} CRA rates provisional — verify in Tax Rules</Badge>
        )} />

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Revenue" value={money(data.revenue.total)}
          sub={`GST collected ${money(data.revenue.gst_collected)}`} />
        <StatCard label="Expenses" value={money(data.expenses.total)}
          sub={`ITCs ${money(data.itcs.total)}`} />
        <StatCard label="Net income" value={money(net)}
          tone={net >= 0 ? "good" : "bad"}
          delta={net >= 0 ? "profitable" : "running at a loss"} />
        <StatCard label={gst.owing ? "GST owing" : "GST refund"}
          value={money(Math.abs(gst.line_109_net_tax))}
          tone={gst.owing ? "bad" : "good"}
          sub="Line 109 net tax" />
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Business km" value={data.mileage.business_km.toLocaleString()}
          sub={`${data.mileage.business_pct}% business use`} />
        <StatCard label="Profit / km" value={money(data.kpis.profit_per_km)}
          tone={data.kpis.profit_per_km >= 0 ? "good" : "bad"}
          sub={`cost ${money(data.kpis.cost_per_km)} / km`} />
        <StatCard label="CRA km allowance" value={money(data.mileage.cra_allowance)}
          sub="tax-free vehicle allowance" />
        <StatCard label="Fuel purchased" value={`${data.mileage.fuel_litres.toLocaleString()} L`}
          sub="tracked for IFTA" />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Monthly revenue vs expenses">
          <MonthlyPnL data={data.monthly} />
        </Card>
        <Card title="Profit per km by month">
          <ProfitPerKm data={data.monthly} />
        </Card>
      </div>

      {categories.length > 0 && (
        <Card title="Deductible expenses by category">
          <ExpenseBreakdown data={categories} />
        </Card>
      )}
    </div>
  );
}
