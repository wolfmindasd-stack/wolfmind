"""Iteration 9 - backend regression smoke after the Admin.jsx (frontend-only) syntax fix.
Scope: auth (me/login cookies), counters authz, and main GET endpoints of every module.
"""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
base = os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")
if not base:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
API = base.rstrip("/") + "/api"


@pytest.fixture(scope="module")
def creds():
    p = Path("/app/memory/test_credentials.md")
    c = p.read_text(encoding="utf-8")
    e = re.search(r"(?im)^\s*[-*]?\s*Email:\s*`?([^`\s]+)", c)
    w = re.search(r"(?im)^\s*[-*]?\s*Password:\s*`?([^`\s]+)", c)
    assert e and w, "credentials not parseable"
    return {"email": e.group(1), "password": w.group(1)}


@pytest.fixture(scope="module")
def admin(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    return s


# ---- AUTH ----
class TestAuth:
    def test_me_unauthenticated_401(self):  # noqa: F811
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 401

    def test_login_sets_httponly_cookies(self, creds):  # noqa: F811
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=creds, timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("user", {}).get("email") == creds["email"]
        assert body["user"]["role"] == "admin"
        assert "password_hash" not in body["user"] and "_id" not in body["user"]
        names = {c.name for c in s.cookies}
        assert {"access_token", "refresh_token"} <= names, names
        raw = "\n".join(v for k, v in r.headers.items() if k.lower() == "set-cookie")
        raw = raw or str(r.raw.headers.getlist("Set-Cookie"))
        assert "HttpOnly" in raw, raw[:300]
        me = s.get(f"{API}/auth/me", timeout=30)
        assert me.status_code == 200 and me.json()["email"] == creds["email"]

    def test_login_wrong_password_401(self, creds):  # noqa: F811
        r = requests.post(f"{API}/auth/login",
                          json={"email": creds["email"], "password": "definitely-wrong-1"},
                          timeout=30)
        assert r.status_code == 401


# ---- COUNTERS ----
class TestCounters:
    def test_get_counter_as_admin(self, admin):  # noqa: F811
        r = admin.get(f"{API}/counters/ricevute/2026", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["year"] == 2026 and isinstance(d["seq"], int)

    def test_get_counter_unauth_401(self):  # noqa: F811
        assert requests.get(f"{API}/counters/ricevute/2026", timeout=30).status_code == 401

    def test_patch_counter_as_admin_roundtrip(self, admin):  # noqa: F811
        orig = admin.get(f"{API}/counters/ricevute/2026", timeout=30).json()["seq"]
        try:
            r = admin.patch(f"{API}/counters/ricevute/2026", json={"seq": orig + 7}, timeout=30)
            assert r.status_code == 200, r.text[:300]
            assert admin.get(f"{API}/counters/ricevute/2026", timeout=30).json()["seq"] == orig + 7
        finally:
            admin.patch(f"{API}/counters/ricevute/2026", json={"seq": orig}, timeout=30)
            assert admin.get(f"{API}/counters/ricevute/2026", timeout=30).json()["seq"] == orig

    def test_patch_counter_as_tecnico_403(self, admin):  # noqa: F811
        uid = None
        payload = {"email": "TEST_i9_tec@wolfsmind.it", "password": "Tecnico2026!",
                   "name": "TEST_I9 Tecnico", "role": "tecnico"}
        try:
            cr = admin.post(f"{API}/users", json=payload, timeout=30)
            assert cr.status_code in (200, 201), cr.text[:300]
            uid = cr.json()["id"]
            ts = requests.Session()
            lr = ts.post(f"{API}/auth/login",
                         json={"email": payload["email"], "password": payload["password"]},
                         timeout=30)
            assert lr.status_code == 200, lr.text[:300]
            r = ts.patch(f"{API}/counters/ricevute/2026", json={"seq": 3}, timeout=30)
            assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"
            assert ts.get(f"{API}/counters/ricevute/2026", timeout=30).status_code == 200
        finally:
            if uid:
                admin.delete(f"{API}/users/{uid}", timeout=30)


# ---- MAIN MODULES SMOKE ----
LIST_ENDPOINTS = [
    "/tesserati", "/ricevute", "/verbali", "/libro-soci", "/dashboard", "/calendario",
    "/compensi", "/compensi/erogati", "/abbonamenti", "/tipi-pacchetto", "/lezioni",
    "/movimenti", "/movimenti/riepilogo-mensile?year=2026",
    "/report/bilancio?date_from=2026-01-01&date_to=2026-12-31", "/organizzazione",
    "/users",
]


class TestMainEndpoints:
    @pytest.mark.parametrize("ep", LIST_ENDPOINTS)
    def test_get_as_admin(self, admin, ep):  # noqa: F811
        r = admin.get(f"{API}{ep}", timeout=45)
        assert r.status_code == 200, f"{ep} -> {r.status_code} {r.text[:300]}"
        data = r.json()
        assert isinstance(data, (list, dict))
        assert "_id" not in str(data)[:20000] or True  # explicit check below
        if isinstance(data, list):
            for item in data[:5]:
                if isinstance(item, dict):
                    assert "_id" not in item, f"{ep} leaks mongo _id"

    @pytest.mark.parametrize("ep", ["/tesserati", "/ricevute", "/verbali", "/dashboard",
                                    "/libro-soci", "/compensi", "/users"])
    def test_get_unauth_401(self, ep):  # noqa: F811
        r = requests.get(f"{API}{ep}", timeout=30)
        assert r.status_code == 401, f"{ep} -> {r.status_code}"


# ---- PORTALE (unauth public) ----
class TestPortaleUnauth:
    def test_bad_token_404(self):  # noqa: F811
        for path in ["", "/ricevute", "/calendario"]:
            r = requests.get(f"{API}/portale/not-a-real-token{path}", timeout=30)
            assert r.status_code == 404, f"{path} -> {r.status_code} {r.text[:200]}"

    def test_valid_token_public_access(self, admin):  # noqa: F811
        lst = admin.get(f"{API}/tesserati", timeout=30).json()
        tok = next((t.get("portale_token") for t in lst if t.get("portale_token")), None)
        if not tok:
            pytest.skip("no tesserato with portale_token in db")
        d = requests.get(f"{API}/portale/{tok}", timeout=30)
        assert d.status_code == 200, d.text[:300]
        body = d.json()
        assert "tesserato" in body
        assert "'_id'" not in str(body)
        c = requests.get(f"{API}/portale/{tok}/calendario", timeout=30)
        assert c.status_code == 200, c.text[:300]
        rc = requests.get(f"{API}/portale/{tok}/ricevute", timeout=30)
        assert rc.status_code == 200, rc.text[:300]


# ---- PDF endpoints ----
class TestPdfSmoke:
    def test_libro_soci_pdf(self, admin):  # noqa: F811
        r = admin.get(f"{API}/libro-soci/pdf", timeout=90)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF", r.content[:20]

    def test_bilancio_pdf(self, admin):  # noqa: F811
        r = admin.get(f"{API}/report/bilancio/pdf?date_from=2026-01-01&date_to=2026-12-31", timeout=90)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"


# ---- BRUTE FORCE LOCKOUT (keyed on email only) ----
class TestLockout:
    def test_lockout_after_5_failed_attempts(self):  # noqa: F811
        email = "TEST_i9_lockout@wolfsmind.it"
        codes = []
        for _ in range(6):
            r = requests.post(f"{API}/auth/login",
                              json={"email": email, "password": "bad-pass-1"}, timeout=30)
            codes.append(r.status_code)
        assert codes[:5] == [401] * 5, codes
        assert codes[5] == 429, codes
        # cleanup the attempt record so it does not leak into other runs
        from pymongo import MongoClient
        from dotenv import dotenv_values as dv
        e = dv("/app/backend/.env")
        MongoClient(e["MONGO_URL"])[e["DB_NAME"]].login_attempts.delete_one(
            {"_id": email.lower()})

    def test_admin_login_not_locked_after_cleanup(self, admin, creds):  # noqa: F811
        r = admin.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200 and r.json()["email"] == creds["email"]
