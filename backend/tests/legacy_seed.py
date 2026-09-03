"""Helper: insert a legacy tipo_pacchetto (no esclude_da_compensi) to validate the
startup backfill migration, clear login_attempts, and reset organizzazione images.

Usage:
  python tests/legacy_seed.py seed     # insert legacy doc + clear login_attempts
  python tests/legacy_seed.py cleanup  # remove legacy doc
"""
import sys

from dotenv import dotenv_values
from pymongo import MongoClient

env = dotenv_values("/app/backend/.env")
db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]

LEGACY_NAME = "TEST_legacy_pack_no_flag"

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if mode == "seed":
        db.tipi_pacchetto.delete_many({"nome": LEGACY_NAME})
        db.tipi_pacchetto.insert_one({
            "nome": LEGACY_NAME, "descrizione": "legacy", "num_lezioni": 3,
            "prezzo_default": 30.0, "attivo": True, "created_at": "2025-01-01T00:00:00+00:00"})
        db.login_attempts.delete_many({})
        db.organizzazione.update_one({"_id": "config"},
                                     {"$set": {"logo_base64": None,
                                               "president_signature_base64": None}})
        doc = db.tipi_pacchetto.find_one({"nome": LEGACY_NAME})
        print("seeded legacy doc, esclude_da_compensi present:",
              "esclude_da_compensi" in doc)
    else:
        print("deleted:", db.tipi_pacchetto.delete_many({"nome": LEGACY_NAME}).deleted_count)
