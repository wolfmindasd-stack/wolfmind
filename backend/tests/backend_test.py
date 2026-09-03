"""Wolf's Mind ASD gestionale - backend API tests (pytest).

Iteration 2: covers numero_tessera, president_signature_base64, esclude_da_compensi,
emesso_per_id attribution, physical DELETE ricevuta + counter decrement,
lezioni collettive (partecipanti), /abbonamenti/{id}/storico,
/movimenti/riepilogo-mensile, dashboard tecnico vs admin, PDF auth.
Run serially: cd /app/backend && python -m pytest tests/backend_test.py -q -n 0
"""
import os
import re
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

TS = uuid.uuid4().hex[:8]
TODAY = datetime.now(timezone.utc).date().isoformat()
YEAR = datetime.now(timezone.utc).year
# Valid 120x40 PNG (renderable by reportlab/PIL) used as logo + president signature.
PNG_SIGN = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAAoCAIAAAC6iKly"
            "AAAAhElEQVR4nO3ZsQ2AMAwAQYzYf+WwQToeCe5aN9YXbjxrrYPnnW8v8BdCR4SOCB0R"
            "OiJ0ROiI0BGhI0JHhI4IHRE6InRE6IjQEaEjQkeEjlz78cw0e3zA/vs6nrMNpyMidETo"
            "iNARoSNCR4SOCB0ROiJ0ROiI0BGhI0JHhI4IHRE6InTkBokKCUuvZOX7AAAAAElFTkSu"
            "QmCC")
# Base64 that decodes but is NOT a valid image stream (must be silently skipped).
CORRUPT_IMG = "data:image/png;base64,notarealimage"
# Definitive president name (iteration-5 migration target).
PRESIDENT_NAME = "Drovetti Cassiano Bruno"


def _db():
    """Direct mongo handle (used only for lockout state / counter edge cases)."""
    from pymongo import MongoClient
    env = dotenv_values("/app/backend/.env")
    return MongoClient(env["MONGO_URL"])[env["DB_NAME"]]


def clear_login_attempts():
    _db().login_attempts.delete_many({})


# ------------------------- fixtures -------------------------
@pytest.fixture(scope="session", autouse=True)
def _reset_lockout():
    """Lockout is now keyed on email only, so stale counters would block admin login."""
    clear_login_attempts()
    yield
    clear_login_attempts()
@pytest.fixture(scope="session")
def admin_creds():
    p = Path("/app/memory/test_credentials.md")
    if not p.exists():
        pytest.skip("missing test_credentials.md")
    c = p.read_text()
    e = re.search(r'(?im)^\s*[-*]?\s*(?:\*\*)?Email(?:\*\*)?\s*:\s*`?([^`\s]+)', c)
    pw = re.search(r'(?im)^\s*[-*]?\s*(?:\*\*)?Password(?:\*\*)?\s*:\s*`?([^`\s]+)', c)
    if not e or not pw:
        pytest.skip("credentials not parseable")
    return {"email": e.group(1), "password": pw.group(1)}


