const express = require("express");
const router = express.Router();
const db = require("../db"); // usa il tuo modulo DB

// ------------------------------------
// GET /compensi  → tutti i compensi
// ------------------------------------
router.get("/", async (req, res) => {
  try {
    const rows = await db.query("SELECT * FROM compensi ORDER BY data DESC");
    res.json(rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Errore nel caricamento dei compensi" });
  }
});

// ------------------------------------
// POST /compensi  → aggiungi compenso
// ------------------------------------
router.post("/", async (req, res) => {
  const { persona_id, tipo_persona, descrizione, importo, data } = req.body;

  try {
    await db.query(
      "INSERT INTO compensi (persona_id, tipo_persona, descrizione, importo, data) VALUES (?, ?, ?, ?, ?)",
      [persona_id, tipo_persona, descrizione, importo, data]
    );
    res.json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Errore nell'inserimento del compenso" });
  }
});

// ------------------------------------
// DELETE /compensi/:id  → elimina singolo
// ------------------------------------
router.delete("/:id", async (req, res) => {
  try {
    await db.query("DELETE FROM compensi WHERE id = ?", [req.params.id]);
    res.json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Errore nella cancellazione" });
  }
});

// ------------------------------------
// DELETE /compensi  → AZZERA ARCHIVIO
// ------------------------------------
router.delete("/", async (req, res) => {
  try {
    await db.query("DELETE FROM compensi");
    res.json({ ok: true, message: "Archivio compensi azzerato" });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Errore nell'azzeramento dell'archivio" });
  }
});

module.exports = router;
