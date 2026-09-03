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

## Roadmap / Backlog
- P2: WhatsApp Business API (invio automatico senza wa.me manuale)
- P2: Push notifications tramite service worker per solleciti in-app
- P3: Modalità offline avanzata (cache read-only tesserati/abbonamenti)
