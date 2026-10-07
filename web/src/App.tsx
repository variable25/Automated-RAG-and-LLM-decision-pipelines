import { useEffect } from "react";
import { useApi } from "./api";
import { Link, usePath } from "./router";
import { CardsSkeleton, ChartSkeleton } from "./Skeleton";
import type { Summary } from "./types";
import Frontier from "./views/Frontier";
import { Privacy, REPO_URL, Terms } from "./views/Legal";
import NotFound from "./views/NotFound";
import Overview from "./views/Overview";
import Questions from "./views/Questions";

const TABS = [
  { href: "/", label: "Overview", title: "Overview" },
  { href: "/frontier", label: "Accuracy vs. retrieval", title: "Accuracy vs. retrieval" },
  { href: "/questions", label: "Questions", title: "Questions" },
];
const OTHER_TITLES: Record<string, string> = { "/privacy": "Privacy policy", "/terms": "Terms of use" };

export default function App() {
  const path = usePath();
  const summary = useApi<Summary>("/api/summary");
  const tab = TABS.find((t) => t.href === path);
  const title = tab?.title ?? OTHER_TITLES[path] ?? "Page not found";

  useEffect(() => {
    document.title = path === "/" ? "RAG Decision Explorer" : `${title} · RAG Decision Explorer`;
  }, [path, title]);

  return (
    <div className="shell">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="header">
        <Link href="/" className="brand">
          <span className="logo" aria-hidden="true" />
          RAG Decision Explorer
        </Link>
        <nav className="tabs" aria-label="Dashboard">
          {TABS.map((t) => (
            <Link key={t.href} href={t.href} aria-current={t.href === path ? "page" : undefined}>
              {t.label}
            </Link>
          ))}
        </nav>
      </header>

      <main id="main" key={path} className="page">
        {tab && summary.error && <p className="error">Could not load results: {summary.error}</p>}
        {tab && !summary.data && !summary.error && path !== "/questions" && (
          <>
            <CardsSkeleton />
            <ChartSkeleton />
          </>
        )}
        {path === "/" && summary.data && <Overview summary={summary.data} />}
        {path === "/frontier" && summary.data && <Frontier summary={summary.data} />}
        {path === "/questions" && <Questions />}
        {path === "/privacy" && <Privacy />}
        {path === "/terms" && <Terms />}
        {!tab && !OTHER_TITLES[path] && <NotFound path={path} />}
      </main>

      <footer className="footer">
        <p className="muted small">
          Research demo on 1,000 PopQA questions. Answers are AI-generated and often wrong. Built with Meta Llama 3.
        </p>
        <nav aria-label="Legal and source" className="footer-links">
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <a href={REPO_URL}>GitHub</a>
        </nav>
      </footer>
    </div>
  );
}
