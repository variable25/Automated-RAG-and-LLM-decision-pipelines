import { Link } from "../router";

export default function NotFound({ path }: { path: string }) {
  return (
    <section className="notfound">
      <p className="eyebrow">Error 404</p>
      <h1>Nothing was retrieved for this page.</h1>
      <p className="muted">
        A closed-book model would confidently invent an answer for <code>{path}</code>. We'd rather say "I don't
        know".
      </p>
      <div className="cta-row">
        <Link href="/" className="btn primary">
          Back to the overview
        </Link>
        <Link href="/questions" className="btn">
          Browse the questions
        </Link>
      </div>
    </section>
  );
}
