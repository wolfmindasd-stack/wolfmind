import React, { useEffect, useState } from "react";
import { api, fmtEur, fmtDate, formatApiErrorDetail, todayIso } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus, Trash2, MapPin, User as UserIcon, Users as UsersIcon, ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

export default function Abbonamenti() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [list, setList] = useState([]);
  const [tesserati, setTesserati] = useState([]);
  const [tipi, setTipi] = useState([]);
  const [tecnici, setTecnici] = useState([]);
  const [open, setOpen] = useState(false);
  const [lezioneOpen, setLezioneOpen] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [storico, setStorico] = useState(null);
  const [form, setForm] = useState({
    tesserato_id: "", tipo_pacchetto_id: "", descrizione: "",
    num_lezioni_totali: "", prezzo: 0, data_acquisto: todayIso(),
  });
  const [lezioneForm, setLezioneForm] = useState({
    data: todayIso(), luogo: "", tecnico_id: "", note: "", partecipanti: [],
  });

  const load = async () => {
    const [a, t, p, u] = await Promise.all([
      api.get("/abbonamenti"), api.get("/tesserati"),
      api.get("/tipi-pacchetto"), api.get("/users").catch(() => ({ data: [] })),
    ]);
    setList(a.data); setTesserati(t.data); setTipi(p.data);
    setTecnici(u.data.filter((x) => x.role === "tecnico" && x.active !== false));
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
      toast.success("Abbonamento creato"); setOpen(false);
      setForm({ tesserato_id: "", tipo_pacchetto_id: "", descrizione: "",
                num_lezioni_totali: "", prezzo: 0, data_acquisto: todayIso() });
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const toggle = async (a) => {
    if (expanded === a.id) { setExpanded(null); setStorico(null); return; }
    setExpanded(a.id);
    const { data } = await api.get(`/abbonamenti/${a.id}/storico`);
    setStorico(data);
  };

  const openLezione = () => {
    // Pre-fill with abbonamenti with residue > 0
    const attivi = list.filter((a) =>
      a.lezioni_residue === null || a.lezioni_residue > 0
    );
    setLezioneForm({
      data: todayIso(), luogo: "", tecnico_id: isAdmin ? "" : user.id, note: "",
      partecipanti: [],
    });
    setLezioneOpen(true);
  };

  const addPartecipante = () => {
    setLezioneForm((f) => ({ ...f, partecipanti: [...f.partecipanti, { abbonamento_id: "" }] }));
  };
  const removePartecipante = (i) => {
    setLezioneForm((f) => ({ ...f, partecipanti: f.partecipanti.filter((_, x) => x !== i) }));
  };
  const setPartecipante = (i, abbonamento_id) => {
    const ab = list.find((a) => a.id === abbonamento_id);
    setLezioneForm((f) => ({
      ...f, partecipanti: f.partecipanti.map((p, x) =>
        x === i ? { abbonamento_id, tesserato_id: ab?.tesserato_id || "" } : p),
    }));
  };

  const saveLezione = async () => {
    if (lezioneForm.partecipanti.length === 0 ||
        lezioneForm.partecipanti.some((p) => !p.abbonamento_id)) {
      toast.error("Aggiungi almeno un partecipante e seleziona l'abbonamento"); return;
    }
    try {
      await api.post("/lezioni", {
        ...lezioneForm,
        tecnico_id: lezioneForm.tecnico_id || null,
        partecipanti: lezioneForm.partecipanti.map((p) => ({
          abbonamento_id: p.abbonamento_id, tesserato_id: p.tesserato_id,
        })),
      });
      toast.success("Lezione registrata"); setLezioneOpen(false); load();
      if (expanded) { const { data } = await api.get(`/abbonamenti/${expanded}/storico`); setStorico(data); }
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const tessName = (tid) => {
    const t = tesserati.find((x) => x.id === tid);
    return t ? `${t.cognome} ${t.nome}` : "—";
  };
  const tecName = (tid) => {
    const t = tecnici.find((x) => x.id === tid);
    if (t) return t.name;
    if (tid === user.id) return user.name;
    return "—";
  };

  return (
    <div className="space-y-6" data-testid="abbonamenti-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="wm-label">Pacchetti</div>
          <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter mt-2">Abbonamenti</h1>
          <p className="text-white/50 mt-2 text-sm">Lezioni acquistate, effettuate e residue. Le lezioni possono avere più partecipanti.</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={openLezione} variant="outline" data-testid="add-lezione-btn" className="border-white/20">
            <UsersIcon size={16} className="mr-1" /> Registra lezione
          </Button>
          <Button onClick={() => setOpen(true)} data-testid="add-abbonamento-btn"
            className="bg-[#007AFF] hover:bg-[#005BB5]">
            <Plus size={16} className="mr-1" /> Nuovo abbonamento
          </Button>
        </div>
      </div>

      <div className="wm-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.02] border-b border-white/10">
            <tr className="text-left">
              <th className="p-3 wm-label w-8"></th>
              <th className="p-3 wm-label">Tesserato</th>
              <th className="p-3 wm-label">Descrizione</th>
              <th className="p-3 wm-label">Acquisto</th>
              <th className="p-3 wm-label text-center">Totali</th>
              <th className="p-3 wm-label text-center">Effettuate</th>
              <th className="p-3 wm-label text-center">Residue</th>
              <th className="p-3 wm-label text-right">Prezzo</th>
            </tr>
          </thead>
          <tbody>
            {list.map((a) => (
              <React.Fragment key={a.id}>
                <tr className="border-b border-white/5 cursor-pointer" onClick={() => toggle(a)}
                  data-testid={`abbonamento-row-${a.id}`}>
                  <td className="p-3">{expanded === a.id ?
                    <ChevronDown size={14} className="text-white/40" /> :
                    <ChevronRight size={14} className="text-white/40" />}</td>
                  <td className="p-3 font-medium">{tessName(a.tesserato_id)}</td>
                  <td className="p-3">{a.descrizione}</td>
                  <td className="p-3">{fmtDate(a.data_acquisto)}</td>
                  <td className="p-3 text-center">{a.num_lezioni_totali ?? "-"}</td>
                  <td className="p-3 text-center">{a.lezioni_effettuate}</td>
                  <td className={`p-3 text-center font-semibold ${
                    a.lezioni_residue === 0 ? "text-[#FF3B30]" :
                    a.lezioni_residue !== null && a.lezioni_residue <= 2 ? "text-[#FFCC00]" :
                    "text-[#34C759]"}`}>{a.lezioni_residue ?? "-"}</td>
                  <td className="p-3 text-right font-semibold">{fmtEur(a.prezzo)}</td>
                </tr>
                {expanded === a.id && storico && (
                  <tr>
                    <td colSpan={8} className="p-4 bg-black/40">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="wm-label mb-2">Storico lezioni ({storico.lezioni.length})</div>
                          {storico.lezioni.length === 0 && <div className="text-white/40 text-sm">Nessuna lezione.</div>}
                          <div className="space-y-1 max-h-60 overflow-y-auto">
                            {storico.lezioni.map((l) => (
                              <div key={l.id} className="text-xs bg-black/30 p-2 rounded">
                                <div className="flex justify-between">
                                  <span className="font-semibold">{fmtDate(l.data)}</span>
                                  <span className="text-white/50">{tecName(l.tecnico_id)}</span>
                                </div>
                                {l.luogo && <div className="text-white/60 mt-0.5"><MapPin size={10} className="inline mr-1" />{l.luogo}</div>}
                                <div className="text-white/50 mt-0.5">
                                  <UsersIcon size={10} className="inline mr-1" />
                                  {l.partecipanti.length} partecipante/i
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <div className="wm-label mb-2">Spesa & ricevute</div>
                          <div className="wm-card p-3 mb-2 bg-black/30">
                            <div className="wm-label text-xs">Speso per questo abbonamento</div>
                            <div className="mt-1 font-display text-xl font-bold text-[#007AFF]">
                              {fmtEur(storico.spesa_totale_abbonamento)}
                            </div>
                          </div>
                          <div className="space-y-1 max-h-40 overflow-y-auto">
                            {storico.ricevute.map((r) => (
                              <div key={r.id} className="text-xs bg-black/30 p-2 rounded flex justify-between">
                                <span className="font-mono">N.{r.numero} · {fmtDate(r.data)}</span>
                                <span className="font-semibold text-[#34C759]">{fmtEur(r.totale)}</span>
                              </div>
                            ))}
                            {storico.ricevute.length === 0 && (
                              <div className="text-white/40 text-xs">Nessuna ricevuta collegata.</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {list.length === 0 && (
              <tr><td colSpan={8} className="p-8 text-center text-white/40">Nessun abbonamento</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Nuovo abbonamento */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0F0F13] border-white/10">
          <DialogHeader><DialogTitle className="font-display">Nuovo abbonamento</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="wm-label text-xs">Tesserato *</Label>
              <Select value={form.tesserato_id} onValueChange={(v) => setForm({ ...form, tesserato_id: v })}>
                <SelectTrigger className="bg-black/40 border-white/10"><SelectValue placeholder="Seleziona" /></SelectTrigger>
                <SelectContent className="bg-[#0F0F13] border-white/10 text-white max-h-72">
                  {tesserati.map((t) => (<SelectItem key={t.id} value={t.id}>{t.cognome} {t.nome}</SelectItem>))}
                </SelectContent>
              </Select></div>
            <div><Label className="wm-label text-xs">Pacchetto</Label>
              <Select value={form.tipo_pacchetto_id} onValueChange={applyTipo}>
                <SelectTrigger className="bg-black/40 border-white/10"><SelectValue placeholder="Seleziona pacchetto (opz.)" /></SelectTrigger>
                <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                  {tipi.filter((x) => x.attivo).map((t) => (
                    <SelectItem key={t.id} value={t.id}>{t.nome} — {fmtEur(t.prezzo_default)}</SelectItem>
                  ))}
                </SelectContent>
              </Select></div>
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

      {/* Nuova lezione collettiva */}
      <Dialog open={lezioneOpen} onOpenChange={setLezioneOpen}>
        <DialogContent className="max-w-2xl bg-[#0F0F13] border-white/10 max-h-[90vh] overflow-y-auto"
          data-testid="lezione-dialog">
          <DialogHeader><DialogTitle className="font-display">Registra lezione</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <div><Label className="wm-label text-xs">Data</Label>
                <Input type="date" value={lezioneForm.data}
                  onChange={(e) => setLezioneForm({ ...lezioneForm, data: e.target.value })}
                  className="bg-black/40 border-white/10" data-testid="lezione-data" /></div>
              <div className="col-span-2"><Label className="wm-label text-xs">Luogo</Label>
                <Input value={lezioneForm.luogo}
                  onChange={(e) => setLezioneForm({ ...lezioneForm, luogo: e.target.value })}
                  placeholder="Es. Palestra comunale Front"
                  className="bg-black/40 border-white/10" data-testid="lezione-luogo" /></div>
            </div>
            <div><Label className="wm-label text-xs">Tecnico</Label>
              <Select value={lezioneForm.tecnico_id || (isAdmin ? "" : user.id)}
                onValueChange={(v) => setLezioneForm({ ...lezioneForm, tecnico_id: v })}>
                <SelectTrigger className="bg-black/40 border-white/10" data-testid="lezione-tecnico">
                  <SelectValue placeholder="Seleziona tecnico" />
                </SelectTrigger>
                <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                  {isAdmin && <SelectItem value={user.id}>{user.name} (io)</SelectItem>}
                  {tecnici.map((t) => (
                    <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select></div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label className="wm-label text-xs">Partecipanti (una lezione scalata per ognuno)</Label>
                <Button size="sm" variant="outline" onClick={addPartecipante}
                  className="border-white/20 h-7" data-testid="add-partecipante-btn">
                  <Plus size={12} className="mr-1" /> Aggiungi
                </Button>
              </div>
              <div className="space-y-2">
                {lezioneForm.partecipanti.map((p, i) => {
                  const attivi = list.filter((a) =>
                    (a.lezioni_residue === null || a.lezioni_residue > 0) ||
                    a.id === p.abbonamento_id);
                  return (
                    <div key={i} className="flex gap-2 items-center">
                      <Select value={p.abbonamento_id} onValueChange={(v) => setPartecipante(i, v)}>
                        <SelectTrigger className="bg-black/40 border-white/10 flex-1"
                          data-testid={`partecipante-${i}`}>
                          <SelectValue placeholder="Seleziona tesserato + abbonamento" />
                        </SelectTrigger>
                        <SelectContent className="bg-[#0F0F13] border-white/10 text-white max-h-72">
                          {attivi.map((a) => (
                            <SelectItem key={a.id} value={a.id}>
                              {tessName(a.tesserato_id)} — {a.descrizione}
                              {a.lezioni_residue !== null && ` (residue: ${a.lezioni_residue})`}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button size="sm" variant="ghost" onClick={() => removePartecipante(i)}
                        className="text-[#FF3B30]"><Trash2 size={14} /></Button>
                    </div>
                  );
                })}
                {lezioneForm.partecipanti.length === 0 && (
                  <div className="text-white/40 text-xs py-4 text-center">
                    Nessun partecipante. Aggiungine almeno uno.
                  </div>
                )}
              </div>
            </div>
            <div><Label className="wm-label text-xs">Note (opzionale)</Label>
              <Input value={lezioneForm.note}
                onChange={(e) => setLezioneForm({ ...lezioneForm, note: e.target.value })}
                className="bg-black/40 border-white/10" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLezioneOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={saveLezione} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-lezione-btn">Registra</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
