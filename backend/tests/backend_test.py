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
            "president_name": "Drovelli Caivano Bruno"}, timeout=30)
        assert p.status_code == 200, p.text[:300]
        assert p.json()["president_signature_base64"] == PNG_SIGN
        g = admin.get(f"{API}/organizzazione", timeout=30).json()
        assert g["president_signature_base64"] == PNG_SIGN
        assert g["logo_base64"] == PNG_SIGN
        assert "_id" not in g and g["id"] == "config"
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
            admin.patch(f"{API}/organizzazione",
                        json={"logo_base64": None,
                              "president_signature_base64": None}, timeout=30)


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
            assert doc["last_sent_email"] == "delivered@resend.dev"
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)
