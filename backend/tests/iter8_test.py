"""Iteration 8: focused verification of the GET /api/portale/{token}/calendario
500 fix (await inside any() genexp) + per-tesserato gia_prenotato isolation.

Run: cd /app/backend && python -m pytest tests/iter8_test.py -q -n 0
"""
import requests

from tests.iter7_test import API  # noqa: F401  reuse base url
from tests.iter7_test import (  # noqa: F401  reuse fixtures
    admin,
    admin_creds,
    mk_slot,
    mk_tesserato,
)


class TestPortaleCalendarioFix:
    def test_calendario_200_and_flags_before_and_after_booking(self, mk_tesserato, mk_slot):  # noqa: F811
        t = mk_tesserato()
        tok = t["portale_token"]
        s1 = mk_slot(days_ahead=4, ora="19:15")
        s2 = mk_slot(days_ahead=7, ora="19:45")

        r = requests.get(f"{API}/portale/{tok}/calendario", timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        rows = {x["id"]: x for x in r.json()}
        assert s1["id"] in rows and s2["id"] in rows
        assert rows[s1["id"]]["gia_prenotato"] is False
        assert rows[s2["id"]]["gia_prenotato"] is False
        assert rows[s1["id"]]["posti_liberi"] == 8

        pr = requests.post(f"{API}/portale/{tok}/prenota", json={"slot_id": s1["id"]}, timeout=60)
        assert pr.status_code == 200, pr.text[:300]

        r2 = requests.get(f"{API}/portale/{tok}/calendario", timeout=30)
        assert r2.status_code == 200, f"regression: calendario {r2.status_code} {r2.text[:300]}"
        rows2 = {x["id"]: x for x in r2.json()}
        assert rows2[s1["id"]]["gia_prenotato"] is True
        assert rows2[s1["id"]]["posti_liberi"] == 7
        assert rows2[s2["id"]]["gia_prenotato"] is False
        assert rows2[s2["id"]]["posti_liberi"] == 8

    def test_gia_prenotato_isolated_between_tesserati(self, mk_tesserato, mk_slot):  # noqa: F811
        a = mk_tesserato()
        b = mk_tesserato()
        slot = mk_slot(days_ahead=8, ora="20:30")
        assert requests.post(f"{API}/portale/{a['portale_token']}/prenota",
                             json={"slot_id": slot["id"]}, timeout=60).status_code == 200

        ra = requests.get(f"{API}/portale/{a['portale_token']}/calendario", timeout=30)
        rb = requests.get(f"{API}/portale/{b['portale_token']}/calendario", timeout=30)
        assert ra.status_code == 200 and rb.status_code == 200
        row_a = next(x for x in ra.json() if x["id"] == slot["id"])
        row_b = next(x for x in rb.json() if x["id"] == slot["id"])
        assert row_a["gia_prenotato"] is True
        assert row_b["gia_prenotato"] is False
        assert row_b["posti_liberi"] == 7
        # public payload must not leak other members' bookings
        assert "prenotazioni" not in row_b

    def test_calendario_after_cancel_flag_resets(self, mk_tesserato, mk_slot):  # noqa: F811
        t = mk_tesserato()
        tok = t["portale_token"]
        slot = mk_slot(days_ahead=10, ora="17:00")
        assert requests.post(f"{API}/portale/{tok}/prenota",
                             json={"slot_id": slot["id"]}, timeout=60).status_code == 200
        assert requests.delete(f"{API}/portale/{tok}/prenota/{slot['id']}",
                               timeout=60).status_code == 200
        r = requests.get(f"{API}/portale/{tok}/calendario", timeout=30)
        assert r.status_code == 200, r.text[:300]
        row = next(x for x in r.json() if x["id"] == slot["id"])
        assert row["gia_prenotato"] is False
        assert row["posti_liberi"] == 8

    def test_calendario_bad_token_404(self):  # noqa: F811
        r = requests.get(f"{API}/portale/nope-not-a-token/calendario", timeout=30)
        assert r.status_code == 404, f"{r.status_code} {r.text[:200]}"
