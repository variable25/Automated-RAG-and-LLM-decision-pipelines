import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useApi } from "../api";
import { AXIS_TICK, compact, MODE_COLOR, MODE_LABEL, ms, num, pct, TOOLTIP } from "../format";
import { MODES, type PopularityBucket, type Split, type Summary } from "../types";

const SPLITS: { id: Split; label: string }[] = [
  { id: "test", label: "Test (500, held out)" },
  { id: "tune", label: "Tune (500)" },
  { id: "all", label: "All (1,000)" },
];

const METRICS = [
  { key: "accuracy", label: "Accuracy" },
  { key: "strict_accuracy", label: "Strict accuracy" },
  { key: "hallucination_rate", label: "Hallucinated" },
  { key: "abstain_rate", label: "Said \"I don't know\"" },
] as const;

export default function Overview({ summary }: { summary: Summary }) {
  const [split, setSplit] = useState<Split>("test");
  const runs = MODES.map((m) => summary.runs.find((r) => r.mode === m && r.split === split)!);
  const pop = useApi<PopularityBucket[]>(`/api/by-popularity?split=${split}`);

  const bars = METRICS.map((m) => ({
    metric: m.label,
    ...Object.fromEntries(runs.map((r) => [r.mode, r[m.key]])),
  }));

  return (
    <>
      <div className="toolbar">
        <span className="muted">Split</span>
        <div className="segmented">
          {SPLITS.map((s) => (
            <button key={s.id} aria-pressed={split === s.id} onClick={() => setSplit(s.id)}>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <section className="cards">
        {runs.map((r) => (
          <article key={r.mode} className="card" style={{ borderTopColor: MODE_COLOR[r.mode] }}>
            <h3>{MODE_LABEL[r.mode]}</h3>
            <div className="big">{pct(r.accuracy)}</div>
            <div className="muted">accuracy · strict {pct(r.strict_accuracy)}</div>
            <dl>
              <dt>Retrieves for</dt>
              <dd>{pct(r.retrieval_rate)}</dd>
              <dt>Hallucinated</dt>
              <dd>{pct(r.hallucination_rate)}</dd>
              <dt>Avg latency</dt>
              <dd>{ms(r.avg_latency_ms)}</dd>
            </dl>
            {r.mode === "adaptive" && (
              <p className="note">
                Retrieves when popularity &lt; {num(summary.pop_threshold)} views/month or confidence &lt;{" "}
                {summary.conf_threshold}
              </p>
            )}
          </article>
        ))}
      </section>

      <section className="panel">
        <h2>How the three policies compare</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={bars} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="metric" tick={AXIS_TICK} />
            <YAxis tickFormatter={(v: number) => pct(v, 0)} domain={[0, 1]} tick={AXIS_TICK} />
            <Tooltip formatter={(v) => pct(Number(v))} contentStyle={TOOLTIP} cursor={{ fill: "var(--hover)" }} />
            <Legend itemSorter={null} formatter={(m: string) => MODE_LABEL[m as keyof typeof MODE_LABEL]} />
            {MODES.map((m) => (
              <Bar key={m} dataKey={m} fill={MODE_COLOR[m]} radius={[3, 3, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </section>

      <section className="panel">
        <h2>Accuracy by how famous the subject is</h2>
        <p className="muted">
          Questions grouped into 10 buckets by the subject's monthly Wikipedia views. Looking things up helps most for
          obscure subjects; where the orange and blue lines overlap, adaptive retrieved just like always-retrieve.
        </p>
        {pop.error && <p className="error">{pop.error}</p>}
        {pop.data && (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={pop.data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis
                dataKey="bucket"
                tickFormatter={(b: number) => compact(pop.data![b].max)}
                tick={AXIS_TICK}
              />
              <YAxis tickFormatter={(v: number) => pct(v, 0)} domain={[0, 1]} tick={AXIS_TICK} />
              <Tooltip
                contentStyle={TOOLTIP}
                labelFormatter={(b) => {
                  const r = pop.data![Number(b)];
                  return `${num(r.min)}–${num(r.max)} views/month (${r.n} questions)`;
                }}
                formatter={(v, m) => [pct(Number(v)), MODE_LABEL[m as keyof typeof MODE_LABEL]]}
              />
              <Legend itemSorter={null} formatter={(m: string) => MODE_LABEL[m as keyof typeof MODE_LABEL]} />
              {MODES.map((m) => (
                <Line key={m} dataKey={m} stroke={MODE_COLOR[m]} strokeWidth={2} dot={{ r: 3 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
        <p className="muted small">X axis: upper edge of each bucket, in monthly page views.</p>
      </section>
    </>
  );
}
