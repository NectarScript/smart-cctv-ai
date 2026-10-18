import { useEffect, useState } from "react";
import { api, Camera, EventRow, Health } from "./api";
import CameraTile from "./components/CameraTile";
import EventList from "./components/EventList";
import StatsPanel from "./components/StatsPanel";
import SearchPanel from "./components/SearchPanel";
import ChatPanel from "./components/ChatPanel";

function Badge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${
      ok ? "bg-emerald-500/15 text-emerald-300" : "bg-slate-500/15 text-slate-400"
    }`}>
      {ok ? "●" : "○"} {label}
    </span>
  );
}

type Tab = "live" | "analytics";

export default function App() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [privacy, setPrivacy] = useState(false);
  const [tab, setTab] = useState<Tab>("live");

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const [cams, evs, h, p] = await Promise.all([
          api.cameras(), api.events(50), api.health().catch(() => null),
          api.privacyGet().catch(() => ({ enabled: false })),
        ]);
        if (cancelled) return;
        setCameras(cams);
        setEvents(evs);
        setHealth(h);
        setPrivacy(p.enabled);
        setError(null);
      } catch (e: any) {
        if (!cancelled) setError(e.message || String(e));
      }
    };
    tick();
    const t = setInterval(tick, 2000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  const togglePrivacy = async () => {
    try {
      const r = await api.privacySet(!privacy);
      setPrivacy(r.enabled);
    } catch (e: any) {
      setError(e.message || String(e));
    }
  };

  return (
    <div className="min-h-full flex flex-col">
      <header className="border-b border-edge bg-panel px-6 py-3 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-accent" />
          <h1 className="text-lg font-semibold tracking-wide">Smart CCTV AI</h1>
          <span className="text-xs text-slate-400">v0.3 · M3</span>
        </div>
        <nav className="flex items-center gap-2">
          <button
            onClick={() => setTab("live")}
            className={`text-xs px-3 py-1 rounded ${tab === "live" ? "bg-accent/80 text-black" : "bg-edge text-slate-300"}`}
          >Live</button>
          <button
            onClick={() => setTab("analytics")}
            className={`text-xs px-3 py-1 rounded ${tab === "analytics" ? "bg-accent/80 text-black" : "bg-edge text-slate-300"}`}
          >Analytics</button>
          <button
            onClick={togglePrivacy}
            className={`text-xs px-3 py-1 rounded ${privacy ? "bg-warn/80 text-black" : "bg-edge text-slate-300"}`}
            title="Blur faces on live view and recordings"
          >Privacy {privacy ? "ON" : "OFF"}</button>
        </nav>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span>{cameras.length} cam{cameras.length === 1 ? "" : "s"}</span>
          {health && (
            <>
              <Badge label="pose" ok={!!health.pose} />
              <Badge label="rec" ok={!!health.recorder} />
              <Badge label="tg" ok={!!health.telegram} />
              <Badge label="vlm" ok={!!health.vlm} />
            </>
          )}
          {error && <span className="ml-2 text-bad">{error}</span>}
        </div>
      </header>

      {tab === "live" ? (
        <main className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4">
          <section className="lg:col-span-2 space-y-4">
            <h2 className="text-sm uppercase tracking-widest text-slate-400">Live</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {cameras.length === 0 ? (
                <div className="rounded-xl border border-edge bg-panel p-10 text-center text-slate-400">
                  No cameras configured. Edit <code>config.yaml</code>.
                </div>
              ) : (
                cameras.map((c) => <CameraTile key={c.id} camera={c} />)
              )}
            </div>
            <ChatPanel />
          </section>
          <section className="space-y-4">
            <h2 className="text-sm uppercase tracking-widest text-slate-400">Events</h2>
            <EventList events={events} />
          </section>
        </main>
      ) : (
        <main className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 p-4">
          <StatsPanel />
          <SearchPanel />
        </main>
      )}
    </div>
  );
}
