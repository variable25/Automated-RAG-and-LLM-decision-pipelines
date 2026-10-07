import { Fragment, useMemo, useState } from "react";
import { useApi } from "../api";
import { TableSkeleton } from "../Skeleton";
import { MODE_LABEL, num, pct } from "../format";
import { MODES, type Mode, type ModeAnswer, type Question, type Verdict } from "../types";

const PAGE_SIZE = 25;
const VERDICTS: Verdict[] = ["correct (both)", "lenient only", "abstained", "wrong"];

const FOCUS = {
  all: { label: "All questions", test: () => true },
  scoring: {
    label: "Strict and lenient scoring disagree",
    test: (q: Question) => MODES.some((m) => q[m].verdict === "lenient only"),
  },
  helped: {
    label: "Retrieval fixed the answer",
    test: (q: Question) => !q.never.correct && q.always.correct,
  },
  hurt: {
    label: "Retrieval broke the answer",
    test: (q: Question) => q.never.correct && !q.always.correct,
  },
  adaptiveMissed: {
    label: "Adaptive skipped retrieval and was wrong",
    test: (q: Question) => !q.adaptive.retrieved && !q.adaptive.correct && q.always.correct,
  },
} satisfies Record<string, { label: string; test: (q: Question) => boolean }>;
type Focus = keyof typeof FOCUS;

export default function Questions() {
  const { data, error } = useApi<Question[]>("/api/questions");
  const [search, setSearch] = useState("");
  const [split, setSplit] = useState<"all" | "test" | "tune">("test");
  const [prop, setProp] = useState("all");
  const [focus, setFocus] = useState<Focus>("all");
  const [mode, setMode] = useState<Mode>("adaptive");
  const [verdict, setVerdict] = useState<Verdict | "any">("any");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState<number | null>(null);

  const props = useMemo(() => [...new Set(data?.map((q) => q.prop))].sort(), [data]);
  const rows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (data ?? []).filter(
      (q) =>
        (split === "all" || q.split === split) &&
        (prop === "all" || q.prop === prop) &&
        (verdict === "any" || q[mode].verdict === verdict) &&
        FOCUS[focus].test(q) &&
        (!needle ||
          q.question.toLowerCase().includes(needle) ||
          q.answers.some((a) => a.toLowerCase().includes(needle)) ||
          MODES.some((m) => q[m].answer.toLowerCase().includes(needle))),
    );
  }, [data, search, split, prop, focus, mode, verdict]);

  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const shown = rows.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE);

  // Any filter change goes back to page 1 and collapses the open row.
  function update<T>(set: (v: T) => void, v: T) {
    set(v);
    setPage(0);
    setOpen(null);
  }

  if (error) return <p className="error">{error}</p>;
  if (!data) return <TableSkeleton />;

  return (
    <section className="panel">
      <div className="filters">
        <label className="grow">
          Search
          <input
            type="search"
            placeholder="Question or answer text"
            value={search}
            onChange={(e) => update(setSearch, e.target.value)}
          />
        </label>
        <label>
          Split
          <select value={split} onChange={(e) => update(setSplit, e.target.value as typeof split)}>
            <option value="test">Test</option>
            <option value="tune">Tune</option>
            <option value="all">All</option>
          </select>
        </label>
        <label>
          Relation
          <select value={prop} onChange={(e) => update(setProp, e.target.value)}>
            <option value="all">All</option>
            {props.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="wide">
          Show
          <select value={focus} onChange={(e) => update(setFocus, e.target.value as Focus)}>
            {Object.entries(FOCUS).map(([k, f]) => (
              <option key={k} value={k}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label className="wide">
          Result
          <span className="pair">
            <select value={verdict} onChange={(e) => update(setVerdict, e.target.value as Verdict | "any")}>
              <option value="any">Any</option>
              {VERDICTS.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
            <select value={mode} onChange={(e) => update(setMode, e.target.value as Mode)} aria-label="for policy">
              {MODES.map((m) => (
                <option key={m} value={m}>
                  for {MODE_LABEL[m]}
                </option>
              ))}
            </select>
          </span>
        </label>
      </div>

      <p className="muted small">
        {num(rows.length)} questions. Click a row for confidence, retrieval, and strict vs. lenient scoring.
      </p>

      <div className="table-wrap">
        <table className="qtable">
          <thead>
            <tr>
              <th>Question</th>
              <th>Accepted answers</th>
              {MODES.map((m) => (
                <th key={m}>{MODE_LABEL[m]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((q) => (
              <Fragment key={q.question_id}>
                <tr
                  className={open === q.question_id ? "row open" : "row"}
                  onClick={() => setOpen(open === q.question_id ? null : q.question_id)}
                >
                  <td>
                    <div className="qtext">{q.question}</div>
                    <div className="muted small">
                      {q.prop} · {num(q.s_pop)} views/month
                    </div>
                  </td>
                  <td className="small" data-label="Accepted">
                    {q.answers.slice(0, 3).join(", ")}
                    {q.answers.length > 3 && "…"}
                  </td>
                  {MODES.map((m) => (
                    <td key={m} data-label={MODE_LABEL[m]}>
                      <div className="answer">{q[m].answer || <span className="muted">(empty)</span>}</div>
                      <div className="marks">
                        <Badge v={q[m].verdict} />
                        {q[m].retrieved && <span className="tag">retrieved</span>}
                      </div>
                    </td>
                  ))}
                </tr>
                {open === q.question_id && (
                  <tr className="detail">
                    <td colSpan={5}>
                      <Detail q={q} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <div className="pager">
        <button disabled={current === 0} onClick={() => setPage(current - 1)}>
          Previous
        </button>
        <span className="muted">
          Page {current + 1} of {pages}
        </span>
        <button disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
          Next
        </button>
      </div>
    </section>
  );
}

function Badge({ v }: { v: Verdict }) {
  return <span className={`badge ${v.split(" ")[0]}`}>{v}</span>;
}

function Detail({ q }: { q: Question }) {
  return (
    <div className="detail-body">
      <p className="small">
        <strong>All accepted answers:</strong> {q.answers.join(", ")}
      </p>
      <div className="table-wrap">
        <table className="mini">
          <thead>
            <tr>
              <th>Policy</th>
              <th>Answer</th>
              <th>Confidence</th>
              <th>Retrieved</th>
              <th>Strict</th>
              <th>Lenient</th>
            </tr>
          </thead>
          <tbody>
            {MODES.map((m) => (
              <DetailRow key={m} mode={m} a={q[m]} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Strict: an accepted answer appears word for word. Lenient (the headline metric) also accepts partial answers,
        reordered words, and near-identical spellings.
      </p>
    </div>
  );
}

function DetailRow({ mode, a }: { mode: Mode; a: ModeAnswer }) {
  const mark = (ok: boolean) => <span className={ok ? "ok" : "no"}>{ok ? "✓ correct" : "✗ wrong"}</span>;
  return (
    <tr>
      <td>{MODE_LABEL[mode]}</td>
      <td>{a.answer}</td>
      <td>{pct(a.confidence)}</td>
      <td>{a.retrieved ? "yes" : "no"}</td>
      <td>{mark(a.correct_strict)}</td>
      <td>{mark(a.correct)}</td>
    </tr>
  );
}