@pytest.fixture(scope="session")
def admin(admin_creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=admin_creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    return s


@pytest.fixture(scope="session")
def mk_tecnico(admin):
    """Factory: create a tecnico user, return (session, user_dict). Cleaned up at session end."""
    created = []

    def _mk(perc=50.0):
        tag = uuid.uuid4().hex[:6]
        payload = {"email": f"test_tec_{tag}@example.com", "password": "TecPass2026!",
                   "name": f"TEST_Tecnico_{tag}", "role": "tecnico",
                   "percentuale_compenso": perc}
        r = admin.post(f"{API}/users", json=payload, timeout=30)
        if r.status_code not in (200, 201):
            pytest.fail(f"tecnico create failed {r.status_code}: {r.text[:300]}")
        u = r.json()
        created.append(u["id"])
        s = requests.Session()
        lr = s.post(f"{API}/auth/login", json={"email": payload["email"],
                                               "password": payload["password"]}, timeout=30)
        if lr.status_code != 200:
            pytest.fail(f"tecnico login failed {lr.status_code}: {lr.text[:300]}")
        return s, u
    yield _mk
    for uid in created:
        admin.delete(f"{API}/users/{uid}", timeout=30)


@pytest.fixture(scope="session")
def mk_tesserato(admin):
    created = []

    def _mk(session=None, **extra):
        tag = uuid.uuid4().hex[:6].upper()
        payload = {"cognome": "TEST_Rossi", "nome": f"M{tag}",
                   "codice_fiscale": f"RSSMRA80A01{tag}1Z", "indirizzo": "Via Roma",
                   "civico": "1", "cap": "10070", "citta": "Front", "provincia": "TO",
                   "email": "delivered@resend.dev", "telefono": "+39 3331234567"}
        payload.update(extra)
        r = (session or admin).post(f"{API}/tesserati", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        t = r.json()
        created.append(t["id"])
        return t
    yield _mk
    for tid in created:
        admin.delete(f"{API}/tesserati/{tid}", timeout=30)


def mk_ricevuta(session, tesserato_id, items=None, data="2026-03-15", **extra):
    body = {"tesserato_id": tesserato_id, "data": data, "metodo_pagamento": "Contanti",
            "items": items or [{"descrizione": "TEST_Pacchetto 12 lezioni",
                                "num_lezioni": 12, "importo": 100.0}],
            "note": "TEST"}
    body.update(extra)
    return session.post(f"{API}/ricevute", json=body, timeout=30)


# ------------------------- AUTH -------------------------
class TestAuth:
    def test_login_admin(self, admin_creds):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=admin_creds, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["user"]["email"] == admin_creds["email"]
        assert d["user"]["role"] == "admin"
        assert "password_hash" not in d["user"] and "_id" not in d["user"]
        assert isinstance(d.get("access_token"), str) and d["access_token"]
        raw = r.headers.get("set-cookie", "")
        assert "access_token" in raw and "HttpOnly" in raw, raw
        assert "refresh_token" in raw

    def test_me(self, admin, admin_creds):
        r = admin.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["email"] == admin_creds["email"] and d["role"] == "admin"
        assert "id" in d and "_id" not in d and "password_hash" not in d

    def test_login_wrong_password(self, admin_creds):
        r = requests.post(f"{API}/auth/login",
                          json={"email": admin_creds["email"], "password": "WrongPass1!"},
                          timeout=30)
        assert r.status_code == 401, r.text[:300]

    def test_unauthenticated_401(self):
        assert requests.get(f"{API}/tesserati", timeout=30).status_code == 401

    def test_bearer_token_auth(self, admin_creds):
        tok = requests.post(f"{API}/auth/login", json=admin_creds, timeout=30).json()["access_token"]
        r2 = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r2.status_code == 200 and r2.json()["role"] == "admin"

    def test_bcrypt_hash_format(self):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        env = dotenv_values("/app/backend/.env")

        async def _get():
            c = AsyncIOMotorClient(env["MONGO_URL"])
            u = await c[env["DB_NAME"]].users.find_one({"email": env["ADMIN_EMAIL"].lower()})
            c.close()
            return u
        u = asyncio.run(_get())
        assert u is not None, "admin not seeded"
        assert u["password_hash"].startswith("$2b$"), u["password_hash"][:10]

    def test_brute_force_lockout(self):
        """Lockout after 5 failed attempts (uses a throwaway email, not admin)."""
        email = f"test_bf_{uuid.uuid4().hex[:8]}@example.com"
        codes = []
        for _ in range(6):
            r = requests.post(f"{API}/auth/login",
                              json={"email": email, "password": "Bad!12345"}, timeout=30)
            codes.append(r.status_code)
        assert codes[:5] == [401] * 5, codes
        assert codes[5] == 429, f"no lockout, codes={codes}"

    def test_brute_force_lockout_admin_email(self, admin_creds):
        """Fix 1: lockout is keyed on email only -> must trigger for the real admin email
        and must persist while the window is open; clearing login_attempts unlocks."""
        clear_login_attempts()
        codes = []
        for _ in range(6):
            r = requests.post(f"{API}/auth/login",
                              json={"email": admin_creds["email"], "password": "Wrong!12345"},
                              timeout=30)
            codes.append(r.status_code)
        assert 429 in codes[4:6], f"no lockout for admin email, codes={codes}"
        # still locked on the next wrong attempt (window open)
        again = requests.post(f"{API}/auth/login",
                              json={"email": admin_creds["email"], "password": "Wrong!12345"},
                              timeout=30)
        assert again.status_code == 429, again.status_code
        # even the CORRECT password is refused while locked
        locked_ok = requests.post(f"{API}/auth/login", json=admin_creds, timeout=30)
        assert locked_ok.status_code == 429, locked_ok.status_code
        # unlock and verify success
        clear_login_attempts()
        ok = requests.post(f"{API}/auth/login", json=admin_creds, timeout=30)
        assert ok.status_code == 200, ok.text[:300]

    def test_logout(self, admin_creds):
        s = requests.Session()
        s.post(f"{API}/auth/login", json=admin_creds, timeout=30)
        assert s.post(f"{API}/auth/logout", timeout=30).status_code == 200
        assert s.get(f"{API}/auth/me", timeout=30).status_code == 401


class TestCors:
    def test_cors_app_level_explicit_origin(self):
        """App must echo an explicit origin (not '*') alongside allow-credentials.
        NOTE: checked on the app port because the k8s ingress rewrites CORS headers to '*'."""
        r = requests.get("http://localhost:8001/api/tesserati",
                         headers={"Origin": BASE_URL}, timeout=30)
        assert r.headers.get("access-control-allow-credentials") == "true"
        acao = r.headers.get("access-control-allow-origin")
        assert acao == BASE_URL, acao

    def test_cors_public_url_headers(self):
        r = requests.get(f"{API}/tesserati", headers={"Origin": BASE_URL}, timeout=30)
        acao = r.headers.get("access-control-allow-origin")
        acac = r.headers.get("access-control-allow-credentials")
        assert acac == "true"
        # Informational: ingress currently returns '*'; browsers reject '*'+credentials
        assert acao in ("*", BASE_URL), acao


# ------------------------- USERS -------------------------
class TestUsers:
    def test_tecnico_can_list_users(self, mk_tecnico):
        s, u = mk_tecnico()
        r = s.get(f"{API}/users", timeout=30)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert any(x["id"] == u["id"] for x in data)
        assert all("password_hash" not in x for x in data)

    def test_duplicate_email_409(self, admin, mk_tecnico):
        _, u = mk_tecnico()
        r = admin.post(f"{API}/users", json={"email": u["email"], "password": "Xx123456",
                                             "name": "dup", "role": "tecnico"}, timeout=30)
        assert r.status_code == 409, r.status_code

    def test_role_protection(self, mk_tecnico):
        s, _ = mk_tecnico()
        assert s.post(f"{API}/users", json={"email": f"x{TS}@e.com", "password": "aaaaaa",
                                            "name": "x"}, timeout=30).status_code == 403
        assert s.post(f"{API}/tipi-pacchetto", json={"nome": "TEST_x"}, timeout=30).status_code == 403
        assert s.post(f"{API}/movimenti", json={"data": "2026-03-01", "tipo": "uscita",
                                                "categoria": "c", "descrizione": "d",
                                                "importo": 1}, timeout=30).status_code == 403


# ------------------------- TESSERATI (numero_tessera) -------------------------
class TestTesserati:
    def test_numero_tessera_crud(self, admin):
        payload = {"numero_tessera": f"{YEAR}-001", "cognome": "TEST_Bianchi", "nome": "Luca",
                   "codice_fiscale": f"BNCLCA80A01H50{TS[:2]}", "citta": "Torino"}
        r = admin.post(f"{API}/tesserati", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        t = r.json()
        assert t["numero_tessera"] == f"{YEAR}-001"
        g = admin.get(f"{API}/tesserati/{t['id']}", timeout=30)
        assert g.status_code == 200 and g.json()["numero_tessera"] == f"{YEAR}-001"
        p = admin.patch(f"{API}/tesserati/{t['id']}", json={"numero_tessera": f"{YEAR}-999"},
                        timeout=30)
        assert p.status_code == 200 and p.json()["numero_tessera"] == f"{YEAR}-999"
        assert admin.get(f"{API}/tesserati/{t['id']}",
                         timeout=30).json()["numero_tessera"] == f"{YEAR}-999"
        assert admin.delete(f"{API}/tesserati/{t['id']}", timeout=30).status_code == 200
        assert admin.get(f"{API}/tesserati/{t['id']}", timeout=30).status_code == 404

    def test_numero_tessera_optional(self, mk_tesserato):
        t = mk_tesserato()
        assert t.get("numero_tessera") is None

    def test_bad_id_400(self, admin):
        assert admin.get(f"{API}/tesserati/notanid", timeout=30).status_code == 400


# ------------------------- ORGANIZZAZIONE (firma) -------------------------
class TestOrganizzazione:
    def test_signature_and_logo(self, admin, mk_tecnico):
        r = admin.get(f"{API}/organizzazione", timeout=30)
        assert r.status_code == 200 and "Wolf" in r.json()["name"]
        p = admin.patch(f"{API}/organizzazione", json={
            "president_signature_base64": PNG_SIGN, "logo_base64": PNG_SIGN,
            "president_name": "TEST_Presidente"}, timeout=30)
        assert p.status_code == 200, p.text[:300]
        assert p.json()["president_signature_base64"] == PNG_SIGN
        assert p.json()["president_name"] == "TEST_Presidente"
        g = admin.get(f"{API}/organizzazione", timeout=30).json()
        assert g["president_signature_base64"] == PNG_SIGN
        assert g["logo_base64"] == PNG_SIGN
        assert "_id" not in g and g["id"] == "config"
        # restore the real president name (must not leak test data into the config doc)
        rb = admin.patch(f"{API}/organizzazione",
                         json={"president_name": PRESIDENT_NAME}, timeout=30)
        assert rb.status_code == 200 and rb.json()["president_name"] == PRESIDENT_NAME
        s, _ = mk_tecnico()
        assert s.patch(f"{API}/organizzazione", json={"name": "hack"},
                       timeout=30).status_code == 403


# ------------------------- TIPI PACCHETTO -------------------------
class TestTipiPacchetto:
    def test_list_not_empty_and_shape(self, admin):
        r = admin.get(f"{API}/tipi-pacchetto", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data, "no tipi pacchetto"
        for x in data:
            assert "_id" not in x and "id" in x
            assert "esclude_da_compensi" in x

    def test_esclude_da_compensi_flag(self, admin):
        r = admin.post(f"{API}/tipi-pacchetto", json={"nome": f"TEST_pack_{TS}",
                                                      "num_lezioni": 5, "prezzo_default": 55.0,
                                                      "esclude_da_compensi": True}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        p = r.json()
        assert p["esclude_da_compensi"] is True
        got = [x for x in admin.get(f"{API}/tipi-pacchetto", timeout=30).json()
               if x["id"] == p["id"]][0]
        assert got["esclude_da_compensi"] is True
        u = admin.patch(f"{API}/tipi-pacchetto/{p['id']}",
                        json={"esclude_da_compensi": False}, timeout=30)
        assert u.status_code == 200, u.text[:200]
        assert u.json()["esclude_da_compensi"] is False, "PATCH false ignored"
        got = [x for x in admin.get(f"{API}/tipi-pacchetto", timeout=30).json()
               if x["id"] == p["id"]][0]
        assert got["esclude_da_compensi"] is False
        assert admin.delete(f"{API}/tipi-pacchetto/{p['id']}", timeout=30).status_code == 200


# ------------------------- RICEVUTE: attribuzione -------------------------
class TestRicevutaAttribuzione:
    def test_admin_attributes_to_tecnico(self, admin, mk_tecnico, mk_tesserato):
        tec_s, tec_u = mk_tecnico()
        tec2_s, tec2_u = mk_tecnico()
        t = mk_tesserato()
        r = mk_ricevuta(admin, t["id"], emesso_per_id=tec_u["id"])
        assert r.status_code in (200, 201), r.text[:300]
        d = r.json()
        try:
            assert d["emesso_per_id"] == tec_u["id"]
            assert d["emesso_per_nome"] == tec_u["name"]
            assert d["emesso_da_id"] != tec_u["id"], "emesso_da should stay admin"
            # movimento tecnico_id
            movs = [m for m in admin.get(f"{API}/movimenti", timeout=30).json()
                    if m.get("ricevuta_id") == d["id"]]
            assert len(movs) == 1 and movs[0]["tecnico_id"] == tec_u["id"]
            # tecnico1 sees it
            lst = tec_s.get(f"{API}/ricevute", timeout=30).json()
            assert any(x["id"] == d["id"] for x in lst)
            assert all(x["emesso_per_id"] == tec_u["id"] for x in lst)
            assert tec_s.get(f"{API}/ricevute/{d['id']}", timeout=30).status_code == 200
            # tecnico2 cannot
            assert tec2_s.get(f"{API}/ricevute/{d['id']}", timeout=30).status_code == 403
            assert all(x["id"] != d["id"] for x in tec2_s.get(f"{API}/ricevute",
                                                              timeout=30).json())
            # PATCH re-attribution syncs movimento
            p = admin.patch(f"{API}/ricevute/{d['id']}",
                            json={"emesso_per_id": tec2_u["id"]}, timeout=30)
            assert p.status_code == 200, p.text[:300]
            assert p.json()["emesso_per_id"] == tec2_u["id"]
            assert p.json()["emesso_per_nome"] == tec2_u["name"]
            movs = [m for m in admin.get(f"{API}/movimenti", timeout=30).json()
                    if m.get("ricevuta_id") == d["id"]]
            assert movs[0]["tecnico_id"] == tec2_u["id"], "movimento not synced"
            # tecnico cannot patch someone else's ricevuta
            assert tec_s.patch(f"{API}/ricevute/{d['id']}", json={"note": "x"},
                               timeout=30).status_code == 403
            assert tec2_s.patch(f"{API}/ricevute/{d['id']}", json={"note": "x"},
                                timeout=30).status_code == 403
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)

    def test_tecnico_cannot_attribute_to_other(self, admin, mk_tecnico, mk_tesserato):
        tec_s, tec_u = mk_tecnico()
        _, other_u = mk_tecnico()
        t = mk_tesserato(session=tec_s)
        r = mk_ricevuta(tec_s, t["id"], emesso_per_id=other_u["id"])
        assert r.status_code in (200, 201), r.text[:300]
        d = r.json()
        try:
            assert d["emesso_per_id"] == tec_u["id"], "tecnico managed to reattribute"
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)

    def test_create_invalid_tesserato_404(self, admin):
        assert mk_ricevuta(admin, "507f1f77bcf86cd799439011").status_code == 404


# ------------------------- COMPENSI (esclude_da_compensi) -------------------------
class TestCompensi:
    def test_item_exclusion_math(self, admin, mk_tecnico, mk_tesserato):
        tec_s, tec_u = mk_tecnico(50.0)
        t = mk_tesserato()
        items = [{"descrizione": "TEST_12 lezioni", "num_lezioni": 12, "importo": 100.0},
                 {"descrizione": "TEST_Tesseramento", "importo": 30.0,
                  "esclude_da_compensi": True}]
        r = mk_ricevuta(admin, t["id"], items=items, data="2026-02-10",
                        emesso_per_id=tec_u["id"])
        assert r.status_code in (200, 201), r.text[:300]
        d = r.json()
        try:
            assert d["totale"] == 130.0
            assert d["items"][1]["esclude_da_compensi"] is True
            cp = admin.get(f"{API}/compensi?date_from=2026-02-01&date_to=2026-02-28", timeout=30)
            assert cp.status_code == 200, cp.text[:300]
            rows = [c for c in cp.json()["compensi"] if c["tecnico_id"] == tec_u["id"]]
            assert rows, "tecnico missing in compensi"
            row = rows[0]
            assert row["flusso_generato"] == pytest.approx(130.0)
            assert row["flusso_compensabile"] == pytest.approx(100.0)
            assert row["percentuale"] == 50.0
            assert row["compenso_dovuto"] == pytest.approx(50.0)
            assert row["n_ricevute"] == 1
            # tecnico sees only own row
            own = tec_s.get(f"{API}/compensi?date_from=2026-02-01&date_to=2026-02-28",
                            timeout=30).json()["compensi"]
            assert len(own) == 1 and own[0]["tecnico_id"] == tec_u["id"]
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)


# ------------------------- RICEVUTE: numerazione + delete fisico -------------------------
class TestRicevutaNumerazione:
    def test_delete_last_decrements_counter(self, admin, mk_tesserato):
        t = mk_tesserato()
        r1 = mk_ricevuta(admin, t["id"], data="2026-05-01")
        r2 = mk_ricevuta(admin, t["id"], data="2026-05-02")
        r3 = mk_ricevuta(admin, t["id"], data="2026-05-03")
        for r in (r1, r2, r3):
            assert r.status_code in (200, 201), r.text[:300]
        d1, d2, d3 = r1.json(), r2.json(), r3.json()
        n1 = int(d1["numero"].split("/")[1])
        assert re.match(r"^2026/\d{5}$", d1["numero"]), d1["numero"]
        assert int(d2["numero"].split("/")[1]) == n1 + 1
        assert int(d3["numero"].split("/")[1]) == n1 + 2
        movs_before = [m for m in admin.get(f"{API}/movimenti", timeout=30).json()
                       if m.get("ricevuta_id") == d3["id"]]
        assert len(movs_before) == 1

        # DELETE last -> reusable + physical
        de = admin.delete(f"{API}/ricevute/{d3['id']}", timeout=30)
        assert de.status_code == 200, de.text[:300]
        assert de.json().get("numero_riutilizzabile") is True, de.json()
        assert admin.get(f"{API}/ricevute/{d3['id']}", timeout=30).status_code == 404
        assert not [m for m in admin.get(f"{API}/movimenti", timeout=30).json()
                    if m.get("ricevuta_id") == d3["id"]]
        # next receipt reuses number
        r4 = mk_ricevuta(admin, t["id"], data="2026-05-04")
        d4 = r4.json()
        assert int(d4["numero"].split("/")[1]) == n1 + 2, (d3["numero"], d4["numero"])

        # DELETE a NON-last one -> no decrement
        de2 = admin.delete(f"{API}/ricevute/{d1['id']}", timeout=30)
        assert de2.status_code == 200
        assert de2.json().get("numero_riutilizzabile") is False, de2.json()
        r5 = mk_ricevuta(admin, t["id"], data="2026-05-05")
        assert int(r5.json()["numero"].split("/")[1]) == n1 + 3

        for rid in (d2["id"], d4["id"], r5.json()["id"]):
            admin.delete(f"{API}/ricevute/{rid}", timeout=30)

    def test_delete_nonexistent_404(self, admin):
        assert admin.delete(f"{API}/ricevute/507f1f77bcf86cd799439011",
                            timeout=30).status_code == 404

    def test_numero_riutilizzabile_is_bool_without_counter(self, admin, mk_tesserato):
        """Fix 4: when the year counter doc is missing the flag must be False, not null."""
        t = mk_tesserato()
        d = mk_ricevuta(admin, t["id"], data="2026-07-07").json()
        anno = d.get("anno", 2026)
        db = _db()
        prev = db.counters.find_one({"_id": f"ricevute_{anno}"})
        db.counters.delete_one({"_id": f"ricevute_{anno}"})
        de = admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)
        if prev:  # restore so later tests keep sequential numbering
            db.counters.update_one({"_id": f"ricevute_{anno}"},
                                   {"$set": {"seq": prev.get("seq")}}, upsert=True)
        assert de.status_code == 200, de.text[:300]
        body = de.json()
        assert body["numero_riutilizzabile"] is False, body
        assert isinstance(body["numero_riutilizzabile"], bool)

    def test_tecnico_cannot_delete(self, admin, mk_tecnico, mk_tesserato):
        s, u = mk_tecnico()
        t = mk_tesserato(session=s)
        d = mk_ricevuta(s, t["id"], data="2026-05-09").json()
        try:
            assert s.delete(f"{API}/ricevute/{d['id']}", timeout=30).status_code == 403
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)


