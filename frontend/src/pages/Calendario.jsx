import React, { useEffect, useState } from "react";
import { api, fmtDate, formatApiErrorDetail, todayIso } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Switch } from "../components/ui/switch";
import { Plus, Trash2, MapPin, Clock, Users as UsersIcon, Repeat } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

const DAYS = ["Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"];
const MONTH_NAMES = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
                      "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"];

function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function fmtIso(d) { return d.toISOString().slice(0, 10); }

export default function Calendario() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [slots, setSlots] = useState([]);
  const [tesserati, setTesserati] = useState([]);
  const [tecnici, setTecnici] = useState([]);
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date(); const dow = d.getDay();
    return addDays(d, -((dow + 6) % 7)); // Monday
  });
  const [open, setOpen] = useState(false);
  const [prenOpen, setPrenOpen] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [form, setForm] = useState({
    data: todayIso(), ora: "18:00", durata_min: 60, luogo: "",
    tecnico_id: user?.id || "", capacita: 8, descrizione: "",
    ricorrenza_settimanale: false, ricorrenza_fino_al: "",
  });
  const [prenForm, setPrenForm] = useState({ tesserato_id: "" });

  const load = async () => {
    const from = fmtIso(weekStart);
    const to = fmtIso(addDays(weekStart, 27));
    const [s, t, u] = await Promise.all([
      api.get(`/calendario?date_from=${from}&date_to=${to}`),
      api.get("/tesserati"),
      api.get("/users").catch(() => ({ data: [] })),
    ]);
    setSlots(s.data); setTesserati(t.data);
    setTecnici(u.data.filter((x) => x.role === "tecnico" && x.active !== false));
  };
  useEffect(() => { load(); }, [weekStart]);

  const days = Array.from({ length: 28 }, (_, i) => addDays(weekStart, i));

  const slotsByDay = {};
  slots.forEach((s) => {
    slotsByDay[s.data] = slotsByDay[s.data] || [];
    slotsByDay[s.data].push(s);
  });
  Object.values(slotsByDay).forEach(arr => arr.sort((a, b) => a.ora.localeCompare(b.ora)));

  const openNewSlot = (data) => {
    setForm({ data: data || todayIso(), ora: "18:00", durata_min: 60, luogo: "",
              tecnico_id: user.id, capacita: 8, descrizione: "",
              ricorrenza_settimanale: false, ricorrenza_fino_al: "" });
    setOpen(true);
  };
  const saveSlot = async () => {
    if (!form.data || !form.ora) { toast.error("Data e ora obbligatorie"); return; }
    if (form.ricorrenza_settimanale && !form.ricorrenza_fino_al) {
      toast.error("Se attivi ricorrenza indica data fine"); return;
    }
    try {
      const { data } = await api.post("/calendario", {
        ...form, durata_min: Number(form.durata_min), capacita: Number(form.capacita),
        tecnico_id: form.tecnico_id || null,
        ricorrenza_fino_al: form.ricorrenza_settimanale ? form.ricorrenza_fino_al : null,
      });
      toast.success(`Slot creato: ${data.created} occorrenza/e`);
      setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const delSlot = async (s) => {
    if (!window.confirm("Eliminare questo slot?")) return;
    try { await api.delete(`/calendario/${s.id}`); toast.success("Slot eliminato"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const openPrenota = (s) => { setSelectedSlot(s); setPrenForm({ tesserato_id: "" }); setPrenOpen(true); };
  const doPrenota = async () => {
    if (!prenForm.tesserato_id) { toast.error("Seleziona un tesserato"); return; }
    try {
      await api.post("/calendario/prenota", {
        slot_id: selectedSlot.id, tesserato_id: prenForm.tesserato_id,
      });
      toast.success("Prenotazione registrata (email di conferma inviata)");
      setPrenOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const cancelPrenot = async (s, tid) => {
    if (!window.confirm("Annullare prenotazione?")) return;
    try {
      await api.delete(`/calendario/prenota/${s.id}/${tid}`);
      toast.success("Prenotazione annullata"); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const tecName = (tid) => tecnici.find((x) => x.id === tid)?.name ||
                            (tid === user?.id ? user.name : "—");

  return (
    <div className="space-y-6" data-testid="calendario-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="wm-label">Pianificazione</div>
          <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter mt-2">Calendario Lezioni</h1>
          <p className="text-white/50 mt-2 text-sm">
            {isAdmin ? "Crea slot con ricorrenza settimanale e prenota partecipanti." :
                       "Crea le tue lezioni. Ricorrenza settimanale disponibile."}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" onClick={() => setWeekStart(addDays(weekStart, -7))}
            className="border-white/20 h-9 px-3" data-testid="prev-week">←</Button>
          <div className="wm-label text-xs px-2 hidden sm:block">
            {weekStart.toLocaleDateString("it-IT")} → {addDays(weekStart, 27).toLocaleDateString("it-IT")}
          </div>
          <Button variant="outline" onClick={() => setWeekStart(addDays(weekStart, 7))}
            className="border-white/20 h-9 px-3" data-testid="next-week">→</Button>
          <Button onClick={() => openNewSlot()} className="bg-[#007AFF] hover:bg-[#005BB5]"
            data-testid="add-slot-btn">
            <Plus size={16} className="mr-1" /> Nuovo slot
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
        {days.map((d) => {
          const iso = fmtIso(d);
          const daySlots = slotsByDay[iso] || [];
          const isPast = d < new Date(new Date().setHours(0, 0, 0, 0));
          return (
            <div key={iso} className={`wm-card p-2 min-h-32 ${isPast ? "opacity-60" : ""}`}
              data-testid={`day-${iso}`}>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <div className="wm-label text-[10px]">{DAYS[d.getDay()]}</div>
                  <div className="font-display font-bold">{d.getDate()}</div>
                  <div className="text-[10px] text-white/40">{MONTH_NAMES[d.getMonth()].slice(0,3)}</div>
                </div>
                <button onClick={() => openNewSlot(iso)} data-testid={`add-slot-${iso}`}
                  className="text-white/40 hover:text-[#007AFF] transition-colors">
                  <Plus size={14} />
                </button>
              </div>
              <div className="space-y-1">
                {daySlots.map((s) => {
                  const full = s.prenotazioni.length >= s.capacita;
                  return (
                    <div key={s.id}
                      className="bg-[#007AFF]/10 border border-[#007AFF]/30 rounded p-1.5 text-xs"
                      data-testid={`slot-${s.id}`}>
                      <div className="flex items-center justify-between font-bold">
                        <span className="flex items-center gap-1"><Clock size={10} />{s.ora}</span>
                        {(isAdmin || s.tecnico_id === user?.id) && (
                          <button onClick={() => delSlot(s)} className="text-[#FF3B30]/70 hover:text-[#FF3B30]"
                            data-testid={`del-slot-${s.id}`}>
                            <Trash2 size={10} />
                          </button>
                        )}
                      </div>
                      <div className="text-white/70">{s.descrizione || "Lezione"}</div>
                      {s.luogo && <div className="text-white/50 text-[10px]"><MapPin size={8} className="inline" /> {s.luogo}</div>}
                      <div className="text-white/50 text-[10px]">{tecName(s.tecnico_id)}</div>
                      <div className={`text-[10px] ${full ? "text-[#FF3B30]" : "text-[#34C759]"}`}>
                        <UsersIcon size={9} className="inline" /> {s.prenotazioni.length}/{s.capacita}
                      </div>
                      {s.prenotazioni.length > 0 && (
                        <div className="mt-1 space-y-0.5">
                          {s.prenotazioni.map((p) => (
                            <div key={p.tesserato_id} className="flex justify-between items-center text-[10px]">
                              <span className="truncate">{p.tesserato_nome}</span>
                              {(isAdmin || s.tecnico_id === user?.id) && (
                                <button onClick={() => cancelPrenot(s, p.tesserato_id)}
                                  className="text-[#FF3B30]/60 hover:text-[#FF3B30]"><Trash2 size={8} /></button>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      {!full && !isPast && (
                        <button onClick={() => openPrenota(s)}
                          data-testid={`prenota-${s.id}`}
                          className="mt-1 w-full bg-[#007AFF] hover:bg-[#005BB5] text-white text-[10px]
                                     rounded px-1.5 py-0.5 font-semibold">
                          Prenota
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Nuovo slot */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0F0F13] border-white/10 max-w-lg">
          <DialogHeader><DialogTitle className="font-display">Nuovo slot lezione</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div><Label className="wm-label text-xs">Data</Label>
                <Input type="date" value={form.data}
                  onChange={(e) => setForm({ ...form, data: e.target.value })}
                  className="bg-black/40 border-white/10" data-testid="slot-data" /></div>
              <div><Label className="wm-label text-xs">Ora</Label>
                <Input type="time" value={form.ora}
                  onChange={(e) => setForm({ ...form, ora: e.target.value })}
                  className="bg-black/40 border-white/10" data-testid="slot-ora" /></div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div><Label className="wm-label text-xs">Durata (min)</Label>
                <Input type="number" value={form.durata_min}
                  onChange={(e) => setForm({ ...form, durata_min: e.target.value })}
                  className="bg-black/40 border-white/10" /></div>
              <div><Label className="wm-label text-xs">Capacità</Label>
                <Input type="number" value={form.capacita}
                  onChange={(e) => setForm({ ...form, capacita: e.target.value })}
                  className="bg-black/40 border-white/10" /></div>
            </div>
            <div><Label className="wm-label text-xs">Luogo</Label>
              <Input value={form.luogo} placeholder="Es. Palestra comunale Front"
                onChange={(e) => setForm({ ...form, luogo: e.target.value })}
                className="bg-black/40 border-white/10" data-testid="slot-luogo" /></div>
            <div><Label className="wm-label text-xs">Descrizione</Label>
              <Input value={form.descrizione} placeholder="Es. Corso principianti"
                onChange={(e) => setForm({ ...form, descrizione: e.target.value })}
                className="bg-black/40 border-white/10" /></div>
            {isAdmin && (
              <div><Label className="wm-label text-xs">Tecnico</Label>
                <Select value={form.tecnico_id} onValueChange={(v) => setForm({ ...form, tecnico_id: v })}>
                  <SelectTrigger className="bg-black/40 border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                    <SelectItem value={user.id}>{user.name} (io)</SelectItem>
                    {tecnici.map((t) => (<SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>))}
                  </SelectContent>
                </Select></div>
            )}
            <div className="pt-2 border-t border-white/10 space-y-2">
              <div className="flex items-center gap-2">
                <Switch checked={form.ricorrenza_settimanale}
                  onCheckedChange={(v) => setForm({ ...form, ricorrenza_settimanale: v })}
                  data-testid="slot-ricorrenza" />
                <Label className="flex items-center gap-1">
                  <Repeat size={14} /> Ripeti ogni settimana
                </Label>
              </div>
              {form.ricorrenza_settimanale && (
                <div><Label className="wm-label text-xs">Fino al</Label>
                  <Input type="date" value={form.ricorrenza_fino_al}
                    onChange={(e) => setForm({ ...form, ricorrenza_fino_al: e.target.value })}
                    className="bg-black/40 border-white/10" data-testid="slot-fine" /></div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={saveSlot} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-slot-btn">Crea</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Prenota */}
      <Dialog open={prenOpen} onOpenChange={setPrenOpen}>
        <DialogContent className="bg-[#0F0F13] border-white/10">
          <DialogHeader><DialogTitle className="font-display">Prenota partecipante</DialogTitle></DialogHeader>
          {selectedSlot && (
            <div className="text-sm text-white/70">
              <div><b>{fmtDate(selectedSlot.data)} · {selectedSlot.ora}</b></div>
              <div>{selectedSlot.descrizione || "Lezione"} · {selectedSlot.luogo}</div>
            </div>
          )}
          <div>
            <Label className="wm-label text-xs">Tesserato</Label>
            <Select value={prenForm.tesserato_id}
              onValueChange={(v) => setPrenForm({ tesserato_id: v })}>
              <SelectTrigger className="bg-black/40 border-white/10"
                data-testid="prenota-tesserato-select"><SelectValue placeholder="Seleziona" /></SelectTrigger>
              <SelectContent className="bg-[#0F0F13] border-white/10 text-white max-h-72">
                {tesserati.map((t) => (
                  <SelectItem key={t.id} value={t.id}>{t.cognome} {t.nome}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="text-xs text-white/50">
            Verrà inviata email di conferma a tesserato, tecnico e amministratore.
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPrenOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={doPrenota} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="confirm-prenota-btn">Conferma prenotazione</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
