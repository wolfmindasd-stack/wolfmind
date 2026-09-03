"""Iteration 4 edge-case probes (input validation / error handling)."""
import requests
from backend_test import API, mk_ricevuta, _db  # noqa: F401
from backend_test import admin, admin_creds, mk_tecnico, mk_tesserato, _reset_lockout  # noqa: F401


class TestCalendarioEdges:
    def test_invalid_date_format(self, admin):  # noqa: F811
        r = admin.post(f"{API}/calendario", json={"data": "01/03/2026", "ora": "18:00"}, timeout=30)
        print("invalid data ->", r.status_code, r.text[:200])
        assert r.status_code in (400, 422), f"expected 4xx, got {r.status_code}"

    def test_invalid_ricorrenza_fino_al(self, admin):  # noqa: F811
        r = admin.post(f"{API}/calendario", json={"data": "2026-07-01", "ora": "18:00",
                                                  "ricorrenza_settimanale": True,
                                                  "ricorrenza_fino_al": "nope"}, timeout=30)
        print("invalid ricorrenza_fino_al ->", r.status_code, r.text[:200])
        if r.status_code == 200:
            for s in r.json().get("slots", []):
                admin.delete(f"{API}/calendario/{s['id']}", timeout=30)
        assert r.status_code in (400, 422), f"expected 4xx, got {r.status_code}"

    def test_negative_capacita(self, admin):  # noqa: F811
        r = admin.post(f"{API}/calendario", json={"data": "2026-07-08", "ora": "18:00",
                                                  "capacita": -3}, timeout=30)
        print("negative capacita ->", r.status_code, r.text[:200])
        if r.status_code == 200:
            for s in r.json().get("slots", []):
                admin.delete(f"{API}/calendario/{s['id']}", timeout=30)
        assert r.status_code in (400, 422), f"expected 4xx, got {r.status_code}"

    def test_cancel_nonexistent_prenotazione(self, admin, mk_tesserato):  # noqa: F811
        t = mk_tesserato()
        sid = admin.post(f"{API}/calendario", json={"data": "2026-07-15", "ora": "18:00"},
                         timeout=30).json()["slots"][0]["id"]
        try:
            r = admin.delete(f"{API}/calendario/prenota/{sid}/{t['id']}", timeout=60)
            print("cancel non-booked ->", r.status_code, r.text[:200])
            assert r.status_code == 404, f"expected 404, got {r.status_code}"
        finally:
            admin.delete(f"{API}/calendario/{sid}", timeout=30)

    def test_tecnico_can_reassign_own_slot_to_other(self, admin, mk_tecnico):  # noqa: F811
        s1, _ = mk_tecnico()
        _, u2 = mk_tecnico()
        sid = s1.post(f"{API}/calendario", json={"data": "2026-07-22", "ora": "18:00"},
                      timeout=30).json()["slots"][0]["id"]
        try:
            r = s1.patch(f"{API}/calendario/{sid}", json={"tecnico_id": u2["id"]}, timeout=30)
            print("tecnico reassign via PATCH ->", r.status_code, r.text[:200])
            assert r.status_code == 403, f"expected 403, got {r.status_code}"
        finally:
            admin.delete(f"{API}/calendario/{sid}", timeout=30)


class TestCompensiEdges:
    def test_negative_importo(self, admin, mk_tecnico):  # noqa: F811
        _, u = mk_tecnico()
        r = admin.post(f"{API}/compensi/eroga",
                       json={"tecnico_id": u["id"], "data": "2026-03-01", "importo": -50.0},
                       timeout=30)
        print("negative eroga importo ->", r.status_code, r.text[:200])
        if r.status_code == 200:
            mv = r.json()["movimento"]["id"]
            admin.delete(f"{API}/movimenti/{mv}", timeout=30)
            # NOTE: DELETE /movimenti does NOT remove the compensi_erogati record -> manual purge
            _db().compensi_erogati.delete_many({"movimento_id": mv})
        assert r.status_code in (400, 422), f"expected 4xx, got {r.status_code}"

    def test_eroga_to_admin_user(self, admin, admin_creds):  # noqa: F811
        me = admin.get(f"{API}/auth/me", timeout=30).json()
        r = admin.post(f"{API}/compensi/eroga",
                       json={"tecnico_id": me["id"], "data": "2026-03-01", "importo": 10.0},
                       timeout=30)
        print("eroga to admin (non-tecnico) ->", r.status_code, r.text[:200])
        if r.status_code == 200:
            mvid = r.json()['movimento']['id']
            admin.delete(f"{API}/movimenti/{mvid}", timeout=30)
            _db().compensi_erogati.delete_many({"movimento_id": mvid})
        assert r.status_code in (400, 422), f"expected 4xx, got {r.status_code}"


class TestPublicPdfEdges:
    def test_public_endpoint_no_auth_leak(self, admin, mk_tesserato):  # noqa: F811
        """Public token must not expose any JSON PII endpoint."""
        t = mk_tesserato()
        d = mk_ricevuta(admin, t["id"], data="2026-08-01").json()
        try:
            r = requests.get(f"{API}/public/ricevuta/{d['public_token']}", timeout=30)
            print("public json (no /pdf) ->", r.status_code)
            assert r.status_code in (404, 405), r.status_code
        finally:
            admin.delete(f"{API}/ricevute/{d['id']}", timeout=30)
