import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { fmtEur, fmtDate, API, formatApiErrorDetail } from "../lib/api";
import { toast, Toaster } from "sonner";
import { Calendar, Clock, MapPin, User, Download, CheckCircle, AlertCircle, XCircle } from "lucide-react";

// Public unauth axios (no cookies)
const pub = axios.create({ baseURL: API });

export default function Portale() {
  const { token } = useParams();
  const [dash, setDash] = useState(null);
  const [ricevute, setRicevute] = useState([]);
  const [slots, setSlots] = useState([]);
  const [tab, setTab] = useState("home");
  const [err, setErr] = useState("");

  const loadAll = async () => {
    try {
      const [d, r, s] = await Promise.all([
        pub.get(`/portale/${token}`),
        pub.get(`/portale/${token}/ricevute`),
        pub.get(`/portale/${token}/calendario`),
      ]);
      setDash(d.data); setRicevute(r.data); setSlots(s.data);
    } catch (e) {
      setErr(formatApiErrorDetail(e.response?.data?.detail) || "Portale non valido o link scaduto");
    }
  };
  useEffect(() => { loadAll(); }, [token]);

  const prenota = async (slotId) => {
    try {
      await pub.post(`/portale/${token}/prenota`, { slot_id: slotId });
      toast.success("Prenotazione confermata. Riceverai un'email.");
      loadAll();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const annulla = async (slotId) => {
    if (!window.confirm("Annullare la prenotazione?")) return;
    try {
      await pub.delete(`/portale/${token}/prenota/${slotId}`);
      toast.success("Prenotazione annullata"); loadAll();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const downloadRicevuta = async (rid) => {
    try {
      const res = await pub.get(`/portale/${token}/ricevuta/${rid}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `Ricevuta.pdf`; a.click(); URL.revokeObjectURL(url);
    } catch { toast.error("Errore download"); }
  };

  if (err) return (
    <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center px-6">
      <div className="max-w-md text-center">
        <XCircle size={48} className="mx-auto text-[#FF3B30] mb-4" />
        <h1 className="font-display text-2xl font-bold">Accesso non disponibile</h1>
        <p className="text-white/60 mt-2 text-sm">{err}</p>
      </div>
    </div>
  );
  if (!dash) return <div className="min-h-screen bg-[#050505] flex items-center justify-center text-white/60">Caricamento…</div>;

  const t = dash.tesserato;
  const org = dash.organizzazione;
  const isExpiring = (iso) => iso && (new Date(iso) - new Date()) / (1000 * 3600 * 24) < 30;

  return (
    <div className="min-h-screen bg-[#050505] text-white">
      <header className="border-b border-white/10 bg-[#0A0A0F]">
        <div className="max-w-4xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {org.logo_base64 && <img src={org.logo_base64} alt="logo" className="h-10 w-10 object-contain" />}
            <div>
              <div className="font-display font-black text-lg leading-tight">{org.name}</div>
              <div className="text-xs text-white/50">Portale Tesserato</div>
            </div>
          </div>
          <div className="text-right text-sm">
            <div className="font-semibold">{t.cognome} {t.nome}</div>
            {t.numero_tessera && <div className="text-xs text-white/50 font-mono">Tessera {t.numero_tessera}</div>}
          </div>
        </div>
        <div className="max-w-4xl mx-auto px-6 pb-2">
          <div className="flex gap-1">
            {["home", "abbonamenti", "ricevute", "calendario"].map((v) => (
              <button key={v} onClick={() => setTab(v)}
                data-testid={`portale-tab-${v}`}
                className={`px-4 py-2 text-sm rounded-t border-b-2 transition-colors ${
                  tab === v ? "border-[#007AFF] text-white" : "border-transparent text-white/50 hover:text-white"
                }`}>
                {v[0].toUpperCase() + v.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-6 space-y-6">
        {tab === "home" && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="wm-card p-5">
                <div className="wm-label mb-2 flex items-center gap-1"><User size={12} /> Tesseramento</div>
                <div className={`text-lg font-bold ${isExpiring(t.scadenza_tesseramento) ? "text-[#FF3B30]" : "text-[#34C759]"}`}>
                  {fmtDate(t.scadenza_tesseramento) || "Non impostato"}
                </div>
                {isExpiring(t.scadenza_tesseramento) && (
                  <div className="mt-1 text-xs text-[#FF3B30]"><AlertCircle size={10} className="inline" /> In scadenza</div>
                )}
              </div>
              <div className="wm-card p-5">
                <div className="wm-label mb-2 flex items-center gap-1"><CheckCircle size={12} /> Visita medica</div>
                <div className={`text-lg font-bold ${isExpiring(t.scadenza_visita_medica) ? "text-[#FF3B30]" : "text-[#34C759]"}`}>
                  {fmtDate(t.scadenza_visita_medica) || "Non impostata"}
                </div>
              </div>
            </div>
            <div className="wm-card p-5">
              <div className="wm-label mb-3">I tuoi abbonamenti</div>
              {dash.abbonamenti.length === 0 && <div className="text-white/40 text-sm">Nessun abbonamento attivo.</div>}
              {dash.abbonamenti.map((a) => (
                <div key={a.id} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                  <div>
                    <div className="font-medium">{a.descrizione}</div>
                    <div className="text-xs text-white/50">Acquisto {fmtDate(a.data_acquisto)}</div>
                  </div>
                  <div className="text-right">
                    <div className={`font-display text-2xl font-bold ${
                      a.lezioni_residue === 0 ? "text-[#FF3B30]" :
                      a.lezioni_residue <= 2 ? "text-[#FFCC00]" : "text-[#34C759]"}`}>
                      {a.lezioni_residue ?? "∞"}
                    </div>
                    <div className="text-xs text-white/50">residue / {a.num_lezioni_totali ?? "-"}</div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === "abbonamenti" && (
          <div className="wm-card p-5">
            <div className="wm-label mb-3">Storico abbonamenti</div>
            <table className="w-full text-sm">
              <thead className="border-b border-white/10 text-left">
                <tr><th className="p-2 wm-label">Descrizione</th>
                    <th className="p-2 wm-label text-center">Totali</th>
                    <th className="p-2 wm-label text-center">Effettuate</th>
                    <th className="p-2 wm-label text-center">Residue</th>
                    <th className="p-2 wm-label text-right">Prezzo</th></tr>
              </thead>
              <tbody>
                {dash.abbonamenti.map((a) => (
                  <tr key={a.id} className="border-b border-white/5">
                    <td className="p-2 font-medium">{a.descrizione}</td>
                    <td className="p-2 text-center">{a.num_lezioni_totali ?? "-"}</td>
                    <td className="p-2 text-center">{a.lezioni_effettuate}</td>
                    <td className="p-2 text-center font-semibold">{a.lezioni_residue ?? "-"}</td>
                    <td className="p-2 text-right">{fmtEur(a.prezzo)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === "ricevute" && (
          <div className="wm-card p-5">
            <div className="wm-label mb-3">Le tue ricevute</div>
            {ricevute.length === 0 && <div className="text-white/40 text-sm">Nessuna ricevuta.</div>}
            {ricevute.map((r) => (
              <div key={r.id} className="flex items-center justify-between py-3 border-b border-white/5 last:border-0">
                <div>
                  <div className="font-mono font-semibold">N. {r.numero}</div>
                  <div className="text-xs text-white/50">{fmtDate(r.data)} · {r.metodo_pagamento}</div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="font-semibold text-[#007AFF]">{fmtEur(r.totale)}</div>
                  <button onClick={() => downloadRicevuta(r.id)}
                    data-testid={`portale-ricevuta-${r.id}`}
                    className="px-3 py-1.5 bg-[#007AFF] hover:bg-[#005BB5] rounded text-xs font-semibold flex items-center gap-1">
                    <Download size={12} /> PDF
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "calendario" && (
          <div className="wm-card p-5">
            <div className="wm-label mb-3">Lezioni prenotabili (prossime 3 settimane)</div>
            {slots.length === 0 && <div className="text-white/40 text-sm">Nessuno slot disponibile al momento.</div>}
            <div className="space-y-2">
              {slots.map((s) => {
                const disabled = s.posti_liberi === 0 && !s.gia_prenotato;
                return (
                  <div key={s.id} className="flex items-center justify-between p-3 bg-black/30 rounded border border-white/5">
                    <div>
                      <div className="font-semibold flex items-center gap-2">
                        <Calendar size={12} />{fmtDate(s.data)} · <Clock size={12} />{s.ora}
                      </div>
                      <div className="text-xs text-white/60 mt-1">
                        {s.descrizione || "Lezione"} · <MapPin size={10} className="inline" /> {s.luogo || "—"} ·
                        Tecnico: {s.tecnico_nome || "—"}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-xs text-white/60">{s.posti_liberi}/{s.capacita} liberi</div>
                      {s.gia_prenotato ? (
                        <button onClick={() => annulla(s.id)}
                          data-testid={`portale-annulla-${s.id}`}
                          className="px-3 py-1.5 border border-[#FF3B30]/40 text-[#FF3B30] hover:bg-[#FF3B30]/10 rounded text-xs font-semibold">
                          Annulla
                        </button>
                      ) : (
                        <button onClick={() => prenota(s.id)} disabled={disabled}
                          data-testid={`portale-prenota-${s.id}`}
                          className={`px-3 py-1.5 rounded text-xs font-semibold ${
                            disabled ? "bg-white/5 text-white/30" :
                            "bg-[#34C759] hover:bg-[#28a745] text-white"}`}>
                          Prenota
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>

      <footer className="max-w-4xl mx-auto px-6 py-6 text-center text-xs text-white/40">
        {org.name} · Portale privato · Non condividere questo link
      </footer>
      <Toaster theme="dark" position="top-right" richColors />
    </div>
  );
}
