import React, { useEffect, useState } from "react";
import { api, fmtEur, fmtDate, formatApiErrorDetail, todayIso } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus, Trash2, Check } from "lucide-react";
import { toast } from "sonner";

export default function Abbonamenti() {
  const [list, setList] = useState([]);
  const [tesserati, setTesserati] = useState([]);
  const [tipi, setTipi] = useState([]);
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [lezioni, setLezioni] = useState([]);
  const [form, setForm] = useState({
    tesserato_id: "", tipo_pacchetto_id: "", descrizione: "",
    num_lezioni_totali: "", prezzo: 0, data_acquisto: todayIso(),
  });

  const load = async () => {
    const [a, t, p] = await Promise.all([
      api.get("/abbonamenti"), api.get("/tesserati"), api.get("/tipi-pacchetto"),
    ]);
    setList(a.data); setTesserati(t.data); setTipi(p.data);
  };
  useEffect(() => { load(); }, []);

  const applyTipo = (tid) => {
    const t = tipi.find((x) => x.id === tid);
    if (t) setForm((f) => ({
      ...f, tipo_pacchetto_id: tid, descrizione: t.nome,
      num_lezioni_totali: t.num_lezioni ?? "", prezzo: t.prezzo_default,
    }));
  };

  const save = async () => {
    if (!form.tesserato_id || !form.descrizione) {
      toast.error("Compila tesserato e descrizione"); return;
    }
    try {
      await api.post("/abbonamenti", {
        ...form, tipo_pacchetto_id: form.tipo_pacchetto_id || null,
        num_lezioni_totali: form.num_lezioni_totali === "" ? null : Number(form.num_lezioni_totali),
        prezzo: Number(form.prezzo),
      });
      toast.success("Abbonamento creato");
      setOpen(false);
      setForm({ tesserato_id: "", tipo_pacchetto_id: "", descrizione: "",
                num_lezioni_totali: "", prezzo: 0, data_acquisto: todayIso() });
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const toggle = async (a) => {
    if (expanded === a.id) { setExpanded(null); return; }
    setExpanded(a.id);
    const { data } = await api.get(`/lezioni?abbonamento_id=${a.id}`);
    setLezioni(data);
  };

  const addLezione = async (a) => {
    try {
      await api.post("/lezioni", { abbonamento_id: a.id, data: todayIso(), note: "" });
      toast.success("Lezione registrata");
      const { data } = await api.get(`/lezioni?abbonamento_id=${a.id}`);
      setLezioni(data); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const delLezione = async (lid, aid) => {
    await api.delete(`/lezioni/${lid}`);
    const { data } = await api.get(`/lezioni?abbonamento_id=${aid}`);
    setLezioni(data); load();
  };

  return (
    <div className="space-y-6" data-testid="abbonamenti-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="wm-label">Pacchetti</div>
          <h1 className="font-display text-4xl font-black tracking-tighter mt-2">Abbonamenti</h1>
          <p className="text-white/50 mt-2 text-sm">Lezioni acquistate, effettuate e residue per ogni tesserato.</p>
        </div>
        <Button onClick={() => setOpen(true)} data-testid="add-abbonamento-btn"
          className="bg-[#007AFF] hover:bg-[#005BB5]">
          <Plus size={16} className="mr-1" /> Nuovo abbonamento
        </Button>
      </div>

      <div className="wm-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.02] border-b border-white/10">
            <tr className="text-left">
              <th className="p-3 wm-label">Tesserato</th>
              <th className="p-3 wm-label">Descrizione</th>
              <th className="p-3 wm-label">Acquisto</th>
              <th className="p-3 wm-label text-center">Totali</th>
              <th className="p-3 wm-label text-center">Effettuate</th>
              <th className="p-3 wm-label text-center">Residue</th>
              <th className="p-3 wm-label text-right">Prezzo</th>
              <th className="p-3 wm-label text-right"></th>
            </tr>
          </thead>
          <tbody>
            {list.map((a) => {
              const t = tesserati.find((x) => x.id === a.tesserato_id);
              return (
                <React.Fragment key={a.id}>
                  <tr className="border-b border-white/5 cursor-pointer" onClick={() => toggle(a)}
                    data-testid={`abbonamento-row-${a.id}`}>
                    <td className="p-3 font-medium">{t ? `${t.cognome} ${t.nome}` : "—"}</td>
                    <td className="p-3">{a.descrizione}</td>
                    <td className="p-3">{fmtDate(a.data_acquisto)}</td>
                    <td className="p-3 text-center">{a.num_lezioni_totali ?? "-"}</td>
                    <td className="p-3 text-center">{a.lezioni_effettuate}</td>
                    <td className={`p-3 text-center font-semibold ${
                      a.lezioni_residue === 0 ? "text-[#FF3B30]" :
                      a.lezioni_residue !== null && a.lezioni_residue <= 2 ? "text-[#FFCC00]" :
                      "text-[#34C759]"}`}>
                      {a.lezioni_residue ?? "-"}
                    </td>
                    <td className="p-3 text-right font-semibold">{fmtEur(a.prezzo)}</td>
                    <td className="p-3 text-right">
                      <Button size="sm" variant="outline" className="border-white/20"
                        onClick={(e) => { e.stopPropagation(); addLezione(a); }}
                        data-testid={`add-lezione-${a.id}`}>
                        <Check size={12} className="mr-1" /> Segna lezione
                      </Button>
                    </td>
                  </tr>
                  {expanded === a.id && (
                    <tr>
                      <td colSpan={8} className="p-4 bg-black/40">
                        <div className="wm-label mb-2">Lezioni effettuate</div>
                        {lezioni.length === 0 && <div className="text-white/40 text-sm">Nessuna lezione registrata.</div>}
                        <div className="space-y-1">
                          {lezioni.map((l) => (
                            <div key={l.id} className="flex justify-between items-center py-1">
                              <div className="text-sm">{fmtDate(l.data)}</div>
                              <Button size="sm" variant="ghost" className="text-[#FF3B30]"
                                onClick={() => delLezione(l.id, a.id)}>
                                <Trash2 size={12} />
                              </Button>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
            {list.length === 0 && (
              <tr><td colSpan={8} className="p-8 text-center text-white/40">Nessun abbonamento</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0F0F13] border-white/10">
          <DialogHeader><DialogTitle className="font-display">Nuovo abbonamento</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="wm-label text-xs">Tesserato *</Label>
              <Select value={form.tesserato_id} onValueChange={(v) => setForm({ ...form, tesserato_id: v })}>
                <SelectTrigger className="bg-black/40 border-white/10"><SelectValue placeholder="Seleziona" /></SelectTrigger>
                <SelectContent className="bg-[#0F0F13] border-white/10 text-white max-h-72">
                  {tesserati.map((t) => (<SelectItem key={t.id} value={t.id}>{t.cognome} {t.nome}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="wm-label text-xs">Pacchetto</Label>
              <Select value={form.tipo_pacchetto_id} onValueChange={applyTipo}>
                <SelectTrigger className="bg-black/40 border-white/10"><SelectValue placeholder="Seleziona pacchetto (opz.)" /></SelectTrigger>
                <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                  {tipi.filter((x) => x.attivo).map((t) => (
                    <SelectItem key={t.id} value={t.id}>{t.nome} — {fmtEur(t.prezzo_default)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Input placeholder="Descrizione *" value={form.descrizione}
              onChange={(e) => setForm({ ...form, descrizione: e.target.value })}
              className="bg-black/40 border-white/10" />
            <div className="grid grid-cols-3 gap-2">
              <Input type="number" placeholder="N. lezioni" value={form.num_lezioni_totali}
                onChange={(e) => setForm({ ...form, num_lezioni_totali: e.target.value })}
                className="bg-black/40 border-white/10" />
              <Input type="number" step="0.01" placeholder="Prezzo €" value={form.prezzo}
                onChange={(e) => setForm({ ...form, prezzo: e.target.value })}
                className="bg-black/40 border-white/10" />
              <Input type="date" value={form.data_acquisto}
                onChange={(e) => setForm({ ...form, data_acquisto: e.target.value })}
                className="bg-black/40 border-white/10" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={save} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-abbonamento-btn">Salva</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
