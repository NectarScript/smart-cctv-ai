export type Severity = "normal" | "suspicious" | "critical";

export interface Camera {
  id: string;
  name: string;
  alive: boolean;
  fps: number;
}

export interface EventRow {
  id: number;
  camera_id: string;
  type: string;
  severity: Severity;
  track_ids: number[];
  zone: string | null;
  start_ts: string;
  end_ts: string;
  snapshot: string | null;
  clip: string | null;
  vlm_verdict: string | null;
  vlm_summary: string | null;
  meta: Record<string, unknown>;
}

const json = <T,>(r: Response): Promise<T> => {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
};

export interface Health {
  ok: boolean;
  cameras?: Record<string, boolean>;
  telegram?: boolean;
  vlm?: boolean;
  recorder?: boolean;
  pose?: boolean;
}

export interface Stats {
  window_hours: number;
  total: number;
  by_hour: { hour: string; count: number }[];
  by_type: { type: string; count: number }[];
  by_camera: { camera_id: string; count: number }[];
  by_severity: { severity: string; count: number }[];
}

export interface SearchHit {
  id: number;
  type: string;
  severity: Severity;
  camera_id: string;
  zone: string | null;
  start_ts: string;
  snapshot_url: string;
  clip_url: string | null;
  score: number;
}

export interface ChatReply {
  answer: string;
  tool: string | null;
  args: Record<string, unknown>;
  result: unknown;
}

export const api = {
  cameras: () => fetch("/cameras").then((r) => json<Camera[]>(r)),
  events: (limit = 50) =>
    fetch(`/events?limit=${limit}`).then((r) => json<EventRow[]>(r)),
  health: () => fetch("/healthz").then((r) => json<Health>(r)),
  stats: (hours = 24) =>
    fetch(`/stats?hours=${hours}`).then((r) => json<Stats>(r)),
  search: (q: string, top_k = 10) =>
    fetch(`/search?q=${encodeURIComponent(q)}&top_k=${top_k}`)
      .then((r) => json<{ query: string; hits: SearchHit[] }>(r)),
  chat: (question: string) =>
    fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }).then((r) => json<ChatReply>(r)),
  privacyGet: () => fetch("/privacy").then((r) => json<{ enabled: boolean }>(r)),
  privacySet: (enabled: boolean) =>
    fetch("/privacy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    }).then((r) => json<{ enabled: boolean }>(r)),
};
