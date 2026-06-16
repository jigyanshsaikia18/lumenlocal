"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AI_PROVIDER_LABELS } from "@/lib/geo/types";
import type { ProviderBreakdown } from "@/lib/geo/types";

interface ProviderBreakdownChartProps {
  data: ProviderBreakdown[];
  /** Chart height in px (default 240). */
  height?: number;
}

/**
 * Bar chart of SAIV per AI surface (AI Overviews, AI Mode, Gemini, ChatGPT,
 * Perplexity, Grok) — shows which providers actually cite the business.
 */
export function ProviderBreakdownChart({ data, height = 240 }: ProviderBreakdownChartProps) {
  const chartData = data.map((d) => ({ ...d, label: AI_PROVIDER_LABELS[d.provider] }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} margin={{ top: 4, right: 12, left: -8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: "var(--color-muted, #6b7280)" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: "var(--color-muted, #6b7280)" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v}%`}
        />
        <Tooltip
          formatter={(value, name) => [
            `${value}%`,
            name === "saiv" ? "SAIV" : "Mention rate",
          ]}
          labelStyle={{ color: "var(--color-foreground, #111827)", fontWeight: 600 }}
          contentStyle={{
            borderRadius: 8,
            border: "1px solid rgba(0,0,0,0.08)",
            fontSize: 12,
          }}
        />
        <Bar dataKey="saiv" fill="#7c3aed" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
