import React, { useEffect, useState } from "react";
import { api, fmtEur, formatApiErrorDetail } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Switch } from "../components/ui/switch";
import { Plus, Trash2, Pencil } from "lucide-react";
import { toast } from "sonner";

export default function Admin() {
  return (
    <div className="space-y-6" data-testid="admin-page">
      <div>
        <div className="wm-label">Amministrazione</div>
        <h1 className="font-display text-4xl font-black tracking-tighter mt-2">Pannello Admin</h1>



      </div>
      <Tabs defaultValue="utenti">
        <TabsList className="bg-[#0F0F13] border border-white/10">
          <TabsTrigger value="utenti" data-testid="tab-utenti">Utenti & Tecnici</TabsTrigger>
          <TabsTrigger value="pacchetti" data-testid="tab-pacchetti">Pacchetti / Listino</TabsTrigger>
          <TabsTrigger value="numerazione" data-testid="tab-numerazione">Numerazione ricevute</TabsTrigger>
          <TabsTrigger value="org" data-testid="tab-org">Dati Organizzazione</TabsTrigger>
        </TabsList>
        <TabsContent value="utenti" className="mt-4"><UtentiTab /></TabsContent>
        <TabsContent value="pacchetti" className="mt-4"><PacchettiTab /></TabsContent>
        <TabsContent value="numerazione" className="mt-4"><NumerazioneTab /></TabsContent>
        <TabsContent value="org" className="mt-4"><OrgTab /></TabsContent>
      </Tabs>
    </div>
  );
}

function NumerazioneTab() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [seq, setSeq] = useState(0);
  const [newSeq, setNewSeq] = useState(0);
  const load = async () => {
    const { data } = await api.get(`/counters/ricevute/${year}`);
    setSeq(data.seq); setNewSeq(data.seq);
  };
  useEffect(() => { load(); }, [year]);
  const save = async () => {
    if (!window.confirm(`Impostare il contatore ricevute ${year} a ${newSeq}? La prossima ricevuta sarà N. ${year}/${String(Number(newSeq) + 1).padStart(5,'0')}`)) return;
    try {
      await api.patch(`/counters/ricevute/${year}`, { seq: Number(newSeq) });
      toast.success("Numerazione aggiornata"); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  return (
    <div className="wm-card p-6 space-y-4 max-w-xl">
      <div className="text-sm text-white/70">
        Imposta manualmente il progressivo delle ricevute per un anno.
        Utile per iniziare da un numero specifico (es. da 51). Il valore rappresenta l'ultima
        ricevuta emessa; la successiva sarà quel valore +1.
      </div>
      <div className="grid grid-cols-3 gap-3 items-end">
        <div><Label className="wm-label text-xs">Anno</Label>
          <Input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))}
            className="bg-black/40 border-white/10" data-testid="numerazione-anno" /></div>
        <div><Label className="wm-label text-xs">Ultima ricevuta emessa</Label>
          <Input type="number" value={newSeq} min={0}
            onChange={(e) => setNewSeq(e.target.value)}
            className="bg-black/40 border-white/10" data-testid="numerazione-seq" /></div>
        <Button onClick={save} className="bg-[#007AFF] hover:bg-[#005BB5]"
          data-testid="save-counter-btn">Applica</Button>
      </div>
      <div className="text-xs text-white/50">
        Attualmente il contatore per l'anno {year} è a <b>{seq}</b>. Prossima ricevuta:
        <b> {year}/{String(seq + 1).padStart(5, '0')}</b>.
      </div>
    </div>
  );
}

