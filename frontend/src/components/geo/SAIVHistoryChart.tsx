"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { SAIVDataPoint } from "@/lib/geo/types";

interface SAIVHistoryChartProps {
  data: SAIVDataPoint[];
  /** Chart height in px (default 220). */
  height?: number;
}

function shortDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/**
 * Line chart of AI-Search Visibility (SAIV) over time.
 * Mirrors SoLVHistoryChart so the two scores read alike on the dashboard.
 */
export function SAIVHistoryChart({ data, height = 220 }: SAIVHistoryChartProps) {
  const chartData = data.map((d) => ({ ...d, dateLabel: shortDate(d.date) }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 4, right: 12, left: -8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
        <XAxis
          dataKey="dateLabel"
          tick={{ fontSize: 11, fill: "var(--color-muted, #6b7280)" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: "var(--color-muted, #6b7280)" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v}%`}
        />
        <Tooltip
          formatter={(value) => [`${value}%`, "SAIV"]}
          labelStyle={{ color: "var(--color-foreground, #111827)", fontWeight: 600 }}
          contentStyle={{
            borderRadius: 8,
            border: "1px solid rgba(0,0,0,0.08)",
            fontSize: 12,
          }}
        />
        <Line
          type="monotone"
          dataKey="saiv"
          stroke="#7c3aed"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
