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

export const api = {
  cameras: () => fetch("/cameras").then((r) => json<Camera[]>(r)),
  events: (limit = 50) =>
    fetch(`/events?limit=${limit}`).then((r) => json<EventRow[]>(r)),
};
