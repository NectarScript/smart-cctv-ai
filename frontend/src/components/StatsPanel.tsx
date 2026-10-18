import { useEffect, useState } from "react";
import { api, Stats } from "../api";

function Bar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="text-xs">
      <div className="flex justify-between text-slate-400">
        <span className="truncate">{label}</span>
        <span>{value}</span>
      </div>
      <div className="h-1.5 bg-edge rounded overflow-hidden">
        <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function StatsPanel() {
  const [s, setS] = useState<Stats | null>(null);
  useEffect(() => {
    const tick = () => api.stats(24).then(setS).catch(() => {});
    tick();
    const t = setInterval(tick, 5000);
    return () => clearInterval(t);
  }, []);
  if (!s) return null;
  const maxType = Math.max(1, ...s.by_type.map((x) => x.count));
  const maxCam = Math.max(1, ...s.by_camera.map((x) => x.count));
  const maxHour = Math.max(1, ...s.by_hour.map((x) => x.count));
  return (
    <div className="rounded-xl border border-edge bg-panel p-4 space-y-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm uppercase tracking-widest text-slate-400">
          Last 24h
        </h3>
        <span className="text-2xl font-semibold">{s.total}</span>
      </div>
      <div className="space-y-2">
        <div className="text-xs text-slate-500">By type</div>
        {s.by_type.map((t) => (
          <Bar key={t.type} label={t.type} value={t.count} max={maxType} />
        ))}
      </div>
      <div className="space-y-2">
        <div className="text-xs text-slate-500">By camera</div>
        {s.by_camera.map((c) => (
          <Bar key={c.camera_id} label={c.camera_id} value={c.count} max={maxCam} />
        ))}
      </div>
      <div className="space-y-1">
        <div className="text-xs text-slate-500">By hour</div>
        <div className="flex items-end gap-0.5 h-16">
          {s.by_hour.slice(-24).map((h) => (
            <div
              key={h.hour}
              title={`${h.hour} · ${h.count}`}
              className="flex-1 bg-accent/60 rounded-t"
              style={{ height: `${(h.count / maxHour) * 100}%` }}
            />
          ))}
        </div>
      </div>
      <div className="flex gap-2 text-xs">
        {s.by_severity.map((sv) => (
          <span key={sv.severity} className="px-2 py-1 rounded bg-edge">
            {sv.severity}: <b>{sv.count}</b>
          </span>
        ))}
      </div>
    </div>
  );
}
