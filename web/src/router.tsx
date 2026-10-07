import { useEffect, useState, type AnchorHTMLAttributes, type MouseEvent } from "react";

/** Minimal client-side routing: the server already returns index.html for every page. */
export function usePath(): string {
  const [path, setPath] = useState(() => normalize(window.location.pathname));
  useEffect(() => {
    const onPop = () => setPath(normalize(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  return path;
}

export function navigate(to: string) {
  if (to === window.location.pathname) return;
  window.history.pushState(null, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo({ top: 0 });
}

export function Link({ href, onClick, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const handle = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    // Let the browser handle new-tab clicks and external links.
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (!href.startsWith("/")) return;
    e.preventDefault();
    navigate(href);
  };
  return <a href={href} onClick={handle} {...rest} />;
}

function normalize(p: string): string {
  return p.length > 1 ? p.replace(/\/+$/, "") : p;
}
