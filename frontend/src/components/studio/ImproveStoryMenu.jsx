import { useState } from "react";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Creative } from "../../lib/api";
import { withRealLLMToast } from "../../lib/llmToast";

const IMPROVE_OPTIONS = [
  { kind: "suspenseful", label: "Make more suspenseful" },
  { kind: "emotional", label: "Make more emotional" },
  { kind: "romantic", label: "Make more romantic" },
  { kind: "darker", label: "Make darker" },
  { kind: "cliffhanger", label: "Add stronger cliffhanger" },
  { kind: "realistic-dialogue", label: "Make dialogue more realistic" },
  { kind: "cinematic", label: "Make scenes more cinematic" },
];

export function ImproveStoryMenu({ projectId, disabled, onImproved }) {
  const [busy, setBusy] = useState(false);
  const run = async (kind) => {
    setBusy(true);
    try {
      const res = await withRealLLMToast(
        `improve story (${kind})`,
        () => Creative.improveStory(projectId, kind)
      );
      // Mock mode: surface the per-kind note as a small toast. Real mode:
      // the LLM toast already displayed completion timing.
      if (res?.llm_mode !== "real" && res?.llm_status !== "fallback") {
        toast.success(res.improvement.note);
      }
      onImproved?.(res);
    } catch {
      // withRealLLMToast handled the error toast in real mode; show fallback
      // for mock mode where the helper short-circuited.
      toast.error("Improve failed");
    } finally {
      setBusy(false);
    }
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled || busy}
          data-testid="improve-story-trigger"
          className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
        >
          <Sparkles className="w-3.5 h-3.5 mr-1.5" />
          {busy ? "Improving…" : "Improve story"}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="bg-[#121212] border-white/10 text-white w-60"
        data-testid="improve-story-menu"
      >
        <DropdownMenuLabel className="text-[10px] uppercase tracking-widest text-[#A1A1AA]">
          Mock improvements
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="bg-white/10" />
        {IMPROVE_OPTIONS.map((opt) => (
          <DropdownMenuItem
            key={opt.kind}
            onClick={() => run(opt.kind)}
            data-testid={`improve-story-${opt.kind}`}
            className="cursor-pointer hover:bg-white/5 focus:bg-white/5"
          >
            {opt.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