# ------------------------- PDF -------------------------
class TestPdf:
    def test_ricevuta_pdf_with_cookie_and_without(self, admin, mk_tesserato):
        # ensure a valid logo + president signature are stored (PDF must embed them)
        admin.patch(f"{API}/organizzazione", json={"logo_base64": PNG_SIGN,
                                                   "president_signature_base64": PNG_SIGN},
                    timeout=30)
        t = mk_tesserato()
        d = mk_ricevuta(admin, t["id"], data="2026-06-01").json()
        try:
            pdf = admin.get(f"{API}/ricevute/{d['id']}/pdf", timeout=60)
            assert pdf.status_code == 200, pdf.text[:200]
            assert pdf.headers["content-type"].startswith("application/pdf")
            assert pdf.content[:4] == b"%PDF" and len(pdf.content) > 1000
            anon = requests.get(f"{API}/ricevute/{d['id']}/pdf", timeout=30)
            assert anon.status_code == 401, anon.status_code
            wa = admin.get(f"{API}/ricevute/{d['id']}/whatsapp-link", timeout=30)
            assert wa.status_code == 200 and wa.json()["url"].startswith("https://wa.me/")
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)

    def test_bilancio_pdf(self, admin):
        r = admin.get(f"{API}/report/bilancio/pdf?date_from=2026-01-01&date_to=2026-12-31",
                      timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF" and len(r.content) > 1000

    def test_bilancio_json(self, admin):
        r = admin.get(f"{API}/report/bilancio?date_from=2026-01-01&date_to=2026-12-31", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        t = d["totali"]
        assert t["saldo"] == pytest.approx(t["entrate"] - t["uscite"])
        assert all("_id" not in m for m in d["movimenti"])

    def test_bilancio_missing_params_422(self, admin):
        assert admin.get(f"{API}/report/bilancio", timeout=30).status_code == 422

    def test_pdf_resilient_to_corrupt_images(self, admin, mk_tesserato):
        """Fix 2: corrupt logo/signature base64 must be skipped, not 500."""
        t = mk_tesserato()
        d = mk_ricevuta(admin, t["id"], data="2026-06-11").json()
        try:
            p = admin.patch(f"{API}/organizzazione",
                            json={"logo_base64": CORRUPT_IMG,
                                  "president_signature_base64": CORRUPT_IMG}, timeout=30)
            assert p.status_code == 200, p.text[:200]
            pdf = admin.get(f"{API}/ricevute/{d['id']}/pdf", timeout=60)
            assert pdf.status_code == 200, f"{pdf.status_code}: {pdf.text[:300]}"
            assert pdf.headers["content-type"].startswith("application/pdf")
            assert pdf.content[:4] == b"%PDF"
            bil = admin.get(f"{API}/report/bilancio/pdf"
                            "?date_from=2026-01-01&date_to=2026-12-31", timeout=60)
            assert bil.status_code == 200, f"{bil.status_code}: {bil.text[:300]}"
            assert bil.content[:4] == b"%PDF"
            em = admin.post(f"{API}/ricevute/{d['id']}/send-email",
                            json={"email": "delivered@resend.dev"}, timeout=90)
            assert em.status_code == 200, f"{em.status_code}: {em.text[:300]}"
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)
            # NOTE: PATCH /organizzazione drops None values, so images cannot be
            # cleared through the API - reset directly to avoid test pollution.
            _db().organizzazione.update_one(
                {"_id": "config"},
                {"$set": {"logo_base64": None, "president_signature_base64": None}})


# ------------------------- LEZIONI COLLETTIVE + STORICO -------------------------
class TestLezioniCollettive:
    def test_multi_partecipanti_decrement(self, admin, mk_tecnico, mk_tesserato):
        tec_s, tec_u = mk_tecnico()
        t1 = mk_tesserato()
        t2 = mk_tesserato()
        abs_ = []
        for t in (t1, t2):
            r = admin.post(f"{API}/abbonamenti", json={
                "tesserato_id": t["id"], "descrizione": "TEST_12 lezioni",
                "num_lezioni_totali": 12, "prezzo": 100.0,
                "data_acquisto": "2026-03-01"}, timeout=30)
            assert r.status_code in (200, 201), r.text[:300]
            abs_.append(r.json())
        lezioni_ids = []
        try:
            for i in range(3):
                lr = admin.post(f"{API}/lezioni", json={
                    "data": f"2026-03-0{i+2}", "luogo": "Palestra TEST",
                    "tecnico_id": tec_u["id"], "note": "TEST",
                    "partecipanti": [{"tesserato_id": t1["id"], "abbonamento_id": abs_[0]["id"]},
                                     {"tesserato_id": t2["id"], "abbonamento_id": abs_[1]["id"]}]},
                    timeout=30)
                assert lr.status_code in (200, 201), lr.text[:300]
                ld = lr.json()
                assert len(ld["partecipanti"]) == 2
                assert ld["luogo"] == "Palestra TEST"
                assert ld["tecnico_id"] == tec_u["id"]
                lezioni_ids.append(ld["id"])

            lst = admin.get(f"{API}/abbonamenti", timeout=30).json()
            for ab in abs_:
                mine = [x for x in lst if x["id"] == ab["id"]][0]
                assert mine["lezioni_effettuate"] == 3, mine
                assert mine["lezioni_residue"] == 9, mine
            lez = admin.get(f"{API}/lezioni?abbonamento_id={abs_[0]['id']}", timeout=30).json()
            assert len(lez) == 3
            # tecnico sees his lessons
            tl = tec_s.get(f"{API}/lezioni", timeout=30).json()
            assert len({x["id"] for x in tl} & set(lezioni_ids)) == 3

            # storico
            st = admin.get(f"{API}/abbonamenti/{abs_[0]['id']}/storico", timeout=30)
            assert st.status_code == 200, st.text[:300]
            sd = st.json()
            for k in ["abbonamento", "tesserato", "lezioni", "ricevute",
                      "spesa_totale_abbonamento"]:
                assert k in sd, k
            assert sd["abbonamento"]["id"] == abs_[0]["id"]
            assert sd["tesserato"]["id"] == t1["id"]
            assert len(sd["lezioni"]) == 3
            assert sd["spesa_totale_abbonamento"] == 0.0

            # ricevuta referencing the abbonamento -> spesa
            ric = mk_ricevuta(admin, t1["id"], items=[
                {"descrizione": "TEST_acconto", "importo": 60.0,
                 "abbonamento_id": abs_[0]["id"]},
                {"descrizione": "TEST_altro", "importo": 25.0}], data="2026-03-10").json()
            try:
                sd2 = admin.get(f"{API}/abbonamenti/{abs_[0]['id']}/storico",
                                timeout=30).json()
                assert sd2["spesa_totale_abbonamento"] == pytest.approx(60.0), sd2
                assert len(sd2["ricevute"]) == 1
                assert all("_id" not in r for r in sd2["ricevute"])
            finally:
                admin.delete(f"{API}/ricevute/{ric['id']}", timeout=30)
        finally:
            for lid in lezioni_ids:
                admin.delete(f"{API}/lezioni/{lid}", timeout=30)
            for ab in abs_:
                admin.delete(f"{API}/abbonamenti/{ab['id']}", timeout=30)

    def test_abbonamento_esaurito_400(self, admin, mk_tesserato):
        t = mk_tesserato()
        ab = admin.post(f"{API}/abbonamenti", json={
            "tesserato_id": t["id"], "descrizione": "TEST_1 lezione",
            "num_lezioni_totali": 1, "prezzo": 10.0,
            "data_acquisto": "2026-03-01"}, timeout=30).json()
        lids = []
        try:
            r1 = admin.post(f"{API}/lezioni", json={
                "data": "2026-03-02", "luogo": "X",
                "partecipanti": [{"tesserato_id": t["id"], "abbonamento_id": ab["id"]}]},
                timeout=30)
            assert r1.status_code in (200, 201), r1.text[:300]
            lids.append(r1.json()["id"])
            r2 = admin.post(f"{API}/lezioni", json={
                "data": "2026-03-03", "luogo": "X",
                "partecipanti": [{"tesserato_id": t["id"], "abbonamento_id": ab["id"]}]},
                timeout=30)
            assert r2.status_code == 400, r2.status_code
            assert "esaurito" in r2.json().get("detail", "").lower(), r2.text[:200]
        finally:
            for lid in lids:
                admin.delete(f"{API}/lezioni/{lid}", timeout=30)
            admin.delete(f"{API}/abbonamenti/{ab['id']}", timeout=30)

    def test_lezione_no_partecipanti_400(self, admin):
        r = admin.post(f"{API}/lezioni", json={"data": "2026-03-01", "partecipanti": []},
                       timeout=30)
        assert r.status_code == 400, r.status_code

    def test_lezione_invalid_abbonamento_404(self, admin):
        r = admin.post(f"{API}/lezioni", json={
            "data": "2026-03-01",
            "partecipanti": [{"tesserato_id": "507f1f77bcf86cd799439011",
                              "abbonamento_id": "507f1f77bcf86cd799439011"}]}, timeout=30)
        assert r.status_code == 404, r.status_code

    def test_storico_invalid_404(self, admin):
        assert admin.get(f"{API}/abbonamenti/507f1f77bcf86cd799439011/storico",
                         timeout=30).status_code == 404


# ------------------------- MOVIMENTI + RIEPILOGO MENSILE -------------------------
class TestMovimenti:
    def test_crud_and_filter(self, admin):
        r = admin.post(f"{API}/movimenti", json={"data": "2026-04-10", "tipo": "uscita",
                                                  "categoria": "TEST_Affitto",
                                                  "descrizione": "TEST_palestra",
                                                  "importo": 200.0}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        m = r.json()
        assert m["tipo"] == "uscita" and "_id" not in m
        f = admin.get(f"{API}/movimenti?date_from=2026-04-01&date_to=2026-04-30", timeout=30)
        assert f.status_code == 200 and any(x["id"] == m["id"] for x in f.json())
        out = admin.get(f"{API}/movimenti?date_from=2026-05-01&date_to=2026-05-31", timeout=30)
        assert all(x["id"] != m["id"] for x in out.json())
        p = admin.patch(f"{API}/movimenti/{m['id']}", json={"importo": 250.0}, timeout=30)
        assert p.status_code == 200 and p.json()["importo"] == 250.0
        assert admin.delete(f"{API}/movimenti/{m['id']}", timeout=30).status_code == 200
        assert admin.delete(f"{API}/movimenti/{m['id']}", timeout=30).status_code == 404

    def test_riepilogo_mensile(self, admin):
        mv = admin.post(f"{API}/movimenti", json={"data": "2026-08-15", "tipo": "uscita",
                                                   "categoria": "TEST_Cat",
                                                   "descrizione": "TEST_riep",
                                                   "importo": 40.0}, timeout=30).json()
        try:
            r = admin.get(f"{API}/movimenti/riepilogo-mensile?year=2026", timeout=30)
            assert r.status_code == 200, r.text[:300]
            d = r.json()
            assert d["year"] == 2026
            assert len(d["mesi"]) == 12
            assert [m["mese"] for m in d["mesi"]] == [f"2026-{i:02d}" for i in range(1, 13)]
            for m in d["mesi"]:
                for k in ["entrate", "uscite", "saldo", "count"]:
                    assert k in m, k
                assert m["saldo"] == pytest.approx(m["entrate"] - m["uscite"])
            aug = [m for m in d["mesi"] if m["mese"] == "2026-08"][0]
            assert aug["uscite"] >= 40.0 and aug["count"] >= 1
            tot = d["totali"]
            assert tot["entrate"] == pytest.approx(sum(m["entrate"] for m in d["mesi"]))
            assert tot["uscite"] == pytest.approx(sum(m["uscite"] for m in d["mesi"]))
            assert tot["saldo"] == pytest.approx(tot["entrate"] - tot["uscite"])
        finally:
            admin.delete(f"{API}/movimenti/{mv['id']}", timeout=30)

    def test_riepilogo_missing_year_422(self, admin):
        assert admin.get(f"{API}/movimenti/riepilogo-mensile", timeout=30).status_code == 422

    def test_tecnico_movimenti_filtered(self, admin, mk_tecnico, mk_tesserato):
        s, u = mk_tecnico()
        t = mk_tesserato(session=s)
        d = mk_ricevuta(s, t["id"], data="2026-07-02").json()
        try:
            movs = s.get(f"{API}/movimenti", timeout=30).json()
            assert all(m.get("tecnico_id") == u["id"] for m in movs), "sees others' movimenti"
            assert any(m.get("ricevuta_id") == d["id"] for m in movs)
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)


# ------------------------- DASHBOARD -------------------------
class TestDashboard:
    def test_admin_dashboard(self, admin):
        r = admin.get(f"{API}/dashboard", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ["tesserati_count", "abbon_count", "ricevute_mese_count", "incassato_mese",
                  "entrate_anno", "uscite_anno", "saldo_anno", "compenso_maturato",
                  "scadenze_imminenti"]:
            assert k in d, k
        assert isinstance(d["tesserati_count"], int) and isinstance(d["abbon_count"], int)
        assert d["compenso_maturato"] is None
        assert d["saldo_anno"] == pytest.approx(d["entrate_anno"] - d["uscite_anno"])
        assert isinstance(d["scadenze_imminenti"], list)

    def test_tecnico_dashboard_scoped(self, admin, mk_tecnico, mk_tesserato):
        s, u = mk_tecnico(50.0)
        # tesserato created by the tecnico, with imminent expiry
        soon = (datetime.now(timezone.utc).date().replace(day=1)).isoformat()
        from datetime import timedelta
        soon = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()
        t_own = mk_tesserato(session=s, scadenza_tesseramento=soon)
        mk_tesserato()  # admin-owned, must not be counted
        d_ric = mk_ricevuta(admin, t_own["id"], items=[
            {"descrizione": "TEST_pack", "importo": 100.0},
            {"descrizione": "TEST_quota", "importo": 30.0, "esclude_da_compensi": True}],
            data=TODAY, emesso_per_id=u["id"]).json()
        try:
            r = s.get(f"{API}/dashboard", timeout=30)
            assert r.status_code == 200, r.text[:300]
            d = r.json()
            assert d["tesserati_count"] == 1, d["tesserati_count"]
            assert d["ricevute_mese_count"] == 1, d
            assert d["incassato_mese"] == pytest.approx(130.0)
            assert isinstance(d["compenso_maturato"], (int, float))
            assert d["compenso_maturato"] == pytest.approx(50.0), d["compenso_maturato"]
            assert [x["id"] for x in d["scadenze_imminenti"]] == [t_own["id"]]
        finally:
            admin.delete(f"{API}/ricevute/{d_ric['id']}", timeout=30)


# ------------------------- EMAIL -------------------------
class TestEmail:
    def test_send_email_with_pdf(self, admin, mk_tesserato):
        t = mk_tesserato()
        d = mk_ricevuta(admin, t["id"], data="2026-06-20").json()
        try:
            e = admin.post(f"{API}/ricevute/{d['id']}/send-email",
                           json={"email": "delivered@resend.dev",
                                 "message": "Grazie e buona giornata"}, timeout=90)
            assert e.status_code == 200, f"{e.status_code}: {e.text[:300]}"
            body = e.json()
            assert body["ok"] is True and body.get("email_id"), body
            doc = admin.get(f"{API}/ricevute/{d['id']}", timeout=30).json()
            assert doc["last_sent_email_to"] == "delivered@resend.dev", doc
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)


# ------------------------- ITERATION 4: PUBLIC PDF TOKEN -------------------------
class TestPublicReceiptPdf:
    def test_public_pdf_unauthenticated(self, admin, mk_tesserato):
        t = mk_tesserato()
        d = mk_ricevuta(admin, t["id"], data="2026-04-02").json()
        try:
            assert d.get("public_token"), f"public_token missing on create: {d}"
            anon = requests.Session()  # no cookies / no auth header
            r = anon.get(f"{API}/public/ricevuta/{d['public_token']}/pdf", timeout=60)
            assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
            assert r.headers.get("content-type", "").startswith("application/pdf"), r.headers
            assert r.content[:4] == b"%PDF", r.content[:20]
            assert len(r.content) > 1000
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)

    def test_public_pdf_invalid_token_404(self):
        anon = requests.Session()
        r = anon.get(f"{API}/public/ricevuta/{uuid.uuid4().hex}/pdf", timeout=30)
        assert r.status_code == 404, f"{r.status_code}: {r.text[:200]}"

    def test_public_pdf_after_delete_404(self, admin, mk_tesserato):
        t = mk_tesserato()
        d = mk_ricevuta(admin, t["id"], data="2026-04-03").json()
        token = d["public_token"]
        assert admin.delete(f"{API}/ricevute/{d['id']}", timeout=30).status_code == 200
        r = requests.get(f"{API}/public/ricevuta/{token}/pdf", timeout=30)
        assert r.status_code == 404, f"{r.status_code}: {r.text[:200]}"


