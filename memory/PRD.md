# Wolf's Mind ASD - Gestionale (PRD)

## Problem statement
Gestionale multi-utente per associazione sportiva Wolf's Mind ASD con tecnici dislocati. Funzioni: tesserati, abbonamenti, ricevute con numerazione condivisa per tecnico, movimenti contabili, compensi tecnici (% su flusso), report bilancio PDF, invio ricevute email/WhatsApp.

## Personas
- Amministratore: accesso completo, modifica campi e correzioni
- Tecnico: emette ricevute (numerazione condivisa), gestisce propri tesserati, vede proprio flusso cassa e compenso

## Stack
FastAPI + MongoDB + React 19 + Tailwind + Shadcn + reportlab (PDF) + Resend (email)

## Implemented (2026-02)
- JWT auth (httpOnly cookies), admin seed
- Tesserati CRUD con scadenze
- Tipi Pacchetto (listino editabile)
- Abbonamenti + Lezioni effettuate (residue calc.)
- Ricevute numerazione anno/progressivo, PDF layout Wolf's Mind
- Send email via Resend con PDF allegato
- WhatsApp link (wa.me) con testo pre-compilato
- Movimenti (libro contabile) - auto entrata su ricevuta
- Compensi tecnici % su flusso
- Report Bilancio PDF export
- Pannello Admin: utenti, pacchetti, dati organizzazione, logo upload
- Responsive design (drawer mobile, tablet, desktop)
- Verbali & Assemblee, Portale Tesserato, Solleciti automatici (CRON), Compensi PDF (busta paga)
- Libro Soci PDF export
- **PWA (2026-02)**: manifest.json + service worker + install prompt (Android/iOS via "Aggiungi a Home"), icone 192/512/maskable, meta tag apple-mobile-web-app-*, pulsante "Installa App" nella sidebar e nel login
- **Abbonamenti evoluti (2026-02)**:
  - Tab "Attivi" (solo abbonamenti con residue > 0 o illimitati) con 4 stat card riassuntivi
  - Modifica manuale del numero di lezioni effettuate (icona matita → PATCH /abbonamenti/{id} con delta salvato in `lezioni_manuali`)
  - Tab "Storico per cliente" con card raggruppate per tesserato e totali: lezioni acquistate, effettuate, residue, spesa totale
  - Espansione card cliente → dettaglio di tutti gli abbonamenti (attivi + esauriti) con badge stato
- **Release rev 2 abbonamenti (2026-02)**:
  - Sidebar riordinata: Tesserati → Abbonamenti → Ricevute → Calendario → Libro Soci → Libro Contabile → Compensi → Verbali → Report → Admin
  - Abbonamento multi-voce con categorie (Lezioni / Quota associativa / Merchandising / Altro) → un movimento contabile per voce
  - Se una voce è "Quota associativa" → aggiorna automaticamente `scadenza_tesseramento` del tesserato (+1 anno)
  - Admin: toggle "Genera ricevuta automatica" (organizzazione.auto_ricevuta_abbonamento) + upload firma segretario
  - Ogni abbonamento ha un badge "Ricevuta ✓ N.XXX" (link al PDF) o "Genera" (POST /abbonamenti/{aid}/genera-ricevuta)
  - Admin può modificare tutti i campi ed eliminare (delete rimuove anche movimenti collegati)
  - Compensi: card "Da compensare" + colonne Erogato / Da erogare + alert giallo evidenziato
  - Busta paga PDF a 2 pagine: pag1 compenso+firme (segretario+presidente), pag2 riepilogo ricevute che hanno generato il compenso
  - Verbali arricchiti: sede, ora_inizio, ora_chiusura, data_chiusura, partecipanti_remoti[], toggle firme_abilitate
  - PWA install button con istruzioni PC dettagliate (Chrome/Edge/Brave: icona installa nell'URL o menu ⋮ → Installa app)
- **Compensi CRUD (2026-02)**:
  - PATCH /compensi/erogati/{cid} aggiorna anche il movimento contabile collegato
  - DELETE /compensi/erogati/{cid} rimuove anche il movimento (annullamento)
  - Frontend: icone matita/cestino nella tabella storico erogazioni (solo admin)
  - Dialog "Modifica compenso erogato" riusa il form dell'erogazione con etichette dinamiche

## Roadmap / Backlog
- P2: WhatsApp Business API (invio automatico senza wa.me manuale)
- P2: Push notifications tramite service worker per solleciti in-app
- P3: Modalità offline avanzata (cache read-only tesserati/abbonamenti)
