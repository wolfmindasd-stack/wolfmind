import React, { useEffect, useState } from "react";
import { api, fmtEur, fmtDate, formatApiErrorDetail, todayIso } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus, Trash2, Pencil, ArrowUp, ArrowDown } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

const CATEGORIE = [
  "Ricevuta", "Iscrizione", "Sponsor", "Contributo",
  "Compenso tecnico", "Acquisto materiali", "Affitto", "Utenze",
  "Manutenzione", "Assicurazione", "Federazione", "Altro",
];

export default function Movimenti() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [tecnici, setTecnici] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    data: todayIso(), tipo: "uscita", categoria: "Altro",
    descrizione: "", importo: 0, tecnico_id: "",
  });

  const load = async () => {
    const [m, u] = await Promise.all([
      api.get("/movimenti"),
      user?.role === "admin" ? api.get("/users") : Promise.resolve({ data: [] }),
    ]);
    setList(m.data);
    setTecnici(u.data.filter((x) => x.role === "tecnico"));
  };
  useEffect(() => { load(); }, []);

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
      if (editing) {
        await api.patch(`/movimenti/${editing}`, payload);
        toast.success("Movimento aggiornato");
      } else {
        await api.post("/movimenti", payload);
        toast.success("Movimento aggiunto");
      }
      setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const del = async (m) => {
    if (!window.confirm("Eliminare il movimento?")) return;
    try {
      await api.delete(`/movimenti/${m.id}`);
      toast.success("Eliminato"); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const entrate = list.filter((m) => m.tipo === "entrata").reduce((s, m) => s + m.importo, 0);
  const uscite = list.filter((m) => m.tipo === "uscita").reduce((s, m) => s + m.importo, 0);

  return (
    <div className="space-y-6" data-testid="movimenti-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="wm-label">Contabilità</div>
          <h1 className="font-display text-4xl font-black tracking-tighter mt-2">Libro Contabile</h1>
          <p className="text-white/50 mt-2 text-sm">Entrate e uscite dell'associazione. Le ricevute generano entrate automatiche.</p>
        </div>
        {user?.role === "admin" && (
          <Button onClick={openNew} className="bg-[#007AFF] hover:bg-[#005BB5]"
            data-testid="add-movimento-btn">
            <Plus size={16} className="mr-1" /> Nuovo movimento
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="wm-card p-5"><div className="wm-label">Entrate</div>
          <div className="mt-2 font-display text-2xl font-bold text-[#34C759]">{fmtEur(entrate)}</div></div>
        <div className="wm-card p-5"><div className="wm-label">Uscite</div>
          <div className="mt-2 font-display text-2xl font-bold text-[#FF3B30]">{fmtEur(uscite)}</div></div>
        <div className="wm-card p-5"><div className="wm-label">Saldo</div>
          <div className={`mt-2 font-display text-2xl font-bold ${entrate - uscite >= 0 ? "text-white" : "text-[#FF3B30]"}`}>
            {fmtEur(entrate - uscite)}</div></div>
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
              {user?.role === "admin" && <th className="p-3 wm-label text-right">Azioni</th>}
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
                <td className={`p-3 text-right font-semibold ${m.tipo === "entrata" ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                  {m.tipo === "entrata" ? "+" : "-"}{fmtEur(m.importo)}
                </td>
                {user?.role === "admin" && (
                  <td className="p-3 text-right">
                    <Button size="sm" variant="ghost" onClick={() => openEdit(m)}
                      data-testid={`edit-movimento-${m.id}`}><Pencil size={14} /></Button>
                    <Button size="sm" variant="ghost" onClick={() => del(m)}
                      className="text-[#FF3B30]" data-testid={`delete-movimento-${m.id}`}>
                      <Trash2 size={14} />
                    </Button>
                  </td>
                )}
              </tr>
            ))}
            {list.length === 0 && (
              <tr><td colSpan={6} className="p-8 text-center text-white/40">Nessun movimento</td></tr>
            )}
          </tbody>
        </table>
      </div>

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
            {form.tipo === "uscita" && tecnici.length > 0 && (
              <div><Label className="wm-label text-xs">Tecnico (per compensi)</Label>
                <Select value={form.tecnico_id} onValueChange={(v) => setForm({ ...form, tecnico_id: v })}>
                  <SelectTrigger className="bg-black/40 border-white/10"><SelectValue placeholder="Nessuno" /></SelectTrigger>
                  <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                    {tecnici.map((t) => (<SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>))}
                  </SelectContent>
                </Select></div>
            )}
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
