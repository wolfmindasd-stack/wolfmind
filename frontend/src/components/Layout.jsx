import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import {
  LayoutDashboard, Users, Package, Receipt, BookOpen,
  BarChart3, Wallet, Settings, LogOut, ShieldCheck,
} from "lucide-react";
import { Toaster } from "sonner";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/tesserati", label: "Tesserati", icon: Users, testid: "nav-tesserati" },
  { to: "/ricevute", label: "Ricevute", icon: Receipt, testid: "nav-ricevute" },
  { to: "/abbonamenti", label: "Abbonamenti", icon: Package, testid: "nav-abbonamenti" },
  { to: "/movimenti", label: "Libro Contabile", icon: BookOpen, testid: "nav-movimenti" },
  { to: "/compensi", label: "Compensi", icon: Wallet, testid: "nav-compensi" },
  { to: "/report", label: "Report Bilancio", icon: BarChart3, testid: "nav-report" },
];

const adminLinks = [
  { to: "/admin", label: "Pannello Admin", icon: ShieldCheck, testid: "nav-admin" },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const isAdmin = user?.role === "admin";

  const handleLogout = async () => {
    await logout();
    nav("/login");
  };

  return (
    <div className="flex min-h-screen bg-[#050505] text-white">
      <aside className="w-64 shrink-0 border-r border-white/10 bg-[#0A0A0F] flex flex-col">
        <div className="px-6 py-5 border-b border-white/10">
          <div className="font-display text-lg font-black tracking-tight leading-tight">
            WOLF'S MIND
          </div>
          <div className="wm-label mt-1">A.S.D. Gestionale</div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.to === "/"} data-testid={l.testid}
              className={({ isActive }) => `wm-sidebar-link ${isActive ? "active" : ""}`}>
              <l.icon size={18} strokeWidth={1.75} /> <span>{l.label}</span>
            </NavLink>
          ))}
          {isAdmin && (
            <>
              <div className="wm-label mt-4 mb-2 px-3">Amministratore</div>
              {adminLinks.map((l) => (
                <NavLink key={l.to} to={l.to} data-testid={l.testid}
                  className={({ isActive }) => `wm-sidebar-link ${isActive ? "active" : ""}`}>
                  <l.icon size={18} strokeWidth={1.75} /> <span>{l.label}</span>
                </NavLink>
              ))}
            </>
          )}
        </nav>

        <div className="border-t border-white/10 p-4">
          <div className="mb-3">
            <div className="text-sm font-semibold truncate" data-testid="current-user-name">
              {user?.name}
            </div>
            <div className="text-xs text-white/50 truncate">
              {user?.email} · {user?.role === "admin" ? "Admin" : "Tecnico"}
            </div>
          </div>
          <button onClick={handleLogout} data-testid="logout-btn"
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md
                       border border-white/10 text-sm text-white/70 hover:text-white
                       hover:border-white/25 transition-colors">
            <LogOut size={16} /> Esci
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1400px] mx-auto px-8 py-8">{children}</div>
      </main>

      <Toaster theme="dark" position="top-right" richColors />
    </div>
  );
}
