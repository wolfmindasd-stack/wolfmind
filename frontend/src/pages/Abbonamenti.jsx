import React, { useEffect, useMemo, useState } from "react";
import { api, fmtEur, fmtDate, formatApiErrorDetail, todayIso } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import {
  Plus, Trash2, MapPin, Users as UsersIcon,
  ChevronDown, ChevronRight, Pencil, History, ListChecks,
  Receipt as ReceiptIcon, Check, FileText,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

const CATEGORIE = [
  { v: "Lezioni", l: "Lezioni" },
  { v: "Quota associativa", l: "Quota associativa" },
  { v: "Merchandising", l: "Merchandising" },
  { v: "Altro", l: "Altro" },
];

const emptyItem = () => ({
  descrizione: "", categoria: "Lezioni", num_lezioni: "", importo: 0, tipo_pacchetto_id: null,
});

const emptyForm = () => ({
  tesserato_id: "", data_acquisto: todayIso(),
  metodo_pagamento: "Contanti",
  items: [emptyItem()],
  crea_ricevuta: null, // null = usa default admin
});

export default function Abbonamenti() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [tab, setTab] = useState("attivi");
  const [list, setList] = useState([]);
  const [gruppi, setGruppi] = useState([]);
  const [tesserati, setTesserati] = useState([]);
  const [tipi, setTipi] = useState([]);
  const [tecnici, setTecnici] = useState([]);
  const [orgAutoRic, setOrgAutoRic] = useState(false);

  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [lezioneOpen, setLezioneOpen] = useState(false);
  const [editEff, setEditEff] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [storico, setStorico] = useState(null);
  const [expandedCliente, setExpandedCliente] = useState(null);

  const [form, setForm] = useState(emptyForm());
  const [lezioneForm, setLezioneForm] = useState({
    data: todayIso(), luogo: "", tecnico_id: "", note: "", partecipanti: [],
  });

  const load = async () => {
    const [a, g, t, p, u, o] = await Promise.all([
      api.get("/abbonamenti", { params: { stato: "attivi" } }),
      api.get("/abbonamenti-per-cliente"),
      api.get("/tesserati"),
      api.get("/tipi-pacchetto"),
      api.get("/users").catch(() => ({ data: [] })),
      api.get("/organizzazione").catch(() => ({ data: {} })),
    ]);
    setList(a.data);
    setGruppi(g.data);
    setTesserati(t.data);
    setTipi(p.data);
    setTecnici(u.data.filter((x) => x.role === "tecnico" && x.active !== false));
    setOrgAutoRic(!!o.data?.auto_ricevuta_abbonamento);
  };
  useEffect(() => { load(); }, []);

  const applyTipoOnItem = (idx, tid) => {
    const t = tipi.find((x) => x.id === tid);
    setForm((f) => ({
      ...f,
      items: f.items.map((it, i) => i !== idx ? it : ({
        ...it,
        tipo_pacchetto_id: tid,
        descrizione: t?.nome || it.descrizione,
        num_lezioni: t?.num_lezioni ?? "",
        importo: t?.prezzo_default ?? it.importo,
        categoria: t?.esclude_da_compensi ? "Quota associativa" : "Lezioni",
      })),
    }));
  };

  const updateItem = (idx, patch) => {
    setForm((f) => ({
      ...f,
      items: f.items.map((it, i) => i !== idx ? it : { ...it, ...patch }),
    }));
  };
  const addItem = () => setForm((f) => ({ ...f, items: [...f.items, emptyItem()] }));
  const removeItem = (idx) => setForm((f) => ({
    ...f, items: f.items.filter((_, i) => i !== idx),
  }));

  const totItems = useMemo(
    () => form.items.reduce((s, it) => s + (Number(it.importo) || 0), 0),
    [form.items]
  );

  const openNew = () => {
    setEditingId(null);
    setForm(emptyForm());
    setOpen(true);
  };

  const openEdit = (a) => {
    if (!isAdmin) return;
    setEditingId(a.id);
    setForm({
      tesserato_id: a.tesserato_id,
      data_acquisto: (a.data_acquisto || "").slice(0, 10) || todayIso(),
      metodo_pagamento: a.metodo_pagamento || "Contanti",
      items: (a.items && a.items.length > 0)
        ? a.items.map((it) => ({
            descrizione: it.descrizione || "",
            categoria: it.categoria || "Lezioni",
            num_lezioni: it.num_lezioni ?? "",
            importo: it.importo,
            tipo_pacchetto_id: it.tipo_pacchetto_id || null,
          }))
        : [{
            descrizione: a.descrizione || "",
            categoria: "Lezioni",
            num_lezioni: a.num_lezioni_totali ?? "",
            importo: a.prezzo || 0,
            tipo_pacchetto_id: a.tipo_pacchetto_id || null,
          }],
      crea_ricevuta: null,
    });
    setOpen(true);
  };

  const save = async () => {
    if (!form.tesserato_id) { toast.error("Seleziona il tesserato"); return; }
    if (form.items.length === 0 || form.items.some((it) => !it.descrizione)) {
      toast.error("Aggiungi almeno una voce con descrizione"); return;
    }
    const items = form.items.map((it) => ({
      descrizione: it.descrizione,
      categoria: it.categoria || "Lezioni",
      num_lezioni: it.num_lezioni === "" || it.num_lezioni === null ? null : Number(it.num_lezioni),
      importo: Number(it.importo) || 0,
      tipo_pacchetto_id: it.tipo_pacchetto_id || null,
    }));
    const totLezioni = items
      .filter((it) => it.categoria === "Lezioni")
      .reduce((s, it) => s + (Number(it.num_lezioni) || 0), 0);
    const descrRiassunto = items.map((it) => it.descrizione).join(" + ");
    try {
      if (editingId) {
        await api.patch(`/abbonamenti/${editingId}`, {
          tesserato_id: form.tesserato_id,
          data_acquisto: form.data_acquisto,
          metodo_pagamento: form.metodo_pagamento,
          items,
          descrizione: descrRiassunto,
          num_lezioni_totali: totLezioni > 0 ? totLezioni : null,
        });
        toast.success("Abbonamento aggiornato");
      } else {
        await api.post("/abbonamenti", {
          tesserato_id: form.tesserato_id,
          tipo_pacchetto_id: null,
          descrizione: descrRiassunto,
          num_lezioni_totali: totLezioni > 0 ? totLezioni : null,
          prezzo: items.reduce((s, it) => s + it.importo, 0),
          data_acquisto: form.data_acquisto,
          metodo_pagamento: form.metodo_pagamento,
          items,
          crea_ricevuta: form.crea_ricevuta,
        });
        toast.success("Abbonamento creato");
      }
      setOpen(false); setEditingId(null); setForm(emptyForm()); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const remove = async (a) => {
    if (!isAdmin) return;
    if (!window.confirm(
      `Eliminare l'abbonamento di ${tessName(a.tesserato_id)}?\n` +
      `Verranno rimossi anche i movimenti contabili collegati.`
    )) return;
    try {
      await api.delete(`/abbonamenti/${a.id}`);
      toast.success("Abbonamento eliminato");
      setExpanded(null);
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const generaRicevuta = async (a) => {
    try {
      await api.post(`/abbonamenti/${a.id}/genera-ricevuta`);
      toast.success("Ricevuta generata");
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const downloadRicevutaPdf = async (a) => {
    if (!a.ricevuta_id) return;
    try {
      const res = await api.get(`/ricevute/${a.ricevuta_id}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `Ricevuta_${a.ricevuta_numero || a.ricevuta_id}.pdf`;
      link.click(); URL.revokeObjectURL(url);
    } catch { toast.error("Errore download ricevuta"); }
  };

  const toggle = async (a) => {
    if (expanded === a.id) { setExpanded(null); setStorico(null); return; }
    setExpanded(a.id);
    const { data } = await api.get(`/abbonamenti/${a.id}/storico`);
    setStorico(data);
  };

  const openLezione = () => {
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
      toast.error("Aggiungi almeno un partecipante"); return;
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
      if (expanded) {
        const { data } = await api.get(`/abbonamenti/${expanded}/storico`); setStorico(data);
      }
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const saveEffettuate = async () => {
    if (!editEff) return;
    const n = Number(editEff.value);
    if (!Number.isInteger(n) || n < 0) {
      toast.error("Inserisci un numero intero valido (>= 0)"); return;
    }
    try {
      await api.patch(`/abbonamenti/${editEff.id}`, { lezioni_effettuate: n });
      toast.success("Lezioni effettuate aggiornate");
      setEditEff(null); load();
      if (expanded) {
        const { data } = await api.get(`/abbonamenti/${expanded}/storico`); setStorico(data);
      }
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  function tessName(tid) {
    const t = tesserati.find((x) => x.id === tid);
    return t ? `${t.cognome} ${t.nome}` : "—";
  }
  const tecName = (tid) => {
    const t = tecnici.find((x) => x.id === tid);
    if (t) return t.name;
    if (tid === user.id) return user.name;
    return "—";
  };

  const totali = useMemo(() => {
    let acq = 0, eff = 0, res = 0, hasLimit = false;
    list.forEach((a) => {
      eff += a.lezioni_effettuate || 0;
      if (a.num_lezioni_totali) {
        hasLimit = true;
        acq += a.num_lezioni_totali;
        res += a.lezioni_residue || 0;
      }
    });
    return { acq, eff, res, hasLimit };
  }, [list]);

  return (
    <div className="space-y-6" data-testid="abbonamenti-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="wm-label">Pacchetti</div>
          <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter mt-2">Abbonamenti</h1>
          <p className="text-white/50 mt-2 text-sm">
            Lezioni acquistate, effettuate e residue. Puoi combinare più voci in un unico abbonamento (es. 6 lezioni + tessera socio + maglietta).
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button onClick={openLezione} variant="outline" data-testid="add-lezione-btn" className="border-white/20">
            <UsersIcon size={16} className="mr-1" /> Registra lezione
          </Button>
          <Button onClick={openNew} data-testid="add-abbonamento-btn"
            className="bg-[#007AFF] hover:bg-[#005BB5]">
            <Plus size={16} className="mr-1" /> Nuovo abbonamento
          </Button>
        </div>
      </div>

      <div className="flex gap-2 border-b border-white/10">
        <button onClick={() => setTab("attivi")} data-testid="tab-attivi"
          className={`px-4 py-2 text-sm flex items-center gap-2 border-b-2 transition-colors
            ${tab === "attivi" ? "border-[#007AFF] text-white" : "border-transparent text-white/50 hover:text-white/80"}`}>
          <ListChecks size={15} /> Attivi ({list.length})
        </button>
        <button onClick={() => setTab("storico")} data-testid="tab-storico"
          className={`px-4 py-2 text-sm flex items-center gap-2 border-b-2 transition-colors
            ${tab === "storico" ? "border-[#007AFF] text-white" : "border-transparent text-white/50 hover:text-white/80"}`}>
          <History size={15} /> Storico per cliente ({gruppi.length})
        </button>
      </div>

      {tab === "attivi" && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard label="Abbonamenti attivi" value={list.length} />
            <StatCard label="Lezioni acquistate" value={totali.hasLimit ? totali.acq : "—"} />
            <StatCard label="Lezioni effettuate" value={totali.eff} />
            <StatCard label="Lezioni residue" value={totali.hasLimit ? totali.res : "—"} accent="#34C759" />
          </div>

          <div className="wm-card overflow-x-auto">
            <table className="w-full text-sm min-w-[900px]">
              <thead className="bg-white/[0.02] border-b border-white/10">
                <tr className="text-left">
                  <th className="p-3 wm-label w-8"></th>
                  <th className="p-3 wm-label">Tesserato</th>
                  <th className="p-3 wm-label">Descrizione</th>
                  <th className="p-3 wm-label">Acquisto</th>
                  <th className="p-3 wm-label text-center">Tot.</th>
                  <th className="p-3 wm-label text-center">Eff.</th>
                  <th className="p-3 wm-label text-center">Res.</th>
                  <th className="p-3 wm-label text-right">Prezzo</th>
                  <th className="p-3 wm-label text-center">Ricevuta</th>
                  <th className="p-3 wm-label text-right w-24">Azioni</th>
                </tr>
              </thead>
              <tbody>
                {list.map((a) => (
                  <React.Fragment key={a.id}>
                    <tr className="border-b border-white/5 hover:bg-white/[0.02]"
                      data-testid={`abbonamento-row-${a.id}`}>
                      <td className="p-3 cursor-pointer" onClick={() => toggle(a)}>
                        {expanded === a.id ? <ChevronDown size={14} className="text-white/40" />
                          : <ChevronRight size={14} className="text-white/40" />}
                      </td>
                      <td className="p-3 font-medium cursor-pointer" onClick={() => toggle(a)}>
                        {tessName(a.tesserato_id)}
                      </td>
                      <td className="p-3">{a.descrizione}</td>
                      <td className="p-3">{fmtDate(a.data_acquisto)}</td>
                      <td className="p-3 text-center">{a.num_lezioni_totali ?? "-"}</td>
                      <td className="p-3 text-center">
                        <div className="inline-flex items-center gap-1.5">
                          <span>{a.lezioni_effettuate}</span>
                          <button onClick={() => setEditEff({ id: a.id, value: String(a.lezioni_effettuate) })}
                            data-testid={`edit-effettuate-${a.id}`}
                            title="Modifica lezioni effettuate"
                            className="text-white/40 hover:text-[#007AFF] transition-colors">
                            <Pencil size={12} />
                          </button>
                        </div>
                      </td>
                      <td className={`p-3 text-center font-semibold ${
                        a.lezioni_residue === 0 ? "text-[#FF3B30]" :
                        a.lezioni_residue !== null && a.lezioni_residue <= 2 ? "text-[#FFCC00]" :
                        "text-[#34C759]"}`}>{a.lezioni_residue ?? "-"}</td>
                      <td className="p-3 text-right font-semibold">{fmtEur(a.prezzo)}</td>
                      <td className="p-3 text-center">
                        {a.ricevuta_generata ? (
                          <button
                            onClick={() => downloadRicevutaPdf(a)}
                            data-testid={`ric-generata-${a.id}`}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px]
                                       bg-[#34C759]/15 text-[#34C759] border border-[#34C759]/30 hover:bg-[#34C759]/25 transition-colors"
                            title="Scarica ricevuta PDF">
                            <Check size={11} /> N.{a.ricevuta_numero}
                          </button>
                        ) : (
                          <button
                            onClick={() => generaRicevuta(a)}
                            data-testid={`gen-ricevuta-${a.id}`}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px]
                                       bg-white/5 text-white/60 border border-white/15 hover:bg-white/10 hover:text-white transition-colors"
                            title="Genera ricevuta">
                            <ReceiptIcon size={11} /> Genera
                          </button>
                        )}
                      </td>
                      <td className="p-3 text-right whitespace-nowrap">
                        {isAdmin && (
                          <>
                            <button onClick={() => openEdit(a)}
                              data-testid={`edit-abb-${a.id}`}
                              title="Modifica abbonamento"
                              className="text-white/50 hover:text-[#007AFF] p-1 transition-colors">
                              <Pencil size={14} />
                            </button>
                            <button onClick={() => remove(a)}
                              data-testid={`del-abb-${a.id}`}
                              title="Elimina abbonamento"
                              className="text-white/50 hover:text-[#FF3B30] p-1 ml-1 transition-colors">
                              <Trash2 size={14} />
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                    {expanded === a.id && storico && (
                      <tr>
                        <td colSpan={10} className="p-4 bg-black/40">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                              <div className="wm-label mb-2">Voci abbonamento</div>
                              {(a.items && a.items.length > 0) ? (
                                <div className="space-y-1">
                                  {a.items.map((it, i) => (
                                    <div key={i} className="text-xs bg-black/30 p-2 rounded flex justify-between">
                                      <span>
                                        <span className="text-white/50 mr-1">[{it.categoria}]</span>
                                        {it.descrizione}
                                        {it.num_lezioni ? ` (${it.num_lezioni} lezioni)` : ""}
                                      </span>
                                      <span className="font-semibold">{fmtEur(it.importo)}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div className="text-white/40 text-xs">Voce singola: {a.descrizione}</div>
                              )}
                              <div className="mt-3 wm-label">Storico lezioni ({storico.lezioni.length})</div>
                              <div className="space-y-1 max-h-40 overflow-y-auto mt-1">
                                {storico.lezioni.map((l) => (
                                  <div key={l.id} className="text-xs bg-black/30 p-2 rounded">
                                    <div className="flex justify-between">
                                      <span className="font-semibold">{fmtDate(l.data)}</span>
                                      <span className="text-white/50">{tecName(l.tecnico_id)}</span>
                                    </div>
                                    {l.luogo && <div className="text-white/60 mt-0.5"><MapPin size={10} className="inline mr-1" />{l.luogo}</div>}
                                  </div>
                                ))}
                                {storico.lezioni.length === 0 && <div className="text-white/40 text-xs">Nessuna lezione registrata.</div>}
                              </div>
                              {a._lezioni_manuali !== 0 && (
                                <div className="mt-2 text-[11px] text-white/50">
                                  Regolazione manuale: {a._lezioni_manuali > 0 ? "+" : ""}{a._lezioni_manuali} lezioni
                                </div>
                              )}
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
                                {storico.ricevute.length === 0 && <div className="text-white/40 text-xs">Nessuna ricevuta collegata.</div>}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
                {list.length === 0 && (
                  <tr><td colSpan={10} className="p-8 text-center text-white/40">Nessun abbonamento attivo</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "storico" && (
        <div className="space-y-3" data-testid="storico-clienti">
          {gruppi.length === 0 && (
            <div className="wm-card p-8 text-center text-white/40">
              Nessuno storico disponibile.
            </div>
          )}
          {gruppi.map((g) => {
            const opn = expandedCliente === g.tesserato.id;
            return (
              <div key={g.tesserato.id} className="wm-card overflow-hidden"
                data-testid={`cliente-card-${g.tesserato.id}`}>
                <button
                  onClick={() => setExpandedCliente(opn ? null : g.tesserato.id)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-white/[0.02] transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    {opn ? <ChevronDown size={16} className="text-white/50 shrink-0" /> :
                            <ChevronRight size={16} className="text-white/50 shrink-0" />}
                    <div className="text-left min-w-0">
                      <div className="font-semibold truncate">{g.tesserato.cognome} {g.tesserato.nome}</div>
                      <div className="text-xs text-white/50 mt-0.5">
                        {g.num_abbonamenti} abbonamenti · {g.num_abbonamenti_attivi} attivi
                      </div>
                    </div>
                  </div>
                  <div className="hidden sm:flex items-center gap-6 text-xs">
                    <MiniStat label="Acquistate" value={g.totale_lezioni_acquistate ?? "—"} />
                    <MiniStat label="Effettuate" value={g.totale_lezioni_effettuate} />
                    <MiniStat label="Residue" value={g.totale_lezioni_residue ?? "—"}
                      valueClass={(g.totale_lezioni_residue ?? 0) === 0 ? "text-[#FF3B30]" : "text-[#34C759]"} />
                    <MiniStat label="Speso" value={fmtEur(g.totale_speso)} valueClass="text-[#007AFF]" />
                  </div>
                </button>
                <div className="sm:hidden px-4 pb-3 grid grid-cols-4 gap-2 text-[11px]">
                  <MiniStat label="Acq." value={g.totale_lezioni_acquistate ?? "—"} />
                  <MiniStat label="Eff." value={g.totale_lezioni_effettuate} />
                  <MiniStat label="Res." value={g.totale_lezioni_residue ?? "—"}
                    valueClass={(g.totale_lezioni_residue ?? 0) === 0 ? "text-[#FF3B30]" : "text-[#34C759]"} />
                  <MiniStat label="€" value={fmtEur(g.totale_speso)} valueClass="text-[#007AFF]" />
                </div>
                {opn && (
                  <div className="border-t border-white/10 bg-black/30 overflow-x-auto">
                    <table className="w-full text-xs min-w-[720px]">
                      <thead className="bg-white/[0.02]">
                        <tr className="text-left">
                          <th className="p-2 wm-label">Data</th>
                          <th className="p-2 wm-label">Descrizione</th>
                          <th className="p-2 wm-label text-center">Tot.</th>
                          <th className="p-2 wm-label text-center">Eff.</th>
                          <th className="p-2 wm-label text-center">Res.</th>
                          <th className="p-2 wm-label text-right">Prezzo</th>
                          <th className="p-2 wm-label text-center">Ricevuta</th>
                          <th className="p-2 wm-label text-center">Stato</th>
                        </tr>
                      </thead>
                      <tbody>
                        {g.abbonamenti.map((a) => (
                          <tr key={a.id} className="border-t border-white/5">
                            <td className="p-2">{fmtDate(a.data_acquisto)}</td>
                            <td className="p-2">{a.descrizione}</td>
                            <td className="p-2 text-center">{a.num_lezioni_totali ?? "—"}</td>
                            <td className="p-2 text-center">{a.lezioni_effettuate}</td>
                            <td className="p-2 text-center">{a.lezioni_residue ?? "—"}</td>
                            <td className="p-2 text-right font-semibold">{fmtEur(a.prezzo)}</td>
                            <td className="p-2 text-center">
                              {a.ricevuta_id
                                ? <span className="text-[10px] text-[#34C759]">✓ N.{a.ricevuta_numero || "—"}</span>
                                : <span className="text-[10px] text-white/40">—</span>}
                            </td>
                            <td className="p-2 text-center">
                              {a.attivo
                                ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#34C759]/15 text-[#34C759] border border-[#34C759]/30">Attivo</span>
                                : <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/50 border border-white/10">Esaurito</span>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Modifica lezioni effettuate */}
      <Dialog open={!!editEff} onOpenChange={(v) => !v && setEditEff(null)}>
        <DialogContent className="bg-[#0F0F13] border-white/10 sm:max-w-md" data-testid="edit-effettuate-dialog">
          <DialogHeader><DialogTitle className="font-display">Modifica lezioni effettuate</DialogTitle></DialogHeader>
          <div className="space-y-3 text-sm">
            <p className="text-white/60">
              Imposta il numero totale di lezioni effettuate per questo abbonamento.
              Le lezioni registrate nel calendario continueranno a essere conteggiate; questa rettifica applica un aggiustamento manuale.
            </p>
            <div>
              <Label className="wm-label text-xs">Lezioni effettuate</Label>
              <Input type="number" min="0" value={editEff?.value ?? ""}
                onChange={(e) => setEditEff((s) => ({ ...s, value: e.target.value }))}
                className="bg-black/40 border-white/10" data-testid="edit-effettuate-input" autoFocus />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditEff(null)} className="border-white/20">Annulla</Button>
            <Button onClick={saveEffettuate} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-effettuate-btn">Salva</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Nuovo / Modifica abbonamento multi-voce */}
      <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setEditingId(null); } }}>
        <DialogContent className="max-w-3xl bg-[#0F0F13] border-white/10 max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-display">
              {editingId ? "Modifica abbonamento" : "Nuovo abbonamento"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <div className="sm:col-span-2">
                <Label className="wm-label text-xs">Tesserato *</Label>
                <Select value={form.tesserato_id} onValueChange={(v) => setForm({ ...form, tesserato_id: v })}
                  disabled={!!editingId && !isAdmin}>
                  <SelectTrigger className="bg-black/40 border-white/10" data-testid="abb-tesserato">
                    <SelectValue placeholder="Seleziona" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0F0F13] border-white/10 text-white max-h-72">
                    {tesserati.map((t) => (<SelectItem key={t.id} value={t.id}>{t.cognome} {t.nome}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="wm-label text-xs">Data acquisto</Label>
                <Input type="date" value={form.data_acquisto}
                  onChange={(e) => setForm({ ...form, data_acquisto: e.target.value })}
                  className="bg-black/40 border-white/10" data-testid="abb-data" />
              </div>
            </div>

            <div>
              <Label className="wm-label text-xs">Metodo di pagamento</Label>
              <Select value={form.metodo_pagamento}
                onValueChange={(v) => setForm({ ...form, metodo_pagamento: v })}>
                <SelectTrigger className="bg-black/40 border-white/10"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                  {["Contanti", "Bonifico", "Carta", "Assegno"].map((m) => (
                    <SelectItem key={m} value={m}>{m}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Items */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <Label className="wm-label text-xs">Voci acquistate</Label>
                <Button size="sm" variant="outline" onClick={addItem} className="h-7 border-white/20"
                  data-testid="add-item-btn">
                  <Plus size={12} className="mr-1" /> Aggiungi voce
                </Button>
              </div>
              <div className="space-y-2">
                {form.items.map((it, i) => (
                  <div key={i} className="wm-card p-3 space-y-2 bg-black/30" data-testid={`abb-item-${i}`}>
                    <div className="grid grid-cols-1 sm:grid-cols-12 gap-2">
                      <div className="sm:col-span-3">
                        <Label className="wm-label text-[10px]">Categoria</Label>
                        <Select value={it.categoria}
                          onValueChange={(v) => updateItem(i, { categoria: v })}>
                          <SelectTrigger className="bg-black/40 border-white/10 h-9" data-testid={`item-cat-${i}`}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                            {CATEGORIE.map((c) => (<SelectItem key={c.v} value={c.v}>{c.l}</SelectItem>))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="sm:col-span-4">
                        <Label className="wm-label text-[10px]">
                          {it.categoria === "Lezioni" ? "Pacchetto (opz.)" : "Descrizione"}
                        </Label>
                        {it.categoria === "Lezioni" ? (
                          <Select value={it.tipo_pacchetto_id || ""}
                            onValueChange={(v) => applyTipoOnItem(i, v)}>
                            <SelectTrigger className="bg-black/40 border-white/10 h-9">
                              <SelectValue placeholder="Seleziona pacchetto…" />
                            </SelectTrigger>
                            <SelectContent className="bg-[#0F0F13] border-white/10 text-white">
                              {tipi.filter((x) => x.attivo).map((t) => (
                                <SelectItem key={t.id} value={t.id}>
                                  {t.nome} — {fmtEur(t.prezzo_default)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Input value={it.descrizione}
                            onChange={(e) => updateItem(i, { descrizione: e.target.value })}
                            placeholder={it.categoria === "Quota associativa"
                              ? "Es. Tessera socio 2026"
                              : it.categoria === "Merchandising"
                                ? "Es. Maglietta, cappellino…"
                                : "Descrizione"}
                            className="bg-black/40 border-white/10 h-9"
                            data-testid={`item-desc-${i}`} />
                        )}
                      </div>
                      {it.categoria === "Lezioni" && (
                        <div className="sm:col-span-3">
                          <Label className="wm-label text-[10px]">Descrizione</Label>
                          <Input value={it.descrizione}
                            onChange={(e) => updateItem(i, { descrizione: e.target.value })}
                            placeholder="Es. 6 lezioni"
                            className="bg-black/40 border-white/10 h-9"
                            data-testid={`item-desc-${i}`} />
                        </div>
                      )}
                      <div className={it.categoria === "Lezioni" ? "sm:col-span-1" : "sm:col-span-2"}>
                        <Label className="wm-label text-[10px]">N. Lez.</Label>
                        <Input type="number" value={it.num_lezioni}
                          onChange={(e) => updateItem(i, { num_lezioni: e.target.value })}
                          disabled={it.categoria !== "Lezioni"}
                          className="bg-black/40 border-white/10 h-9 disabled:opacity-40"
                          data-testid={`item-numlez-${i}`} />
                      </div>
                      <div className={it.categoria === "Lezioni" ? "sm:col-span-1" : "sm:col-span-2"}>
                        <Label className="wm-label text-[10px]">Prezzo €</Label>
                        <Input type="number" step="0.01" value={it.importo}
                          onChange={(e) => updateItem(i, { importo: e.target.value })}
                          className="bg-black/40 border-white/10 h-9"
                          data-testid={`item-imp-${i}`} />
                      </div>
                      <div className="sm:col-span-1 flex sm:items-end sm:justify-end">
                        <Button size="sm" variant="ghost" onClick={() => removeItem(i)}
                          disabled={form.items.length === 1}
                          className="text-[#FF3B30] disabled:opacity-30 h-9"
                          data-testid={`item-del-${i}`}>
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex justify-between items-center px-1">
                <span className="text-xs text-white/50">
                  {form.items.length} {form.items.length === 1 ? "voce" : "voci"}
                </span>
                <span className="font-display text-lg font-bold text-[#007AFF]">
                  Totale: {fmtEur(totItems)}
                </span>
              </div>
            </div>

            {!editingId && (
              <div className="border-t border-white/10 pt-3">
                <div className="flex items-start gap-3">
                  <input
                    id="crea-ric"
                    type="checkbox"
                    checked={form.crea_ricevuta === null ? orgAutoRic : !!form.crea_ricevuta}
                    onChange={(e) => setForm({ ...form, crea_ricevuta: e.target.checked })}
                    className="mt-1 h-4 w-4 accent-[#007AFF]"
                    data-testid="crea-ricevuta"
                  />
                  <label htmlFor="crea-ric" className="text-sm cursor-pointer">
                    <span className="font-semibold">Genera anche la ricevuta</span>
                    <span className="block text-xs text-white/50 mt-0.5">
                      {orgAutoRic
                        ? "L'impostazione admin è ATTIVA: la ricevuta viene creata di default."
                        : "L'impostazione admin è DISATTIVATA."} Puoi comunque scegliere manualmente qui.
                    </span>
                  </label>
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/20">Annulla</Button>
            <Button onClick={save} className="bg-[#007AFF] hover:bg-[#005BB5]"
              data-testid="save-abbonamento-btn">
              {editingId ? "Aggiorna" : "Crea abbonamento"}
            </Button>
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
                  {tecnici.map((t) => (<SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>))}
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

function StatCard({ label, value, accent }) {
  return (
    <div className="wm-card p-3">
      <div className="wm-label text-[10px]">{label}</div>
      <div className="font-display text-2xl font-black mt-1"
        style={accent ? { color: accent } : undefined}>
        {value}
      </div>
    </div>
  );
}

function MiniStat({ label, value, valueClass = "" }) {
  return (
    <div className="text-center">
      <div className="text-[10px] uppercase tracking-wider text-white/40">{label}</div>
      <div className={`font-semibold ${valueClass}`}>{value}</div>
    </div>
  );
}