# ------------------------- ITERATION 4: SEND TRACKING -------------------------
class TestSendTracking:
    def test_email_tracking_fields(self, admin, mk_tesserato):
        t = mk_tesserato()
        d = mk_ricevuta(admin, t["id"], data="2026-04-04").json()
        try:
            assert d["last_sent_email_at"] is None and d["last_sent_email_to"] is None
            e = admin.post(f"{API}/ricevute/{d['id']}/send-email",
                           json={"email": "delivered@resend.dev"}, timeout=120)
            assert e.status_code == 200, f"{e.status_code}: {e.text[:300]}"
            assert e.json().get("email_id"), e.json()
            doc = admin.get(f"{API}/ricevute/{d['id']}", timeout=30).json()
            assert doc["last_sent_email_to"] == "delivered@resend.dev", doc
            assert isinstance(doc["last_sent_email_at"], str) and doc["last_sent_email_at"]
            datetime.fromisoformat(doc["last_sent_email_at"].replace("Z", "+00:00"))
            # list endpoint exposes tracking fields too
            lst = admin.get(f"{API}/ricevute", timeout=60).json()
            row = next(x for x in lst if x["id"] == d["id"])
            assert row["last_sent_email_to"] == "delivered@resend.dev", row
            assert row["last_sent_email_at"]
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)

    def test_mark_whatsapp_and_link(self, admin, mk_tesserato):
        t = mk_tesserato()
        d = mk_ricevuta(admin, t["id"], data="2026-04-05").json()
        try:
            r = admin.post(f"{API}/ricevute/{d['id']}/mark-whatsapp", timeout=30)
            assert r.status_code == 200, r.text[:300]
            assert r.json() == {"ok": True}
            doc = admin.get(f"{API}/ricevute/{d['id']}", timeout=30).json()
            assert isinstance(doc["last_sent_whatsapp_at"], str)
            datetime.fromisoformat(doc["last_sent_whatsapp_at"].replace("Z", "+00:00"))
            wl = admin.get(f"{API}/ricevute/{d['id']}/whatsapp-link", timeout=30)
            assert wl.status_code == 200, wl.text[:300]
            body = wl.json()
            assert body["url"].startswith("https://wa.me/"), body
            assert f"public/ricevuta/{d['public_token']}/pdf" in body["pdf_url"], body
            # the link handed to the user must actually work unauthenticated
            pr = requests.get(body["pdf_url"], timeout=60)
            assert pr.status_code == 200 and pr.content[:4] == b"%PDF", pr.status_code
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)

    def test_mark_whatsapp_404(self, admin):
        r = admin.post(f"{API}/ricevute/{'0' * 24}/mark-whatsapp", timeout=30)
        assert r.status_code == 404, r.status_code


