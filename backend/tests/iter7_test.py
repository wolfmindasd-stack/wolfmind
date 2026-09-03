"""Iteration 7 backend tests: COUNTERS, VERBALI (CRUD+PDF), COMPENSO busta paga PDF,
PORTALE TESSERATO (unauthenticated, token-based), CRON solleciti scadenze,
portale_token startup migration.

Run: cd /app/backend && python -m pytest tests/iter7_test.py -q -n 0
"""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
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

BE_ENV = dotenv_values("/app/backend/.env")
CRON_SECRET = BE_ENV.get("WEBHOOK_CRON_SECRET", "")
TODAY = datetime.now(timezone.utc).date()


def _db():
    from pymongo import MongoClient
    return MongoClient(BE_ENV["MONGO_URL"])[BE_ENV["DB_NAME"]]


def _pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        return ""
    reader = PdfReader(BytesIO(content))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


# ------------------------- fixtures -------------------------
@pytest.fixture(scope="session", autouse=True)
def _reset_state():
    d = _db()
    d.login_attempts.delete_many({})
    yield
    d.login_attempts.delete_many({})


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
    created = []

    def _mk(perc=50.0):
        tag = uuid.uuid4().hex[:6]
        payload = {"email": f"test_i7_{tag}@example.com", "password": "TecPass2026!",
                   "name": f"TEST_I7Tec_{tag}", "role": "tecnico",
                   "percentuale_compenso": perc}
        r = admin.post(f"{API}/users", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        u = r.json()
        created.append(u["id"])
        s = requests.Session()
        lr = s.post(f"{API}/auth/login", json={"email": payload["email"],
                                               "password": payload["password"]}, timeout=30)
        assert lr.status_code == 200, lr.text[:300]
        return s, u
    yield _mk
    for uid in created:
        admin.delete(f"{API}/users/{uid}", timeout=30)


@pytest.fixture(scope="session")
def mk_tesserato(admin):
    created = []

    def _mk(**extra):
        tag = uuid.uuid4().hex[:6].upper()
        payload = {"cognome": "TEST_I7", "nome": f"P{tag}",
                   "codice_fiscale": f"RSSMRA80A01{tag}1Z", "indirizzo": "Via Roma",
                   "civico": "1", "cap": "10070", "citta": "Front", "provincia": "TO",
                   "email": "delivered@resend.dev", "telefono": "+39 3331234567"}
        payload.update(extra)
        r = admin.post(f"{API}/tesserati", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        t = r.json()
        created.append(t["id"])
        return t
    yield _mk
    for tid in created:
        admin.delete(f"{API}/tesserati/{tid}", timeout=30)


@pytest.fixture(scope="session")
def mk_slot(admin):
    created = []

    def _mk(days_ahead=5, capacita=8, ora="18:00"):
        d = (TODAY + timedelta(days=days_ahead)).isoformat()
        r = admin.post(f"{API}/calendario", json={"data": d, "ora": ora, "durata_min": 60,
                                                  "luogo": "TEST_I7 Palestra", "capacita": capacita,
                                                  "descrizione": "TEST_I7 slot"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        slot = r.json()["slots"][0]
        created.append(slot["id"])
        return slot
    yield _mk
    for sid in created:
        admin.delete(f"{API}/calendario/{sid}", timeout=30)


def mk_ricevuta(session, tesserato_id, importo=100.0, data="2026-03-15", **extra):
    body = {"tesserato_id": tesserato_id, "data": data, "metodo_pagamento": "Contanti",
            "items": [{"descrizione": "TEST_I7 Pacchetto", "num_lezioni": 12, "importo": importo}],
            "note": "TEST_I7"}
    body.update(extra)
    return session.post(f"{API}/ricevute", json=body, timeout=30)


# ============================================================
# COUNTERS - numerazione ricevute modificabile
# ============================================================
class TestCounters:
    def test_get_counter(self, admin):
        r = admin.get(f"{API}/counters/ricevute/2026", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["year"] == 2026
        assert isinstance(d["seq"], int)

    def test_get_counter_unauthenticated(self):
        r = requests.get(f"{API}/counters/ricevute/2026", timeout=30)
        assert r.status_code == 401, r.status_code

    def test_patch_counter_then_next_receipt_number(self, admin, mk_tesserato):
        orig = admin.get(f"{API}/counters/ricevute/2026", timeout=30).json()["seq"]
        try:
            r = admin.patch(f"{API}/counters/ricevute/2026", json={"seq": 50}, timeout=30)
            assert r.status_code == 200, r.text[:300]
            assert r.json() == {"year": 2026, "seq": 50}
            # persisted
            assert admin.get(f"{API}/counters/ricevute/2026", timeout=30).json()["seq"] == 50
            t = mk_tesserato()
            rr = mk_ricevuta(admin, t["id"], data="2026-03-15")
            assert rr.status_code == 200, rr.text[:300]
            assert rr.json()["numero"] == "2026/00051", rr.json()["numero"]
            admin.delete(f"{API}/ricevute/{rr.json()['id']}", timeout=30)
        finally:
            admin.patch(f"{API}/counters/ricevute/2026", json={"seq": orig}, timeout=30)

    def test_patch_counter_negative_rejected(self, admin):
        r = admin.patch(f"{API}/counters/ricevute/2026", json={"seq": -1}, timeout=30)
        assert r.status_code == 422, r.status_code

    def test_patch_counter_tecnico_forbidden(self, mk_tecnico):
        s, _ = mk_tecnico()
        r = s.patch(f"{API}/counters/ricevute/2026", json={"seq": 5}, timeout=30)
        assert r.status_code == 403, f"{r.status_code} {r.text[:200]}"


# ============================================================
# VERBALI - CRUD
# ============================================================
VERBALE = {"tipo": "assemblea", "data": "2026-03-15", "oggetto": "TEST_I7 Bilancio",
           "contenuto": "testo del verbale di prova", "presenti": ["Alfa Uno", "Beta Due", "Gamma Tre"],
           "assenti": ["Delta Quattro"], "delibere": "approvato all'unanimita"}


class TestVerbaliCrud:
    def test_full_crud(self, admin):
        r = admin.post(f"{API}/verbali", json=VERBALE, timeout=30)
        assert r.status_code == 200, r.text[:300]
        v = r.json()
        assert "id" in v and "_id" not in v
        assert v["oggetto"] == VERBALE["oggetto"]
        assert v["presenti"] == VERBALE["presenti"]
        vid = v["id"]

        # GET one - full doc
        g = admin.get(f"{API}/verbali/{vid}", timeout=30)
        assert g.status_code == 200
        assert g.json()["contenuto"] == VERBALE["contenuto"]
        assert g.json()["delibere"] == VERBALE["delibere"]

        # LIST contains it
        lst = admin.get(f"{API}/verbali", timeout=30)
        assert lst.status_code == 200
        assert any(x["id"] == vid for x in lst.json())

        # PATCH
        p = admin.patch(f"{API}/verbali/{vid}", json={"oggetto": "TEST_I7 Bilancio MOD",
                                                      "presenti": ["Solo Uno"]}, timeout=30)
        assert p.status_code == 200, p.text[:300]
        assert p.json()["oggetto"] == "TEST_I7 Bilancio MOD"
        g2 = admin.get(f"{API}/verbali/{vid}", timeout=30).json()
        assert g2["oggetto"] == "TEST_I7 Bilancio MOD"
        assert g2["presenti"] == ["Solo Uno"]
        assert g2["contenuto"] == VERBALE["contenuto"]  # untouched

        # DELETE then 404
        d = admin.delete(f"{API}/verbali/{vid}", timeout=30)
        assert d.status_code == 200, d.text[:300]
        assert admin.get(f"{API}/verbali/{vid}", timeout=30).status_code == 404
        assert admin.delete(f"{API}/verbali/{vid}", timeout=30).status_code == 404

    def test_list_excludes_heavy_allegato(self, admin):
        payload = dict(VERBALE)
        payload["allegato_base64"] = "data:application/pdf;base64," + ("QQ==" * 50)
        r = admin.post(f"{API}/verbali", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:300]
        vid = r.json()["id"]
        try:
            item = next(x for x in admin.get(f"{API}/verbali", timeout=30).json()
                        if x["id"] == vid)
            assert "allegato_base64" not in item
            assert item.get("has_allegato") is True
            full = admin.get(f"{API}/verbali/{vid}", timeout=30).json()
            assert full["allegato_base64"] == payload["allegato_base64"]
        finally:
            admin.delete(f"{API}/verbali/{vid}", timeout=30)

    def test_tecnico_cannot_write(self, mk_tecnico, admin):
        s, _ = mk_tecnico()
        assert s.post(f"{API}/verbali", json=VERBALE, timeout=30).status_code == 403
        r = admin.post(f"{API}/verbali", json=VERBALE, timeout=30)
        vid = r.json()["id"]
        try:
            assert s.patch(f"{API}/verbali/{vid}", json={"oggetto": "x"}, timeout=30).status_code == 403
            assert s.delete(f"{API}/verbali/{vid}", timeout=30).status_code == 403
        finally:
            admin.delete(f"{API}/verbali/{vid}", timeout=30)

    def test_unauthenticated_blocked(self):
        assert requests.get(f"{API}/verbali", timeout=30).status_code == 401
        assert requests.post(f"{API}/verbali", json=VERBALE, timeout=30).status_code == 401

    def test_invalid_tipo_rejected(self, admin):
        bad = dict(VERBALE, tipo="pippo")
        assert admin.post(f"{API}/verbali", json=bad, timeout=30).status_code == 422

    def test_get_invalid_id(self, admin):
        r = admin.get(f"{API}/verbali/not-an-objectid", timeout=30)
        assert r.status_code in (400, 404, 422), f"{r.status_code} {r.text[:200]}"


# ============================================================
# VERBALI - PDF
# ============================================================
class TestVerbalePdf:
    def test_pdf_content(self, admin):
        vid = admin.post(f"{API}/verbali", json=VERBALE, timeout=30).json()["id"]
        try:
            r = admin.get(f"{API}/verbali/{vid}/pdf", timeout=60)
            assert r.status_code == 200, r.text[:300]
            assert r.headers.get("content-type", "").startswith("application/pdf")
            assert "attachment" in r.headers.get("content-disposition", "")
            assert r.content[:4] == b"%PDF"
            txt = _pdf_text(r.content)
            assert "VERBALE DI ASSEMBLEA" in txt.upper(), txt[:400]
            for name in VERBALE["presenti"]:
                assert name in txt, f"missing presente {name} in PDF"
            assert VERBALE["oggetto"] in txt
            assert "approvato" in txt
        finally:
            admin.delete(f"{API}/verbali/{vid}", timeout=30)

    def test_pdf_404(self, admin):
        assert admin.get(f"{API}/verbali/507f1f77bcf86cd799439011/pdf", timeout=30).status_code == 404

    def test_pdf_unauthenticated(self, admin):
        vid = admin.post(f"{API}/verbali", json=VERBALE, timeout=30).json()["id"]
        try:
            assert requests.get(f"{API}/verbali/{vid}/pdf", timeout=30).status_code == 401
        finally:
            admin.delete(f"{API}/verbali/{vid}", timeout=30)


# ============================================================
# COMPENSO EROGATO - busta paga PDF
# ============================================================
class TestCompensoPdf:
    @pytest.fixture(scope="class")
    def erogazione(self, admin, mk_tecnico, mk_tesserato):
        s, tec = mk_tecnico(perc=50.0)
        t = mk_tesserato()
        r1 = mk_ricevuta(admin, t["id"], importo=200.0, data="2026-03-10",
                         emesso_per_id=tec["id"])
        assert r1.status_code == 200, r1.text[:300]
        er = admin.post(f"{API}/compensi/eroga", json={
            "tecnico_id": tec["id"], "data": "2026-03-31", "importo": 100.0,
            "periodo_da": "2026-03-01", "periodo_a": "2026-03-31",
            "metodo": "Bonifico", "note": "TEST_I7 compenso"}, timeout=30)
        assert er.status_code == 200, er.text[:300]
        lst = admin.get(f"{API}/compensi/erogati?tecnico_id={tec['id']}", timeout=30)
        assert lst.status_code == 200, lst.text[:300]
        rows = lst.json()
        assert len(rows) >= 1
        row = rows[0]
        assert row["importo"] == 100.0
        assert "_id" not in row
        yield {"tec": tec, "tec_session": s, "cid": row["id"], "ricevuta_id": r1.json()["id"]}
        admin.delete(f"{API}/ricevute/{r1.json()['id']}", timeout=30)

    def test_pdf_as_admin(self, admin, erogazione):
        r = admin.get(f"{API}/compensi/erogati/{erogazione['cid']}/pdf", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert "attachment" in r.headers.get("content-disposition", "")
        txt = _pdf_text(r.content)
        assert "EROGAZIONE COMPENSO" in txt.upper(), txt[:400]
        assert erogazione["tec"]["name"] in txt, txt[:600]
        assert "100" in txt

    def test_pdf_as_own_tecnico(self, erogazione):
        r = erogazione["tec_session"].get(f"{API}/compensi/erogati/{erogazione['cid']}/pdf", timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert r.content[:4] == b"%PDF"

    def test_pdf_other_tecnico_forbidden(self, mk_tecnico, erogazione):
        other, _ = mk_tecnico()
        r = other.get(f"{API}/compensi/erogati/{erogazione['cid']}/pdf", timeout=30)
        assert r.status_code == 403, f"{r.status_code} {r.text[:200]}"

    def test_pdf_unauthenticated(self, erogazione):
        r = requests.get(f"{API}/compensi/erogati/{erogazione['cid']}/pdf", timeout=30)
        assert r.status_code == 401

    def test_pdf_404(self, admin):
        r = admin.get(f"{API}/compensi/erogati/507f1f77bcf86cd799439011/pdf", timeout=30)
        assert r.status_code == 404

    def test_erogati_tecnico_sees_only_own(self, mk_tecnico, erogazione):
        other, other_u = mk_tecnico()
        rows = other.get(f"{API}/compensi/erogati", timeout=30).json()
        assert all(x["tecnico_id"] == other_u["id"] for x in rows), rows[:2]


# ============================================================
# PORTALE TESSERATO (unauthenticated, token based)
# ============================================================
class TestPortaleDashboard:
    def test_create_returns_portale_token(self, mk_tesserato):
        t = mk_tesserato()
        assert t.get("portale_token"), t
        assert len(t["portale_token"]) >= 16

    def test_dashboard_unauthenticated(self, mk_tesserato):
        t = mk_tesserato()
        r = requests.get(f"{API}/portale/{t['portale_token']}", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert set(["tesserato", "abbonamenti", "organizzazione"]).issubset(d.keys())
        assert d["tesserato"]["nome"] == t["nome"]
        assert d["tesserato"]["cognome"] == t["cognome"]
        assert d["tesserato"]["numero_tessera"] == t.get("numero_tessera")
        assert "scadenza_tesseramento" in d["tesserato"]
        assert "scadenza_visita_medica" in d["tesserato"]
        assert "name" in d["organizzazione"]
        assert isinstance(d["abbonamenti"], list)
        # must not leak internals
        for leak in ("codice_fiscale", "portale_token", "_id", "id", "created_by"):
            assert leak not in d["tesserato"], f"leaked {leak}"
        assert "president_signature_base64" not in d["organizzazione"]

    def test_dashboard_abbonamenti_lezioni_residue(self, admin, mk_tesserato):
        t = mk_tesserato()
        ab = admin.post(f"{API}/abbonamenti", json={
            "tesserato_id": t["id"], "descrizione": "TEST_I7 12 lezioni",
            "num_lezioni_totali": 12, "prezzo": 100.0,
            "data_acquisto": "2026-03-12"}, timeout=30)
        assert ab.status_code == 200, ab.text[:300]
        aid = ab.json()["id"]
        try:
            d = requests.get(f"{API}/portale/{t['portale_token']}", timeout=30).json()
            assert len(d["abbonamenti"]) >= 1, d["abbonamenti"]
            row = next(x for x in d["abbonamenti"] if x["id"] == aid)
            assert "lezioni_residue" in row
            assert row["lezioni_residue"] == 12, row
            assert row["lezioni_effettuate"] == 0
            assert "_id" not in row
        finally:
            admin.delete(f"{API}/abbonamenti/{aid}", timeout=30)

    def test_invalid_token_404(self):
        assert requests.get(f"{API}/portale/wrong-token", timeout=30).status_code == 404
        assert requests.get(f"{API}/portale/wrong-token/ricevute", timeout=30).status_code == 404
        assert requests.get(f"{API}/portale/wrong-token/calendario", timeout=30).status_code == 404


class TestPortaleRicevute:
    def test_only_own_and_not_annullate(self, admin, mk_tesserato):
        a = mk_tesserato()
        b = mk_tesserato()
        ra = mk_ricevuta(admin, a["id"], importo=100.0, data="2026-03-11")
        ra2 = mk_ricevuta(admin, a["id"], importo=50.0, data="2026-03-12")
        rb = mk_ricevuta(admin, b["id"], importo=70.0, data="2026-03-13")
        assert ra.status_code == 200 and rb.status_code == 200
        rid_del = ra2.json()["id"]
        try:
            rows = requests.get(f"{API}/portale/{a['portale_token']}/ricevute", timeout=30)
            assert rows.status_code == 200
            rows = rows.json()
            ids = {x["id"] for x in rows}
            assert ra.json()["id"] in ids
            assert rb.json()["id"] not in ids, "cross-tesserato receipt leak"
            row = next(x for x in rows if x["id"] == ra.json()["id"])
            for k in ("numero", "data", "totale"):
                assert row.get(k) is not None, row
            assert row["totale"] == 100.0
            # delete/annulla the 2nd one -> must disappear
            admin.delete(f"{API}/ricevute/{rid_del}", timeout=30)
            ids2 = {x["id"] for x in requests.get(
                f"{API}/portale/{a['portale_token']}/ricevute", timeout=30).json()}
            assert rid_del not in ids2, "annullata/deleted receipt still listed"
        finally:
            admin.delete(f"{API}/ricevute/{ra.json()['id']}", timeout=30)
            admin.delete(f"{API}/ricevute/{rb.json()['id']}", timeout=30)

    def test_pdf_download_and_isolation(self, admin, mk_tesserato):
        a = mk_tesserato()
        b = mk_tesserato()
        ra = mk_ricevuta(admin, a["id"], importo=100.0, data="2026-03-14")
        rb = mk_ricevuta(admin, b["id"], importo=60.0, data="2026-03-14")
        rid_a, rid_b = ra.json()["id"], rb.json()["id"]
        try:
            r = requests.get(f"{API}/portale/{a['portale_token']}/ricevuta/{rid_a}/pdf", timeout=60)
            assert r.status_code == 200, r.text[:300]
            assert r.headers.get("content-type", "").startswith("application/pdf")
            assert r.content[:4] == b"%PDF"
            assert "RICEVUTA" in _pdf_text(r.content).upper()
            # isolation: A cannot fetch B's receipt
            x = requests.get(f"{API}/portale/{a['portale_token']}/ricevuta/{rid_b}/pdf", timeout=30)
            assert x.status_code == 403, f"{x.status_code} {x.text[:200]}"
            # missing receipt
            m = requests.get(
                f"{API}/portale/{a['portale_token']}/ricevuta/507f1f77bcf86cd799439011/pdf", timeout=30)
            assert m.status_code == 404
        finally:
            admin.delete(f"{API}/ricevute/{rid_b}", timeout=30)
            admin.delete(f"{API}/ricevute/{rid_a}", timeout=30)

    def test_pdf_after_delete_returns_404(self, admin, mk_tesserato):
        a = mk_tesserato()
        ra = mk_ricevuta(admin, a["id"], importo=100.0, data="2026-03-16")
        rid = ra.json()["id"]
        admin.delete(f"{API}/ricevute/{rid}", timeout=30)
        r = requests.get(f"{API}/portale/{a['portale_token']}/ricevuta/{rid}/pdf", timeout=30)
        assert r.status_code == 404, f"expected 404 after delete/annulla, got {r.status_code}"


class TestPortaleCalendario:
    def test_window_and_flags(self, mk_tesserato, mk_slot):
        t = mk_tesserato()
        near = mk_slot(days_ahead=5)
        far = mk_slot(days_ahead=30)
        r = requests.get(f"{API}/portale/{t['portale_token']}/calendario", timeout=30)
        assert r.status_code == 200, r.text[:300]
        rows = r.json()
        by_id = {x["id"]: x for x in rows}
        assert near["id"] in by_id, "slot within 3 weeks missing"
        assert far["id"] not in by_id, "slot beyond 3 weeks must not appear"
        s = by_id[near["id"]]
        assert s["posti_liberi"] == 8, s
        assert s["gia_prenotato"] is False
        assert s["data"] == near["data"]
        for k in ("ora", "capacita", "luogo"):
            assert k in s
        assert "prenotazioni" not in s, "raw prenotazioni list leaked to public portal"

    def test_prenota_flow(self, mk_tesserato, mk_slot):
        """Prenota/cancel verified against mongo because GET /portale/{t}/calendario
        currently 500s (async_generator bug in `gia_prenotato`)."""
        from bson import ObjectId
        t = mk_tesserato()
        slot = mk_slot(days_ahead=6)
        tok = t["portale_token"]
        d = _db()

        def prenot_ids():
            s = d.slot_calendario.find_one({"_id": ObjectId(slot["id"])})
            return [p.get("tesserato_id") for p in (s.get("prenotazioni") or [])]

        r = requests.post(f"{API}/portale/{tok}/prenota", json={"slot_id": slot["id"]}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json() == {"ok": True}
        assert prenot_ids() == [t["id"]], prenot_ids()
        # duplicate -> 409
        dup = requests.post(f"{API}/portale/{tok}/prenota", json={"slot_id": slot["id"]}, timeout=30)
        assert dup.status_code == 409, f"{dup.status_code} {dup.text[:200]}"
        assert prenot_ids() == [t["id"]]
        # cancel -> 200
        c = requests.delete(f"{API}/portale/{tok}/prenota/{slot['id']}", timeout=60)
        assert c.status_code == 200, c.text[:300]
        assert prenot_ids() == []
        # cancel again -> 404
        c2 = requests.delete(f"{API}/portale/{tok}/prenota/{slot['id']}", timeout=30)
        assert c2.status_code == 404, f"{c2.status_code} {c2.text[:200]}"

    def test_calendario_500_when_slot_has_prenotazione(self, mk_tesserato, mk_slot):
        """Regression guard for the async_generator TypeError in portale_calendario."""
        t = mk_tesserato()
        slot = mk_slot(days_ahead=9, ora="21:00")
        tok = t["portale_token"]
        assert requests.post(f"{API}/portale/{tok}/prenota",
                             json={"slot_id": slot["id"]}, timeout=60).status_code == 200
        r = requests.get(f"{API}/portale/{tok}/calendario", timeout=30)
        assert r.status_code == 200, f"calendario 500 after booking: {r.status_code}"
        row = next(x for x in r.json() if x["id"] == slot["id"])
        assert row["gia_prenotato"] is True

    def test_prenota_beyond_3_weeks_rejected(self, mk_tesserato, mk_slot):
        t = mk_tesserato()
        slot = mk_slot(days_ahead=30)
        r = requests.post(f"{API}/portale/{t['portale_token']}/prenota",
                          json={"slot_id": slot["id"]}, timeout=30)
        assert r.status_code == 400, f"{r.status_code} {r.text[:200]}"

    def test_prenota_full_slot(self, mk_tesserato, mk_slot):
        slot = mk_slot(days_ahead=7, capacita=1, ora="19:00")
        a, b = mk_tesserato(), mk_tesserato()
        r1 = requests.post(f"{API}/portale/{a['portale_token']}/prenota",
                           json={"slot_id": slot["id"]}, timeout=60)
        assert r1.status_code == 200, r1.text[:300]
        r2 = requests.post(f"{API}/portale/{b['portale_token']}/prenota",
                           json={"slot_id": slot["id"]}, timeout=30)
        assert r2.status_code == 409, f"{r2.status_code} {r2.text[:200]}"

    def test_prenota_bad_token_and_slot(self, mk_tesserato, mk_slot):
        t = mk_tesserato()
        slot = mk_slot(days_ahead=8, ora="20:00")
        assert requests.post(f"{API}/portale/wrong-token/prenota",
                             json={"slot_id": slot["id"]}, timeout=30).status_code == 404
        assert requests.post(f"{API}/portale/{t['portale_token']}/prenota",
                             json={"slot_id": "507f1f77bcf86cd799439011"},
                             timeout=30).status_code == 404


# ============================================================
# CRON: solleciti scadenze
# ============================================================
class TestCronSolleciti:
    def test_no_auth_header(self):
        r = requests.post(f"{API}/cron/solleciti-scadenze", timeout=30)
        assert r.status_code == 401, f"{r.status_code} {r.text[:200]}"

    def test_wrong_secret(self):
        r = requests.post(f"{API}/cron/solleciti-scadenze",
                          headers={"Authorization": "Bearer wrong-secret"}, timeout=30)
        assert r.status_code == 401, f"{r.status_code} {r.text[:200]}"

    def test_non_bearer_scheme(self):
        r = requests.post(f"{API}/cron/solleciti-scadenze",
                          headers={"Authorization": CRON_SECRET}, timeout=30)
        assert r.status_code == 401

    def test_valid_secret_acks(self):
        assert CRON_SECRET, "WEBHOOK_CRON_SECRET missing in backend/.env"
        r = requests.post(f"{API}/cron/solleciti-scadenze",
                          headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json() == {"ok": True, "queued": True}

    def test_functional_reminder_recorded_and_idempotent(self, mk_tesserato):
        import time
        target = (TODAY + timedelta(days=15)).isoformat()
        t = mk_tesserato(scadenza_tesseramento=target)
        d = _db()
        d.solleciti_inviati.delete_many({"tesserato_id": t["id"]})
        hdr = {"Authorization": f"Bearer {CRON_SECRET}"}
        r = requests.post(f"{API}/cron/solleciti-scadenze", headers=hdr, timeout=30)
        assert r.status_code == 200
        rows = []
        for _ in range(15):
            time.sleep(1)
            rows = list(d.solleciti_inviati.find({"tesserato_id": t["id"]}))
            if rows:
                break
        assert rows, f"no sollecito row recorded for tesserato {t['id']}"
        assert t["id"] in rows[0]["_id"], rows[0]
        assert rows[0]["scadenza"] == target
        assert rows[0]["tipo"] == "Tesseramento"
        # idempotency: second run must not duplicate
        requests.post(f"{API}/cron/solleciti-scadenze", headers=hdr, timeout=30)
        time.sleep(6)
        rows2 = list(d.solleciti_inviati.find({"tesserato_id": t["id"]}))
        assert len(rows2) == len(rows), f"duplicate solleciti: {len(rows2)} vs {len(rows)}"
        d.solleciti_inviati.delete_many({"tesserato_id": t["id"]})


# ============================================================
# MIGRATION: portale_token backfill on startup
# ============================================================
class TestPortaleTokenMigration:
    def test_all_tesserati_have_token(self, admin):
        d = _db()
        missing = d.tesserati.count_documents({"portale_token": {"$exists": False}})
        assert missing == 0, f"{missing} tesserati without portale_token"
        nulls = d.tesserati.count_documents({"portale_token": None})
        assert nulls == 0, f"{nulls} tesserati with null portale_token"

    def test_tokens_are_unique(self):
        d = _db()
        toks = [t["portale_token"] for t in d.tesserati.find({}, {"portale_token": 1})]
        assert len(toks) == len(set(toks)), "duplicate portale_token found"
