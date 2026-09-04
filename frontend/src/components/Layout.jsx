import React, { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import {
  LayoutDashboard, Users, Package, Receipt, BookOpen,
  BarChart3, Wallet, LogOut, ShieldCheck,
  BookUser, Calendar, FileSpreadsheet, ScrollText,
  Menu, X,
} from "lucide-react";
import { Toaster, toast } from "sonner";
import InstallPWAButton from "./InstallPWAButton";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/tesserati", label: "Tesserati", icon: Users, testid: "nav-tesserati" },
  { to: "/abbonamenti", label: "Abbonamenti", icon: Package, testid: "nav-abbonamenti" },
  { to: "/ricevute", label: "Ricevute", icon: Receipt, testid: "nav-ricevute" },
  { to: "/calendario", label: "Calendario", icon: Calendar, testid: "nav-calendario" },
  { to: "/libro-soci", label: "Libro Soci", icon: BookUser, testid: "nav-libro-soci" },
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
  const [drawerOpen, setDrawerOpen] = useState(false);
  const isAdmin = user?.role === "admin";

  const handleLogout = async () => {
    setDrawerOpen(false);
    await logout();
    nav("/login");
  };

  const downloadBackup = async () => {
    try {
      const res = await api.get("/export/excel", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `WolfsMind_Backup_${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click(); URL.revokeObjectURL(url);
      toast.success("Backup Excel scaricato");
    } catch { toast.error("Errore export"); }
  };

  const Sidebar = ({ mobile = false }) => (
    <aside className={`${mobile ? "w-72" : "w-64"} shrink-0 border-r border-white/10 bg-[#0A0A0F] flex flex-col h-full`}>
      <div className="px-6 py-5 border-b border-white/10 flex items-center justify-between">
        <div>
          <div className="font-display text-lg font-black tracking-tight leading-tight">WOLF'S MIND</div>
          <div className="wm-label mt-1">A.S.D. Gestionale</div>
        </div>
        {mobile && (
          <button onClick={() => setDrawerOpen(false)} className="text-white/60 hover:text-white"
            data-testid="close-drawer-btn">
            <X size={20} />
          </button>
        )}
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {links.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.to === "/"} data-testid={l.testid}
            onClick={() => setDrawerOpen(false)}
            className={({ isActive }) => `wm-sidebar-link ${isActive ? "active" : ""}`}>
            <l.icon size={18} strokeWidth={1.75} /> <span>{l.label}</span>
          </NavLink>
        ))}
        {isAdmin && (
          <>
            <div className="wm-label mt-4 mb-2 px-3">Amministratore</div>
            {adminLinks.map((l) => (
              <NavLink key={l.to} to={l.to} data-testid={l.testid}
                onClick={() => setDrawerOpen(false)}
                className={({ isActive }) => `wm-sidebar-link ${isActive ? "active" : ""}`}>
                <l.icon size={18} strokeWidth={1.75} /> <span>{l.label}</span>
              </NavLink>
            ))}
          </>
        )}
      </nav>

      <div className="border-t border-white/10 p-4">
        <div className="mb-3">
          <div className="text-sm font-semibold truncate" data-testid="current-user-name">{user?.name}</div>
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
        <InstallPWAButton />
        <button onClick={handleLogout} data-testid="logout-btn"
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md
                     border border-white/10 text-sm text-white/70 hover:text-white
                     hover:border-white/25 transition-colors">
          <LogOut size={16} /> Esci
        </button>
      </div>
    </aside>
  );

  return (
    <div className="flex min-h-screen bg-[#050505] text-white">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex"><Sidebar /></div>

      {/* Mobile drawer */}
      {drawerOpen && (
        <>
          <div className="fixed inset-0 bg-black/70 z-40 lg:hidden"
            onClick={() => setDrawerOpen(false)} />
          <div className="fixed inset-y-0 left-0 z-50 lg:hidden">
            <Sidebar mobile />
          </div>
        </>
      )}

      <main className="flex-1 overflow-y-auto min-w-0">
        {/* Mobile top bar */}
        <div className="lg:hidden sticky top-0 z-30 bg-[#0A0A0F] border-b border-white/10 px-4 py-3
                        flex items-center justify-between">
          <button onClick={() => setDrawerOpen(true)} data-testid="open-drawer-btn"
            className="text-white/70 hover:text-white">
            <Menu size={22} />
          </button>
          <div className="font-display font-black tracking-tight text-sm">WOLF'S MIND</div>
          <div className="w-6" />
        </div>

        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-5 lg:py-8">{children}</div>
      </main>

      <Toaster theme="dark" position="top-right" richColors />
    </div>
  );
}
