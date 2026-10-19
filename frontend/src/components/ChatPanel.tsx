import { useState } from "react";
import { api } from "../api";

interface Msg { role: "user" | "bot"; text: string }

export default function ChatPanel() {
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "bot", text: 'Try: "how many intrusions in the last hour?" or "list critical events today"' },
  ]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    const text = q.trim();
    if (!text) return;
    setMsgs((m) => [...m, { role: "user", text }]);
    setQ(""); setBusy(true);
    try {
      const r = await api.chat(text);
      setMsgs((m) => [...m, { role: "bot", text: r.answer }]);
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "bot", text: `(error: ${e.message || e})` }]);
    } finally { setBusy(false); }
  };
  return (
    <div className="rounded-xl border border-edge bg-panel p-4 space-y-2 flex flex-col h-80">
      <h3 className="text-sm uppercase tracking-widest text-slate-400">
        Ask your cameras
      </h3>
      <div className="flex-1 overflow-y-auto space-y-2 text-sm">
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "user"
            ? "text-slate-100 bg-edge/60 rounded px-2 py-1 ml-6"
            : "text-slate-300 bg-base/40 rounded px-2 py-1 mr-6"}>
            {m.text}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={busy}
          className="flex-1 bg-base border border-edge rounded px-2 py-1 text-sm"
          placeholder="Ask about events…"
        />
        <button onClick={send} disabled={busy}
                className="px-3 py-1 bg-accent/80 hover:bg-accent text-black rounded text-sm font-medium disabled:opacity-50">
          {busy ? "..." : "Ask"}
        </button>
      </div>
    </div>
  );
}
