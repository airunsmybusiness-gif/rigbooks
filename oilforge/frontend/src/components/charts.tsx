/** OilForge dashboard charts (Recharts), per the dataviz method: thin
 * rounded marks, hairline solid grid, one $ axis, text tokens for labels,
 * tooltips everywhere, validated palette tokens for series. */
import {
  Bar, BarChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { money } from "../api";

const css = (v: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(v).trim();

const tooltipStyle = () => ({
  background: css("--surface-1"),
  border: `1px solid ${css("--grid")}`,
  borderRadius: 12,
  fontSize: 12,
  color: css("--ink-1"),
  boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
} as const);

const axisTick = () => ({ fill: css("--ink-3"), fontSize: 11 });

export type CashMonth = {
  month: string; cash_in: number; cash_out: number; net: number; cumulative: number;
};

/** Monthly cash in/out columns + cumulative line — all on one $ axis. */
export function CashFlow({ data }: { data: CashMonth[] }) {
  return (
    <div>
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }} barGap={2}>
          <CartesianGrid stroke={css("--grid")} strokeWidth={1} vertical={false} />
          <XAxis dataKey="month" tick={axisTick()} axisLine={{ stroke: css("--axis") }}
            tickLine={false} />
          <YAxis tick={axisTick()} axisLine={false} tickLine={false} width={56}
            tickFormatter={(v) => (Math.abs(v) >= 1000 ? `$${v / 1000}K` : `$${v}`)} />
          <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: css("--grid"), opacity: 0.35 }}
            formatter={(v: number, name: string) => [money(v), name]} />
          <Bar dataKey="cash_in" name="Cash in" fill="var(--series-1)"
            radius={[4, 4, 0, 0]} maxBarSize={16} />
          <Bar dataKey="cash_out" name="Cash out" fill="var(--series-2)"
            radius={[4, 4, 0, 0]} maxBarSize={16} />
          <Line type="monotone" dataKey="cumulative" name="Cumulative"
            stroke="var(--series-5)" strokeWidth={2} dot={false}
            activeDot={{ r: 5, stroke: css("--surface-1"), strokeWidth: 2 }}
            isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <Legend items={[["Cash in", "var(--series-1)"], ["Cash out", "var(--series-2)"],
                      ["Cumulative", "var(--series-5)"]]} />
    </div>
  );
}

export type JobMargin = {
  job: string; earned: number; costs: number; margin: number; margin_pct: number;
};

/** Earned vs costs per job — grouped horizontal bars, two series. */
export function JobMargins({ data }: { data: JobMargin[] }) {
  const top = data.slice(0, 6);
  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(58 * top.length, 130)}>
        <BarChart data={top} layout="vertical" barGap={2}
          margin={{ top: 4, right: 70, left: 8, bottom: 4 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="job" width={150} tick={axisTick()}
            axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: css("--grid"), opacity: 0.35 }}
            formatter={(v: number, name: string) => [money(v), name]} />
          <Bar dataKey="earned" name="Earned" fill="var(--series-1)"
            radius={[0, 4, 4, 0]} maxBarSize={13}
            label={{ position: "right", fill: css("--ink-2"), fontSize: 11,
                     formatter: (v: number) => money(v) }} />
          <Bar dataKey="costs" name="Costs" fill="var(--series-2)"
            radius={[0, 4, 4, 0]} maxBarSize={13} />
        </BarChart>
      </ResponsiveContainer>
      <Legend items={[["Earned", "var(--series-1)"], ["Costs", "var(--series-2)"]]} />
    </div>
  );
}

export type Utilization = { equipment: string; hours: number; running_costs: number };

/** Field hours per unit — one measure, one hue. */
export function EquipmentHours({ data }: { data: Utilization[] }) {
  const top = data.filter((d) => d.hours > 0).slice(0, 8);
  if (top.length === 0) return null;
  return (
    <ResponsiveContainer width="100%" height={Math.max(46 * top.length, 110)}>
      <BarChart data={top} layout="vertical"
        margin={{ top: 4, right: 64, left: 8, bottom: 4 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="equipment" width={150} tick={axisTick()}
          axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: css("--grid"), opacity: 0.35 }}
          formatter={(v: number, name: string) =>
            name === "Field hours" ? [`${v.toLocaleString()} h`, name] : [money(v), name]} />
        <Bar dataKey="hours" name="Field hours" fill="var(--series-1)"
          radius={[0, 4, 4, 0]} maxBarSize={14}
          label={{ position: "right", fill: css("--ink-2"), fontSize: 11,
                   formatter: (v: number) => `${v.toLocaleString()} h` }} />
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
