import React, { useEffect, useState } from "react";
import { api, fmtEur, fmtDate, formatApiErrorDetail, todayIso, API } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus, Trash2, Download, Mail, MessageCircle, FileText, Eye } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

const emptyItem = { descrizione: "", num_lezioni: "", importo: 0 };

export default function Ricevute() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [tesserati, setTesserati] = useState([]);
  const [tipi, setTipi] = useState([]);
  const [open, setOpen] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);
  const [selectedRid, setSelectedRid] = useState(null);
  const [emailTo, setEmailTo] = useState("");
  const [emailMessage, setEmailMessage] = useState("");
  const [form, setForm] = useState({
    tesserato_id: "", data: todayIso(),
    metodo_pagamento: "Contanti", items: [{ ...emptyItem }], note: "",
  });

  const load = async () => {
    const [r, t, p] = await Promise.all([
      api.get("/ricevute"), api.get("/tesserati"), api.get("/tipi-pacchetto"),
    ]);
    setList(r.data); setTesserati(t.data); setTipi(p.data);
  };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setForm({ tesserato_id: "", data: todayIso(), metodo_pagamento: "Contanti",
              items: [{ ...emptyItem }], note: "" });
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
      importo: t.prezzo_default,
    });
  };

  const total = form.items.reduce((s, it) => s + Number(it.importo || 0), 0);

  const save = async () => {
    if (!form.tesserato_id) { toast.error("Seleziona un tesserato"); return; }
    if (form.items.some((i) => !i.descrizione || !i.importo)) {
      toast.error("Compila descrizione e importo per ogni riga"); return;
    }
    try {
      const payload = { ...form, items: form.items.map((i) => ({
        descrizione: i.descrizione,
        num_lezioni: i.num_lezioni === "" ? null : Number(i.num_lezioni),
        importo: Number(i.importo),
      }))};
      await api.post("/ricevute", payload);
      toast.success("Ricevuta creata");
      setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const downloadPdf = async (r) => {
    try {
      const res = await api.get(`/ricevute/${r.id}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `Ricevuta_${r.numero.replace("/", "-")}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e) { toast.error("Errore download PDF"); }
  };

  const viewPdf = (r) => {
    // Open in new tab using authenticated cookie
    window.open(`${API}/ricevute/${r.id}/pdf`, "_blank");
  };

  const openEmail = (r) => {
    setSelectedRid(r.id);
    const t = tesserati.find((x) => x.id === r.tesserato_id);
    setEmailTo(t?.email || "");
    setEmailMessage("");
    setEmailOpen(true);
  };

  const sendEmail = async () => {
    try {
      await api.post(`/ricevute/${selectedRid}/send-email`,
        { email: emailTo, message: emailMessage });
      toast.success("Email inviata");
      setEmailOpen(false);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const shareWhatsApp = async (r) => {
    try {
      // Download PDF locally first (browser handles it)
      await downloadPdf(r);
      const { data } = await api.get(`/ricevute/${r.id}/whatsapp-link`);
      window.open(data.url, "_blank");
      toast.info("Allega il PDF appena scaricato al messaggio WhatsApp.");
    } catch (e) { toast.error("Errore WhatsApp"); }
  };

  const del = async (r) => {
    if (!window.confirm(`Annullare la ricevuta N.${r.numero}?`)) return;
    try {
      await api.delete(`/ricevute/${r.id}`);
      toast.success("Ricevuta annullata"); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="space-y-6" data-testid="ricevute-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="wm-label">Gestione</div>
          <h1 className="font-display text-4xl font-black tracking-tighter mt-2">Ricevute</h1>
          <p className="text-white/50 mt-2 text-sm">
            Numerazione unica condivisa. Ogni ricevuta è attribuita al tecnico che l'ha emessa.
          </p>
        </div>
        <Button onClick={openNew} data-testid="add-ricevuta-btn"
          className="bg-[#007AFF] hover:bg-[#005BB5]">
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
              <th className="p-3 wm-label">Emessa da</th>
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
                <td className="p-3 text-white/70">{r.emesso_da_nome}</td>
                <td className="p-3 text-right font-semibold">{fmtEur(r.totale)}</td>
                <td className="p-3 text-right whitespace-nowrap">
                  <Button variant="ghost" size="sm" onClick={() => viewPdf(r)}
                    data-testid={`view-pdf-${r.id}`}><Eye size={14} /></Button>
                  <Button variant="ghost" size="sm" onClick={() => downloadPdf(r)}
                    data-testid={`download-pdf-${r.id}`}><Download size={14} /></Button>
                  <Button variant="ghost" size="sm" onClick={() => openEmail(r)}
                    data-testid={`email-ricevuta-${r.id}`}><Mail size={14} /></Button>
                  <Button variant="ghost" size="sm" onClick={() => shareWhatsApp(r)}
                    data-testid={`whatsapp-${r.id}`}><MessageCircle size={14} /></Button>
                  {user?.role === "admin" && !r.annullata && (
                    <Button variant="ghost" size="sm" onClick={() => del(r)}
                      className="text-[#FF3B30]" data-testid={`delete-ricevuta-${r.id}`}>
                      <Trash2 size={14} />
                    </Button>
                  )}
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

      {/* Nuova ricevuta dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl bg-[#0F0F13] border-white/10" data-testid="ricevuta-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">Nuova ricevuta</DialogTitle>
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

            <div className="space-y-2">
              <Label className="wm-label text-xs">Voci</Label>
              {form.items.map((it, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-end">
                  <div className="col-span-3">
                    <Select value="" onValueChange={(v) => applyTipo(i, v)}>
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
                  <Input className="col-span-5 bg-black/40 border-white/10 h-9"
                    placeholder="Descrizione" value={it.descrizione}
                    onChange={(e) => updateItem(i, { descrizione: e.target.value })}
                    data-testid={`item-descrizione-${i}`} />
                  <Input className="col-span-2 bg-black/40 border-white/10 h-9"
                    type="number" placeholder="N. lez." value={it.num_lezioni}
                    onChange={(e) => updateItem(i, { num_lezioni: e.target.value })}
                    data-testid={`item-lezioni-${i}`} />
                  <Input className="col-span-1 bg-black/40 border-white/10 h-9"
                    type="number" step="0.01" placeholder="€" value={it.importo}
                    onChange={(e) => updateItem(i, { importo: e.target.value })}
                    data-testid={`item-importo-${i}`} />
                  <Button variant="ghost" size="sm" className="col-span-1 text-[#FF3B30]"
                    onClick={() => removeItem(i)} disabled={form.items.length === 1}>
                    <Trash2 size={14} />
                  </Button>
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
                  <SelectTrigger className="bg-black/40 border-white/10">
                    <SelectValue />
                  </SelectTrigger>
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
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/20">
              Annulla
            </Button>
            <Button onClick={save} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-ricevuta-btn">Emetti ricevuta</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Email dialog */}
      <Dialog open={emailOpen} onOpenChange={setEmailOpen}>
        <DialogContent className="bg-[#0F0F13] border-white/10" data-testid="email-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">Invia ricevuta via email</DialogTitle>
          </DialogHeader>
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
            <Button variant="outline" onClick={() => setEmailOpen(false)} className="border-white/20">
              Annulla
            </Button>
            <Button onClick={sendEmail} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="send-email-btn">
              <Mail size={14} className="mr-1" /> Invia
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
