import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Film, Clock, ChevronRight, Sparkles } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { Projects } from "../lib/api";

const STATUS_LABEL = {
  draft: "Draft",
  story_ready: "Story",
  scenes_ready: "Scenes",
};

export default function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const load = () =>
    Projects.list()
      .then(setProjects)
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const onCreate = async () => {
    if (!title.trim()) {
      toast.error("Title is required");
      return;
    }
    setCreating(true);
    try {
      const p = await Projects.create({ title: title.trim(), idea: idea.trim() });
      toast.success("Project created");
      setOpen(false);
      setTitle("");
      setIdea("");
      setProjects((prev) => [p, ...prev]);
    } catch (e) {
      toast.error("Failed to create");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="es-fade">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-10">
        <div>
          <p className="es-label mb-3">Studio · Workspace</p>
          <h1 className="font-display text-4xl sm:text-5xl font-black tracking-tight">
            Make episodes. <span className="text-[#FF3B30]">Fast.</span>
          </h1>
          <p className="mt-3 text-[#A1A1AA] max-w-xl text-sm">
            Turn a rough idea into a finished 1–3 minute AI episode with story,
            scenes, voice, music and stitched video — all in one canvas.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button
              data-testid="open-create-project-btn"
              className="bg-[#FF3B30] hover:bg-[#FF453A] text-white font-semibold rounded-md h-11 px-5"
            >
              <Plus className="w-4 h-4 mr-2" /> New project
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#121212] border-white/10 text-white">
            <DialogHeader>
              <DialogTitle className="font-display">New project</DialogTitle>
              <DialogDescription className="text-[#A1A1AA]">
                Give your episode a working title and a rough story idea.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="es-label block mb-2">Title</label>
                <Input
                  data-testid="project-title-input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="The Last Signal"
                  className="bg-[#0A0A0A] border-white/10 text-white"
                />
              </div>
              <div>
                <label className="es-label block mb-2">Idea / Logline</label>
                <Textarea
                  data-testid="project-idea-input"
                  value={idea}
                  onChange={(e) => setIdea(e.target.value)}
                  placeholder="A radio operator in 1962 picks up a transmission from the future…"
                  className="bg-[#0A0A0A] border-white/10 text-white min-h-[120px]"
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setOpen(false)}
                className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
                data-testid="cancel-create-btn"
              >
                Cancel
              </Button>
              <Button
                onClick={onCreate}
                disabled={creating}
                data-testid="submit-create-project-btn"
                className="bg-[#FF3B30] hover:bg-[#FF453A] text-white"
              >
                {creating ? "Creating…" : "Create project"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8" data-testid="dashboard-stats">
        <Stat label="Projects" value={projects.length} icon={<Film className="w-4 h-4" />} />
        <Stat
          label="In progress"
          value={projects.filter((p) => p.status !== "scenes_ready").length}
          icon={<Clock className="w-4 h-4" />}
        />
        <Stat label="Mock provider" value="Active" icon={<Sparkles className="w-4 h-4" />} />
        <Stat label="Credits / scene" value="~8" icon={<Sparkles className="w-4 h-4" />} />
      </div>

      {/* Projects grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-xl font-bold">Your projects</h2>
          <span className="es-label">{projects.length} total</span>
        </div>
        {loading ? (
          <div className="text-[#A1A1AA] text-sm">Loading…</div>
        ) : projects.length === 0 ? (
          <EmptyState onCreate={() => setOpen(true)} />
        ) : (
          <div
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
            data-testid="projects-grid"
          >
            {projects.map((p) => (
              <Link
                key={p.id}
                to={`/projects/${p.id}`}
                data-testid={`project-card-${p.id}`}
                className="es-card es-card-hover p-5 group block"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-[#A1A1AA]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#FF3B30]" />
                    {STATUS_LABEL[p.status] || "Draft"}
                  </div>
                  <ChevronRight className="w-4 h-4 text-[#A1A1AA] group-hover:text-white transition-colors" />
                </div>
                <h3 className="font-display text-xl font-bold mb-2 text-white">
                  {p.title}
                </h3>
                <p className="text-sm text-[#A1A1AA] line-clamp-3 min-h-[60px]">
                  {p.idea || "No idea yet — open the project to add one."}
                </p>
                <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between text-xs text-[#A1A1AA]">
                  <span className="font-mono">{p.id.slice(0, 8)}</span>
                  <span>{new Date(p.created_at).toLocaleDateString()}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, icon }) {
  return (
    <div className="es-card p-4">
      <div className="flex items-center justify-between mb-2 text-[#A1A1AA]">
        <span className="es-label">{label}</span>
        <span>{icon}</span>
      </div>
      <div className="font-display text-2xl font-bold">{value}</div>
    </div>
  );
}

function EmptyState({ onCreate }) {
  return (
    <div className="es-card p-12 text-center" data-testid="empty-state">
      <div className="w-12 h-12 rounded-md bg-white/5 mx-auto mb-4 flex items-center justify-center">
        <Film className="w-6 h-6 text-[#FF3B30]" />
      </div>
      <h3 className="font-display text-2xl font-bold mb-2">No projects yet</h3>
      <p className="text-[#A1A1AA] mb-6 text-sm">
        Start a new project to draft your first episode.
      </p>
      <Button
        onClick={onCreate}
        data-testid="empty-create-btn"
        className="bg-[#FF3B30] hover:bg-[#FF453A] text-white"
      >
        <Plus className="w-4 h-4 mr-2" /> Create project
      </Button>
    </div>
  );
}
