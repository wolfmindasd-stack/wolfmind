"""One-off cleanup of UI-test leftovers (ricevute/abbonamenti/verbali with UITEST/TEST_ markers)."""
import os
import re
from pathlib import Path

import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
API = (os.environ.get("REACT_APP_BACKEND_URL") or fe["REACT_APP_BACKEND_URL"]).rstrip("/") + "/api"
c = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
creds = {"email": re.search(r"(?im)^\s*[-*]?\s*Email:\s*`?([^`\s]+)", c).group(1),
         "password": re.search(r"(?im)^\s*[-*]?\s*Password:\s*`?([^`\s]+)", c).group(1)}

s = requests.Session()
r = s.post(f"{API}/auth/login", json=creds, timeout=30)
r.raise_for_status()


def blob(d):
    return str(d)


removed = []
for ric in s.get(f"{API}/ricevute", timeout=30).json():
    if "UITEST" in blob(ric) or "TEST_" in blob(ric):
        s.delete(f"{API}/ricevute/{ric['id']}", timeout=30)
        removed.append(("ricevuta", ric.get("numero")))
for ab in s.get(f"{API}/abbonamenti", timeout=30).json():
    if "UITEST" in blob(ab) or "TEST_" in blob(ab):
        s.delete(f"{API}/abbonamenti/{ab['id']}", timeout=30)
        removed.append(("abbonamento", ab.get("descrizione")))
for v in s.get(f"{API}/verbali", timeout=30).json():
    if "UITEST" in blob(v) or "TEST_" in blob(v):
        s.delete(f"{API}/verbali/{v['id']}", timeout=30)
        removed.append(("verbale", v.get("oggetto")))
for t in s.get(f"{API}/tesserati", timeout=30).json():
    if str(t.get("cognome", "")).startswith("TEST_"):
        s.delete(f"{API}/tesserati/{t['id']}", timeout=30)
        removed.append(("tesserato", t.get("cognome")))
print("removed:", removed)
