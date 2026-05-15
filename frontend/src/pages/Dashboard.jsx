import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Film, Clock, ChevronRight, Sparkles, AlertCircle, Trash2 } from "lucide-react";
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

const WALLET_STATE_COLOR = {
  normal: "#34C759",
  warning: "#FFCC00",
  high: "#FF9500",
  insufficient: "#FF3B30",
};

function MiniWalletRing({ summary }) {
  if (!summary || summary.estimate_unavailable) {
    return (
      <span
        className="text-[10px] font-mono text-[#A1A1AA]"
        data-testid="dash-card-estimate-unavailable"
      >
        Estimate unavailable
      </span>
    );
  }
  const radius = 11;
  const stroke = 3;
  const c = 2 * Math.PI * radius;
  const pct = summary.wallet_pct ?? 0;
  const clamped = Math.max(0, Math.min(100, pct));
  const dash = (clamped / 100) * c;
  const color = WALLET_STATE_COLOR[summary.wallet_state] || WALLET_STATE_COLOR.normal;
  const tooltip = `This draft would use about ${Math.round(pct)}% of your available ${summary.wallet_credits} credits.`;
  return (
    <span
      className="inline-flex items-center gap-1.5"
      title={tooltip}
      data-testid="dash-card-wallet-ring"
      data-state={summary.wallet_state}
    >
      <svg width="28" height="28" viewBox="0 0 28 28" className="rotate-[-90deg]">
        <circle cx="14" cy="14" r={radius} stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} fill="none" />
        <circle
          cx="14"
          cy="14"
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={`${dash} ${c}`}
        />
      </svg>
      <span
        className="text-[11px] font-mono"
        style={{ color }}
        data-testid="dash-card-wallet-text"
      >
        ~{summary.grand_total_credits} credits · {Math.round(pct)}% of wallet
      </span>
      {summary.wallet_state === "insufficient" && (
        <AlertCircle className="w-3 h-3 text-[#FF3B30]" />
      )}
    </span>
  );
}

export default function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [sortKey, setSortKey] = useState("newest");

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

  const onDelete = async (project) => {
    // Optimistically remove from list; restore on failure or undo.
    const prev = projects;
    setProjects((list) => list.filter((p) => p.id !== project.id));
    try {
      await Projects.remove(project.id);
    } catch {
      setProjects(prev);
      toast.error("Delete failed");
      return;
    }
    toast(`Deleted "${project.title}"`, {
      id: `del-${project.id}`,
      duration: 5000,
      "data-testid": "project-delete-toast",
      action: {
        label: "Undo",
        onClick: async () => {
          try {
            const restored = await Projects.restore(project.id);
            // Re-fetch list so cost_summary etc. comes back fresh.
            const fresh = await Projects.list();
            setProjects(fresh);
            toast.success(`Restored "${restored.title || project.title}"`, {
              id: `restore-${project.id}`,
              "data-testid": "project-restore-toast",
            });
          } catch {
            toast.error("Restore failed");
          }
        },
      },
    });
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
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h2 className="font-display text-xl font-bold">Your projects</h2>
          <div className="flex items-center gap-2 flex-wrap" data-testid="dash-sort-row">
            <span className="es-label">Sort by</span>
            {[
              { key: "newest", label: "Newest" },
              { key: "title", label: "Title A→Z" },
              { key: "cost-desc", label: "Cost ↓" },
              { key: "cost-asc", label: "Cost ↑" },
            ].map((opt) => (
              <button
                key={opt.key}
                type="button"
                onClick={() => setSortKey(opt.key)}
                data-testid={`sort-${opt.key}`}
                className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
                  sortKey === opt.key
                    ? "bg-[#FF3B30] border-[#FF3B30] text-white"
                    : "border-white/10 bg-transparent text-[#A1A1AA] hover:text-white hover:bg-white/5"
                }`}
              >
                {opt.label}
              </button>
            ))}
            <span className="es-label">{projects.length} total</span>
          </div>
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
            {[...projects]
              .sort((a, b) => {
                const ac = a.cost_summary?.grand_total_credits ?? 0;
                const bc = b.cost_summary?.grand_total_credits ?? 0;
                if (sortKey === "title") return (a.title || "").localeCompare(b.title || "");
                if (sortKey === "cost-desc") return bc - ac;
                if (sortKey === "cost-asc") return ac - bc;
                // newest
                return new Date(b.created_at) - new Date(a.created_at);
              })
              .map((p) => (
              <ProjectCard key={p.id} project={p} onDelete={onDelete} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ProjectCard({ project, onDelete }) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="relative group">
      <Link
        to={`/projects/${project.id}`}
        data-testid={`project-card-${project.id}`}
        className="es-card es-card-hover p-5 block"
      >
        <div className="flex items-start justify-between mb-3">
          <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-[#A1A1AA]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#FF3B30]" />
            {STATUS_LABEL[project.status] || "Draft"}
          </div>
          <ChevronRight className="w-4 h-4 text-[#A1A1AA] group-hover:text-white transition-colors" />
        </div>
        <h3 className="font-display text-xl font-bold mb-2 text-white pr-8">
          {project.title}
        </h3>
        <p className="text-sm text-[#A1A1AA] line-clamp-3 min-h-[60px]">
          {project.idea || "No idea yet — open the project to add one."}
        </p>
        <div className="mt-3">
          <MiniWalletRing summary={project.cost_summary} />
        </div>
        <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between text-xs text-[#A1A1AA]">
          <span className="font-mono">{project.id.slice(0, 8)}</span>
          <span>{new Date(project.created_at).toLocaleDateString()}</span>
        </div>
      </Link>

      <button
        type="button"
        disabled={busy}
        onClick={async (e) => {
          e.preventDefault();
          e.stopPropagation();
          setBusy(true);
          try {
            await onDelete(project);
          } finally {
            setBusy(false);
          }
        }}
        data-testid={`delete-project-btn-${project.id}`}
        title="Delete project (undo available for 5 seconds)"
        className="absolute top-3 right-12 p-1.5 rounded-md text-[#A1A1AA] opacity-0 group-hover:opacity-100 hover:text-[#FF3B30] hover:bg-white/5 transition-opacity"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
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
