import React, { useEffect, useState } from "react";
import { api, fmtEur } from "../lib/api";

export default function Compensi() {
  const [data, setData] = useState(null);
  const [from, setFrom] = useState(`${new Date().getFullYear()}-01-01`);
  const [to, setTo] = useState(`${new Date().getFullYear()}-12-31`);

  const load = async () => {
    const { data } = await api.get(`/compensi?date_from=${from}&date_to=${to}`);
    setData(data);
  };
  useEffect(() => { load(); }, []);

  if (!data) return <div className="text-white/50">Caricamento…</div>;

  const totFlusso = data.compensi.reduce((s, c) => s + c.flusso_generato, 0);
  const totCompenso = data.compensi.reduce((s, c) => s + c.compenso_dovuto, 0);

  return (
    <div className="space-y-6" data-testid="compensi-page">
      <div>
        <div className="wm-label">Analisi</div>
        <h1 className="font-display text-4xl font-black tracking-tighter mt-2">Compensi tecnici</h1>
        <p className="text-white/50 mt-2 text-sm">
          Percentuale sul flusso cassa generato da ricevute emesse in prima persona.
        </p>
      </div>

      <div className="wm-card p-4 flex items-end gap-3">
        <div><label className="wm-label">Da</label>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
            className="block mt-1 bg-black/40 border border-white/10 rounded px-3 py-2 text-sm" /></div>
        <div><label className="wm-label">A</label>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            className="block mt-1 bg-black/40 border border-white/10 rounded px-3 py-2 text-sm" /></div>
        <button onClick={load} data-testid="compensi-filter-btn"
          className="px-4 py-2 rounded bg-[#007AFF] hover:bg-[#005BB5] text-sm font-semibold">
          Aggiorna
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="wm-card p-5"><div className="wm-label">Flusso cassa totale</div>
          <div className="mt-2 font-display text-2xl font-bold">{fmtEur(totFlusso)}</div></div>
        <div className="wm-card p-5"><div className="wm-label">Totale compensi dovuti</div>
          <div className="mt-2 font-display text-2xl font-bold text-[#FFCC00]">{fmtEur(totCompenso)}</div></div>
      </div>

      <div className="wm-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.02] border-b border-white/10">
            <tr className="text-left">
              <th className="p-3 wm-label">Tecnico</th>
              <th className="p-3 wm-label text-center">N. ricevute</th>
              <th className="p-3 wm-label text-right">Flusso totale</th>
              <th className="p-3 wm-label text-right">Compensabile</th>
              <th className="p-3 wm-label text-center">%</th>
              <th className="p-3 wm-label text-right">Compenso dovuto</th>
            </tr>
          </thead>
          <tbody>
            {data.compensi.map((c) => (
              <tr key={c.tecnico_id} className="border-b border-white/5"
                data-testid={`compenso-row-${c.tecnico_id}`}>
                <td className="p-3 font-medium">{c.tecnico_nome}</td>
                <td className="p-3 text-center">{c.n_ricevute}</td>
                <td className="p-3 text-right text-white/70">{fmtEur(c.flusso_generato)}</td>
                <td className="p-3 text-right font-semibold">{fmtEur(c.flusso_compensabile)}</td>
                <td className="p-3 text-center">{c.percentuale}%</td>
                <td className="p-3 text-right font-semibold text-[#FFCC00]">{fmtEur(c.compenso_dovuto)}</td>
              </tr>
            ))}
            {data.compensi.length === 0 && (
              <tr><td colSpan={6} className="p-8 text-center text-white/40">Nessun tecnico configurato</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
