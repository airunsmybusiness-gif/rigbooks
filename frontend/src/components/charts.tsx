/** Dashboard charts (Recharts), styled per the dataviz method:
 * thin rounded bars, 2px lines, hairline solid grid, text tokens for all
 * labels, tooltips on hover, colors from the validated palette tokens. */
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { money } from "../api";

const css = (v: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(v).trim();

function tooltipStyle() {
  return {
    background: css("--surface-1"),
    border: `1px solid ${css("--grid")}`,
    borderRadius: 12,
    fontSize: 12,
    color: css("--ink-1"),
    boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
  } as const;
}

const axisTick = () => ({ fill: css("--ink-3"), fontSize: 11 });

export type MonthPoint = {
  month: string; revenue: number; expenses: number; net: number;
  business_km: number; profit_per_km: number;
};

/** Monthly revenue vs expenses — grouped columns, one baseline. */
export function MonthlyPnL({ data }: { data: MonthPoint[] }) {
  return (
    <div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }} barGap={2}>
          <CartesianGrid stroke={css("--grid")} strokeWidth={1} vertical={false} />
          <XAxis dataKey="month" tick={axisTick()} axisLine={{ stroke: css("--axis") }}
            tickLine={false} />
          <YAxis tick={axisTick()} axisLine={false} tickLine={false} width={52}
            tickFormatter={(v) => (v >= 1000 ? `$${v / 1000}K` : `$${v}`)} />
          <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: css("--grid"), opacity: 0.35 }}
            formatter={(v: number, name: string) => [money(v), name]} />
          <Bar dataKey="revenue" name="Revenue" fill="var(--series-1)"
            radius={[4, 4, 0, 0]} maxBarSize={18} />
          <Bar dataKey="expenses" name="Expenses" fill="var(--series-2)"
            radius={[4, 4, 0, 0]} maxBarSize={18} />
        </BarChart>
      </ResponsiveContainer>
      <Legend items={[["Revenue", "var(--series-1)"], ["Expenses", "var(--series-2)"]]} />
    </div>
  );
}

/** Profit per business km, month by month — single 2px line. */
export function ProfitPerKm({ data }: { data: MonthPoint[] }) {
  const has = data.some((d) => d.business_km > 0);
  // Months with no logged km are gaps, not zeros.
  const points = data.map((d) =>
    d.business_km > 0 ? d : { ...d, profit_per_km: null as unknown as number });
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={points} margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
        <CartesianGrid stroke={css("--grid")} strokeWidth={1} vertical={false} />
        <XAxis dataKey="month" tick={axisTick()} axisLine={{ stroke: css("--axis") }}
          tickLine={false} />
        <YAxis tick={axisTick()} axisLine={false} tickLine={false} width={52}
          tickFormatter={(v) => `$${v}`} />
        <Tooltip contentStyle={tooltipStyle()}
          formatter={(v: number) => [money(v) + " / km", "Profit per km"]} />
        <Line type="monotone" dataKey="profit_per_km" name="Profit per km"
          stroke="var(--series-5)" strokeWidth={2} dot={false}
          activeDot={{ r: 5, stroke: css("--surface-1"), strokeWidth: 2 }}
          strokeLinecap="round" isAnimationActive={false} />
        {!has && <text x="50%" y="45%" textAnchor="middle"
          fill={css("--ink-3")} fontSize={12}>Log trips to see profit per km</text>}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Expense breakdown — horizontal bars, one hue (nominal categories:
 * bar length carries the value, so no rainbow). */
export function ExpenseBreakdown({ data }: { data: { category: string; amount: number }[] }) {
  const top = data.slice(0, 8);
  return (
    <ResponsiveContainer width="100%" height={Math.max(48 * top.length, 120)}>
      <BarChart data={top} layout="vertical"
        margin={{ top: 4, right: 64, left: 8, bottom: 4 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="category" width={170} tick={axisTick()}
          axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: css("--grid"), opacity: 0.35 }}
          formatter={(v: number) => [money(v), "Deductible"]} />
        <Bar dataKey="amount" name="Deductible" fill="var(--series-1)"
          radius={[0, 4, 4, 0]} maxBarSize={16}
          label={{ position: "right", fill: css("--ink-2"), fontSize: 11,
                   formatter: (v: number) => money(v) }}>
          {top.map((d) => <Cell key={d.category} fill="var(--series-1)" />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function Legend({ items }: { items: [string, string][] }) {
  return (
    <div className="mt-1 flex flex-wrap gap-4 px-2">
      {items.map(([label, color]) => (
        <span key={label} className="flex items-center gap-1.5 text-xs text-ink-2">
          <span className="size-2.5 rounded-full" style={{ background: color }} />
          {label}
        </span>
      ))}
    </div>
  );
}