function UtentiTab() {
  const [users, setUsers] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ email: "", name: "", password: "",
    role: "tecnico", percentuale_compenso: 50, active: true });

  const load = async () => { const { data } = await api.get("/users"); setUsers(data); };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ email: "", name: "", password: "", role: "tecnico",
              percentuale_compenso: 50, active: true });
    setOpen(true);
  };
  const openEdit = (u) => {
    setEditing(u.id);
    setForm({ email: u.email, name: u.name, password: "", role: u.role,
              percentuale_compenso: u.percentuale_compenso || 0, active: u.active !== false });
    setOpen(true);
  };
  const save = async () => {
    try {
      if (editing) {
        const payload = { name: form.name, role: form.role,
          percentuale_compenso: Number(form.percentuale_compenso), active: form.active };
        if (form.password) payload.password = form.password;
        await api.patch(`/users/${editing}`, payload);
        toast.success("Utente aggiornato");
      } else {
        await api.post("/users", { ...form,
          percentuale_compenso: Number(form.percentuale_compenso) });
        toast.success("Utente creato");
      }
      setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const del = async (u) => {
    if (!window.confirm(`Eliminare ${u.email}?`)) return;
    try { await api.delete(`/users/${u.id}`); toast.success("Eliminato"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={openNew} className="bg-[#007AFF] hover:bg-[#005BB5]"
          data-testid="add-user-btn">
          <Plus size={16} className="mr-1" /> Nuovo utente
        </Button>
      </div>
      <div className="wm-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.02] border-b border-white/10">
            <tr className="text-left">
              <th className="p-3 wm-label">Nome</th>
              <th className="p-3 wm-label">Email</th>
              <th className="p-3 wm-label">Ruolo</th>
              <th className="p-3 wm-label text-center">%</th>
              <th className="p-3 wm-label text-center">Attivo</th>
              <th className="p-3 wm-label text-right"></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-white/5" data-testid={`user-row-${u.id}`}>
                <td className="p-3 font-medium">{u.name}</td>
                <td className="p-3 text-white/70">{u.email}</td>
                <td className="p-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                    u.role === "admin" ? "bg-[#007AFF]/20 text-[#007AFF]" : "bg-white/10"
                  }`}>{u.role}</span>
                </td>
                <td className="p-3 text-center">{u.percentuale_compenso || 0}%</td>
                <td className="p-3 text-center">{u.active !== false ? "✓" : "—"}</td>
                <td className="p-3 text-right">
                  <Button size="sm" variant="ghost" onClick={() => openEdit(u)}
                    data-testid={`edit-user-${u.id}`}><Pencil size={14} /></Button>
                  <Button size="sm" variant="ghost" onClick={() => del(u)} className="text-[#FF3B30]"
                    data-testid={`delete-user-${u.id}`}><Trash2 size={14} /></Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0F0F13] border-white/10">
          <DialogHeader><DialogTitle className="font-display">
            {editing ? "Modifica utente" : "Nuovo utente"}
          </DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="wm-label text-xs">Nome</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="bg-black/40 border-white/10" data-testid="user-name-input" /></div>
            <div><Label className="wm-label text-xs">Email</Label>
              <Input type="email" value={form.email} disabled={!!editing}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="bg-black/40 border-white/10" data-testid="user-email-input" /></div>
            <div><Label className="wm-label text-xs">
              {editing ? "Nuova password (opz.)" : "Password"}
            </Label>
              <Input type="password" value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="bg-black/40 border-white/10" data-testid="user-password-input" /></div>
            <div className="grid grid-cols-2 gap-2">
              <div><Label className="wm-label text-xs">Ruolo</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger className="bg-black/40 border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                    <SelectItem value="tecnico">Tecnico</SelectItem>
                    <SelectItem value="admin">Amministratore</SelectItem>
                  </SelectContent>
                </Select></div>
              <div><Label className="wm-label text-xs">% Compenso</Label>
                <Input type="number" value={form.percentuale_compenso}
                  onChange={(e) => setForm({ ...form, percentuale_compenso: e.target.value })}
                  className="bg-black/40 border-white/10" /></div>
            </div>
            {editing && (
              <div className="flex items-center gap-2">
                <Switch checked={form.active} onCheckedChange={(v) => setForm({ ...form, active: v })} />
                <Label>Utente attivo</Label>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={save} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-user-btn">Salva</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PacchettiTab() {
  const [list, setList] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ nome: "", descrizione: "", num_lezioni: "",
    prezzo_default: 0, attivo: true, esclude_da_compensi: false });

  const load = async () => { const { data } = await api.get("/tipi-pacchetto"); setList(data); };
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm({ nome: "", descrizione: "",
    num_lezioni: "", prezzo_default: 0, attivo: true, esclude_da_compensi: false }); setOpen(true); };
  const openEdit = (p) => { setEditing(p.id); setForm({ ...p,
    num_lezioni: p.num_lezioni ?? "", esclude_da_compensi: !!p.esclude_da_compensi }); setOpen(true); };
  const save = async () => {
    try {
      const payload = { ...form,
        num_lezioni: form.num_lezioni === "" ? null : Number(form.num_lezioni),
        prezzo_default: Number(form.prezzo_default) };
      if (editing) await api.patch(`/tipi-pacchetto/${editing}`, payload);
      else await api.post("/tipi-pacchetto", payload);
      toast.success("Salvato"); setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const del = async (p) => {
    if (!window.confirm(`Eliminare "${p.nome}"?`)) return;
    await api.delete(`/tipi-pacchetto/${p.id}`); toast.success("Eliminato"); load();
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={openNew} className="bg-[#007AFF] hover:bg-[#005BB5]"
          data-testid="add-pacchetto-btn">
          <Plus size={16} className="mr-1" /> Nuovo pacchetto
        </Button>
      </div>
      <div className="wm-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.02] border-b border-white/10">
            <tr className="text-left">
              <th className="p-3 wm-label">Nome</th>
              <th className="p-3 wm-label">Descrizione</th>
              <th className="p-3 wm-label text-center">N. lezioni</th>
              <th className="p-3 wm-label text-right">Prezzo</th>
              <th className="p-3 wm-label text-center">Attivo</th>
              <th className="p-3 wm-label text-center">Compensi</th>
              <th className="p-3 wm-label text-right"></th>
            </tr>
          </thead>
          <tbody>
            {list.map((p) => (
              <tr key={p.id} className="border-b border-white/5" data-testid={`pacchetto-row-${p.id}`}>
                <td className="p-3 font-medium">{p.nome}</td>
                <td className="p-3 text-white/70">{p.descrizione}</td>
                <td className="p-3 text-center">{p.num_lezioni ?? "-"}</td>
                <td className="p-3 text-right">{fmtEur(p.prezzo_default)}</td>
                <td className="p-3 text-center">{p.attivo ? "✓" : "—"}</td>
                <td className="p-3 text-center text-xs">
                  {p.esclude_da_compensi ?
                    <span className="text-[#FFCC00]">Escluso</span> :
                    <span className="text-white/60">Incluso</span>}
                </td>
                <td className="p-3 text-right">
                  <Button size="sm" variant="ghost" onClick={() => openEdit(p)}><Pencil size={14} /></Button>
                  <Button size="sm" variant="ghost" onClick={() => del(p)} className="text-[#FF3B30]">
                    <Trash2 size={14} /></Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0F0F13] border-white/10">
          <DialogHeader><DialogTitle className="font-display">
            {editing ? "Modifica pacchetto" : "Nuovo pacchetto"}
          </DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="wm-label text-xs">Nome</Label>
              <Input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })}
                className="bg-black/40 border-white/10" data-testid="pacchetto-nome" /></div>
            <div><Label className="wm-label text-xs">Descrizione</Label>
              <Input value={form.descrizione} onChange={(e) => setForm({ ...form, descrizione: e.target.value })}
                className="bg-black/40 border-white/10" /></div>
            <div className="grid grid-cols-2 gap-2">
              <div><Label className="wm-label text-xs">Numero lezioni (vuoto = varie)</Label>
                <Input type="number" value={form.num_lezioni}
                  onChange={(e) => setForm({ ...form, num_lezioni: e.target.value })}
                  className="bg-black/40 border-white/10" /></div>
              <div><Label className="wm-label text-xs">Prezzo (€)</Label>
                <Input type="number" step="0.01" value={form.prezzo_default}
                  onChange={(e) => setForm({ ...form, prezzo_default: e.target.value })}
                  className="bg-black/40 border-white/10" data-testid="pacchetto-prezzo" /></div>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={form.attivo} onCheckedChange={(v) => setForm({ ...form, attivo: v })} />
              <Label>Attivo (mostrato in ricevute)</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={form.esclude_da_compensi}
                onCheckedChange={(v) => setForm({ ...form, esclude_da_compensi: v })}
                data-testid="pacchetto-esclude-compensi" />
              <Label>Escludi dal calcolo compensi tecnici (es. tesseramento)</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={save} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-pacchetto-btn">Salva</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function OrgTab() {
  const [org, setOrg] = useState(null);

  const load = async () => { const { data } = await api.get("/organizzazione"); setOrg(data); };
  useEffect(() => { load(); }, []);

  const save = async () => {
    try {
      const payload = { name: org.name, address: org.address, fiscal_code: org.fiscal_code,
        email: org.email, pec: org.pec, affiliation: org.affiliation,
        president_name: org.president_name, logo_base64: org.logo_base64,
        president_signature_base64: org.president_signature_base64 };
      await api.patch("/organizzazione", payload);
      toast.success("Salvato");
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const uploadLogo = (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    const reader = new FileReader();
    reader.onload = () => setOrg({ ...org, logo_base64: reader.result });
    reader.readAsDataURL(f);
  };

  const uploadSignature = (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    const reader = new FileReader();
    reader.onload = () => setOrg({ ...org, president_signature_base64: reader.result });
    reader.readAsDataURL(f);
  };

  if (!org) return <div className="text-white/50">Caricamento…</div>;

  return (
    <div className="wm-card p-6 space-y-4 max-w-2xl">
      <div className="grid grid-cols-2 gap-3">
        {[["name", "Ragione sociale"], ["fiscal_code", "Codice Fiscale"],
          ["address", "Indirizzo completo"], ["email", "Email"],
          ["pec", "PEC"], ["affiliation", "Affiliazione"],
          ["president_name", "Nome Presidente"]].map(([k, lbl]) => (
          <div key={k} className={k === "address" ? "col-span-2" : ""}>
            <Label className="wm-label text-xs">{lbl}</Label>
            <Input value={org[k] || ""} onChange={(e) => setOrg({ ...org, [k]: e.target.value })}
              className="bg-black/40 border-white/10" data-testid={`org-${k}`} />
          </div>
        ))}
      </div>
      <div>
        <Label className="wm-label text-xs">Logo (JPG/PNG)</Label>
        <div className="flex items-center gap-4 mt-2">
          {org.logo_base64 && (
            <img src={org.logo_base64} alt="logo" className="h-16 w-16 object-contain bg-white/5 rounded p-1" />
          )}
          <input type="file" accept="image/*" onChange={uploadLogo} data-testid="org-logo-upload"
            className="text-sm text-white/60" />
          {org.logo_base64 && (
            <Button size="sm" variant="ghost" className="text-[#FF3B30]"
              onClick={() => setOrg({ ...org, logo_base64: null })}>Rimuovi</Button>
          )}
        </div>
      </div>
      <div>
        <Label className="wm-label text-xs">Firma digitalizzata Presidente (PNG con sfondo trasparente consigliato)</Label>
        <div className="flex items-center gap-4 mt-2">
          {org.president_signature_base64 && (
            <img src={org.president_signature_base64} alt="signature"
              className="h-14 w-40 object-contain bg-white/95 rounded p-1" />
          )}
          <input type="file" accept="image/*" onChange={uploadSignature}
            data-testid="org-signature-upload" className="text-sm text-white/60" />
          {org.president_signature_base64 && (
            <Button size="sm" variant="ghost" className="text-[#FF3B30]"
              onClick={() => setOrg({ ...org, president_signature_base64: null })}>Rimuovi</Button>
          )}
        </div>
        <div className="text-xs text-white/40 mt-1">
          La firma apparirà sopra il nome del Presidente in ogni ricevuta PDF.
        </div>
      </div>
      <div className="flex justify-end">
        <Button onClick={save} className="bg-[#007AFF] hover:bg-[#005BB5]"
          data-testid="save-org-btn">Salva</Button>
      </div>
    </div>
  );
}
