import React, { useEffect, useState } from "react";
import { api, fmtDate, formatApiErrorDetail, todayIso } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus, Trash2, Pencil, Download, FileText } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

const TIPI = [
  { v: "assemblea", l: "Assemblea dei Soci" },
  { v: "direttivo", l: "Consiglio Direttivo" },
  { v: "altro", l: "Altro" },
];

const empty = {
  tipo: "assemblea", data: todayIso(), oggetto: "",
  contenuto: "", delibere: "",
  presenti: [], assenti: [],
};

export default function Verbali() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [list, setList] = useState([]);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(empty);
  const [presentiInput, setPresentiInput] = useState("");
  const [assentiInput, setAssentiInput] = useState("");

  const load = async () => { const { data } = await api.get("/verbali"); setList(data); };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditingId(null); setForm(empty);
    setPresentiInput(""); setAssentiInput(""); setOpen(true);
  };

  const openEdit = async (v) => {
    try {
      const { data } = await api.get(`/verbali/${v.id}`);
      setEditingId(v.id);
      setForm({ tipo: data.tipo, data: (data.data || "").slice(0, 10),
                oggetto: data.oggetto, contenuto: data.contenuto || "",
                delibere: data.delibere || "",
                presenti: data.presenti || [], assenti: data.assenti || [] });
      setPresentiInput((data.presenti || []).join(", "));
      setAssentiInput((data.assenti || []).join(", "));
      setOpen(true);
    } catch { toast.error("Errore caricamento verbale"); }
  };

  const save = async () => {
    if (!form.oggetto) { toast.error("Oggetto obbligatorio"); return; }
    const payload = {
      ...form,
      presenti: presentiInput.split(",").map((s) => s.trim()).filter(Boolean),
      assenti: assentiInput.split(",").map((s) => s.trim()).filter(Boolean),
    };
    try {
      if (editingId) { await api.patch(`/verbali/${editingId}`, payload); toast.success("Verbale aggiornato"); }
      else { await api.post("/verbali", payload); toast.success("Verbale creato"); }
      setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const del = async (v) => {
    if (!window.confirm(`Eliminare il verbale del ${fmtDate(v.data)}?`)) return;
    try { await api.delete(`/verbali/${v.id}`); toast.success("Eliminato"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const downloadPdf = async (v) => {
    try {
      const res = await api.get(`/verbali/${v.id}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `Verbale_${(v.data || "").slice(0, 10)}_${v.tipo}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    } catch { toast.error("Errore download PDF"); }
  };

  return (
    <div className="space-y-6" data-testid="verbali-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="wm-label">Registro</div>
          <h1 className="font-display text-4xl font-black tracking-tighter mt-2">Verbali & Assemblee</h1>
          <p className="text-white/50 mt-2 text-sm">Archivio dei verbali di assemblea e consiglio direttivo con esportazione PDF.</p>
        </div>
        {isAdmin && (
          <Button onClick={openNew} className="bg-[#007AFF] hover:bg-[#005BB5]"
            data-testid="add-verbale-btn">
            <Plus size={16} className="mr-1" /> Nuovo verbale
          </Button>
        )}
      </div>

      <div className="wm-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.02] border-b border-white/10">
            <tr className="text-left">
              <th className="p-3 wm-label">Data</th>
              <th className="p-3 wm-label">Tipo</th>
              <th className="p-3 wm-label">Oggetto</th>
              <th className="p-3 wm-label text-center">Presenti</th>
              <th className="p-3 wm-label text-right">Azioni</th>
            </tr>
          </thead>
          <tbody>
            {list.map((v) => (
              <tr key={v.id} className="border-b border-white/5" data-testid={`verbale-row-${v.id}`}>
                <td className="p-3">{fmtDate(v.data)}</td>
                <td className="p-3">
                  <span className="px-2 py-0.5 rounded text-xs bg-[#007AFF]/20 text-[#007AFF] border border-[#007AFF]/30">
                    {TIPI.find((t) => t.v === v.tipo)?.l || v.tipo}
                  </span>
                </td>
                <td className="p-3 font-medium">{v.oggetto}</td>
                <td className="p-3 text-center">{(v.presenti || []).length}</td>
                <td className="p-3 text-right space-x-1">
                  <Button size="sm" variant="outline" onClick={() => downloadPdf(v)}
                    data-testid={`pdf-verbale-${v.id}`} className="border-white/20 h-8">
                    <Download size={12} className="mr-1" /> PDF
                  </Button>
                  {isAdmin && (
                    <>
                      <Button size="sm" variant="ghost" onClick={() => openEdit(v)}
                        data-testid={`edit-verbale-${v.id}`}><Pencil size={13} /></Button>
                      <Button size="sm" variant="ghost" onClick={() => del(v)}
                        className="text-[#FF3B30]" data-testid={`del-verbale-${v.id}`}>
                        <Trash2 size={13} /></Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {list.length === 0 && (
              <tr><td colSpan={5} className="p-8 text-center text-white/40">Nessun verbale</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl bg-[#0F0F13] border-white/10 max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display">
            {editingId ? "Modifica verbale" : "Nuovo verbale"}
          </DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <div><Label className="wm-label text-xs">Tipo</Label>
                <Select value={form.tipo} onValueChange={(v) => setForm({ ...form, tipo: v })}>
                  <SelectTrigger className="bg-black/40 border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                    {TIPI.map((t) => <SelectItem key={t.v} value={t.v}>{t.l}</SelectItem>)}
                  </SelectContent>
                </Select></div>
              <div className="col-span-2"><Label className="wm-label text-xs">Data</Label>
                <Input type="date" value={form.data}
                  onChange={(e) => setForm({ ...form, data: e.target.value })}
                  className="bg-black/40 border-white/10" data-testid="verbale-data" /></div>
            </div>
            <div><Label className="wm-label text-xs">Oggetto *</Label>
              <Input value={form.oggetto} placeholder="Es. Approvazione bilancio 2025"
                onChange={(e) => setForm({ ...form, oggetto: e.target.value })}
                className="bg-black/40 border-white/10" data-testid="verbale-oggetto" /></div>
            <div><Label className="wm-label text-xs">Presenti (separati da virgola)</Label>
              <Input value={presentiInput} onChange={(e) => setPresentiInput(e.target.value)}
                placeholder="Es. Mario Rossi, Luigi Bianchi, ..."
                className="bg-black/40 border-white/10" data-testid="verbale-presenti" /></div>
            <div><Label className="wm-label text-xs">Assenti (separati da virgola)</Label>
              <Input value={assentiInput} onChange={(e) => setAssentiInput(e.target.value)}
                className="bg-black/40 border-white/10" data-testid="verbale-assenti" /></div>
            <div><Label className="wm-label text-xs">Svolgimento / Contenuto</Label>
              <textarea value={form.contenuto} rows={6}
                onChange={(e) => setForm({ ...form, contenuto: e.target.value })}
                className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm"
                data-testid="verbale-contenuto" /></div>
            <div><Label className="wm-label text-xs">Delibere</Label>
              <textarea value={form.delibere} rows={4}
                onChange={(e) => setForm({ ...form, delibere: e.target.value })}
                className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm"
                data-testid="verbale-delibere" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={save} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-verbale-btn">Salva</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