# ------------------------- ITERATION 4: CALENDARIO -------------------------
class TestCalendario:
    def _mk_slot(self, session, **extra):
        body = {"data": "2026-03-01", "ora": "18:00", "durata_min": 60,
                "luogo": "Palestra Front", "capacita": 8, "descrizione": "TEST_slot"}
        body.update(extra)
        return session.post(f"{API}/calendario", json=body, timeout=30)

    def test_recurrence_creates_weekly_slots(self, admin):
        r = self._mk_slot(admin, ricorrenza_settimanale=True,
                          ricorrenza_fino_al="2026-03-22", descrizione="TEST_ric")
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["created"] == 4, body
        assert len(body["slots"]) == 4
        ids = [s["id"] for s in body["slots"]]
        try:
            dates = sorted(s["data"] for s in body["slots"])
            assert dates == ["2026-03-01", "2026-03-08", "2026-03-15", "2026-03-22"], dates
            for s in body["slots"]:
                assert s["ora"] == "18:00" and s["capacita"] == 8
                assert s["prenotazioni"] == []
                assert "_id" not in s
            lst = admin.get(f"{API}/calendario",
                            params={"date_from": "2026-03-01", "date_to": "2026-03-31"},
                            timeout=30)
            assert lst.status_code == 200, lst.text[:300]
            got = [s for s in lst.json() if s["id"] in ids]
            assert len(got) == 4, len(got)
        finally:
            for sid in ids:
                admin.delete(f"{API}/calendario/{sid}", timeout=30)

    def test_single_slot_crud(self, admin):
        r = self._mk_slot(admin, data="2026-05-04", ricorrenza_settimanale=False)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["created"] == 1, body
        sid = body["slots"][0]["id"]
        p = admin.patch(f"{API}/calendario/{sid}",
                        json={"ora": "19:30", "capacita": 4, "luogo": "TEST_Sala B"}, timeout=30)
        assert p.status_code == 200, p.text[:300]
        assert p.json()["ora"] == "19:30" and p.json()["capacita"] == 4
        got = admin.get(f"{API}/calendario", params={"date_from": "2026-05-04",
                                                     "date_to": "2026-05-04"}, timeout=30).json()
        row = next(s for s in got if s["id"] == sid)
        assert row["ora"] == "19:30" and row["luogo"] == "TEST_Sala B"
        d = admin.delete(f"{API}/calendario/{sid}", timeout=30)
        assert d.status_code == 200 and d.json()["ok"] is True
        got = admin.get(f"{API}/calendario", params={"date_from": "2026-05-04",
                                                     "date_to": "2026-05-04"}, timeout=30).json()
        assert all(s["id"] != sid for s in got)
        assert admin.delete(f"{API}/calendario/{sid}", timeout=30).status_code == 404

    def test_tecnico_cannot_create_for_other(self, mk_tecnico):
        s1, _ = mk_tecnico()
        _, u2 = mk_tecnico()
        r = self._mk_slot(s1, data="2026-05-11", tecnico_id=u2["id"])
        assert r.status_code == 403, f"{r.status_code}: {r.text[:200]}"

    def test_tecnico_cannot_edit_other_slot(self, admin, mk_tecnico):
        s1, _ = mk_tecnico()
        r = self._mk_slot(admin, data="2026-05-18")
        sid = r.json()["slots"][0]["id"]
        try:
            assert s1.patch(f"{API}/calendario/{sid}", json={"ora": "07:00"},
                            timeout=30).status_code == 403
            assert s1.delete(f"{API}/calendario/{sid}", timeout=30).status_code == 403
        finally:
            admin.delete(f"{API}/calendario/{sid}", timeout=30)


