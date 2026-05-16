import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, X, RefreshCw, Trash2, Link2 } from "lucide-react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Textarea } from "../ui/textarea";
import { apiErrorMessage, Segments } from "../../lib/api";

export function SegmentCard({ segment, index, parent, dragHandle, reload }) {
  const [busy, setBusy] = useState(false);
  const [continuity, setContinuity] = useState(segment.continuity_prompt || "");
  const [saveState, setSaveState] = useState("idle"); // idle | saving | saved | error
  useEffect(() => {
    setContinuity(segment.continuity_prompt || "");
  }, [segment.continuity_prompt]);

  const persistContinuity = async () => {
    if ((continuity || "").trim() === (segment.continuity_prompt || "").trim()) return;
    setSaveState("saving");
    try {
      await Segments.update(segment.id, { continuity_prompt: continuity });
      setSaveState("saved");
      setTimeout(() => setSaveState((s) => (s === "saved" ? "idle" : s)), 1500);
    } catch {
      setSaveState("error");
    }
  };

  const setStatus = async (status) => {
    setBusy(true);
    try {
      await Segments.setStatus(segment.id, status);
      toast.success(`Segment ${status}`);
      reload();
    } finally {
      setBusy(false);
    }
  };
  const regen = async () => {
    setBusy(true);
    try {
      await Segments.regenerate(segment.id);
      toast.success("Regenerated");
      reload();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Regen failed (mock)"));
    } finally {
      setBusy(false);
    }
  };
  const removeSeg = async () => {
    setBusy(true);
    try {
      await Segments.remove(segment.id);
      toast.success("Segment deleted");
      reload();
    } finally {
      setBusy(false);
    }
  };

  const statusColor =
    segment.status === "approved"
      ? "border-[#34C759] text-[#34C759]"
      : segment.status === "rejected"
        ? "border-[#FF3B30] text-[#FF3B30]"
        : "border-white/20 text-[#A1A1AA]";

  const start = segment.start_second ?? index * 5;
  const dur = segment.duration ?? 5;
  const mode = segment.expand_mode || (index === 0 ? "initial" : "expand");

  return (
    <div className="es-card p-3" data-testid={`segment-${segment.id}`}>
      <div className="aspect-video bg-black rounded-md overflow-hidden mb-3 border border-white/10 relative">
        <video src={segment.video_url} controls className="w-full h-full" muted />
        {dragHandle && (
          <div className="absolute top-1 left-1 bg-black/70 rounded backdrop-blur">
            {dragHandle}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[10px] uppercase tracking-widest text-[#A1A1AA]">
          #{String((segment.order ?? index) + 1).padStart(2, "0")} · {mode}
        </span>
        <Badge variant="outline" className={`font-mono text-[10px] ${statusColor}`}>
          {segment.status}
        </Badge>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] mb-3 font-mono">
        <dt className="text-[#A1A1AA]">Start</dt>
        <dd className="text-white text-right" data-testid={`segment-start-${segment.id}`}>
          {start}s
        </dd>
        <dt className="text-[#A1A1AA]">Duration</dt>
        <dd
          className="text-white text-right"
          data-testid={`segment-duration-${segment.id}`}
        >
          {dur}s
        </dd>
        <dt className="text-[#A1A1AA] flex items-center gap-1">
          <Link2 className="w-3 h-3" /> Parent
        </dt>
        <dd
          className="text-white text-right truncate"
          data-testid={`segment-parent-${segment.id}`}
          title={segment.parent_segment_id || "—"}
        >
          {parent
            ? `#${String((parent.order ?? 0) + 1).padStart(2, "0")}`
            : segment.parent_segment_id
              ? segment.parent_segment_id.slice(0, 6)
              : "—"}
        </dd>
      </dl>

      {segment.continuity_prompt !== undefined && (
        <div className="mb-3" data-testid={`continuity-edit-${segment.id}`}>
          <label className="es-label flex items-center justify-between mb-1">
            <span>Continuity prompt</span>
            <span
              className="font-mono normal-case tracking-normal"
              data-testid={`continuity-state-${segment.id}`}
              style={{
                color:
                  saveState === "saving"
                    ? "#A1A1AA"
                    : saveState === "saved"
                      ? "#34C759"
                      : saveState === "error"
                        ? "#FF3B30"
                        : "#52525B",
              }}
            >
              {saveState === "saving"
                ? "Saving…"
                : saveState === "saved"
                  ? "Saved"
                  : saveState === "error"
                    ? "Failed to save"
                    : ""}
            </span>
          </label>
          <Textarea
            value={continuity}
            onChange={(e) => setContinuity(e.target.value)}
            onBlur={persistContinuity}
            data-testid={`continuity-input-${segment.id}`}
            placeholder="↳ Continue smoothly from the previous clip…"
            className="bg-[#0A0A0A] border-white/10 text-white text-xs min-h-[52px]"
          />
        </div>
      )}

      <div className="grid grid-cols-4 gap-1.5">
        <Button
          size="sm"
          disabled={busy}
          onClick={() => setStatus("approved")}
          data-testid={`approve-${segment.id}`}
          className="bg-[#34C759]/20 hover:bg-[#34C759]/30 text-[#34C759] border border-[#34C759]/30 h-8"
        >
          <Check className="w-3.5 h-3.5" />
        </Button>
        <Button
          size="sm"
          disabled={busy}
          onClick={() => setStatus("rejected")}
          data-testid={`reject-${segment.id}`}
          className="bg-[#FF3B30]/15 hover:bg-[#FF3B30]/25 text-[#FF3B30] border border-[#FF3B30]/30 h-8"
        >
          <X className="w-3.5 h-3.5" />
        </Button>
        <Button
          size="sm"
          disabled={busy}
          onClick={regen}
          variant="outline"
          data-testid={`regen-${segment.id}`}
          className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white h-8"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </Button>
        <Button
          size="sm"
          disabled={busy}
          onClick={removeSeg}
          variant="outline"
          data-testid={`delete-segment-${segment.id}`}
          className="border-white/15 bg-transparent text-[#A1A1AA] hover:bg-[#FF3B30]/15 hover:text-[#FF3B30] hover:border-[#FF3B30]/30 h-8"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}
