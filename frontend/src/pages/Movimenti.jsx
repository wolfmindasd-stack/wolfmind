import React, { useEffect, useState } from "react";
import { api, fmtEur, fmtDate, formatApiErrorDetail, todayIso, API } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Plus, Trash2, Pencil, ArrowUp, ArrowDown, Download } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

const CATEGORIE = [
  "Ricevuta", "Iscrizione", "Sponsor", "Contributo",
  "Compenso tecnico", "Acquisto materiali", "Affitto", "Utenze",
  "Manutenzione", "Assicurazione", "Federazione", "Altro",
];

const MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
              "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"];

export default function Movimenti() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [tab, setTab] = useState("dettaglio");
  const [list, setList] = useState([]);
  const [tecnici, setTecnici] = useState([]);
  const [mensile, setMensile] = useState(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    data: todayIso(), tipo: "uscita", categoria: "Altro",
    descrizione: "", importo: 0, tecnico_id: "",
  });

  const load = async () => {
    const [m, u, mm] = await Promise.all([
      api.get("/movimenti"),
      api.get("/users").catch(() => ({ data: [] })),
      api.get(`/movimenti/riepilogo-mensile?year=${year}`),
    ]);
    setList(m.data);
    setTecnici(u.data.filter((x) => x.role === "tecnico"));
    setMensile(mm.data);
  };
  useEffect(() => { load(); }, [year]);

  const openNew = () => {
    setEditing(null);
    setForm({ data: todayIso(), tipo: "uscita", categoria: "Altro",
              descrizione: "", importo: 0, tecnico_id: "" });
    setOpen(true);
  };
  const openEdit = (m) => {
    setEditing(m.id);
    setForm({ data: (m.data || "").slice(0, 10), tipo: m.tipo, categoria: m.categoria,
              descrizione: m.descrizione, importo: m.importo, tecnico_id: m.tecnico_id || "" });
    setOpen(true);
  };

  const save = async () => {
    try {
      const payload = { ...form, importo: Number(form.importo),
                         tecnico_id: form.tecnico_id || null };
      if (editing) { await api.patch(`/movimenti/${editing}`, payload); toast.success("Movimento aggiornato"); }
      else { await api.post("/movimenti", payload); toast.success("Movimento aggiunto"); }
      setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const del = async (m) => {
    if (!window.confirm("Eliminare il movimento?")) return;
    try { await api.delete(`/movimenti/${m.id}`); toast.success("Eliminato"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const downloadReportMensile = async () => {
    // Uses report/bilancio/pdf which now groups by month
    const from = `${year}-01-01`, to = `${year}-12-31`;
    const res = await api.get(`/report/bilancio/pdf?date_from=${from}&date_to=${to}`,
      { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a"); a.href = url;
    a.download = `Bilancio_${year}.pdf`; a.click(); URL.revokeObjectURL(url);
  };

  const entrateTot = mensile?.totali?.entrate || 0;
  const usciteTot = mensile?.totali?.uscite || 0;
  const saldoTot = mensile?.totali?.saldo || 0;
  const tecName = (tid) => tecnici.find((x) => x.id === tid)?.name || (tid === user?.id ? user.name : "—");

  return (
    <div className="space-y-6" data-testid="movimenti-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="wm-label">Contabilità</div>
          <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter mt-2">Libro Contabile</h1>
          <p className="text-white/50 mt-2 text-sm">Entrate e uscite. Le ricevute generano entrate automatiche attribuite al tecnico.</p>
        </div>
        <div className="flex items-center gap-2">
          <Label className="wm-label">Anno</Label>
          <Input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))}
            className="w-24 bg-black/40 border-white/10 h-9" data-testid="year-input" />
          {isAdmin && (
            <Button onClick={openNew} className="bg-[#007AFF] hover:bg-[#005BB5]" data-testid="add-movimento-btn">
              <Plus size={16} className="mr-1" /> Nuovo movimento
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="wm-card p-5"><div className="wm-label">Entrate {year}</div>
          <div className="mt-2 font-display text-2xl font-bold text-[#34C759]" data-testid="tot-entrate">
            {fmtEur(entrateTot)}</div></div>
        <div className="wm-card p-5"><div className="wm-label">Uscite {year}</div>
          <div className="mt-2 font-display text-2xl font-bold text-[#FF3B30]" data-testid="tot-uscite">
            {fmtEur(usciteTot)}</div></div>
        <div className="wm-card p-5"><div className="wm-label">Saldo {year}</div>
          <div className={`mt-2 font-display text-2xl font-bold ${saldoTot >= 0 ? "text-white" : "text-[#FF3B30]"}`}
            data-testid="tot-saldo">{fmtEur(saldoTot)}</div></div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <div className="flex items-center justify-between">
          <TabsList className="bg-[#0F0F13] border border-white/10">
            <TabsTrigger value="dettaglio" data-testid="tab-dettaglio">Dettaglio movimenti</TabsTrigger>
            <TabsTrigger value="mensile" data-testid="tab-mensile">Totali per mese</TabsTrigger>
          </TabsList>
          <Button variant="outline" onClick={downloadReportMensile} className="border-white/20"
            data-testid="download-report-mensile">
            <Download size={14} className="mr-1" /> Report bilancio {year} (PDF)
          </Button>
        </div>

        <TabsContent value="dettaglio" className="mt-4">
          <div className="wm-card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-white/[0.02] border-b border-white/10">
                <tr className="text-left">
                  <th className="p-3 wm-label">Data</th>
                  <th className="p-3 wm-label">Tipo</th>
                  <th className="p-3 wm-label">Categoria</th>
                  <th className="p-3 wm-label">Descrizione</th>
                  <th className="p-3 wm-label">Tecnico</th>
                  <th className="p-3 wm-label text-right">Importo</th>
                  {isAdmin && <th className="p-3 wm-label text-right">Azioni</th>}
                </tr>
              </thead>
              <tbody>
                {list.map((m) => (
                  <tr key={m.id} className="border-b border-white/5" data-testid={`movimento-row-${m.id}`}>
                    <td className="p-3">{fmtDate(m.data)}</td>
                    <td className="p-3">
                      {m.tipo === "entrata" ?
                        <span className="inline-flex items-center gap-1 text-[#34C759]"><ArrowUp size={12} /> Entrata</span> :
                        <span className="inline-flex items-center gap-1 text-[#FF3B30]"><ArrowDown size={12} /> Uscita</span>}
                    </td>
                    <td className="p-3 text-white/80">{m.categoria}</td>
                    <td className="p-3 text-white/80">{m.descrizione}</td>
                    <td className="p-3 text-white/60 text-xs">{tecName(m.tecnico_id)}</td>
                    <td className={`p-3 text-right font-semibold ${m.tipo === "entrata" ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                      {m.tipo === "entrata" ? "+" : "-"}{fmtEur(m.importo)}
                    </td>
                    {isAdmin && (
                      <td className="p-3 text-right">
                        <Button size="sm" variant="ghost" onClick={() => openEdit(m)}
                          data-testid={`edit-movimento-${m.id}`}><Pencil size={14} /></Button>
                        <Button size="sm" variant="ghost" onClick={() => del(m)}
                          className="text-[#FF3B30]" data-testid={`delete-movimento-${m.id}`}>
                          <Trash2 size={14} /></Button>
                      </td>
                    )}
                  </tr>
                ))}
                {list.length === 0 && (
                  <tr><td colSpan={isAdmin ? 7 : 6} className="p-8 text-center text-white/40">Nessun movimento</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="mensile" className="mt-4">
          <div className="wm-card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-white/[0.02] border-b border-white/10">
                <tr className="text-left">
                  <th className="p-3 wm-label">Mese</th>
                  <th className="p-3 wm-label text-center">N. movimenti</th>
                  <th className="p-3 wm-label text-right">Entrate</th>
                  <th className="p-3 wm-label text-right">Uscite</th>
                  <th className="p-3 wm-label text-right">Saldo mese</th>
                </tr>
              </thead>
              <tbody>
                {mensile?.mesi.map((m, i) => (
                  <tr key={m.mese} className="border-b border-white/5"
                    data-testid={`mensile-row-${m.mese}`}>
                    <td className="p-3 font-medium">{MESI[i]}</td>
                    <td className="p-3 text-center">{m.count}</td>
                    <td className="p-3 text-right text-[#34C759] font-semibold">
                      {m.entrate > 0 ? fmtEur(m.entrate) : "—"}
                    </td>
                    <td className="p-3 text-right text-[#FF3B30] font-semibold">
                      {m.uscite > 0 ? fmtEur(m.uscite) : "—"}
                    </td>
                    <td className={`p-3 text-right font-bold ${m.saldo >= 0 ? "text-white" : "text-[#FF3B30]"}`}>
                      {m.count > 0 ? fmtEur(m.saldo) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-white/20 bg-white/[0.03]">
                <tr>
                  <td className="p-3 font-display font-bold">Totale {year}</td>
                  <td className="p-3"></td>
                  <td className="p-3 text-right text-[#34C759] font-bold">{fmtEur(entrateTot)}</td>
                  <td className="p-3 text-right text-[#FF3B30] font-bold">{fmtEur(usciteTot)}</td>
                  <td className={`p-3 text-right font-black ${saldoTot >= 0 ? "text-white" : "text-[#FF3B30]"}`}>
                    {fmtEur(saldoTot)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </TabsContent>
      </Tabs>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0F0F13] border-white/10">
          <DialogHeader><DialogTitle className="font-display">
            {editing ? "Modifica movimento" : "Nuovo movimento"}
          </DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div><Label className="wm-label text-xs">Data</Label>
                <Input type="date" value={form.data} onChange={(e) => setForm({ ...form, data: e.target.value })}
                  className="bg-black/40 border-white/10" /></div>
              <div><Label className="wm-label text-xs">Tipo</Label>
                <Select value={form.tipo} onValueChange={(v) => setForm({ ...form, tipo: v })}>
                  <SelectTrigger className="bg-black/40 border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                    <SelectItem value="entrata">Entrata</SelectItem>
                    <SelectItem value="uscita">Uscita</SelectItem>
                  </SelectContent>
                </Select></div>
            </div>
            <div><Label className="wm-label text-xs">Categoria</Label>
              <Select value={form.categoria} onValueChange={(v) => setForm({ ...form, categoria: v })}>
                <SelectTrigger className="bg-black/40 border-white/10"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                  {CATEGORIE.map((c) => (<SelectItem key={c} value={c}>{c}</SelectItem>))}
                </SelectContent>
              </Select></div>
            <div><Label className="wm-label text-xs">Descrizione</Label>
              <Input value={form.descrizione} onChange={(e) => setForm({ ...form, descrizione: e.target.value })}
                className="bg-black/40 border-white/10" /></div>
            <div><Label className="wm-label text-xs">Importo (€)</Label>
              <Input type="number" step="0.01" value={form.importo}
                onChange={(e) => setForm({ ...form, importo: e.target.value })}
                className="bg-black/40 border-white/10" /></div>
            <div><Label className="wm-label text-xs">Attribuisci al tecnico (opzionale)</Label>
              <Select value={form.tecnico_id || "none"}
                onValueChange={(v) => setForm({ ...form, tecnico_id: v === "none" ? "" : v })}>
                <SelectTrigger className="bg-black/40 border-white/10" data-testid="movimento-tecnico-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                  <SelectItem value="none">Nessuno (generale)</SelectItem>
                  {tecnici.map((t) => (<SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>))}
                </SelectContent>
              </Select></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={save} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-movimento-btn">Salva</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
