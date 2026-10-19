import { Camera } from "../api";

export default function CameraTile({ camera }: { camera: Camera }) {
  const dot = camera.alive ? "bg-emerald-400" : "bg-bad";
  return (
    <div className="rounded-xl overflow-hidden border border-edge bg-panel">
      <div className="flex items-center justify-between px-3 py-2 text-sm">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${dot}`} />
          <span className="font-medium">{camera.name || camera.id}</span>
        </div>
        <span className="text-xs text-slate-400">{camera.fps.toFixed(1)} fps</span>
      </div>
      <div className="aspect-video bg-black">
        <img
          src={`/stream/${camera.id}`}
          alt={camera.id}
          className="w-full h-full object-contain"
        />
      </div>
    </div>
  );
}
