import { useState } from "react";
import { api, SearchHit } from "../api";

export default function SearchPanel() {
  const [q, setQ] = useState("person with backpack");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const go = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api.search(q, 10);
      setHits(r.hits);
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="rounded-xl border border-edge bg-panel p-4 space-y-3">
      <h3 className="text-sm uppercase tracking-widest text-slate-400">
        Search events (CLIP)
      </h3>
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go()}
          className="flex-1 bg-base border border-edge rounded px-2 py-1 text-sm"
          placeholder="red jacket near gate"
        />
        <button
          onClick={go}
          disabled={busy}
          className="px-3 py-1 bg-accent/80 hover:bg-accent text-black rounded text-sm font-medium disabled:opacity-50"
        >
          {busy ? "..." : "Search"}
        </button>
      </div>
      {err && <div className="text-xs text-bad">{err}</div>}
      <div className="grid grid-cols-2 gap-2 max-h-72 overflow-y-auto">
        {hits.map((h) => (
          <a
            key={h.id}
            href={h.clip_url || h.snapshot_url}
            target="_blank" rel="noreferrer"
            className="block rounded border border-edge hover:border-accent overflow-hidden"
          >
            <img src={h.snapshot_url} alt={h.type}
                 className="w-full h-24 object-cover" />
            <div className="p-1 text-[10px] text-slate-400 flex justify-between">
              <span>{h.type}</span>
              <span>{h.score}</span>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