class TestPrenotazioni:
    def test_prenota_flow(self, admin, mk_tesserato):
        r = admin.post(f"{API}/calendario", json={"data": "2026-05-25", "ora": "18:00",
                                                  "luogo": "TEST", "capacita": 1,
                                                  "descrizione": "TEST_prenota"}, timeout=30)
        sid = r.json()["slots"][0]["id"]
        t1 = mk_tesserato()
        t2 = mk_tesserato()
        try:
            p = admin.post(f"{API}/calendario/prenota",
                           json={"slot_id": sid, "tesserato_id": t1["id"]}, timeout=120)
            assert p.status_code == 200, f"{p.status_code}: {p.text[:300]}"
            slot = next(s for s in admin.get(f"{API}/calendario",
                        params={"date_from": "2026-05-25", "date_to": "2026-05-25"},
                        timeout=30).json() if s["id"] == sid)
            assert len(slot["prenotazioni"]) == 1, slot
            assert slot["prenotazioni"][0]["tesserato_nome"].startswith("TEST_Rossi"), slot
            # duplicate booking
            dup = admin.post(f"{API}/calendario/prenota",
                             json={"slot_id": sid, "tesserato_id": t1["id"]}, timeout=60)
            assert dup.status_code == 409, f"{dup.status_code}: {dup.text[:200]}"
            # slot full (capacita=1)
            full = admin.post(f"{API}/calendario/prenota",
                              json={"slot_id": sid, "tesserato_id": t2["id"]}, timeout=60)
            assert full.status_code == 409, f"{full.status_code}: {full.text[:200]}"
            # cancel
            c = admin.delete(f"{API}/calendario/prenota/{sid}/{t1['id']}", timeout=120)
            assert c.status_code == 200, c.text[:300]
            slot = next(s for s in admin.get(f"{API}/calendario",
                        params={"date_from": "2026-05-25", "date_to": "2026-05-25"},
                        timeout=30).json() if s["id"] == sid)
            assert slot["prenotazioni"] == [], slot
            # now t2 fits
            ok = admin.post(f"{API}/calendario/prenota",
                            json={"slot_id": sid, "tesserato_id": t2["id"]}, timeout=120)
            assert ok.status_code == 200, ok.text[:300]
        finally:
            admin.delete(f"{API}/calendario/{sid}", timeout=30)

    def test_prenota_invalid_ids(self, admin, mk_tesserato):
        t = mk_tesserato()
        r = admin.post(f"{API}/calendario/prenota",
                       json={"slot_id": "0" * 24, "tesserato_id": t["id"]}, timeout=30)
        assert r.status_code == 404, r.status_code
        s = admin.post(f"{API}/calendario", json={"data": "2026-06-01", "ora": "10:00"},
                       timeout=30).json()["slots"][0]["id"]
        try:
            r2 = admin.post(f"{API}/calendario/prenota",
                            json={"slot_id": s, "tesserato_id": "0" * 24}, timeout=30)
            assert r2.status_code == 404, r2.status_code
        finally:
            admin.delete(f"{API}/calendario/{s}", timeout=30)


