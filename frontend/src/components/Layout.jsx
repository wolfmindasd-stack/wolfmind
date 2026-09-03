import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api, API } from "../lib/api";
import {
  LayoutDashboard, Users, Package, Receipt, BookOpen,
  BarChart3, Wallet, Settings, LogOut, ShieldCheck,
  BookUser, Calendar, FileSpreadsheet, ScrollText,
} from "lucide-react";
import { Toaster, toast } from "sonner";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/tesserati", label: "Tesserati", icon: Users, testid: "nav-tesserati" },
  { to: "/libro-soci", label: "Libro Soci", icon: BookUser, testid: "nav-libro-soci" },
  { to: "/ricevute", label: "Ricevute", icon: Receipt, testid: "nav-ricevute" },
  { to: "/abbonamenti", label: "Abbonamenti", icon: Package, testid: "nav-abbonamenti" },
  { to: "/calendario", label: "Calendario", icon: Calendar, testid: "nav-calendario" },
  { to: "/movimenti", label: "Libro Contabile", icon: BookOpen, testid: "nav-movimenti" },
  { to: "/compensi", label: "Compensi", icon: Wallet, testid: "nav-compensi" },
  { to: "/verbali", label: "Verbali", icon: ScrollText, testid: "nav-verbali" },
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

  const downloadBackup = async () => {
    try {
      const res = await api.get("/export/excel", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `WolfsMind_Backup_${new Date().toISOString().slice(0,10)}.xlsx`;
      a.click(); URL.revokeObjectURL(url);
      toast.success("Backup Excel scaricato");
    } catch { toast.error("Errore export"); }
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
          {isAdmin && (
            <button onClick={downloadBackup} data-testid="download-backup-btn"
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md mb-2
                         border border-[#34C759]/40 text-sm text-[#34C759] hover:bg-[#34C759]/10
                         transition-colors">
              <FileSpreadsheet size={16} /> Backup Excel
            </button>
          )}
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
