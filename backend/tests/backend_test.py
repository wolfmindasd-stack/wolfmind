"""Wolf's Mind ASD gestionale - backend API tests (pytest)."""
import os
import re
import uuid
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


# ------------------------- fixtures -------------------------
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
    """Session authenticated as admin via cookies."""
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=admin_creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    return s


@pytest.fixture(scope="session")
def tecnico(admin):
    """Create a tecnico user (50%) and return (session, user_dict)."""
    payload = {
        "email": f"TEST_tec_{TS}@example.com".lower(),
        "password": "TecPass2026!",
        "name": f"TEST_Tecnico_{TS}",
        "role": "tecnico",
        "percentuale_compenso": 50,
    }
    r = admin.post(f"{API}/users", json=payload, timeout=30)
    if r.status_code not in (200, 201):
        pytest.fail(f"tecnico create failed {r.status_code}: {r.text[:300]}")
    u = r.json()
    s = requests.Session()
    lr = s.post(f"{API}/auth/login", json={"email": payload["email"],
                                           "password": payload["password"]}, timeout=30)
    if lr.status_code != 200:
        pytest.fail(f"tecnico login failed {lr.status_code}: {lr.text[:300]}")
    yield s, u
    admin.delete(f"{API}/users/{u['id']}", timeout=30)


