import React, { useEffect, useState } from "react";
import { api, fmtEur, fmtDate } from "../lib/api";
import { TrendingUp, TrendingDown, Users, Receipt, AlertTriangle, Wallet, Package } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";

const KpiCard = ({ title, value, icon: Icon, hint, color = "text-white", testid }) => (
  <div className="wm-card p-6" data-testid={testid}>
    <div className="flex items-start justify-between">
      <div className="wm-label">{title}</div>
      <Icon size={18} className="text-white/40" strokeWidth={1.5} />
    </div>
    <div className={`mt-4 font-display text-3xl font-bold tracking-tight ${color}`}>{value}</div>
    {hint && <div className="mt-1 text-xs text-white/40">{hint}</div>}
  </div>
);

export default function Dashboard() {
  const { user } = useAuth();
  const [d, setD] = useState(null);
  useEffect(() => {
    api.get("/dashboard").then((r) => setD(r.data)).catch(() => {});
  }, []);

  if (!d) return <div className="text-white/50">Caricamento…</div>;
  const isTecnico = user?.role === "tecnico";

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      <div>
        <div className="wm-label">Dashboard {isTecnico && "· Tecnico"}</div>
        <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter mt-2">Panoramica</h1>
        <p className="text-white/50 mt-2 text-sm">
          {isTecnico ? "I tuoi dati: tesserati, ricevute, movimenti e compenso maturato." :
                       "Le metriche chiave del gestionale in tempo reale."}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title={isTecnico ? "Tuoi tesserati" : "Tesserati totali"}
          value={d.tesserati_count} icon={Users} testid="kpi-tesserati" />
        <KpiCard title={isTecnico ? "Tuoi abbonamenti" : "Abbonamenti"}
          value={d.abbon_count} icon={Package} testid="kpi-abbonamenti" />
        <KpiCard title="Ricevute del mese" value={d.ricevute_mese_count} icon={Receipt}
          hint={fmtEur(d.incassato_mese) + " incassati"} testid="kpi-ricevute-mese" />
        {isTecnico ? (
          <KpiCard title="Compenso maturato" value={fmtEur(d.compenso_maturato || 0)}
            icon={Wallet} color="text-[#FFCC00]" testid="kpi-compenso" hint="Anno in corso" />
        ) : (
          <KpiCard title="Entrate (anno)" value={fmtEur(d.entrate_anno)} icon={TrendingUp}
            color="text-[#34C759]" testid="kpi-entrate" />
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="wm-card p-6 lg:col-span-1">
          <div className="wm-label mb-4">{isTecnico ? "Il tuo saldo movimenti" : "Saldo anno"}</div>
          <div className={`font-display text-4xl sm:text-5xl font-black tracking-tighter
              ${d.saldo_anno >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}
              data-testid="kpi-saldo">{fmtEur(d.saldo_anno)}</div>
          <div className="mt-4 text-sm text-white/50">
            {isTecnico ? "Entrate meno uscite attribuite a te (anno in corso)." :
                          "Differenza tra entrate e uscite dall'inizio dell'anno."}
          </div>
          {!isTecnico && (
            <div className="mt-4 pt-4 border-t border-white/10 space-y-1">
              <div className="flex justify-between text-sm"><span className="text-white/50">Entrate</span>
                <span className="text-[#34C759] font-semibold">{fmtEur(d.entrate_anno)}</span></div>
              <div className="flex justify-between text-sm"><span className="text-white/50">Uscite</span>
                <span className="text-[#FF3B30] font-semibold">{fmtEur(d.uscite_anno)}</span></div>
            </div>
          )}
        </div>

        <div className="wm-card p-6 lg:col-span-2" data-testid="scadenze-panel">
          <div className="flex items-center justify-between mb-4">
            <div className="wm-label flex items-center gap-2">
              <AlertTriangle size={14} className="text-[#FF3B30]" />
              Scadenze imminenti (30 gg)
            </div>
            <Link to="/tesserati" className="text-xs text-[#007AFF] hover:underline">
              Vai ai tesserati →
            </Link>
          </div>
          {d.scadenze_imminenti.length === 0 && (
            <div className="text-white/50 text-sm py-4">Nessuna scadenza nei prossimi 30 giorni.</div>
          )}
          <div className="space-y-2">
            {d.scadenze_imminenti.slice(0, 6).map((t) => (
              <div key={t.id} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                <div>
                  <div className="font-medium">{t.cognome} {t.nome}</div>
                  <div className="text-xs text-white/50">
                    {t.scadenza_tesseramento && `Tesseramento: ${fmtDate(t.scadenza_tesseramento)}`}
                    {t.scadenza_tesseramento && t.scadenza_visita_medica && " · "}
                    {t.scadenza_visita_medica && `Visita: ${fmtDate(t.scadenza_visita_medica)}`}
                  </div>
                </div>
                <Link to={`/tesserati`} className="text-xs text-[#007AFF] hover:underline">Apri</Link>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
