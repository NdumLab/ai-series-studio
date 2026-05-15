import { useState } from "react";
import { toast } from "sonner";
import { Wand2, Save, Split } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import { ProviderHintChip } from "../../components/studio/ProviderHintChip";
import { QualityScorePanel } from "../../components/studio/QualityScorePanel";
import { ImproveStoryMenu } from "../../components/studio/ImproveStoryMenu";
import { Projects } from "../../lib/api";
import { withRealLLMToast } from "../../lib/llmToast";

export function StoryTab({ project, providers, options, reload, onContinue }) {
  const [idea, setIdea] = useState(project.idea || "");
  const [story, setStory] = useState(project.rewritten_story || "");
  const [busy, setBusy] = useState(false);

  const saveIdea = async () => {
    await Projects.update(project.id, { idea });
    toast.success("Idea saved");
  };

  const rewrite = async () => {
    setBusy(true);
    try {
      await Projects.update(project.id, { idea });
      const res = await withRealLLMToast("story rewrite", () => Projects.rewrite(project.id));
      setStory(res.rewritten_story);
      if (res.llm_mode !== "real" && res.llm_status !== "fallback") {
        toast.success(`Story rewritten · -${res.cost} credits`);
      }
      reload();
    } catch {
      // withRealLLMToast already toasted error; nothing extra needed.
    } finally {
      setBusy(false);
    }
  };

  const saveStory = async () => {
    await Projects.update(project.id, { rewritten_story: story });
    toast.success("Story saved");
    reload();
  };

  const split = async () => {
    setBusy(true);
    try {
      await Projects.update(project.id, { rewritten_story: story });
      await Projects.splitScenes(project.id);
      toast.success("Split into scenes");
      reload();
      onContinue();
    } catch {
      toast.error("Scene split failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <ProviderHintChip
        providers={providers}
        modality="llm"
        action="story rewrite"
        credits={options?.costs?.rewrite ? `~${options.costs.rewrite} credits` : null}
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="es-card p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display text-lg font-bold">Idea / Logline</h3>
            <Button
              size="sm"
              variant="outline"
              onClick={saveIdea}
              data-testid="save-idea-btn"
              className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
            >
              <Save className="w-3.5 h-3.5 mr-1.5" /> Save
            </Button>
          </div>
          <Textarea
            data-testid="idea-textarea"
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder="A rough premise — one or two sentences."
            className="bg-[#0A0A0A] border-white/10 text-white min-h-[180px]"
          />
          <Button
            onClick={rewrite}
            disabled={busy}
            data-testid="rewrite-btn"
            className="mt-4 bg-[#FF3B30] hover:bg-[#FF453A] text-white w-full"
          >
            <Wand2 className="w-4 h-4 mr-2" />{" "}
            {busy ? "Rewriting…" : "Rewrite as episode draft"}
          </Button>
        </div>

        <div className="es-card p-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-display text-lg font-bold">Episode draft</h3>
              <p className="text-xs text-[#A1A1AA] mt-0.5">
                Edit freely before splitting into scenes.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <ImproveStoryMenu
                projectId={project.id}
                disabled={!story.trim()}
                onImproved={(res) => {
                  setStory(res.rewritten_story);
                  reload();
                }}
              />
              <Button
                size="sm"
                variant="outline"
                onClick={saveStory}
                data-testid="save-story-btn"
                className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
              >
                <Save className="w-3.5 h-3.5 mr-1.5" /> Save
              </Button>
            </div>
          </div>
          <Textarea
            data-testid="story-textarea"
            value={story}
            onChange={(e) => setStory(e.target.value)}
            placeholder="Your rewritten episode will appear here. You can freely edit it."
            className="bg-[#0A0A0A] border-white/10 text-white min-h-[260px]"
          />
          <Button
            onClick={split}
            disabled={busy || !story.trim()}
            data-testid="split-scenes-btn"
            className="mt-4 bg-white text-black hover:bg-white/90 w-full"
          >
            <Split className="w-4 h-4 mr-2" />{" "}
            {busy ? "Splitting…" : "Save & split into scenes →"}
          </Button>
        </div>
      </div>

      <QualityScorePanel scores={project.quality_scores} />
    </div>
  );
}
