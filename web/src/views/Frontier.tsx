import { useMemo } from "react";
import {
  CartesianGrid, LabelList, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { useApi } from "../api";
import { useMediaQuery } from "../media";
import { CardsSkeleton, ChartSkeleton } from "../Skeleton";
import { AXIS_TICK, MODE_COLOR, MODE_LABEL, num, pct, TOOLTIP } from "../format";
import type { Frontier as FrontierData, Summary } from "../types";

const LABEL_POS = { never: "right", adaptive: "bottom", always: "top" } as const;

interface Point {
  retrieval_rate: number;
  accuracy: number;
  label: string;
}

export default function Frontier({ summary }: { summary: Summary }) {
  const { data, error } = useApi<FrontierData>("/api/frontier");
  const narrow = useMediaQuery("(max-width: 640px)");

  const series = useMemo(() => {
    if (!data) return undefined;
    const setting = (p: { pop_threshold: number; conf_threshold: number }) =>
      `popularity < ${num(p.pop_threshold)}, confidence < ${p.conf_threshold}`;
    const pareto = [...data.pareto]
      .sort((a, b) => a.retrieval_rate - b.retrieval_rate)
      .map((p) => ({ ...p, label: setting(p) }));
    return {
      grid: data.grid.map((p) => ({ ...p, label: setting(p) })),
      pareto,
      modes: data.modes.map((m) => ({ ...m, label: MODE_LABEL[m.mode] })),
      cheapest: cheapestWithin(pareto, 0.05),
    };
  }, [data]);

  if (error) return <p className="error">{error}</p>;
  if (!series)
    return (
      <>
        <ChartSkeleton height={420} />
        <CardsSkeleton count={2} />
      </>
    );
  const adaptive = series.modes.find((m) => m.mode === "adaptive")!;

  return (
    <>
      <section className="panel">
        <h2>Accuracy vs. how often we retrieve</h2>
        <p className="muted">
          Each grey dot is one adaptive threshold setting, scored on the 500 tune questions. Retrieving costs time
          (about 6× slower per question), so points further left are cheaper. The line joins the settings that no other
          setting beats on both axes.
        </p>
        <ResponsiveContainer width="100%" height={narrow ? 320 : 420}>
          <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: -8 }}>
            <CartesianGrid stroke="var(--grid)" />
            <XAxis
              type="number"
              dataKey="retrieval_rate"
              name="Retrieval rate"
              domain={[-0.03, 1.03]}
              ticks={[0, 0.25, 0.5, 0.75, 1]}
              tickFormatter={(v: number) => pct(v, 0)}
              tick={AXIS_TICK}
              label={{ value: "Questions that trigger retrieval", position: "insideBottom", offset: -8, fill: "var(--muted)", fontSize: 12 }}
            />
            <YAxis
              type="number"
              dataKey="accuracy"
              name="Accuracy"
              domain={[0.2, 0.75]}
              ticks={[0.2, 0.3, 0.4, 0.5, 0.6, 0.7]}
              tickFormatter={(v: number) => pct(v, 0)}
              tick={AXIS_TICK}
            />
            <ZAxis range={narrow ? [20, 20] : [36, 36]} />
            <Tooltip contentStyle={TOOLTIP} content={<PointTip />} cursor={{ strokeDasharray: "3 3" }} />
            <Legend verticalAlign="top" height={narrow ? 72 : 32} itemSorter={null} wrapperStyle={{ fontSize: narrow ? 12 : 14 }} />
            <Scatter name="Threshold setting" data={series.grid} fill="var(--dot)" isAnimationActive={false} />
            <Scatter
              name="Best trade-offs"
              data={series.pareto}
              fill="var(--accent)"
              line={{ stroke: "var(--accent)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
            {series.modes.map((m) => (
              <Scatter key={m.mode} name={m.label} data={[m]} fill={MODE_COLOR[m.mode]} shape={ModeMarker} isAnimationActive={false}>
                <LabelList dataKey="label" position={LABEL_POS[m.mode]} offset={12} fill="var(--text)" fontSize={12} />
              </Scatter>
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </section>

      <section className="cards">
        <article className="card" style={{ borderTopColor: MODE_COLOR.adaptive }}>
          <h3>Chosen setting</h3>
          <div className="big">{pct(adaptive.retrieval_rate)}</div>
          <div className="muted">retrieval at {pct(adaptive.accuracy)} accuracy (tune)</div>
          <p className="note">
            Fewest retrievals within 1 accuracy point of the best. Popularity &lt; {num(summary.pop_threshold)},
            confidence &lt; {summary.conf_threshold}.
          </p>
        </article>
        {series.cheapest && (
          <article className="card" style={{ borderTopColor: "var(--accent)" }}>
            <h3>Cheaper option</h3>
            <div className="big">{pct(series.cheapest.retrieval_rate)}</div>
            <div className="muted">retrieval at {pct(series.cheapest.accuracy)} accuracy (tune)</div>
            <p className="note">Cheapest setting within 5 points of the best: {series.cheapest.label}.</p>
          </article>
        )}
      </section>
    </>
  );
}

function cheapestWithin(points: Point[], tolerance: number): Point | undefined {
  const best = Math.max(...points.map((p) => p.accuracy));
  return points.find((p) => p.accuracy >= best - tolerance);
}

function ModeMarker({ cx, cy, fill }: { cx?: number; cy?: number; fill?: string }) {
  return <circle cx={cx} cy={cy} r={8} fill={fill} stroke="var(--surface)" strokeWidth={2} />;
}

function PointTip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div style={TOOLTIP} className="tip">
      <strong>{p.label}</strong>
      <div>Accuracy {pct(p.accuracy)}</div>
      <div>Retrieves for {pct(p.retrieval_rate)}</div>
    </div>
  );
}
