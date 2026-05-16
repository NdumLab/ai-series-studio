import { useEffect, useState } from "react";
import { Admin as AdminApi, Projects } from "../lib/api";
import { toast } from "sonner";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import { Users, FolderKanban, Sparkles, AlertTriangle, DollarSign, Activity, Trash2, RotateCcw } from "lucide-react";

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [projects, setProjects] = useState([]);
  const [gens, setGens] = useState([]);
  const [creditEvents, setCreditEvents] = useState([]);
  const [failed, setFailed] = useState([]);
  const [activity, setActivity] = useState({ items: [], count: 0 });
  const [health, setHealth] = useState({ window_minutes: 60, modalities: [] });
  const [deleted, setDeleted] = useState({ items: [], count: 0 });

  const loadActivity = () =>
    AdminApi.providerActivity(50).then((d) =>
      setActivity({ items: d.items || [], count: d.count || 0 })
    );
  const loadHealth = () => AdminApi.providerHealth().then(setHealth);
  const loadDeleted = () =>
    AdminApi.deletedProjects().then((d) =>
      setDeleted({ items: d.items || [], count: d.count || 0 })
    );

  useEffect(() => {
    AdminApi.stats().then(setStats);
    AdminApi.users().then(setUsers);
    AdminApi.projects().then(setProjects);
    AdminApi.generations().then(setGens);
    AdminApi.creditEvents().then(setCreditEvents);
    AdminApi.failedJobs().then(setFailed);
    loadActivity();
    loadHealth();
    loadDeleted();
  }, []);

  const onRestore = async (project) => {
    try {
      await Projects.restore(project.id);
      setDeleted((prev) => ({
        count: Math.max(0, prev.count - 1),
        items: prev.items.filter((p) => p.id !== project.id),
      }));
      toast.success(`Restored "${project.title}"`, {
        id: `admin-restore-${project.id}`,
        "data-testid": "admin-project-restore-toast",
      });
    } catch {
      toast.error("Restore failed");
    }
  };

  return (
    <div className="es-fade">
      <p className="es-label mb-3">Operations · Internal</p>
      <h1 className="font-display text-4xl font-black tracking-tight mb-2">
        Admin <span className="text-[#FF3B30]">Console</span>
      </h1>
      <p className="text-[#A1A1AA] text-sm mb-8 max-w-2xl">
        High-level health of the studio: users, projects, generations, failed
        jobs and estimated internal compute cost.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-10" data-testid="admin-stats">
        <Metric label="Users" value={stats?.users ?? "—"} icon={<Users className="w-4 h-4" />} />
        <Metric label="Projects" value={stats?.projects ?? "—"} icon={<FolderKanban className="w-4 h-4" />} />
        <Metric label="Generations" value={stats?.generations ?? "—"} icon={<Sparkles className="w-4 h-4" />} />
        <Metric label="Failed jobs" value={stats?.failed_jobs ?? "—"} icon={<AlertTriangle className="w-4 h-4" />} accent />
        <Metric
          label="Internal cost"
          value={stats ? `$${stats.internal_cost_usd}` : "—"}
          sub={`${stats?.credits_used ?? 0} credits`}
          icon={<DollarSign className="w-4 h-4" />}
        />
      </div>

      <Tabs defaultValue="users">
        <TabsList className="bg-[#121212] border border-white/10">
          <TabsTrigger value="users" data-testid="admin-tab-users">Users</TabsTrigger>
          <TabsTrigger value="projects" data-testid="admin-tab-projects">Projects</TabsTrigger>
          <TabsTrigger value="generations" data-testid="admin-tab-generations">Generations</TabsTrigger>
          <TabsTrigger value="credits" data-testid="admin-tab-credits">Credits</TabsTrigger>
          <TabsTrigger value="failed" data-testid="admin-tab-failed">Failed jobs</TabsTrigger>
          <TabsTrigger value="provider-activity" data-testid="admin-tab-provider-activity">
            <span className="inline-flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5" /> Provider activity
            </span>
          </TabsTrigger>
          <TabsTrigger value="deleted" data-testid="admin-tab-deleted">
            <span className="inline-flex items-center gap-1.5">
              <Trash2 className="w-3.5 h-3.5" /> Recently Deleted
              {deleted.count > 0 && (
                <span
                  className="ml-1 px-1.5 py-0.5 rounded-full bg-[#FF3B30]/20 text-[#FF3B30] text-[10px] font-mono"
                  data-testid="admin-deleted-count-badge"
                >
                  {deleted.count}
                </span>
              )}
            </span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="mt-4">
          <Table
            head={["Name", "Email", "Role", "Available", "Used", "Reserved", "Joined"]}
            rows={users.map((u) => [
              u.name,
              u.email,
              u.role,
              u.credits ?? 0,
              u.credits_used ?? 0,
              u.credits_reserved ?? 0,
              new Date(u.created_at).toLocaleDateString(),
            ])}
            testId="admin-users-table"
          />
        </TabsContent>

        <TabsContent value="projects" className="mt-4">
          <Table
            head={["Title", "Status", "Created"]}
            rows={projects.map((p) => [
              p.title,
              p.status,
              new Date(p.created_at).toLocaleString(),
            ])}
            testId="admin-projects-table"
          />
        </TabsContent>

        <TabsContent value="generations" className="mt-4">
          <Table
            head={["Type", "Project", "Credits", "Status", "When"]}
            rows={gens.map((g) => [
              g.type,
              g.project_id?.slice(0, 8) || "—",
              g.cost_credits,
              g.status,
              new Date(g.created_at).toLocaleString(),
            ])}
            testId="admin-generations-table"
          />
        </TabsContent>

        <TabsContent value="credits" className="mt-4">
          <Table
            head={["When", "User", "Project", "Operation", "Delta", "Balance", "Reason"]}
            rows={creditEvents.map((e) => [
              new Date(e.created_at).toLocaleString(),
              e.user_id?.slice(0, 12) || "—",
              e.project_id?.slice(0, 8) || "—",
              e.operation,
              e.credits_delta,
              e.balance_after,
              e.reason || "—",
            ])}
            testId="admin-credit-events-table"
          />
        </TabsContent>

        <TabsContent value="failed" className="mt-4">
          <Table
            head={["Type", "Error", "Project", "When"]}
            rows={failed.map((g) => [
              g.type,
              g.error || "—",
              g.project_id?.slice(0, 8) || "—",
              new Date(g.created_at).toLocaleString(),
            ])}
            testId="admin-failed-table"
          />
        </TabsContent>

        <TabsContent value="provider-activity" className="mt-4">
          <ProviderHealthPulse
            health={health}
            onRefresh={() => {
              loadHealth();
              loadActivity();
            }}
          />
          <div className="flex items-center justify-between mb-2 mt-4">
            <p className="text-xs text-[#A1A1AA]">
              Last 50 provider executions · safe metadata only · no prompts, outputs or API keys are stored.
            </p>
            <button
              type="button"
              onClick={() => {
                loadHealth();
                loadActivity();
              }}
              data-testid="admin-provider-activity-refresh"
              className="text-xs px-3 py-1.5 rounded-md border border-white/15 text-white hover:bg-white/5"
            >
              Refresh
            </button>
          </div>
          <Table
            head={["When", "Modality", "Provider/Model", "Source", "Mode", "Status", "Credits", "Job id", "Duration", "Message"]}
            rows={activity.items.map((r) => [
              new Date(r.created_at).toLocaleTimeString(),
              r.modality,
              `${r.provider_name || "—"}/${r.model_name || "—"}`,
              r.source || "—",
              r.mode,
              r.status,
              r.estimated_credits ?? 0,
              r.provider_job_id || "—",
              r.duration_ms != null ? `${r.duration_ms}ms` : "—",
              r.error || r.message || "—",
            ])}
            testId="admin-provider-activity-table"
          />
        </TabsContent>

        <TabsContent value="deleted" className="mt-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-[#A1A1AA]">
              Soft-deleted projects inside their 24h restore window. After the
              window passes, the background purge cleans them up permanently.
            </p>
            <button
              type="button"
              onClick={loadDeleted}
              data-testid="admin-deleted-refresh"
              className="text-xs px-3 py-1.5 rounded-md border border-white/15 text-white hover:bg-white/5"
            >
              Refresh
            </button>
          </div>
          {deleted.items.length === 0 ? (
            <div
              className="es-card p-8 text-center text-sm text-[#A1A1AA]"
              data-testid="admin-deleted-empty"
            >
              Nothing here — no projects are currently in the restore window.
            </div>
          ) : (
            <div className="overflow-x-auto" data-testid="admin-deleted-table">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left">
                    {["Title", "Deleted at", "Restore until", "Scenes", "Characters", "Segments", ""].map((h) => (
                      <th key={h} className="es-label py-2 pr-4 border-b border-white/10">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {deleted.items.map((p) => (
                    <tr
                      key={p.id}
                      className="border-b border-white/5 hover:bg-white/5"
                      data-testid={`admin-deleted-row-${p.id}`}
                    >
                      <td className="py-2.5 pr-4 text-white font-medium">{p.title || "(untitled)"}</td>
                      <td className="py-2.5 pr-4 text-[#A1A1AA] font-mono text-xs">
                        {p.deleted_at ? new Date(p.deleted_at).toLocaleString() : "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-[#A1A1AA] font-mono text-xs">
                        {p.delete_expires_at ? new Date(p.delete_expires_at).toLocaleString() : "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-[#A1A1AA] font-mono">{p.scenes_count}</td>
                      <td className="py-2.5 pr-4 text-[#A1A1AA] font-mono">{p.characters_count}</td>
                      <td className="py-2.5 pr-4 text-[#A1A1AA] font-mono">{p.segments_count}</td>
                      <td className="py-2.5 pr-4 text-right">
                        <button
                          type="button"
                          onClick={() => onRestore(p)}
                          data-testid={`admin-restore-btn-${p.id}`}
                          className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md border border-white/15 text-white hover:bg-white/10"
                        >
                          <RotateCcw className="w-3 h-3" /> Restore
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Metric({ label, value, sub, icon, accent }) {
  return (
    <div className={`es-card p-4 ${accent ? "border-[#FF3B30]/40" : ""}`}>
      <div className="flex items-center justify-between text-[#A1A1AA] mb-2">
        <span className="es-label">{label}</span>
        {icon}
      </div>
      <div className={`font-display text-2xl font-bold ${accent ? "text-[#FF3B30]" : ""}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-[#A1A1AA] mt-1 font-mono">{sub}</div>}
    </div>
  );
}

function Table({ head, rows, testId }) {
  return (
    <div data-testid={testId} className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left">
            {head.map((h) => (
              <th key={h} className="es-label py-2 pr-4 border-b border-white/10">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={head.length} className="py-6 text-center text-[#A1A1AA]">
                Nothing here yet.
              </td>
            </tr>
          )}
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-white/5">
              {r.map((cell, j) => (
                <td key={j} className="py-2 pr-4 text-[#F5F5F5]">
                  {String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


const STATUS_DISPLAY = {
  healthy:     { label: "Healthy",     color: "#34C759", dot: "#34C759" },
  slow:        { label: "Slow",        color: "#FFCC00", dot: "#FFCC00" },
  failing:     { label: "Failing",     color: "#FF3B30", dot: "#FF3B30" },
  no_activity: { label: "No activity", color: "#A1A1AA", dot: "#52525B" },
};

const MODALITY_DISPLAY = {
  llm:    "LLM",
  image:  "Image",
  video:  "Video",
  voice:  "Voice",
  music:  "Music",
  export: "Export",
};

function ProviderHealthPulse({ health, onRefresh }) {
  const modalities = (health && health.modalities) || [];
  return (
    <div
      className="es-card p-4"
      data-testid="provider-health-pulse"
    >
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="es-label">Provider health pulse</p>
          <p className="text-xs text-[#A1A1AA] mt-0.5">
            Aggregated from the last {health.window_minutes || 60} minutes of activity · mock mode only.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          data-testid="provider-health-refresh"
          className="text-xs px-3 py-1.5 rounded-md border border-white/15 text-white hover:bg-white/5"
        >
          Refresh
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        {modalities.map((m) => {
          const d = STATUS_DISPLAY[m.status] || STATUS_DISPLAY.no_activity;
          const noActivity = m.status === "no_activity";
          return (
            <div
              key={m.modality}
              data-testid={`pulse-${m.modality}`}
              data-status={m.status}
              className="es-card p-2.5 bg-white/[0.02] border-white/5"
              title={`${MODALITY_DISPLAY[m.modality]} · ${d.label} · avg ${m.avg_duration_ms}ms · ${m.total_calls} calls · ${m.failed_calls} failed`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono uppercase tracking-widest text-white">
                  {MODALITY_DISPLAY[m.modality] || m.modality}
                </span>
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: d.dot }}
                />
              </div>
              <div className="font-mono text-[10px]" style={{ color: d.color }}>
                {d.label}
              </div>
              <div className="font-mono text-[10px] text-[#A1A1AA] mt-1">
                {noActivity ? (
                  <>0 calls</>
                ) : (
                  <>
                    {m.avg_duration_ms}ms · {m.total_calls} call
                    {m.total_calls === 1 ? "" : "s"}
                    {m.failed_calls > 0 && (
                      <span className="text-[#FF3B30]"> · {m.failed_calls} failed</span>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
