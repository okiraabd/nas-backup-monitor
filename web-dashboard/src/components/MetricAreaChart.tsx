import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export interface MetricChartPoint {
  time: string;
  fullDate: string;
  value: number | null;
}

interface MetricAreaChartProps {
  data: MetricChartPoint[];
  /** Tooltip/legend series label. */
  label: string;
  /** Append "%" to axis ticks and tooltip values. */
  isPercentage?: boolean;
  /** Unique gradient id so multiple charts on a page don't clash. */
  gradientId?: string;
  /** Fixed Y-axis domain, e.g. [0, 100]. Omit for auto-scaling. */
  yDomain?: [number, number];
  /** Show an active dot on hover (used by NAS charts). */
  showActiveDot?: boolean;
  /** Left margin; NAS charts pull in with -20, Ceph uses 0. */
  marginLeft?: number;
}

/**
 * Shared area chart for metric history (NAS CPU/RAM and Ceph storage). All the
 * axis/grid/tooltip styling lives here so every chart looks identical; the few
 * real differences are exposed as props.
 */
export function MetricAreaChart({
  data,
  label,
  isPercentage = false,
  gradientId = "colorValue",
  yDomain,
  showActiveDot = false,
  marginLeft = 0,
}: MetricAreaChartProps) {
  const suffix = isPercentage ? "%" : "";
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: marginLeft }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
        <XAxis
          dataKey="time"
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
          tickLine={false}
          axisLine={false}
          domain={yDomain}
          tickFormatter={(value) => `${value}${suffix}`}
        />
        <Tooltip
          contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
          labelStyle={{ color: "hsl(var(--foreground))", fontWeight: "bold" }}
          itemStyle={{ color: "hsl(var(--primary))" }}
          labelFormatter={(labelValue, entries) => entries?.[0]?.payload.fullDate || labelValue}
          formatter={(value) => [`${value}${suffix}`, label]}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke="hsl(var(--primary))"
          fillOpacity={1}
          fill={`url(#${gradientId})`}
          strokeWidth={2}
          activeDot={
            showActiveDot
              ? { r: 6, fill: "hsl(var(--primary))", stroke: "hsl(var(--background))", strokeWidth: 2 }
              : undefined
          }
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
