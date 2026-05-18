import { useEffect, useState } from "react";
import { ProviderHintChip } from "../../components/studio/ProviderHintChip";
import { Projects } from "../../lib/api";

export function ExportTab({ projectId, providers, options }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    Projects.export(projectId).then(setData);
  }, [projectId]);
  if (!data) return <div className="text-[#A1A1AA] text-sm">Loading export…</div>;
  const c = options?.costs?.export;

  return (
    <div className="space-y-4" data-testid="export-view">
      <ProviderHintChip
        providers={providers}
        modality="export"
        action="export"
        credits={c ? `~${c} credits per final export` : null}
      />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 es-card p-4">
          <div className="aspect-video bg-black rounded-md border border-white/10 overflow-hidden mb-4 relative">
            {data.ready ? (
              <video
                src={data.final_video_url}
                controls
                className="w-full h-full"
                data-testid="final-video"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-center text-[#A1A1AA] text-sm">
                Approve at least one segment to preview the stitched final cut.
              </div>
            )}
          </div>
          <h3 className="font-display text-xl font-bold mb-2">Final Cut</h3>
          <p className="text-sm text-[#A1A1AA]">
            {data.generation_mode === "real"
              ? "FFmpeg stitched the approved local video segments into this export."
              : "A mocked stitched output of all approved segments. Enable the guarded FFmpeg export worker to render a real local MP4."}
          </p>
          {data.ready && (
            <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-mono uppercase tracking-widest text-[#A1A1AA]">
              <span>mode · {data.generation_mode || "mock"}</span>
              <span>ffmpeg · {data.ffmpeg_available ? "available" : "missing"}</span>
            </div>
          )}
        </div>
        <div className="es-card p-4" data-testid="approved-list">
          <div className="flex items-center justify-between mb-3">
            <h4 className="es-label">Approved timeline</h4>
            <span className="font-mono text-xs text-[#A1A1AA]">
              {data.total_duration_seconds}s
            </span>
          </div>
          {data.approved_segments.length === 0 ? (
            <p className="text-xs text-[#A1A1AA]">Nothing approved yet.</p>
          ) : (
            <ul className="space-y-2">
              {data.approved_segments.map((seg, i) => (
                <li
                  key={seg.segment_id}
                  className="flex items-center justify-between text-sm py-2 border-b border-white/5 last:border-0"
                >
                  <div>
                    <div className="font-mono text-[10px] uppercase text-[#A1A1AA]">
                      #{String(i + 1).padStart(2, "0")}
                    </div>
                    <div className="text-white">{seg.scene_title}</div>
                  </div>
                  <span className="font-mono text-xs text-[#34C759]">
                    +{seg.duration}s
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
