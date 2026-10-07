/** Placeholders shaped like the real content, shown while API data loads. */

export function Block({ w = "100%", h = 14, r = 6 }: { w?: number | string; h?: number | string; r?: number }) {
  return <span className="skel" style={{ width: w, height: h, borderRadius: r }} aria-hidden="true" />;
}

export function CardsSkeleton({ count = 3 }: { count?: number }) {
  return (
    <section className="cards" aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <article key={i} className="card">
          <Block w="45%" h={14} />
          <Block w="55%" h={36} />
          <Block w="70%" h={12} />
          <div className="skel-lines">
            <Block h={12} />
            <Block h={12} />
            <Block h={12} />
          </div>
        </article>
      ))}
    </section>
  );
}

export function ChartSkeleton({ height = 300, title = true }: { height?: number; title?: boolean }) {
  return (
    <section className="panel" aria-busy="true" aria-label="Loading chart">
      {title && <Block w="40%" h={18} />}
      <div className="skel-chart" style={{ height }}>
        {[38, 62, 45, 80, 55, 70, 30, 66].map((pctH, i) => (
          <span key={i} className="skel" style={{ height: `${pctH}%` }} />
        ))}
      </div>
    </section>
  );
}

export function TableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <section className="panel" aria-busy="true" aria-label="Loading questions">
      <div className="skel-filters">
        <Block w="100%" h={34} />
        <Block w={120} h={34} />
        <Block w={120} h={34} />
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skel-row">
          <div>
            <Block w="85%" />
            <Block w="40%" h={11} />
          </div>
          <Block w="70%" />
          <Block w="60%" />
          <Block w="60%" />
          <Block w="60%" />
        </div>
      ))}
    </section>
  );
}