# ------------------------- ITERATION 4: LIBRO SOCI -------------------------
class TestLibroSoci:
    def test_libro_soci_states_and_quota(self, admin, mk_tesserato):
        from datetime import timedelta
        future = (datetime.now(timezone.utc) + timedelta(days=200)).date().isoformat()
        t_active = mk_tesserato(scadenza_tesseramento=future)
        t_moroso = mk_tesserato()
        ric = mk_ricevuta(admin, t_active["id"], data=f"{2026}-02-10", items=[
            {"descrizione": "TEST_Quota tesseramento annuale", "importo": 40.0},
            {"descrizione": "TEST_Pacchetto 10 lezioni", "importo": 150.0}]).json()
        try:
            r = admin.get(f"{API}/libro-soci", params={"anno": 2026}, timeout=60)
            assert r.status_code == 200, r.text[:300]
            body = r.json()
            assert body["anno"] == 2026
            assert isinstance(body["soci"], list) and body["soci"]
            by_id = {s["id"]: s for s in body["soci"]}
            for s in body["soci"]:
                assert s["stato_socio"] in ("attivo", "moroso", "iscritto (scaduto)"), s
                assert isinstance(s["quota_pagata_anno"], (int, float))
                assert s["quota_pagata_anno"] >= 0
                assert "_id" not in s and "id" in s
            assert by_id[t_active["id"]]["stato_socio"] == "attivo"
            assert by_id[t_active["id"]]["quota_pagata_anno"] == pytest.approx(40.0), \
                by_id[t_active["id"]]["quota_pagata_anno"]
            assert by_id[t_moroso["id"]]["stato_socio"] == "moroso"
            assert by_id[t_moroso["id"]]["quota_pagata_anno"] == 0
        finally:
            admin.delete(f"{API}/ricevute/{ric['id']}", timeout=30)

    def test_libro_soci_default_anno_and_tecnico_scope(self, admin, mk_tecnico, mk_tesserato):
        s, _ = mk_tecnico()
        own = mk_tesserato(session=s)
        mk_tesserato()
        r = s.get(f"{API}/libro-soci", timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["anno"] == datetime.now(timezone.utc).year
        assert [x["id"] for x in body["soci"]] == [own["id"]], body["soci"]


# ------------------------- ITERATION 4: EROGAZIONE COMPENSI -------------------------
class TestErogazioneCompensi:
    def test_eroga_creates_movimento_and_record(self, admin, mk_tecnico, mk_tesserato):
        _, u = mk_tecnico(50.0)
        t = mk_tesserato()
        ric = mk_ricevuta(admin, t["id"], data="2026-02-20", emesso_per_id=u["id"],
                          items=[{"descrizione": "TEST_Pacchetto", "importo": 200.0}]).json()
        mv_id = None
        try:
            c = admin.get(f"{API}/compensi", params={"date_from": "2026-01-01",
                                                     "date_to": "2026-12-31"}, timeout=60)
            assert c.status_code == 200, c.text[:300]
            row = next(x for x in c.json()["compensi"] if x["tecnico_id"] == u["id"])
            assert row["compenso_dovuto"] == pytest.approx(100.0), row
            assert row["flusso_generato"] == pytest.approx(200.0)

            e = admin.post(f"{API}/compensi/eroga", json={
                "tecnico_id": u["id"], "data": "2026-03-01", "importo": 100.0,
                "periodo_da": "2026-01-01", "periodo_a": "2026-02-28",
                "metodo": "Bonifico", "note": "TEST_eroga"}, timeout=30)
            assert e.status_code == 200, f"{e.status_code}: {e.text[:300]}"
            body = e.json()
            assert body["ok"] is True
            mv = body["movimento"]
            mv_id = mv["id"]
            assert mv["tipo"] == "uscita" and mv["categoria"] == "Compenso tecnico"
            assert mv["importo"] == pytest.approx(100.0)
            assert mv["tecnico_id"] == u["id"]
            assert "_id" not in mv
            # persisted in movimenti
            mvs = admin.get(f"{API}/movimenti", params={"date_from": "2026-03-01",
                                                        "date_to": "2026-03-01"}, timeout=60).json()
            found = next(x for x in mvs if x["id"] == mv_id)
            assert found["categoria"] == "Compenso tecnico"
            assert found["importo"] == pytest.approx(100.0)
            # erogati list
            lst = admin.get(f"{API}/compensi/erogati", params={"tecnico_id": u["id"]}, timeout=30)
            assert lst.status_code == 200, lst.text[:300]
            recs = lst.json()
            assert len(recs) == 1, recs
            rec = recs[0]
            assert rec["tecnico_id"] == u["id"] and rec["importo"] == pytest.approx(100.0)
            assert rec["metodo"] == "Bonifico" and rec["movimento_id"] == mv_id
            assert rec["tecnico_nome"] == u["name"]
        finally:
            if mv_id:
                admin.delete(f"{API}/movimenti/{mv_id}", timeout=30)
                _db().compensi_erogati.delete_many({"movimento_id": mv_id})
            admin.delete(f"{API}/ricevute/{ric['id']}", timeout=30)

    def test_eroga_requires_admin_and_valid_tecnico(self, admin, mk_tecnico):
        s, u = mk_tecnico()
        payload = {"tecnico_id": u["id"], "data": "2026-03-01", "importo": 10.0}
        assert s.post(f"{API}/compensi/eroga", json=payload, timeout=30).status_code == 403
        bad = admin.post(f"{API}/compensi/eroga",
                         json={"tecnico_id": "0" * 24, "data": "2026-03-01", "importo": 10.0},
                         timeout=30)
        assert bad.status_code == 404, bad.status_code

    def test_erogati_scoped_for_tecnico(self, mk_tecnico):
        s, _ = mk_tecnico()
        r = s.get(f"{API}/compensi/erogati", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json() == []


# ------------------------- ITERATION 4: EXCEL EXPORT -------------------------
class TestExcelExport:
    def test_export_excel_admin(self, admin):
        r = admin.get(f"{API}/export/excel", timeout=180)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), r.headers
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd and ".xlsx" in cd, cd
        assert r.content[:2] == b"PK", r.content[:10]
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            assert any(n.startswith("xl/worksheets") for n in z.namelist()), z.namelist()

    def test_export_excel_forbidden_for_tecnico(self, mk_tecnico):
        s, _ = mk_tecnico()
        r = s.get(f"{API}/export/excel", timeout=120)
        assert r.status_code == 403, r.status_code

    def test_export_excel_unauthenticated(self):
        r = requests.get(f"{API}/export/excel", timeout=60)
        assert r.status_code == 401, r.status_code


# ------------------------- ITERATION 4: ORG PRESIDENT NAME -------------------------
class TestPresidentName:
    def test_president_name_is_set(self, admin):
        r = admin.get(f"{API}/organizzazione", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("president_name") == "Drovetti Cassiano Bruno", r.json().get("president_name")


# ------------------------- ITERATION 5: TARGETED FIX VERIFICATION -------------------------
def _pdf_text(content: bytes) -> str:
    """Best-effort text extraction: inflate every (ASCII85+Flate) stream in the PDF."""
    import base64
    import re
    import zlib
    out = [content.decode("latin-1", "ignore")]
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", content, re.S):
        raw = m.group(1).strip(b"\r\n")
        for dec in (lambda b: zlib.decompress(b),
                    lambda b: zlib.decompress(base64.a85decode(b, adobe=True))):
            try:
                out.append(dec(raw).decode("latin-1"))
                break
            except Exception:
                continue
    return "\n".join(out)


class TestIter5PresidentName:
    """Fix 1: startup $set migration of organizzazione.president_name."""

    def test_get_organizzazione_president_name(self, admin):
        r = admin.get(f"{API}/organizzazione", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("president_name") == PRESIDENT_NAME, r.json().get("president_name")

    def test_president_name_in_receipt_pdf(self, admin, mk_tesserato):
        t = mk_tesserato()
        d = mk_ricevuta(admin, t["id"], data="2026-07-02").json()
        try:
            pdf = admin.get(f"{API}/ricevute/{d['id']}/pdf", timeout=60)
            assert pdf.status_code == 200, pdf.text[:200]
            assert pdf.content[:4] == b"%PDF"
            txt = _pdf_text(pdf.content)
            assert "Drovetti" in txt, txt[-1500:]
            assert "Drovelli" not in txt
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)

    def test_migration_recreates_correct_name_on_fresh_doc(self, admin):
        """Deleting the config doc must lazily recreate it with the correct name."""
        db = _db()
        old = db.organizzazione.find_one({"_id": "config"})
        db.organizzazione.delete_one({"_id": "config"})
        try:
            r = admin.get(f"{API}/organizzazione", timeout=30)
            assert r.status_code == 200, r.text[:300]
            assert r.json().get("president_name") == PRESIDENT_NAME, r.json()
        finally:
            db.organizzazione.delete_one({"_id": "config"})
            if old:
                db.organizzazione.insert_one(old)


class TestIter5CalendarValidation:
    """Fix 2: malformed calendar payloads must be 4xx (was 500)."""

    def test_non_iso_date_422(self, admin):
        r = admin.post(f"{API}/calendario",
                       json={"data": "01/03/2026", "ora": "18:00"}, timeout=30)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"

    def test_bad_recurrence_end_422(self, admin):
        r = admin.post(f"{API}/calendario",
                       json={"data": "2026-07-01", "ora": "18:00",
                             "ricorrenza_settimanale": True,
                             "ricorrenza_fino_al": "nope"}, timeout=30)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"

    def test_negative_durata_422(self, admin):
        r = admin.post(f"{API}/calendario",
                       json={"data": "2026-07-01", "ora": "18:00", "durata_min": -10},
                       timeout=30)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"

    def test_zero_capacita_422(self, admin):
        r = admin.post(f"{API}/calendario",
                       json={"data": "2026-07-01", "ora": "18:00", "capacita": 0},
                       timeout=30)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"

    def test_negative_capacita_422(self, admin):
        r = admin.post(f"{API}/calendario",
                       json={"data": "2026-07-01", "ora": "18:00", "capacita": -3},
                       timeout=30)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"

    def test_no_slot_created_after_invalid_payloads(self, admin):
        lst = admin.get(f"{API}/calendario", params={"date_from": "2026-07-01",
                                                     "date_to": "2026-07-01"}, timeout=30)
        assert lst.status_code == 200
        assert lst.json() == [], lst.json()

    def test_valid_payload_still_works(self, admin):
        r = admin.post(f"{API}/calendario",
                       json={"data": "2026-07-08", "ora": "18:00", "durata_min": 60,
                             "capacita": 4, "descrizione": "TEST_iter5_ok"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        sid = r.json()["slots"][0]["id"]
        admin.delete(f"{API}/calendario/{sid}", timeout=30)


class TestIter5PrenotaAsync:
    """Fix 3: notifications moved to BackgroundTasks -> response must be fast."""

    def test_five_bookings_under_2s_each(self, admin, mk_tesserato):
        import time
        r = admin.post(f"{API}/calendario",
                       json={"data": "2026-07-15", "ora": "18:00", "luogo": "TEST",
                             "capacita": 10, "descrizione": "TEST_iter5_async"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        sid = r.json()["slots"][0]["id"]
        tess = [mk_tesserato() for _ in range(5)]
        durations = []
        try:
            for t in tess:
                t0 = time.perf_counter()
                p = admin.post(f"{API}/calendario/prenota",
                               json={"slot_id": sid, "tesserato_id": t["id"]}, timeout=60)
                el = time.perf_counter() - t0
                durations.append(el)
                assert p.status_code == 200, f"{p.status_code}: {p.text[:200]}"
            print("prenota durations:", [round(d, 3) for d in durations])
            assert all(d < 2.0 for d in durations), durations
            # cancel must also be fast (notifications are background too)
            t0 = time.perf_counter()
            c = admin.delete(f"{API}/calendario/prenota/{sid}/{tess[0]['id']}", timeout=60)
            el = time.perf_counter() - t0
            assert c.status_code == 200, c.text[:200]
            print("cancel duration:", round(el, 3))
            assert el < 2.0, el
        finally:
            admin.delete(f"{API}/calendario/{sid}", timeout=30)


class TestIter5CancelPrenotazione:
    """Fix 4: cancelling a non-existent prenotazione -> 404."""

    def test_cancel_not_booked_404_then_booked_200(self, admin, mk_tesserato):
        r = admin.post(f"{API}/calendario",
                       json={"data": "2026-07-22", "ora": "18:00", "capacita": 3,
                             "descrizione": "TEST_iter5_cancel"}, timeout=30)
        sid = r.json()["slots"][0]["id"]
        t = mk_tesserato()
        try:
            miss = admin.delete(f"{API}/calendario/prenota/{sid}/{t['id']}", timeout=60)
            assert miss.status_code == 404, f"{miss.status_code}: {miss.text[:200]}"
            assert admin.post(f"{API}/calendario/prenota",
                              json={"slot_id": sid, "tesserato_id": t["id"]},
                              timeout=60).status_code == 200
            ok = admin.delete(f"{API}/calendario/prenota/{sid}/{t['id']}", timeout=60)
            assert ok.status_code == 200, ok.text[:200]
            # second cancel is now a miss again
            again = admin.delete(f"{API}/calendario/prenota/{sid}/{t['id']}", timeout=60)
            assert again.status_code == 404, again.status_code
            slot = next(s for s in admin.get(f"{API}/calendario",
                        params={"date_from": "2026-07-22", "date_to": "2026-07-22"},
                        timeout=30).json() if s["id"] == sid)
            assert slot["prenotazioni"] == [], slot
        finally:
            admin.delete(f"{API}/calendario/{sid}", timeout=30)

    def test_cancel_unknown_slot_404(self, admin, mk_tesserato):
        t = mk_tesserato()
        r = admin.delete(f"{API}/calendario/prenota/{'0' * 24}/{t['id']}", timeout=30)
        assert r.status_code == 404, r.status_code


class TestIter5ErogaValidation:
    """Fix 5: importo > 0 and target user must be a tecnico."""

    def test_negative_importo_422(self, admin, mk_tecnico):
        _, u = mk_tecnico()
        r = admin.post(f"{API}/compensi/eroga",
                       json={"tecnico_id": u["id"], "data": "2026-03-01", "importo": -50},
                       timeout=30)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"

    def test_zero_importo_422(self, admin, mk_tecnico):
        _, u = mk_tecnico()
        r = admin.post(f"{API}/compensi/eroga",
                       json={"tecnico_id": u["id"], "data": "2026-03-01", "importo": 0},
                       timeout=30)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"

    def test_eroga_to_admin_422(self, admin):
        me = admin.get(f"{API}/auth/me", timeout=30).json()
        admin_id = me.get("id") or me.get("user", {}).get("id")
        assert admin_id, me
        r = admin.post(f"{API}/compensi/eroga",
                       json={"tecnico_id": admin_id, "data": "2026-03-01", "importo": 50},
                       timeout=30)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"

    def test_no_side_effects_from_invalid_eroga(self, admin):
        mvs = admin.get(f"{API}/movimenti", params={"date_from": "2026-03-01",
                                                    "date_to": "2026-03-01"}, timeout=60).json()
        assert [m for m in mvs if m.get("importo", 0) < 0] == [], mvs
        assert _db().compensi_erogati.count_documents({"importo": {"$lte": 0}}) == 0

    def test_valid_eroga_still_200(self, admin, mk_tecnico):
        _, u = mk_tecnico(50.0)
        e = admin.post(f"{API}/compensi/eroga",
                       json={"tecnico_id": u["id"], "data": "2026-03-02", "importo": 75.5,
                             "metodo": "Contanti", "note": "TEST_iter5_eroga"}, timeout=30)
        assert e.status_code == 200, f"{e.status_code}: {e.text[:300]}"
        mv_id = e.json()["movimento"]["id"]
        try:
            recs = admin.get(f"{API}/compensi/erogati",
                             params={"tecnico_id": u["id"]}, timeout=30).json()
            assert len(recs) == 1 and recs[0]["importo"] == pytest.approx(75.5), recs
        finally:
            admin.delete(f"{API}/movimenti/{mv_id}", timeout=30)
            _db().compensi_erogati.delete_many({"movimento_id": mv_id})



# ------------------------- ITER 6: libro-soci PDF export + pdf_utils regression -------------------------
def _pdf_text(content: bytes) -> str:
    """Extract full text from a PDF byte string (validates it is decodable)."""
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(content))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


class TestIter6BackendHealth:
    """Backend module loads cleanly after the pdf_utils IndentationError fix."""

    def test_pdf_utils_imports_all_generators(self):
        import importlib
        m = importlib.import_module("pdf_utils")
        for fn in ("generate_receipt_pdf", "generate_balance_report_pdf",
                   "generate_libro_soci_pdf"):
            assert callable(getattr(m, fn, None)), f"{fn} missing from pdf_utils"

    def test_auth_me_unauthenticated_401(self):
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 401, f"{r.status_code}: {r.text[:200]}"

    def test_root_no_500(self):
        r = requests.get(f"{BASE_URL}/", timeout=30)
        assert r.status_code < 500, f"{r.status_code}: {r.text[:200]}"

    def test_organizzazione_president_name(self, admin):
        r = admin.get(f"{API}/organizzazione", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("president_name") == PRESIDENT_NAME, r.json().get("president_name")


class TestIter6LibroSociPdf:
    def test_pdf_unauthenticated_401(self):
        r = requests.get(f"{API}/libro-soci/pdf", params={"anno": 2026}, timeout=60)
        assert r.status_code == 401, f"{r.status_code}: {r.text[:200]}"

    def test_admin_pdf_valid_and_headers(self, admin, mk_tesserato):
        t = mk_tesserato(numero_tessera="T6-001", scadenza_tesseramento="2026-12-31")
        r = admin.get(f"{API}/libro-soci/pdf", params={"anno": 2026}, timeout=120)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf"), r.headers
        assert "LibroSoci_2026.pdf" in r.headers.get("content-disposition", ""), r.headers
        assert r.content[:4] == b"%PDF", r.content[:20]
        txt = _pdf_text(r.content)
        assert "LIBRO SOCI" in txt.upper(), txt[:500]
        assert "2026" in txt
        assert "RIEPILOGO" in txt.upper() and "ELENCO SOCI" in txt.upper(), txt[:800]
        assert t["cognome"].split("_")[-1] in txt or "T6-001" in txt, txt[:1500]

    def test_pdf_default_anno(self, admin):
        r = admin.get(f"{API}/libro-soci/pdf", timeout=120)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert f"LibroSoci_{YEAR}.pdf" in r.headers.get("content-disposition", ""), r.headers
        assert r.content[:4] == b"%PDF"

    def test_pdf_stats_match_json(self, admin):
        j = admin.get(f"{API}/libro-soci", params={"anno": 2026}, timeout=120).json()
        soci = j["soci"]
        attivi = sum(1 for s in soci if s.get("stato_socio") == "attivo")
        r = admin.get(f"{API}/libro-soci/pdf", params={"anno": 2026}, timeout=120)
        assert r.status_code == 200
        txt = _pdf_text(r.content).replace("\n", " ")
        assert re.search(r"Soci totali\s*" + str(len(soci)), txt), txt[:800]
        assert re.search(r"Attivi\s*" + str(attivi), txt), txt[:800]

    def test_tecnico_pdf_scoped_to_own_tesserati(self, admin, mk_tecnico, mk_tesserato):
        s, _u = mk_tecnico()
        own = mk_tesserato(session=s, cognome="TEST_TecOwn", numero_tessera="T6-TEC")
        other = mk_tesserato(cognome="TEST_AdminOnly", numero_tessera="T6-ADM")
        r = s.get(f"{API}/libro-soci/pdf", params={"anno": 2026}, timeout=120)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert r.content[:4] == b"%PDF"
        txt = _pdf_text(r.content)
        assert "T6-TEC" in txt, f"own tesserato missing: {txt[:1500]}"
        assert "T6-ADM" not in txt, "tecnico PDF leaked another user's tesserato"
        assert own["id"] and other["id"]

    def test_pdf_anno_without_data_still_valid(self, admin):
        r = admin.get(f"{API}/libro-soci/pdf", params={"anno": 1999}, timeout=120)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert r.content[:4] == b"%PDF"
        assert "Anno associativo" in _pdf_text(r.content) or "1999" in _pdf_text(r.content)


class TestIter6PdfRegression:
    def test_ricevuta_pdf_still_works(self, admin, mk_tesserato):
        t = mk_tesserato()
        rc = mk_ricevuta(admin, t["id"])
        assert rc.status_code in (200, 201), rc.text[:300]
        rid = rc.json()["id"]
        try:
            r = admin.get(f"{API}/ricevute/{rid}/pdf", timeout=120)
            assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
            assert r.content[:4] == b"%PDF"
            assert "RICEVUTA" in _pdf_text(r.content).upper()
        finally:
            admin.delete(f"{API}/ricevute/{rid}", timeout=30)

    def test_bilancio_pdf_still_works(self, admin):
        r = admin.get(f"{API}/report/bilancio/pdf",
                      params={"date_from": "2026-01-01", "date_to": "2026-12-31"}, timeout=120)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert r.content[:4] == b"%PDF"
        txt = _pdf_text(r.content).upper()
        assert "REPORT BILANCIO" in txt or "BILANCIO" in txt, txt[:500]
