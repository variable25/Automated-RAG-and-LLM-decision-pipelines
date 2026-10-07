import { useEffect, useState } from "react";

/** Fetch JSON from the FastAPI backend once per path. */
export function useApi<T>(path: string): { data?: T; error?: string } {
  const [state, setState] = useState<{ data?: T; error?: string }>({});
  useEffect(() => {
    let live = true;
    setState({});
    fetch(path)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status} ${r.statusText}`))))
      .then((data: T) => live && setState({ data }))
      .catch((e: Error) => live && setState({ error: e.message }));
    return () => {
      live = false;
    };
  }, [path]);
  return state;
}
