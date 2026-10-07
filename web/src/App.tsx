import { useState } from "react";
import { useApi } from "./api";
import type { Summary } from "./types";
import Overview from "./views/Overview";
import Frontier from "./views/Frontier";
import Questions from "./views/Questions";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "frontier", label: "Accuracy vs. retrieval" },
  { id: "questions", label: "Questions" },
] as const;
type Tab = (typeof TABS)[number]["id"];

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const summary = useApi<Summary>("/api/summary");

  return (
    <div className="shell">
      <header className="header">
        <div>
          <h1>RAG Decision Explorer</h1>
          <p className="muted">
            When should an LLM look things up before answering? 1,000 PopQA questions, three retrieval policies.
            {summary.data && <span className="model"> {summary.data.model}</span>}
          </p>
        </div>
        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {summary.error && <p className="error">Could not load results: {summary.error}</p>}
        {summary.data && tab === "overview" && <Overview summary={summary.data} />}
        {summary.data && tab === "frontier" && <Frontier summary={summary.data} />}
        {tab === "questions" && <Questions />}
      </main>
    </div>
  );
}
