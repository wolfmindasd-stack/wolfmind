import React, { useEffect, useState } from "react";
import { api, fmtEur, fmtDate, formatApiErrorDetail, todayIso } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus, Trash2, Download, Mail, MessageCircle, Eye, Pencil } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

const emptyItem = { descrizione: "", num_lezioni: "", importo: 0,
                    tipo_pacchetto_id: "", esclude_da_compensi: false };

async function fetchPdfBlob(rid) {
  const res = await api.get(`/ricevute/${rid}/pdf`, { responseType: "blob" });
  return res.data;
}

export default function Ricevute() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [list, setList] = useState([]);
  const [tesserati, setTesserati] = useState([]);
  const [tipi, setTipi] = useState([]);
  const [tecnici, setTecnici] = useState([]);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [emailOpen, setEmailOpen] = useState(false);
  const [selectedRid, setSelectedRid] = useState(null);
  const [emailTo, setEmailTo] = useState("");
  const [emailMessage, setEmailMessage] = useState("");
  const [form, setForm] = useState({
    tesserato_id: "", data: todayIso(), metodo_pagamento: "Contanti",
    items: [{ ...emptyItem }], note: "", emesso_per_id: "",
  });

  const load = async () => {
    const [r, t, p, u] = await Promise.all([
      api.get("/ricevute"), api.get("/tesserati"),
      api.get("/tipi-pacchetto"), api.get("/users").catch(() => ({ data: [] })),
    ]);
    setList(r.data); setTesserati(t.data); setTipi(p.data);
    setTecnici(u.data.filter((x) => x.role === "tecnico" && x.active !== false));
  };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditingId(null);
    setForm({ tesserato_id: "", data: todayIso(), metodo_pagamento: "Contanti",
              items: [{ ...emptyItem }], note: "", emesso_per_id: "" });
    setOpen(true);
  };

  const openEdit = (r) => {
    setEditingId(r.id);
    setForm({
      tesserato_id: r.tesserato_id, data: (r.data || "").slice(0, 10),
      metodo_pagamento: r.metodo_pagamento || "Contanti",
      items: r.items.map((i) => ({
        descrizione: i.descrizione, num_lezioni: i.num_lezioni ?? "",
        importo: i.importo, tipo_pacchetto_id: i.tipo_pacchetto_id || "",
        esclude_da_compensi: !!i.esclude_da_compensi,
      })),
      note: r.note || "", emesso_per_id: r.emesso_per_id || "",
    });
    setOpen(true);
  };

  const addItem = () => setForm((f) => ({ ...f, items: [...f.items, { ...emptyItem }] }));
  const removeItem = (i) => setForm((f) => ({ ...f, items: f.items.filter((_, x) => x !== i) }));
  const updateItem = (i, patch) => setForm((f) => ({
    ...f, items: f.items.map((it, x) => x === i ? { ...it, ...patch } : it)
  }));
  const applyTipo = (i, tipoId) => {
    const t = tipi.find((x) => x.id === tipoId);
    if (t) updateItem(i, {
      descrizione: t.nome, num_lezioni: t.num_lezioni ?? "",
      importo: t.prezzo_default, tipo_pacchetto_id: t.id,
      esclude_da_compensi: !!t.esclude_da_compensi,
    });
  };

  const total = form.items.reduce((s, it) => s + Number(it.importo || 0), 0);

  const save = async () => {
    if (!form.tesserato_id) { toast.error("Seleziona un tesserato"); return; }
    if (form.items.some((i) => !i.descrizione || !i.importo)) {
      toast.error("Compila descrizione e importo per ogni riga"); return;
    }
    try {
      const payload = {
        ...form,
        emesso_per_id: form.emesso_per_id || null,
        items: form.items.map((i) => ({
          descrizione: i.descrizione,
          num_lezioni: i.num_lezioni === "" ? null : Number(i.num_lezioni),
          importo: Number(i.importo),
          tipo_pacchetto_id: i.tipo_pacchetto_id || null,
          esclude_da_compensi: !!i.esclude_da_compensi,
        })),
      };
      if (editingId) {
        await api.patch(`/ricevute/${editingId}`, payload);
        toast.success("Ricevuta aggiornata");
      } else {
        await api.post("/ricevute", payload);
        toast.success("Ricevuta creata");
      }
      setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const downloadPdf = async (r) => {
    try {
      const blob = await fetchPdfBlob(r.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `Ricevuta_${r.numero.replace("/", "-")}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e) { toast.error("Errore download PDF"); }
  };

  const viewPdf = async (r) => {
    try {
      const blob = await fetchPdfBlob(r.id);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) { toast.error("Errore apertura PDF"); }
  };

  const openEmail = (r) => {
    setSelectedRid(r.id);
    const t = tesserati.find((x) => x.id === r.tesserato_id);
    setEmailTo(t?.email || ""); setEmailMessage(""); setEmailOpen(true);
  };

  const sendEmail = async () => {
    try {
      await api.post(`/ricevute/${selectedRid}/send-email`,
        { email: emailTo, message: emailMessage });
      toast.success("Email inviata con link alla ricevuta"); setEmailOpen(false);
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const shareWhatsApp = async (r) => {
    try {
      const { data } = await api.get(`/ricevute/${r.id}/whatsapp-link`);
      window.open(data.url, "_blank");
      await api.post(`/ricevute/${r.id}/mark-whatsapp`);
      toast.info("Link ricevuta incluso nel messaggio WhatsApp.");
      load();
    } catch (e) { toast.error("Errore WhatsApp"); }
  };

  const del = async (r) => {
    if (!window.confirm(`Eliminare definitivamente la ricevuta N.${r.numero}? La numerazione verrà scalata se è l'ultima emessa.`)) return;
    try {
      const { data } = await api.delete(`/ricevute/${r.id}`);
      toast.success(data.numero_riutilizzabile ? "Ricevuta eliminata, numerazione riutilizzabile" : "Ricevuta eliminata");
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="space-y-6" data-testid="ricevute-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="wm-label">Gestione</div>
          <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter mt-2">Ricevute</h1>
          <p className="text-white/50 mt-2 text-sm">
            Numerazione unica condivisa. {isAdmin && "Come admin puoi attribuire la ricevuta a un tecnico specifico."}
          </p>
        </div>
        <Button onClick={openNew} data-testid="add-ricevuta-btn" className="bg-[#007AFF] hover:bg-[#005BB5]">
          <Plus size={16} className="mr-1" /> Nuova ricevuta
        </Button>
      </div>

      <div className="wm-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.02] border-b border-white/10">
            <tr className="text-left">
              <th className="p-3 wm-label">Numero</th>
              <th className="p-3 wm-label">Data</th>
              <th className="p-3 wm-label">Tesserato</th>
              <th className="p-3 wm-label">Emessa per</th>
              <th className="p-3 wm-label text-right">Totale</th>
              <th className="p-3 wm-label text-right">Azioni</th>
            </tr>
          </thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.id} className={`border-b border-white/5 ${r.annullata ? "opacity-40" : ""}`}
                data-testid={`ricevuta-row-${r.id}`}>
                <td className="p-3 font-mono font-semibold">{r.numero}
                  {r.annullata && <span className="ml-2 text-xs text-[#FF3B30]">ANNULLATA</span>}</td>
                <td className="p-3">{fmtDate(r.data)}</td>
                <td className="p-3">{r.tesserato_nome}</td>
                <td className="p-3 text-white/70">{r.emesso_per_nome || r.emesso_da_nome}</td>
                <td className="p-3 text-right font-semibold">{fmtEur(r.totale)}</td>
                <td className="p-3 text-right whitespace-nowrap">
                  <div className="inline-flex flex-wrap gap-1 justify-end">
                  <Button variant="outline" size="sm" onClick={() => viewPdf(r)}
                    data-testid={`view-pdf-${r.id}`} className="border-white/20 h-8">
                    <Eye size={13} className="mr-1" /> PDF
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => downloadPdf(r)}
                    data-testid={`download-pdf-${r.id}`} className="border-white/20 h-8">
                    <Download size={13} />
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => openEmail(r)}
                    data-testid={`email-ricevuta-${r.id}`}
                    className={`h-8 ${r.last_sent_email_at ?
                      "border-[#34C759] text-[#34C759] hover:bg-[#34C759]/10 bg-[#34C759]/5" :
                      "border-[#007AFF]/40 text-[#007AFF] hover:bg-[#007AFF]/10"}`}>
                    <Mail size={13} className="mr-1" />
                    {r.last_sent_email_at ? "Inviata" : "Email"}
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => shareWhatsApp(r)}
                    data-testid={`whatsapp-${r.id}`}
                    className={`h-8 ${r.last_sent_whatsapp_at ?
                      "border-[#25D366] text-white bg-[#25D366]/20 hover:bg-[#25D366]/30" :
                      "border-[#25D366]/40 text-[#25D366] hover:bg-[#25D366]/10"}`}>
                    <MessageCircle size={13} className="mr-1" />
                    {r.last_sent_whatsapp_at ? "Condivisa" : "WhatsApp"}
                  </Button>
                  {isAdmin && (
                    <>
                      <Button variant="ghost" size="sm" onClick={() => openEdit(r)}
                        data-testid={`edit-ricevuta-${r.id}`} className="h-8"><Pencil size={13} /></Button>
                      <Button variant="ghost" size="sm" onClick={() => del(r)}
                        className="text-[#FF3B30] h-8" data-testid={`delete-ricevuta-${r.id}`}>
                        <Trash2 size={13} />
                      </Button>
                    </>
                  )}
                  </div>
                </td>
              </tr>
            ))}
            {list.length === 0 && (
              <tr><td colSpan={6} className="p-8 text-center text-white/40">
                Nessuna ricevuta. Clicca "Nuova ricevuta" per iniziare.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Nuova/edit ricevuta dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl bg-[#0F0F13] border-white/10 max-h-[90vh] overflow-y-auto"
          data-testid="ricevuta-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">
              {editingId ? "Modifica ricevuta" : "Nuova ricevuta"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2 space-y-1">
                <Label className="wm-label text-xs">Tesserato *</Label>
                <Select value={form.tesserato_id}
                  onValueChange={(v) => setForm({ ...form, tesserato_id: v })}>
                  <SelectTrigger className="bg-black/40 border-white/10" data-testid="select-tesserato">
                    <SelectValue placeholder="Seleziona tesserato" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0F0F13] border-white/10 text-white max-h-72">
                    {tesserati.map((t) => (
                      <SelectItem key={t.id} value={t.id}>{t.cognome} {t.nome}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="wm-label text-xs">Data *</Label>
                <Input type="date" value={form.data} data-testid="ricevuta-data"
                  onChange={(e) => setForm({ ...form, data: e.target.value })}
                  className="bg-black/40 border-white/10" />
              </div>
            </div>

            {isAdmin && tecnici.length > 0 && (
              <div>
                <Label className="wm-label text-xs">Emessa per (tecnico) — flusso cassa attribuito</Label>
                <Select value={form.emesso_per_id || "self"}
                  onValueChange={(v) => setForm({ ...form, emesso_per_id: v === "self" ? "" : v })}>
                  <SelectTrigger className="bg-black/40 border-white/10" data-testid="select-emesso-per">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                    <SelectItem value="self">Me stesso ({user?.name})</SelectItem>
                    {tecnici.map((t) => (
                      <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label className="wm-label text-xs">Voci</Label>
              {form.items.map((it, i) => (
                <div key={i} className="space-y-2 p-3 bg-black/30 rounded">
                  <div className="grid grid-cols-2 sm:grid-cols-12 gap-2 items-end">
                    <div className="col-span-2 sm:col-span-3">
                      <Select value={it.tipo_pacchetto_id || ""} onValueChange={(v) => applyTipo(i, v)}>
                        <SelectTrigger className="bg-black/40 border-white/10 h-9 text-xs"
                          data-testid={`select-tipo-${i}`}>
                          <SelectValue placeholder="Pacchetto…" />
                        </SelectTrigger>
                        <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                          {tipi.filter((x) => x.attivo).map((t) => (
                            <SelectItem key={t.id} value={t.id}>{t.nome}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <Input className="col-span-2 sm:col-span-3 bg-black/40 border-white/10 h-9"
                      placeholder="Descrizione" value={it.descrizione}
                      onChange={(e) => updateItem(i, { descrizione: e.target.value })}
                      data-testid={`item-descrizione-${i}`} />
                    <Input className="col-span-1 sm:col-span-2 bg-black/40 border-white/10 h-9"
                      type="number" placeholder="Lez." value={it.num_lezioni}
                      onChange={(e) => updateItem(i, { num_lezioni: e.target.value })}
                      data-testid={`item-lezioni-${i}`} />
                    <Input className="col-span-1 sm:col-span-3 bg-black/40 border-white/10 h-9 text-right font-semibold"
                      type="number" step="0.01" placeholder="Importo €" value={it.importo}
                      onChange={(e) => updateItem(i, { importo: e.target.value })}
                      data-testid={`item-importo-${i}`} />
                    <Button variant="ghost" size="sm" className="col-span-2 sm:col-span-1 text-[#FF3B30] justify-self-end"
                      onClick={() => removeItem(i)} disabled={form.items.length === 1}>
                      <Trash2 size={14} />
                    </Button>
                  </div>
                  <label className="flex items-center gap-2 text-xs text-white/60 cursor-pointer">
                    <input type="checkbox" checked={!!it.esclude_da_compensi}
                      onChange={(e) => updateItem(i, { esclude_da_compensi: e.target.checked })}
                      data-testid={`item-esclude-${i}`} />
                    Escludi questa voce dal calcolo dei compensi (es. tesseramento)
                  </label>
                </div>
              ))}
              <Button variant="outline" size="sm" onClick={addItem}
                className="border-white/20" data-testid="add-item-btn">
                <Plus size={14} className="mr-1" /> Aggiungi voce
              </Button>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <Label className="wm-label text-xs">Metodo pagamento</Label>
                <Select value={form.metodo_pagamento}
                  onValueChange={(v) => setForm({ ...form, metodo_pagamento: v })}>
                  <SelectTrigger className="bg-black/40 border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                    {["Contanti", "Bonifico", "Carta", "POS", "Assegno"].map((m) => (
                      <SelectItem key={m} value={m}>{m}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="col-span-2 space-y-1">
                <Label className="wm-label text-xs">Note</Label>
                <Input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })}
                  className="bg-black/40 border-white/10" data-testid="ricevuta-note" />
              </div>
            </div>

            <div className="pt-3 border-t border-white/10 flex justify-between items-center">
              <div className="wm-label">Totale</div>
              <div className="font-display text-2xl font-black text-[#007AFF]"
                data-testid="ricevuta-total">{fmtEur(total)}</div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={save} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-ricevuta-btn">
              {editingId ? "Salva modifiche" : "Emetti ricevuta"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={emailOpen} onOpenChange={setEmailOpen}>
        <DialogContent className="bg-[#0F0F13] border-white/10" data-testid="email-dialog">
          <DialogHeader><DialogTitle className="font-display">Invia ricevuta via email</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="wm-label text-xs">Destinatario</Label>
              <Input value={emailTo} onChange={(e) => setEmailTo(e.target.value)}
                type="email" className="bg-black/40 border-white/10" data-testid="email-to-input" />
            </div>
            <div>
              <Label className="wm-label text-xs">Messaggio (opzionale)</Label>
              <Input value={emailMessage} onChange={(e) => setEmailMessage(e.target.value)}
                className="bg-black/40 border-white/10" data-testid="email-message-input" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmailOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={sendEmail} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="send-email-btn"><Mail size={14} className="mr-1" /> Invia</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
