import { useEffect, useState } from "react";
import { api, Camera, EventRow, Health } from "./api";
import CameraTile from "./components/CameraTile";
import EventList from "./components/EventList";

function Badge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${
      ok ? "bg-emerald-500/15 text-emerald-300" : "bg-slate-500/15 text-slate-400"
    }`}>
      {ok ? "●" : "○"} {label}
    </span>
  );
}

export default function App() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const [cams, evs, h] = await Promise.all([
          api.cameras(), api.events(50), api.health().catch(() => null),
        ]);
        if (cancelled) return;
        setCameras(cams);
        setEvents(evs);
        setHealth(h);
        setError(null);
      } catch (e: any) {
        if (!cancelled) setError(e.message || String(e));
      }
    };
    tick();
    const t = setInterval(tick, 2000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  return (
    <div className="min-h-full flex flex-col">
      <header className="border-b border-edge bg-panel px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-accent" />
          <h1 className="text-lg font-semibold tracking-wide">Smart CCTV AI</h1>
          <span className="text-xs text-slate-400">v0.1 · Milestone 1</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span>{cameras.length} camera{cameras.length === 1 ? "" : "s"}</span>
          {health && (
            <>
              <Badge label="pose" ok={!!health.pose} />
              <Badge label="recorder" ok={!!health.recorder} />
              <Badge label="telegram" ok={!!health.telegram} />
              <Badge label="vlm" ok={!!health.vlm} />
            </>
          )}
          {error && <span className="ml-3 text-bad">· {error}</span>}
        </div>
      </header>

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
        </section>

        <section className="space-y-4">
          <h2 className="text-sm uppercase tracking-widest text-slate-400">Events</h2>
          <EventList events={events} />
        </section>
      </main>
    </div>
  );
}