@pytest.fixture(scope="session")
def tesserato(admin):
    payload = {
        "cognome": "TEST_Rossi", "nome": "Mario", "codice_fiscale": f"RSSMRA80A01H501{TS[:1].upper()}",
        "indirizzo": "Via Roma", "civico": "1", "cap": "10070", "citta": "Front",
        "provincia": "TO", "email": "delivered@resend.dev", "telefono": "+39 3331234567",
    }
    r = admin.post(f"{API}/tesserati", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text[:300]
    t = r.json()
    yield t
    admin.delete(f"{API}/tesserati/{t['id']}", timeout=30)


def mk_ricevuta(session, tesserato_id, importo=100.0, data="2026-03-15"):
    return session.post(f"{API}/ricevute", json={
        "tesserato_id": tesserato_id, "data": data, "metodo_pagamento": "Contanti",
        "items": [{"descrizione": "TEST_Pacchetto 12 lezioni", "num_lezioni": 12,
                   "importo": importo}],
        "note": "TEST",
    }, timeout=30)


# ------------------------- AUTH -------------------------
class TestAuth:
    def test_login_admin(self, admin_creds):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=admin_creds, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["user"]["email"] == admin_creds["email"]
        assert d["user"]["role"] == "admin"
        assert "password_hash" not in d["user"]
        assert isinstance(d.get("access_token"), str) and d["access_token"]
        # httpOnly cookies
        raw = r.headers.get("set-cookie", "")
        assert "access_token" in raw and "HttpOnly" in raw, raw
        assert "refresh_token" in raw

    def test_me(self, admin, admin_creds):
        r = admin.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["email"] == admin_creds["email"]
        assert d["role"] == "admin"
        assert "id" in d and "_id" not in d
        assert "password_hash" not in d

    def test_login_wrong_password(self, admin_creds):
        r = requests.post(f"{API}/auth/login",
                          json={"email": admin_creds["email"], "password": "WrongPass1!"},
                          timeout=30)
        assert r.status_code == 401, r.text[:300]

    def test_unauthenticated_401(self):
        r = requests.get(f"{API}/tesserati", timeout=30)
        assert r.status_code == 401

    def test_bearer_token_auth(self, admin_creds):
        r = requests.post(f"{API}/auth/login", json=admin_creds, timeout=30)
        tok = r.json()["access_token"]
        r2 = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r2.status_code == 200

    def test_bcrypt_hash_format(self):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        env = dotenv_values("/app/backend/.env")

        async def _get():
            c = AsyncIOMotorClient(env["MONGO_URL"])
            u = await c[env["DB_NAME"]].users.find_one({"email": env["ADMIN_EMAIL"].lower()})
            c.close()
            return u
        u = asyncio.get_event_loop().run_until_complete(_get()) if False else asyncio.run(_get())
        assert u is not None, "admin not seeded"
        assert u["password_hash"].startswith("$2b$"), u["password_hash"][:10]

    def test_brute_force_lockout(self, admin_creds):
        """Playbook: account should lock after 5 failed attempts."""
        codes = []
        for _ in range(6):
            r = requests.post(f"{API}/auth/login",
                              json={"email": admin_creds["email"], "password": "Bad!12345"},
                              timeout=30)
            codes.append(r.status_code)
        assert 429 in codes or 423 in codes, f"no lockout, codes={codes}"

    def test_logout(self, admin_creds):
        s = requests.Session()
        s.post(f"{API}/auth/login", json=admin_creds, timeout=30)
        r = s.post(f"{API}/auth/logout", timeout=30)
        assert r.status_code == 200
        assert s.get(f"{API}/auth/me", timeout=30).status_code == 401


# ------------------------- CORS -------------------------
class TestCors:
    def test_cors_credentials_explicit_origin(self):
        r = requests.get(f"{API}/tesserati", headers={"Origin": BASE_URL}, timeout=30)
        acao = r.headers.get("access-control-allow-origin")
        acac = r.headers.get("access-control-allow-credentials")
        assert acac == "true", f"allow-credentials={acac}"
        assert acao != "*", "wildcard origin with credentials is rejected by browsers"


# ------------------------- USERS -------------------------
class TestUsers:
    def test_tecnico_created_and_listed(self, admin, tecnico):
        _, u = tecnico
        assert u["role"] == "tecnico"
        assert u["percentuale_compenso"] == 50
        assert "password_hash" not in u
        r = admin.get(f"{API}/users", timeout=30)
        assert r.status_code == 200
        assert any(x["id"] == u["id"] for x in r.json())

    def test_duplicate_email_409(self, admin, tecnico):
        _, u = tecnico
        r = admin.post(f"{API}/users", json={"email": u["email"], "password": "Xx123456",
                                             "name": "dup", "role": "tecnico"}, timeout=30)
        assert r.status_code == 409, r.status_code

    def test_patch_user_percentuale(self, admin, tecnico):
        _, u = tecnico
        r = admin.patch(f"{API}/users/{u['id']}", json={"percentuale_compenso": 40}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["percentuale_compenso"] == 40
        g = admin.get(f"{API}/users", timeout=30).json()
        assert [x for x in g if x["id"] == u["id"]][0]["percentuale_compenso"] == 40
        admin.patch(f"{API}/users/{u['id']}", json={"percentuale_compenso": 50}, timeout=30)

    def test_role_protection(self, tecnico):
        s, _ = tecnico
        assert s.post(f"{API}/users", json={"email": f"x{TS}@e.com", "password": "aaaaaa",
                                            "name": "x"}, timeout=30).status_code == 403
        assert s.post(f"{API}/tipi-pacchetto", json={"nome": "TEST_x"}, timeout=30).status_code == 403
        assert s.post(f"{API}/movimenti", json={"data": "2026-03-01", "tipo": "uscita",
                                                "categoria": "c", "descrizione": "d",
                                                "importo": 1}, timeout=30).status_code == 403
        assert s.get(f"{API}/users", timeout=30).status_code == 403


# ------------------------- TESSERATI -------------------------
class TestTesserati:
    def test_crud(self, admin):
        payload = {"cognome": "TEST_Bianchi", "nome": "Luca",
                   "codice_fiscale": "BNCLCA80A01H501Z", "citta": "Torino"}
        r = admin.post(f"{API}/tesserati", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        t = r.json()
        assert t["cognome"] == "TEST_Bianchi" and "_id" not in t
        g = admin.get(f"{API}/tesserati/{t['id']}", timeout=30)
        assert g.status_code == 200 and g.json()["nome"] == "Luca"
        p = admin.patch(f"{API}/tesserati/{t['id']}", json={"citta": "Front"}, timeout=30)
        assert p.status_code == 200 and p.json()["citta"] == "Front"
        assert admin.get(f"{API}/tesserati/{t['id']}", timeout=30).json()["citta"] == "Front"
        d = admin.delete(f"{API}/tesserati/{t['id']}", timeout=30)
        assert d.status_code == 200
        assert admin.get(f"{API}/tesserati/{t['id']}", timeout=30).status_code == 404

    def test_bad_id_400(self, admin):
        assert admin.get(f"{API}/tesserati/notanid", timeout=30).status_code == 400

    def test_list(self, admin, tesserato):
        r = admin.get(f"{API}/tesserati", timeout=30)
        assert r.status_code == 200
        assert any(x["id"] == tesserato["id"] for x in r.json())


# ------------------------- TIPI PACCHETTO -------------------------
class TestTipiPacchetto:
    def test_defaults_seeded(self, admin):
        r = admin.get(f"{API}/tipi-pacchetto", timeout=30)
        assert r.status_code == 200
        names = [x["nome"] for x in r.json()]
        for n in ["12 lezioni", "8 lezioni", "Tesseramento annuale"]:
            assert n in names, names

    def test_crud(self, admin):
        r = admin.post(f"{API}/tipi-pacchetto", json={"nome": f"TEST_pack_{TS}",
                                                      "descrizione": "d", "num_lezioni": 5,
                                                      "prezzo_default": 55.0}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        p = r.json()
        u = admin.patch(f"{API}/tipi-pacchetto/{p['id']}", json={"prezzo_default": 66.0}, timeout=30)
        assert u.status_code == 200 and u.json()["prezzo_default"] == 66.0
        assert admin.delete(f"{API}/tipi-pacchetto/{p['id']}", timeout=30).status_code == 200
        assert all(x["id"] != p["id"] for x in admin.get(f"{API}/tipi-pacchetto", timeout=30).json())


# ------------------------- ABBONAMENTI / LEZIONI -------------------------
class TestAbbonamenti:
    def test_create_add_lezioni_residue(self, admin, tesserato):
        r = admin.post(f"{API}/abbonamenti", json={
            "tesserato_id": tesserato["id"], "descrizione": "TEST_12 lezioni",
            "num_lezioni_totali": 12, "prezzo": 100.0, "data_acquisto": "2026-03-01"}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        ab = r.json()
        for i in range(3):
            lr = admin.post(f"{API}/lezioni", json={"abbonamento_id": ab["id"],
                                                     "data": f"2026-03-0{i+2}",
                                                     "note": "TEST"}, timeout=30)
            assert lr.status_code in (200, 201), lr.text[:300]
        lst = admin.get(f"{API}/abbonamenti?tesserato_id={tesserato['id']}", timeout=30)
        assert lst.status_code == 200
        mine = [x for x in lst.json() if x["id"] == ab["id"]][0]
        assert mine["lezioni_effettuate"] == 3
        assert mine["lezioni_residue"] == 9
        lez = admin.get(f"{API}/lezioni?abbonamento_id={ab['id']}", timeout=30).json()
        assert len(lez) == 3
        assert admin.delete(f"{API}/abbonamenti/{ab['id']}", timeout=30).status_code == 200
        assert admin.get(f"{API}/lezioni?abbonamento_id={ab['id']}", timeout=30).json() == []

    def test_lezione_invalid_abbonamento_404(self, admin):
        r = admin.post(f"{API}/lezioni", json={"abbonamento_id": "507f1f77bcf86cd799439011",
                                                "data": "2026-03-01"}, timeout=30)
        assert r.status_code == 404


# ------------------------- RICEVUTE -------------------------
class TestRicevute:
    def test_create_numbering_movimento_and_sharing(self, admin, tecnico, tesserato):
        tec_s, tec_u = tecnico
        r1 = mk_ricevuta(admin, tesserato["id"], 100.0)
        assert r1.status_code in (200, 201), r1.text[:300]
        d1 = r1.json()
        assert re.match(r"^2026/\d{5}$", d1["numero"]), d1["numero"]
        assert d1["totale"] == 100.0
        assert d1["annullata"] is False
        assert d1["tesserato_nome"].startswith("TEST_Rossi")
        n1 = int(d1["numero"].split("/")[1])

        r2 = mk_ricevuta(admin, tesserato["id"], 50.0)
        d2 = r2.json()
        assert int(d2["numero"].split("/")[1]) == n1 + 1, (d1["numero"], d2["numero"])

        r3 = mk_ricevuta(tec_s, tesserato["id"], 70.0)
        assert r3.status_code in (200, 201), r3.text[:300]
        d3 = r3.json()
        assert int(d3["numero"].split("/")[1]) == n1 + 2, "numbering must be shared"
        assert d3["emesso_da_id"] == tec_u["id"]

        # movimento auto-created
        movs = admin.get(f"{API}/movimenti", timeout=30).json()
        m1 = [m for m in movs if m.get("ricevuta_id") == d1["id"]]
        assert len(m1) == 1, "no linked movimento"
        assert m1[0]["tipo"] == "entrata" and m1[0]["importo"] == 100.0

        # visibility: tecnico sees only own
        tec_list = tec_s.get(f"{API}/ricevute", timeout=30).json()
        assert all(x["emesso_da_id"] == tec_u["id"] for x in tec_list)
        assert any(x["id"] == d3["id"] for x in tec_list)
        admin_list = admin.get(f"{API}/ricevute", timeout=30).json()
        ids = {x["id"] for x in admin_list}
        assert {d1["id"], d2["id"], d3["id"]} <= ids

        # tecnico cannot read admin's ricevuta
        assert tec_s.get(f"{API}/ricevute/{d1['id']}", timeout=30).status_code == 403

        # PDF
        pdf = admin.get(f"{API}/ricevute/{d1['id']}/pdf", timeout=60)
        assert pdf.status_code == 200, pdf.text[:200]
        assert pdf.headers["content-type"].startswith("application/pdf")
        assert pdf.content[:4] == b"%PDF" and len(pdf.content) > 1000

        # whatsapp link
        wa = admin.get(f"{API}/ricevute/{d1['id']}/whatsapp-link", timeout=30)
        assert wa.status_code == 200, wa.text[:200]
        assert wa.json()["url"].startswith("https://wa.me/")

        # PATCH correction updates movimento
        pa = admin.patch(f"{API}/ricevute/{d1['id']}", json={
            "items": [{"descrizione": "TEST_corretto", "num_lezioni": 8, "importo": 80.0}]},
            timeout=30)
        assert pa.status_code == 200, pa.text[:300]
        assert pa.json()["totale"] == 80.0
        mv = [m for m in admin.get(f"{API}/movimenti", timeout=30).json()
              if m.get("ricevuta_id") == d1["id"]]
        assert mv and mv[0]["importo"] == 80.0, "movimento not synced"

        # tecnico cannot patch
        assert tec_s.patch(f"{API}/ricevute/{d3['id']}", json={"note": "x"},
                           timeout=30).status_code == 403

        # DELETE -> annullata + movimento removed
        assert admin.delete(f"{API}/ricevute/{d2['id']}", timeout=30).status_code == 200
        got = admin.get(f"{API}/ricevute/{d2['id']}", timeout=30).json()
        assert got["annullata"] is True
        assert not [m for m in admin.get(f"{API}/movimenti", timeout=30).json()
                    if m.get("ricevuta_id") == d2["id"]]

        # compensi for tecnico
        cp = admin.get(f"{API}/compensi?date_from=2026-01-01&date_to=2026-12-31", timeout=30)
        assert cp.status_code == 200, cp.text[:300]
        row = [c for c in cp.json()["compensi"] if c["tecnico_id"] == tec_u["id"]]
        assert row, "tecnico missing in compensi"
        row = row[0]
        assert row["flusso_generato"] == 70.0
        assert row["percentuale"] == 50.0
        assert row["compenso_dovuto"] == pytest.approx(35.0)

        # cleanup
        admin.delete(f"{API}/ricevute/{d1['id']}", timeout=30)
        admin.delete(f"{API}/ricevute/{d3['id']}", timeout=30)

    def test_create_invalid_tesserato_404(self, admin):
        r = mk_ricevuta(admin, "507f1f77bcf86cd799439011")
        assert r.status_code == 404, r.status_code

    def test_send_email(self, admin, tesserato):
        r = mk_ricevuta(admin, tesserato["id"], 30.0)
        rid = r.json()["id"]
        try:
            e = admin.post(f"{API}/ricevute/{rid}/send-email",
                           json={"email": "delivered@resend.dev",
                                 "message": "Grazie e buona giornata"}, timeout=90)
            assert e.status_code == 200, f"{e.status_code}: {e.text[:300]}"
            d = e.json()
            assert d["ok"] is True
            assert d.get("email_id"), d
            doc = admin.get(f"{API}/ricevute/{rid}", timeout=30).json()
            assert doc["last_sent_email"] == "delivered@resend.dev"
        finally:
            admin.delete(f"{API}/ricevute/{rid}", timeout=30)


# ------------------------- MOVIMENTI -------------------------
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
        assert f.status_code == 200
        assert any(x["id"] == m["id"] for x in f.json())
        out = admin.get(f"{API}/movimenti?date_from=2026-05-01&date_to=2026-05-31", timeout=30)
        assert all(x["id"] != m["id"] for x in out.json())
        p = admin.patch(f"{API}/movimenti/{m['id']}", json={"importo": 250.0}, timeout=30)
        assert p.status_code == 200 and p.json()["importo"] == 250.0
        assert admin.delete(f"{API}/movimenti/{m['id']}", timeout=30).status_code == 200
        assert all(x["id"] != m["id"] for x in admin.get(f"{API}/movimenti", timeout=30).json())

    def test_tecnico_can_get_filtered(self, tecnico, tesserato, admin):
        s, u = tecnico
        r = mk_ricevuta(s, tesserato["id"], 60.0)
        assert r.status_code in (200, 201)
        rid = r.json()["id"]
        try:
            movs = s.get(f"{API}/movimenti", timeout=30).json()
            assert all(m.get("tecnico_id") == u["id"] for m in movs), "tecnico sees others' movimenti"
            assert any(m.get("ricevuta_id") == rid for m in movs)
        finally:
            admin.delete(f"{API}/ricevute/{rid}", timeout=30)


# ------------------------- DASHBOARD / REPORT / ORG -------------------------
class TestDashboardReport:
    def test_dashboard(self, admin):
        r = admin.get(f"{API}/dashboard", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ["tesserati_count", "ricevute_mese_count", "incassato_mese", "entrate_anno",
                  "uscite_anno", "saldo_anno", "scadenze_imminenti"]:
            assert k in d, k
        assert isinstance(d["tesserati_count"], int)
        assert isinstance(d["scadenze_imminenti"], list)
        assert d["saldo_anno"] == pytest.approx(d["entrate_anno"] - d["uscite_anno"])

    def test_bilancio(self, admin):
        r = admin.get(f"{API}/report/bilancio?date_from=2026-01-01&date_to=2026-12-31", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "movimenti" in d and "totali" in d
        t = d["totali"]
        assert t["saldo"] == pytest.approx(t["entrate"] - t["uscite"])
        assert all("_id" not in m for m in d["movimenti"])

    def test_bilancio_pdf(self, admin):
        r = admin.get(f"{API}/report/bilancio/pdf?date_from=2026-01-01&date_to=2026-12-31",
                      timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_bilancio_missing_params_422(self, admin):
        assert admin.get(f"{API}/report/bilancio", timeout=30).status_code == 422

    def test_org_get_and_patch(self, admin, tecnico):
        r = admin.get(f"{API}/organizzazione", timeout=30)
        assert r.status_code == 200, r.text[:300]
        org = r.json()
        assert "Wolf" in org["name"]
        assert org["president_name"] == "Drovelli Caivano Bruno"
        p = admin.patch(f"{API}/organizzazione", json={
            "name": "Wolf's Mind A.S.D.", "address": "Via Rivera, 17 - 10070 Front (TO)",
            "president_name": "Drovelli Caivano Bruno",
            "logo_base64": "data:image/png;base64,iVBORw0KGgo="}, timeout=30)
        assert p.status_code == 200, p.text[:300]
        assert p.json()["logo_base64"].startswith("data:image/png")
        g = admin.get(f"{API}/organizzazione", timeout=30).json()
        assert g["logo_base64"].startswith("data:image/png")
        s, _ = tecnico
        assert s.patch(f"{API}/organizzazione", json={"name": "hack"},
                       timeout=30).status_code == 403
