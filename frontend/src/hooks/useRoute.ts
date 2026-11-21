import { useEffect, useState } from "react";

export type Route = { page: "new" } | { page: "meeting"; id: string };

export function parseHash(hash: string): Route {
  const m = hash.match(/^#\/meeting\/([\w-]+)/);
  return m ? { page: "meeting", id: m[1] } : { page: "new" };
}

export const go = (path: string) => { window.location.hash = path; };

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}
