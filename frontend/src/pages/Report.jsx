import React, { useState } from "react";
import { api, fmtEur, fmtDate, API } from "../lib/api";
import { Button } from "../components/ui/button";
import { Download, RefreshCw } from "lucide-react";

export default function Report() {
  const y = new Date().getFullYear();
  const [from, setFrom] = useState(`${y}-01-01`);
  const [to, setTo] = useState(`${y}-12-31`);
  const [data, setData] = useState(null);

  const load = async () => {
    const { data } = await api.get(`/report/bilancio?date_from=${from}&date_to=${to}`);
    setData(data);
  };

  const downloadPdf = async () => {
    const res = await api.get(`/report/bilancio/pdf?date_from=${from}&date_to=${to}`,
      { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a"); a.href = url;
    a.download = `Bilancio_${from}_${to}.pdf`; a.click(); URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6" data-testid="report-page">
      <div>
        <div className="wm-label">Bilancio</div>
        <h1 className="font-display text-4xl font-black tracking-tighter mt-2">Report Bilancio</h1>
        <p className="text-white/50 mt-2 text-sm">Visualizza entrate, uscite e saldo per un periodo, ed esporta in PDF.</p>
      </div>

      <div className="wm-card p-4 flex items-end gap-3 flex-wrap">
        <div><label className="wm-label">Da</label>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
            className="block mt-1 bg-black/40 border border-white/10 rounded px-3 py-2 text-sm"
            data-testid="report-from" /></div>
        <div><label className="wm-label">A</label>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            className="block mt-1 bg-black/40 border border-white/10 rounded px-3 py-2 text-sm"
            data-testid="report-to" /></div>
        <Button onClick={load} className="bg-[#007AFF] hover:bg-[#005BB5]"
          data-testid="report-generate-btn">
          <RefreshCw size={14} className="mr-1" /> Genera
        </Button>
        {data && (
          <Button onClick={downloadPdf} variant="outline" className="border-white/20"
            data-testid="report-pdf-btn">
            <Download size={14} className="mr-1" /> Esporta PDF
          </Button>
        )}
      </div>

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div className="wm-card p-5"><div className="wm-label">Entrate</div>
              <div className="mt-2 font-display text-2xl font-bold text-[#34C759]"
                data-testid="report-entrate">{fmtEur(data.totali.entrate)}</div></div>
            <div className="wm-card p-5"><div className="wm-label">Uscite</div>
              <div className="mt-2 font-display text-2xl font-bold text-[#FF3B30]"
                data-testid="report-uscite">{fmtEur(data.totali.uscite)}</div></div>
            <div className="wm-card p-5"><div className="wm-label">Saldo</div>
              <div className={`mt-2 font-display text-2xl font-bold ${data.totali.saldo >= 0 ? "text-white" : "text-[#FF3B30]"}`}
                data-testid="report-saldo">{fmtEur(data.totali.saldo)}</div></div>
          </div>

          <div className="wm-card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-white/[0.02] border-b border-white/10">
                <tr className="text-left">
                  <th className="p-3 wm-label">Data</th>
                  <th className="p-3 wm-label">Tipo</th>
                  <th className="p-3 wm-label">Categoria</th>
                  <th className="p-3 wm-label">Descrizione</th>
                  <th className="p-3 wm-label text-right">Importo</th>
                </tr>
              </thead>
              <tbody>
                {data.movimenti.map((m) => (
                  <tr key={m.id} className="border-b border-white/5">
                    <td className="p-3">{fmtDate(m.data)}</td>
                    <td className="p-3">{m.tipo}</td>
                    <td className="p-3 text-white/70">{m.categoria}</td>
                    <td className="p-3 text-white/80">{m.descrizione}</td>
                    <td className={`p-3 text-right font-semibold ${m.tipo === "entrata" ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                      {m.tipo === "entrata" ? "+" : "-"}{fmtEur(m.importo)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
