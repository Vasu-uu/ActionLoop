import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { useRoute } from "./hooks/useRoute";
import { useTheme } from "./hooks/useTheme";
import { api } from "./lib/api";
import type { Dashboard, Health, MeetingSummary } from "./lib/types";
import { MeetingPage } from "./pages/MeetingPage";
import { NewMeetingPage } from "./pages/NewMeetingPage";

export default function App() {
  const route = useRoute();
  const { dark, toggle } = useTheme();
  const [health, setHealth] = useState<Health | null>(null);
  const [meetings, setMeetings] = useState<MeetingSummary[] | null>(null);
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [offline, setOffline] = useState(false);
  const [menu, setMenu] = useState(false);

  const refresh = useCallback(() => {
    api.meetings().then((m) => { setMeetings(m); setOffline(false); }).catch(() => setOffline(true));
    api.dashboard().then(setDash).catch(() => {});
  }, []);
  useEffect(() => { api.health().then(setHealth).catch(() => setOffline(true)); refresh(); }, [refresh]);
  useEffect(() => setMenu(false), [route]);

  const currentId = route.page === "meeting" ? route.id : undefined;
  return (
    <div className="flex min-h-screen">
      <div className={`fixed inset-y-0 left-0 z-30 w-72 transform transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${menu ? "translate-x-0" : "-translate-x-full"}`}>
        <Sidebar meetings={meetings} dashboard={dash} health={health} currentId={currentId} loading={meetings === null && !offline}
          onChanged={refresh} dark={dark} toggleTheme={toggle} />
      </div>
      {menu && <div className="fixed inset-0 z-20 bg-black/40 lg:hidden" onClick={() => setMenu(false)} aria-hidden />}
      <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
        <button className="btn-ghost mb-3 lg:hidden" onClick={() => setMenu(true)} aria-label="Open menu">☰ Menu</button>
        {offline && (
          <div role="alert" className="mb-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
            Can’t reach the ActionLoop backend. Start it with <code>make dev</code> (or <code>scripts/dev.ps1</code>) and refresh.
          </div>
        )}
        {route.page === "meeting" ? <MeetingPage id={route.id} onChanged={refresh} /> : <NewMeetingPage health={health} onCreated={refresh} />}
      </main>
    </div>
  );
}
