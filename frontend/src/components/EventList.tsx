import { EventRow, Severity } from "../api";

const sevColor: Record<Severity, string> = {
  normal: "bg-slate-500/20 text-slate-300",
  suspicious: "bg-warn/20 text-warn",
  critical: "bg-bad/20 text-bad",
};

function fmt(ts: string) {
  try { return new Date(ts).toLocaleTimeString(); } catch { return ts; }
}

export default function EventList({ events }: { events: EventRow[] }) {
  if (events.length === 0) {
    return (
      <div className="rounded-xl border border-edge bg-panel p-6 text-center text-slate-400 text-sm">
        No events yet.
      </div>
    );
  }
  return (
    <ul className="space-y-2 max-h-[calc(100vh-10rem)] overflow-y-auto pr-1">
      {events.map((e) => (
        <li key={e.id} className="rounded-lg border border-edge bg-panel p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${sevColor[e.severity]}`}>
                {e.severity}
              </span>
              <span className="font-medium">{e.type}</span>
            </div>
            <span className="text-xs text-slate-400">{fmt(e.start_ts)}</span>
          </div>
          <div className="mt-1 text-xs text-slate-400">
            cam: <span className="text-slate-200">{e.camera_id}</span>
            {e.zone && <> · zone: <span className="text-slate-200">{e.zone}</span></>}
            {e.track_ids.length > 0 && (
              <> · tracks: <span className="text-slate-200">{e.track_ids.join(",")}</span></>
            )}
          </div>
          {e.snapshot && (
            <img
              src={`/events/${e.id}/snapshot`}
              alt={`event ${e.id}`}
              className="mt-2 rounded-md border border-edge max-h-40 object-contain"
            />
          )}
        </li>
      ))}
    </ul>
  );
}
