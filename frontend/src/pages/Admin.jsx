import { useEffect, useState } from "react";
import { Admin as AdminApi } from "../lib/api";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import { Users, FolderKanban, Sparkles, AlertTriangle, DollarSign } from "lucide-react";

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [projects, setProjects] = useState([]);
  const [gens, setGens] = useState([]);
  const [failed, setFailed] = useState([]);

  useEffect(() => {
    AdminApi.stats().then(setStats);
    AdminApi.users().then(setUsers);
    AdminApi.projects().then(setProjects);
    AdminApi.generations().then(setGens);
    AdminApi.failedJobs().then(setFailed);
  }, []);

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
          <TabsTrigger value="failed" data-testid="admin-tab-failed">Failed jobs</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="mt-4">
          <Table
            head={["Name", "Email", "Role", "Credits", "Joined"]}
            rows={users.map((u) => [
              u.name,
              u.email,
              u.role,
              u.credits,
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
