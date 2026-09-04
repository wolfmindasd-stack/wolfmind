"""Iteration 11 - new features: multi-item abbonamenti, auto-ricevuta, admin edit/delete,
compensi da_erogare, busta paga 2 pagine, verbale extended fields, org secretary signature.
"""
import io
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

PNG_B64 = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"
           "C0lEQVR42mP8z8AAAwAB/1qgQ9AAAAAASUVORK5CYII=")


def _creds():
    c = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    e = re.search(r"(?im)^\s*[-*]?\s*Email:\s*`?([^`\s]+)", c)
    w = re.search(r"(?im)^\s*[-*]?\s*Password:\s*`?([^`\s]+)", c)
    assert e and w, "credentials not parseable"
    return {"email": e.group(1), "password": w.group(1)}


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=_creds(), timeout=30)
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    return s


@pytest.fixture(scope="module")
def tesserato(admin):
    r = admin.post(f"{API}/tesserati", json={
        "cognome": "TEST_Abb11", "nome": "Multi", "codice_fiscale": "TSTABB11XXXXXXXX",
        "citta": "Torino", "scadenza_tesseramento": "2020-01-01"}, timeout=30)
    assert r.status_code in (200, 201), r.text[:300]
    tid = r.json()["id"]
    yield tid
    admin.delete(f"{API}/tesserati/{tid}", timeout=30)


@pytest.fixture(scope="module")
def tecnico(admin):
    payload = {"email": "test_tec_iter11@wolfsmind.it", "password": "Tecnico2026!",
               "name": "TEST_Tecnico11", "role": "tecnico", "percentuale_compenso": 50}
    r = admin.post(f"{API}/users", json=payload, timeout=30)
    if r.status_code not in (200, 201):
        # may already exist
        users = admin.get(f"{API}/users", timeout=30).json()
        found = [u for u in users if u["email"] == payload["email"]]
        assert found, f"cannot create tecnico: {r.status_code} {r.text[:200]}"
        uid = found[0]["id"]
        admin.patch(f"{API}/users/{uid}", json={"password": payload["password"],
                                                "active": True}, timeout=30)
    else:
        uid = r.json()["id"]
    s = requests.Session()
    lr = s.post(f"{API}/auth/login", json={"email": payload["email"],
                                           "password": payload["password"]}, timeout=30)
    assert lr.status_code == 200, f"tecnico login failed: {lr.status_code} {lr.text[:200]}"
    yield {"id": uid, "session": s}
    admin.delete(f"{API}/users/{uid}", timeout=30)


def _movimenti_for(admin, aid):
    r = admin.get(f"{API}/movimenti", timeout=30)
    assert r.status_code == 200, r.text[:200]
    return [m for m in r.json() if m.get("abbonamento_id") == aid]


