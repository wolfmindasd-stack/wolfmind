import React, { useEffect, useState } from "react";
import { api, fmtEur, fmtDate, formatApiErrorDetail } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { CheckCircle, AlertCircle, XCircle, Download } from "lucide-react";
import { toast } from "sonner";

const badgeColor = (stato) => {
  if (stato === "attivo") return "text-[#34C759] border-[#34C759]/40 bg-[#34C759]/10";
  if (stato === "iscritto (scaduto)") return "text-[#FFCC00] border-[#FFCC00]/40 bg-[#FFCC00]/10";
  return "text-[#FF3B30] border-[#FF3B30]/40 bg-[#FF3B30]/10";
};

const badgeIcon = (stato) => {
  if (stato === "attivo") return <CheckCircle size={12} />;
  if (stato === "iscritto (scaduto)") return <AlertCircle size={12} />;
  return <XCircle size={12} />;
};

export default function LibroSoci() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState(null);

  const load = async () => {
    const { data } = await api.get(`/libro-soci?anno=${year}`);
    setData(data);
  };
  useEffect(() => { load(); }, [year]);

  const downloadPdf = async () => {
    try {
      const res = await api.get(`/libro-soci/pdf?anno=${year}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `LibroSoci_${year}.pdf`;
      a.click(); URL.revokeObjectURL(url);
      toast.success("PDF Libro Soci scaricato");
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Errore export"); }
  };

  if (!data) return <div className="text-white/50">Caricamento…</div>;

  const attivi = data.soci.filter((s) => s.stato_socio === "attivo").length;
  const morosi = data.soci.filter((s) => s.stato_socio === "moroso").length;
  const scaduti = data.soci.filter((s) => s.stato_socio === "iscritto (scaduto)").length;
  const totQuote = data.soci.reduce((s, x) => s + (x.quota_pagata_anno || 0), 0);

  return (
    <div className="space-y-6" data-testid="libro-soci-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="wm-label">Amministrazione</div>
          <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter mt-2">Libro Soci</h1>
          <p className="text-white/50 mt-2 text-sm">Elenco ufficiale dei soci con stato tesseramento e quota associativa annuale.</p>
        </div>
        <div className="flex items-center gap-2">
          <Label className="wm-label">Anno</Label>
          <Input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))}
            className="w-24 bg-black/40 border-white/10 h-9" data-testid="year-input" />
          <Button onClick={downloadPdf} className="bg-[#007AFF] hover:bg-[#005BB5]"
            data-testid="download-libro-soci-pdf">
            <Download size={16} className="mr-1" /> Esporta PDF
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="wm-card p-5"><div className="wm-label">Soci Totali</div>
          <div className="mt-2 font-display text-2xl font-bold">{data.soci.length}</div></div>
        <div className="wm-card p-5"><div className="wm-label">Attivi</div>
          <div className="mt-2 font-display text-2xl font-bold text-[#34C759]">{attivi}</div></div>
        <div className="wm-card p-5"><div className="wm-label">Scaduti/Morosi</div>
          <div className="mt-2 font-display text-2xl font-bold text-[#FF3B30]">{scaduti + morosi}</div></div>
        <div className="wm-card p-5"><div className="wm-label">Quote incassate {year}</div>
          <div className="mt-2 font-display text-2xl font-bold text-[#007AFF]">{fmtEur(totQuote)}</div></div>
      </div>

      <div className="wm-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.02] border-b border-white/10">
            <tr className="text-left">
              <th className="p-3 wm-label">N. Tessera</th>
              <th className="p-3 wm-label">Socio</th>
              <th className="p-3 wm-label">CF</th>
              <th className="p-3 wm-label">Città</th>
              <th className="p-3 wm-label">Scad. tesseramento</th>
              <th className="p-3 wm-label">Stato</th>
              <th className="p-3 wm-label text-right">Quota {year}</th>
            </tr>
          </thead>
          <tbody>
            {data.soci.map((s) => (
              <tr key={s.id} className="border-b border-white/5" data-testid={`socio-row-${s.id}`}>
                <td className="p-3 font-mono text-xs">{s.numero_tessera || "—"}</td>
                <td className="p-3 font-medium">{s.cognome} {s.nome}</td>
                <td className="p-3 font-mono text-xs text-white/60">{s.codice_fiscale}</td>
                <td className="p-3 text-white/70">{s.citta}</td>
                <td className="p-3 text-white/70">{fmtDate(s.scadenza_tesseramento)}</td>
                <td className="p-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs
                    border ${badgeColor(s.stato_socio)}`}>
                    {badgeIcon(s.stato_socio)} {s.stato_socio}
                  </span>
                </td>
                <td className="p-3 text-right font-semibold">
                  {s.quota_pagata_anno > 0 ? fmtEur(s.quota_pagata_anno) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
