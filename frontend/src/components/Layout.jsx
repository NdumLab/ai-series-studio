import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Film, LayoutDashboard, ShieldCheck } from "lucide-react";

const navItem =
  "px-3 py-1.5 rounded-md text-sm font-medium tracking-tight transition-colors";
const activeNav = "bg-white/10 text-white";
const inactiveNav = "text-[#A1A1AA] hover:text-white hover:bg-white/5";

export default function Layout() {
  const { pathname } = useLocation();
  return (
    <div className="min-h-screen flex flex-col bg-[#050505] text-[#F5F5F5]">
      <header
        className="sticky top-0 z-50 backdrop-blur bg-[#050505]/80 border-b border-white/10"
        data-testid="app-top-nav"
      >
        <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 group" data-testid="logo-link">
            <span className="w-8 h-8 rounded-md bg-[#FF3B30] flex items-center justify-center">
              <Film className="w-4 h-4 text-white" />
            </span>
            <span className="font-display text-lg font-bold tracking-tight">
              AI Episode <span className="text-[#FF3B30]">Studio</span>
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            <NavLink
              to="/"
              data-testid="nav-dashboard"
              className={() =>
                `${navItem} ${pathname === "/" || pathname.startsWith("/projects") ? activeNav : inactiveNav}`
              }
            >
              <span className="inline-flex items-center gap-1.5">
                <LayoutDashboard className="w-3.5 h-3.5" /> Studio
              </span>
            </NavLink>
            <NavLink
              to="/admin"
              data-testid="nav-admin"
              className={({ isActive }) =>
                `${navItem} ${isActive ? activeNav : inactiveNav}`
              }
            >
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" /> Admin
              </span>
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-[1400px] mx-auto w-full px-6 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-white/10 py-5 text-xs text-[#A1A1AA]">
        <div className="max-w-[1400px] mx-auto px-6 flex items-center justify-between">
          <span className="font-mono">v0.1 · mock generation</span>
          <span>Built for creators, by creators</span>
        </div>
      </footer>
    </div>
  );
}