# ---------- ORGANIZZAZIONE (new fields) ----------
class TestOrganizzazione:
    def test_get_org_has_new_fields(self, admin):
        r = admin.get(f"{API}/organizzazione", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "auto_ricevuta_abbonamento" in d, list(d.keys())
        # NOTE: secretary_signature_base64 is absent from the default org doc until
        # it is uploaded once (minor: default _load_org() doc lacks the key).
        assert d.get("president_name") == "Drovetti Cassiano Bruno"
        assert "_id" not in d

    def test_toggle_auto_ricevuta_persists(self, admin):
        try:
            r = admin.patch(f"{API}/organizzazione",
                            json={"auto_ricevuta_abbonamento": True}, timeout=30)
            assert r.status_code == 200, r.text[:300]
            assert r.json()["auto_ricevuta_abbonamento"] is True
            g = admin.get(f"{API}/organizzazione", timeout=30).json()
            assert g["auto_ricevuta_abbonamento"] is True
            # turn OFF again -> must persist False (None-filter bug check)
            r2 = admin.patch(f"{API}/organizzazione",
                             json={"auto_ricevuta_abbonamento": False}, timeout=30)
            assert r2.status_code == 200, r2.text[:300]
            assert r2.json()["auto_ricevuta_abbonamento"] is False, r2.json()
            g2 = admin.get(f"{API}/organizzazione", timeout=30).json()
            assert g2["auto_ricevuta_abbonamento"] is False
        finally:
            admin.patch(f"{API}/organizzazione",
                        json={"auto_ricevuta_abbonamento": False}, timeout=30)

    def test_upload_secretary_signature(self, admin):
        r = admin.patch(f"{API}/organizzazione",
                        json={"secretary_signature_base64": PNG_B64}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["secretary_signature_base64"] == PNG_B64
        g = admin.get(f"{API}/organizzazione", timeout=30).json()
        assert g["secretary_signature_base64"] == PNG_B64


# ---------- ABBONAMENTI multi-item ----------
class TestAbbonamentoMultiItem:
    def test_create_multi_item_movimenti_and_quota(self, admin, tesserato):
        payload = {
            "tesserato_id": tesserato,
            "descrizione": "TEST_Pacchetto misto",
            "prezzo": 0,
            "data_acquisto": "2026-03-10",
            "metodo_pagamento": "Bonifico",
            "crea_ricevuta": False,
            "items": [
                {"descrizione": "10 lezioni", "categoria": "Lezioni",
                 "num_lezioni": 10, "importo": 200},
                {"descrizione": "Quota 2026", "categoria": "Quota associativa",
                 "importo": 50},
                {"descrizione": "T-shirt", "categoria": "Merchandising", "importo": 25},
                {"descrizione": "Extra", "categoria": "Altro", "importo": 5},
            ]}
        r = admin.post(f"{API}/abbonamenti", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:400]
        ab = r.json()
        aid = ab["id"]
        try:
            assert ab["prezzo"] == 280, ab
            assert ab["num_lezioni_totali"] == 10, ab
            assert len(ab["items"]) == 4
            assert ab.get("ricevuta_id") in (None, ""), ab.get("ricevuta_id")
            # (a) 1 movimento per categoria
            movs = _movimenti_for(admin, aid)
            cats = sorted(m["categoria"] for m in movs)
            assert cats == ["Altro", "Lezioni", "Merchandising", "Quota associativa"], cats
            assert round(sum(m["importo"] for m in movs), 2) == 280.0
            assert all(m["tipo"] == "entrata" for m in movs)
            # (b) scadenza tesseramento aggiornata a +1 anno
            t = admin.get(f"{API}/tesserati/{tesserato}", timeout=30).json()
            assert t["scadenza_tesseramento"][:10] == "2027-03-10", t["scadenza_tesseramento"]
            # list endpoint fields
            lst = admin.get(f"{API}/abbonamenti?stato=attivi", timeout=30).json()
            mine = [x for x in lst if x["id"] == aid]
            assert mine, "abbonamento not in stato=attivi list"
            assert mine[0]["ricevuta_generata"] is False
            assert "ricevuta_numero" in mine[0] or mine[0].get("ricevuta_numero") is None
        finally:
            admin.delete(f"{API}/abbonamenti/{aid}", timeout=30)

    def test_quota_not_downgrading_existing_newer_scadenza(self, admin, tesserato):
        admin.patch(f"{API}/tesserati/{tesserato}",
                    json={"scadenza_tesseramento": "2030-01-01"}, timeout=30)
        r = admin.post(f"{API}/abbonamenti", json={
            "tesserato_id": tesserato, "descrizione": "TEST_quota only",
            "prezzo": 0, "data_acquisto": "2026-03-10", "crea_ricevuta": False,
            "items": [{"descrizione": "Quota", "categoria": "Quota associativa",
                       "importo": 30}]}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        aid = r.json()["id"]
        try:
            t = admin.get(f"{API}/tesserati/{tesserato}", timeout=30).json()
            assert t["scadenza_tesseramento"][:10] == "2030-01-01", t["scadenza_tesseramento"]
        finally:
            admin.delete(f"{API}/abbonamenti/{aid}", timeout=30)
            admin.patch(f"{API}/tesserati/{tesserato}",
                        json={"scadenza_tesseramento": "2020-01-01"}, timeout=30)

    def test_create_with_crea_ricevuta_true(self, admin, tesserato):
        r = admin.post(f"{API}/abbonamenti", json={
            "tesserato_id": tesserato, "descrizione": "TEST_con ricevuta",
            "prezzo": 0, "data_acquisto": "2026-04-01", "crea_ricevuta": True,
            "metodo_pagamento": "Contanti",
            "items": [{"descrizione": "5 lezioni", "categoria": "Lezioni",
                       "num_lezioni": 5, "importo": 100},
                      {"descrizione": "Quota", "categoria": "Quota associativa",
                       "importo": 40}]}, timeout=30)
        assert r.status_code in (200, 201), r.text[:400]
        ab = r.json()
        aid = ab["id"]
        try:
            assert ab.get("ricevuta_id"), ab
            assert re.match(r"^\d+/\d{4}$|^\d+", str(ab.get("ricevuta_numero") or "")), ab
            ric = admin.get(f"{API}/ricevute/{ab['ricevuta_id']}", timeout=30)
            assert ric.status_code == 200, ric.text[:300]
            rd = ric.json()
            assert rd["totale"] == 140, rd
            assert rd["numero"] == ab["ricevuta_numero"]
            assert rd["metodo_pagamento"] == "Contanti"
            excl = {i["descrizione"]: i["esclude_da_compensi"] for i in rd["items"]}
            assert excl["Quota"] is True and excl["5 lezioni"] is False, excl
            lst = admin.get(f"{API}/abbonamenti?stato=attivi", timeout=30).json()
            mine = [x for x in lst if x["id"] == aid][0]
            assert mine["ricevuta_generata"] is True
            assert mine["ricevuta_numero"] == ab["ricevuta_numero"]
        finally:
            admin.delete(f"{API}/abbonamenti/{aid}", timeout=30)
            if ab.get("ricevuta_id"):
                admin.delete(f"{API}/ricevute/{ab['ricevuta_id']}", timeout=30)

    def test_auto_ricevuta_from_org_setting(self, admin, tesserato):
        admin.patch(f"{API}/organizzazione",
                    json={"auto_ricevuta_abbonamento": True}, timeout=30)
        aid = None
        rid = None
        try:
            r = admin.post(f"{API}/abbonamenti", json={
                "tesserato_id": tesserato, "descrizione": "TEST_auto org",
                "prezzo": 0, "data_acquisto": "2026-04-02",
                "items": [{"descrizione": "3 lezioni", "categoria": "Lezioni",
                           "num_lezioni": 3, "importo": 60}]}, timeout=30)
            assert r.status_code in (200, 201), r.text[:300]
            ab = r.json()
            aid, rid = ab["id"], ab.get("ricevuta_id")
            assert rid, f"auto ricevuta not created with org toggle ON: {ab}"
        finally:
            admin.patch(f"{API}/organizzazione",
                        json={"auto_ricevuta_abbonamento": False}, timeout=30)
            if aid:
                admin.delete(f"{API}/abbonamenti/{aid}", timeout=30)
            if rid:
                admin.delete(f"{API}/ricevute/{rid}", timeout=30)


# ---------- PATCH / DELETE / genera-ricevuta ----------
class TestAbbonamentoAdminEdit:
    @pytest.fixture
    def abb(self, admin, tesserato):
        r = admin.post(f"{API}/abbonamenti", json={
            "tesserato_id": tesserato, "descrizione": "TEST_edit",
            "prezzo": 0, "data_acquisto": "2026-05-01", "crea_ricevuta": False,
            "items": [{"descrizione": "4 lezioni", "categoria": "Lezioni",
                       "num_lezioni": 4, "importo": 80}]}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        d = r.json()
        yield d
        admin.delete(f"{API}/abbonamenti/{d['id']}", timeout=30)

    def test_patch_items_only_recomputes_prezzo(self, admin, abb):
        aid = abb["id"]
        r = admin.patch(f"{API}/abbonamenti/{aid}", json={"items": [
            {"descrizione": "6 lezioni", "categoria": "Lezioni",
             "num_lezioni": 6, "importo": 120},
            {"descrizione": "Cappello", "categoria": "Merchandising", "importo": 15}]},
            timeout=30)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["prezzo"] == 135, d
        assert len(d["items"]) == 2, d
        lst = admin.get(f"{API}/abbonamenti?stato=attivi", timeout=30).json()
        mine = [x for x in lst if x["id"] == aid][0]
        assert mine["prezzo"] == 135
        assert [i["descrizione"] for i in mine["items"]] == ["6 lezioni", "Cappello"]

    def test_patch_all_admin_fields(self, admin, abb, tesserato):
        aid = abb["id"]
        r = admin.patch(f"{API}/abbonamenti/{aid}", json={
            "tesserato_id": tesserato, "data_acquisto": "2026-06-15",
            "metodo_pagamento": "POS", "descrizione": "TEST_edit updated",
            "num_lezioni_totali": 9, "prezzo": 199.5,
            "lezioni_effettuate": 2}, timeout=30)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["data_acquisto"] == "2026-06-15"
        assert d["metodo_pagamento"] == "POS"
        assert d["descrizione"] == "TEST_edit updated"
        assert d["num_lezioni_totali"] == 9
        assert d["prezzo"] == 199.5
        lst = admin.get(f"{API}/abbonamenti?stato=attivi", timeout=30).json()
        mine = [x for x in lst if x["id"] == aid][0]
        assert mine["lezioni_effettuate"] == 2, mine
        assert mine["lezioni_residue"] == 7, mine

    def test_tecnico_cannot_patch_items_or_tesserato(self, admin, tesserato, tecnico):
        r = admin.post(f"{API}/abbonamenti", json={
            "tesserato_id": tesserato, "descrizione": "TEST_tec403",
            "prezzo": 50, "data_acquisto": "2026-05-05", "crea_ricevuta": False,
            "items": [{"descrizione": "2 lezioni", "categoria": "Lezioni",
                       "num_lezioni": 2, "importo": 50}]}, timeout=30)
        aid = r.json()["id"]
        s = tecnico["session"]
        try:
            r1 = s.patch(f"{API}/abbonamenti/{aid}", json={"items": [
                {"descrizione": "hack", "categoria": "Lezioni", "importo": 1}]}, timeout=30)
            assert r1.status_code == 403, f"items patch by tecnico: {r1.status_code} {r1.text[:200]}"
            r2 = s.patch(f"{API}/abbonamenti/{aid}",
                         json={"tesserato_id": tesserato}, timeout=30)
            assert r2.status_code == 403, f"tesserato_id patch by tecnico: {r2.status_code}"
        finally:
            admin.delete(f"{API}/abbonamenti/{aid}", timeout=30)

    def test_tecnico_cannot_delete(self, admin, tesserato, tecnico):
        r = admin.post(f"{API}/abbonamenti", json={
            "tesserato_id": tesserato, "descrizione": "TEST_tecdel",
            "prezzo": 10, "data_acquisto": "2026-05-06", "crea_ricevuta": False,
            "items": []}, timeout=30)
        aid = r.json()["id"]
        try:
            rd = tecnico["session"].delete(f"{API}/abbonamenti/{aid}", timeout=30)
            assert rd.status_code == 403, rd.status_code
        finally:
            admin.delete(f"{API}/abbonamenti/{aid}", timeout=30)

    def test_delete_removes_movimenti_and_unlinks_ricevuta(self, admin, tesserato):
        r = admin.post(f"{API}/abbonamenti", json={
            "tesserato_id": tesserato, "descrizione": "TEST_del",
            "prezzo": 0, "data_acquisto": "2026-05-10", "crea_ricevuta": True,
            "items": [{"descrizione": "2 lezioni", "categoria": "Lezioni",
                       "num_lezioni": 2, "importo": 44}]}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        ab = r.json()
        aid, rid = ab["id"], ab["ricevuta_id"]
        assert _movimenti_for(admin, aid), "no movimenti created"
        dr = admin.delete(f"{API}/abbonamenti/{aid}", timeout=30)
        assert dr.status_code == 200, dr.text[:200]
        assert _movimenti_for(admin, aid) == [], "movimenti not cleaned up"
        ric = admin.get(f"{API}/ricevute/{rid}", timeout=30)
        assert ric.status_code == 200, "ricevuta should survive deletion"
        assert not ric.json().get("abbonamento_id"), ric.json().get("abbonamento_id")
        lst = admin.get(f"{API}/abbonamenti?stato=attivi", timeout=30).json()
        assert aid not in [x["id"] for x in lst]
        admin.delete(f"{API}/ricevute/{rid}", timeout=30)

    def test_genera_ricevuta_endpoint(self, admin, tesserato):
        r = admin.post(f"{API}/abbonamenti", json={
            "tesserato_id": tesserato, "descrizione": "TEST_genric",
            "prezzo": 0, "data_acquisto": "2026-05-20", "crea_ricevuta": False,
            "items": [{"descrizione": "3 lezioni", "categoria": "Lezioni",
                       "num_lezioni": 3, "importo": 66}]}, timeout=30)
        aid = r.json()["id"]
        rid = None
        try:
            g = admin.post(f"{API}/abbonamenti/{aid}/genera-ricevuta", timeout=30)
            assert g.status_code == 200, g.text[:300]
            body = g.json()
            rid = body["ricevuta_id"]
            assert body.get("numero")
            ric = admin.get(f"{API}/ricevute/{rid}", timeout=30).json()
            assert ric["totale"] == 66, ric
            lst = admin.get(f"{API}/abbonamenti?stato=attivi", timeout=30).json()
            mine = [x for x in lst if x["id"] == aid][0]
            assert mine["ricevuta_generata"] is True
            assert mine["ricevuta_numero"] == body["numero"]
            movs = _movimenti_for(admin, aid)
            assert len(movs) == 1 and movs[0]["categoria"] == "Ricevuta", movs
            g2 = admin.post(f"{API}/abbonamenti/{aid}/genera-ricevuta", timeout=30)
            assert g2.status_code == 400, g2.status_code
        finally:
            admin.delete(f"{API}/abbonamenti/{aid}", timeout=30)
            if rid:
                admin.delete(f"{API}/ricevute/{rid}", timeout=30)


# ---------- COMPENSI ----------
class TestCompensi:
    def test_compensi_fields(self, admin, tecnico):
        r = admin.get(f"{API}/compensi", timeout=30)
        assert r.status_code == 200, r.text[:300]
        rows = r.json()["compensi"]
        assert isinstance(rows, list) and rows, "no tecnici rows"
        for row in rows:
            for k in ("da_erogare", "gia_erogato", "compenso_dovuto", "percentuale"):
                assert k in row, row
            assert row["da_erogare"] == max(
                0.0, round(row["compenso_dovuto"] - row["gia_erogato"], 2)), row

    def test_erogazione_updates_da_erogare_and_pdf_2_pages(self, admin, tesserato, tecnico):
        tid = tecnico["id"]
        # ricevuta attribuita al tecnico -> genera compenso
        rr = admin.post(f"{API}/ricevute", json={
            "tesserato_id": tesserato, "data": "2026-02-10",
            "metodo_pagamento": "Contanti", "emesso_per_id": tid,
            "items": [{"descrizione": "TEST_lezioni compenso", "num_lezioni": 5,
                       "importo": 200, "esclude_da_compensi": False},
                      {"descrizione": "TEST_quota", "importo": 50,
                       "esclude_da_compensi": True}],
            "note": "TEST"}, timeout=30)
        assert rr.status_code in (200, 201), rr.text[:300]
        rid = rr.json()["id"]
        cid = None
        try:
            c = admin.get(f"{API}/compensi?date_from=2026-01-01&date_to=2026-12-31",
                          timeout=30).json()["compensi"]
            row = [x for x in c if x["tecnico_id"] == tid][0]
            assert row["flusso_compensabile"] >= 200, row
            expected = round(row["flusso_compensabile"] * row["percentuale"] / 100, 2)
            assert round(row["compenso_dovuto"], 2) == expected, row
            assert row["da_erogare"] > 0, row
            before = row["da_erogare"]

            er = admin.post(f"{API}/compensi/eroga", json={
                "tecnico_id": tid, "data": "2026-02-15", "importo": 30,
                "periodo_da": "2026-01-01", "periodo_a": "2026-12-31",
                "metodo": "Bonifico", "note": "TEST_erogazione"}, timeout=30)
            assert er.status_code in (200, 201), er.text[:300]
            erogati = admin.get(f"{API}/compensi/erogati?tecnico_id={tid}",
                                timeout=30).json()
            match = [e for e in erogati
                     if e["data"] == "2026-02-15" and e["importo"] == 30]
            assert match, f"erogazione not persisted: {erogati}"
            cid = match[0]["id"]

            c2 = admin.get(f"{API}/compensi?date_from=2026-01-01&date_to=2026-12-31",
                           timeout=30).json()["compensi"]
            row2 = [x for x in c2 if x["tecnico_id"] == tid][0]
            assert row2["gia_erogato"] >= 30, row2
            assert round(row2["da_erogare"], 2) == round(before - 30, 2), (before, row2)

            # PDF busta paga -> 2 pagine
            p = admin.get(f"{API}/compensi/erogati/{cid}/pdf", timeout=60)
            assert p.status_code == 200, p.text[:300]
            assert p.headers["content-type"].startswith("application/pdf")
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(p.content))
            assert len(reader.pages) == 2, f"expected 2 pages, got {len(reader.pages)}"
            t1 = reader.pages[0].extract_text() or ""
            t2 = reader.pages[1].extract_text() or ""
            assert "Drovetti" in t1, t1[:600]
            assert "30" in t1
            assert "riepilogo ricevute" in t2.lower(), t2[:600]
        finally:
            admin.delete(f"{API}/ricevute/{rid}", timeout=30)


# ---------- VERBALI ----------
class TestVerbali:
    def test_create_with_new_fields_and_pdf(self, admin):
        payload = {"tipo": "assemblea", "data": "2026-03-01",
                   "oggetto": "TEST_Assemblea iter11", "contenuto": "Contenuto di prova",
                   "presenti": ["Mario Rossi"], "assenti": ["Luca Bianchi"],
                   "partecipanti_remoti": ["Anna Verdi"], "delibere": "Approvato",
                   "sede": "Sede TEST Via Roma 1", "ora_inizio": "18:30",
                   "ora_chiusura": "20:45", "data_chiusura": "2026-03-01",
                   "firme_abilitate": True}
        r = admin.post(f"{API}/verbali", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:400]
        v = r.json()
        vid = v["id"]
        try:
            for k, val in payload.items():
                assert v.get(k) == val, (k, v.get(k), val)
            g = admin.get(f"{API}/verbali/{vid}", timeout=30).json()
            assert g["sede"] == payload["sede"]
            assert g["partecipanti_remoti"] == ["Anna Verdi"]

            from pypdf import PdfReader
            p = admin.get(f"{API}/verbali/{vid}/pdf", timeout=60)
            assert p.status_code == 200, p.text[:300]
            txt = "".join((pg.extract_text() or "") for pg in
                          PdfReader(io.BytesIO(p.content)).pages)
            for needle in ("Via Roma 1", "18:30", "20:45", "Anna Verdi"):
                assert needle in txt, f"{needle} missing from verbale PDF: {txt[:800]}"
            assert "Drovetti" in txt, txt[:800]

            # firme disabilitate -> nessun blocco firme
            u = admin.patch(f"{API}/verbali/{vid}",
                            json={"firme_abilitate": False}, timeout=30)
            assert u.status_code == 200, u.text[:300]
            assert u.json()["firme_abilitate"] is False, u.json()
            p2 = admin.get(f"{API}/verbali/{vid}/pdf", timeout=60)
            txt2 = "".join((pg.extract_text() or "") for pg in
                           PdfReader(io.BytesIO(p2.content)).pages)
            assert "Drovetti" not in txt2, txt2[-800:]
        finally:
            admin.delete(f"{API}/verbali/{vid}", timeout=30)


# ---------- REGRESSION ----------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/tesserati", "/abbonamenti", "/ricevute", "/movimenti", "/verbali",
        "/libro-soci", "/calendario", "/dashboard", "/tipi-pacchetto",
        "/abbonamenti-per-cliente", "/compensi/erogati", "/users",
    ])
    def test_get_ok(self, admin, path):
        r = admin.get(f"{API}{path}", timeout=45)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
        body = r.json()
        if isinstance(body, list):
            assert all("_id" not in x for x in body if isinstance(x, dict))

    def test_report_bilancio(self, admin):
        r = admin.get(f"{API}/report/bilancio?date_from=2026-01-01&date_to=2026-12-31",
                      timeout=45)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert "movimenti" in d and "totali" in d, list(d.keys())
        tot = d["totali"]
        assert {"entrate", "uscite", "saldo"} <= set(tot.keys()), tot
        assert round(tot["entrate"] - tot["uscite"], 2) == round(tot["saldo"], 2), tot
