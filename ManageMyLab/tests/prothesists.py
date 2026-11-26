"""
Tests for the `prothesists` Flask blueprint (ManageMyLab.routes.prothesists).

Run with:
    pytest test_prothesists.py -v

Same mocking approach as test_patients.py / test_dentists.py: get_connection
and render_template are patched so no real MySQL or real templates are
needed. Helper functions from FunctionFile.py (SearcheTable,
ProthesistDics, GetAllProthesists, UpdateProKhalsaStat, Prothesist_History,
checkValue, ...) are patched per-test.

This file is not exhaustive (prothesists.py is the biggest of the four
blueprints reviewed) but it covers the main routes plus three real bugs
found while writing it -- see the "KNOWN BUGS" tests below. Those are
documented, not silently skipped, so you don't lose track of them.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from ManageMyLab.routes.prothesists import prothesists as prothesists_bp
import ManageMyLab.routes.prothesists as prothesists_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["TESTING"] = True
    app.register_blueprint(prothesists_bp)

    @app.route("/")
    def home():
        return "home", 200

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def no_real_templates(monkeypatch):
    def fake_render_template(name, **kwargs):
        return f"TEMPLATE:{name}|{kwargs}"
    monkeypatch.setattr(prothesists_module, "render_template", fake_render_template)


@pytest.fixture
def mock_db(monkeypatch):
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(prothesists_module, "get_connection", lambda: conn)
    return conn, cursor


@pytest.fixture
def logged_in_session(client):
    with client.session_transaction() as sess:
        sess["id"] = 1
        sess["username"] = "abderrahmen"
    return client


def get_csrf_token(client, path):
    client.get(path)
    with client.session_transaction() as sess:
        return sess["csrf_token"]


# ---------------------------------------------------------------------------
# KNOWN BUGS -- found while writing these tests, documented so they don't
# get lost. Mocked unit tests can prove the Python-level crash risk; they
# cannot prove SQL correctness (same limitation noted in test_dentists.py).
# ---------------------------------------------------------------------------

class TestKnownBugs:
    def test_bug1_datetime_strptime_relies_on_wildcard_import(self, logged_in_session, mock_db):
        """BUG: prothesists.py only does `from datetime import date` at
        the top -- it never imports `datetime` itself. But ProGetKhedma
        calls `datetime.strptime(date, "%Y-%m-%d")`. The only way this
        doesn't crash with `NameError: name 'datetime' is not defined`
        is if `datetime` happens to leak in via
        `from ManageMyLab.FunctionFile import *`. That's fragile and
        accidental, not a real fix.

        If this test fails with NameError, add an explicit
        `from datetime import datetime` (or `import datetime`) at the
        top of prothesists.py -- every real request with a valid date
        hits this exact line.
        """
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1,)  # prothesist exists check
        token = get_csrf_token(logged_in_session, "/prothesists/ProGetKhedma")
        payload = {
            "ProthesistName": "Pro1",
            "ProthesistNumber": "1234567890",
            "khedmaSource": "patient",
            "GetDate": "2026-01-01",
            "GetDeadLine": "2026-02-01",
            "CheckKhalsa": "yes",
            "PriceValue": "1000",
            "PatientSource": "1234567890",
            "csrf_token": token,
        }
        # No assertion needed: if `datetime` is undefined, this call
        # itself raises NameError and pytest reports it directly.
        logged_in_session.post("/prothesists/ProGetKhedma", data=payload)

    def test_bug2_khedma_pro_khalsa_dentist_branch_checks_wrong_variable(self, logged_in_session, mock_db):
        """BUG (copy-paste): in KhedmaProKhalsa's "dentist" branch,
        right after `data = cursor.fetchone()`, the code checks
        `if not result:` (the PREVIOUS query's result) instead of
        `if not data:`. If the service lookup (`data`) comes back empty
        -- which happens whenever the prothesist/dentist/patient
        combination doesn't have a matching other_prothesists_khedma row
        -- the code falls through and crashes on `data[0]` a few lines
        later (TypeError: 'NoneType' object is not subscriptable).

        This test simulates exactly that: `result` is truthy but `data`
        is None. The route's except-block catches the crash, so the
        user just sees a generic error instead of the real problem --
        but the "already paid" check this code is supposed to run is
        silently skipped. Fix: change `if not result:` to `if not data:`
        right after the second fetchone() in that branch.
        """
        conn, cursor = mock_db
        cursor.fetchone.side_effect = [
            (1,),             # call 1: SELECT 1 FROM other_prothesists (pro exists)
            (1,),             # call 2: SELECT 1 FROM dentist_history (reuses var name `result`)
            (10, 20, 2),      # call 3: SELECT d.id, k.id, pr.id FROM dentists JOIN ... (result, 3 cols)
            None,             # call 4: SELECT pPrice, pDate, pKhalsa, pB9aw ... (data) -> None = the bug trigger
        ]
        token = get_csrf_token(logged_in_session, "/prothesists/ProKhalsa")
        payload = {
            "ProthesistChoice": "Pro1",
            "ProthesistNumber": "1234567890",
            "Choice": "dentist",
            "Dentist": "DrDupont",
            "DPatientID": "123456789",
            "DServiceID": "5",
            "csrf_token": token,
        }
        with patch.object(prothesists_module, "SearcheTable", return_value=True):
            resp = logged_in_session.post("/prothesists/ProKhalsa", data=payload)
        body = resp.get_data(as_text=True)
        # Documents CURRENT (buggy) behavior: falls into the generic
        # error path instead of a clean "service introuvable" message.
        assert "An internal error occurred" in body.lower()

    def test_bug3_find_less_pro_khedma_missing_return(self, logged_in_session, mock_db):
        """BUG (minor, functional not security): `if not result:
        render_template(...)` is missing a `return`. The rendered
        template is thrown away and the function falls through to the
        real `return render_template("ALLProKhedma.html", less=result, ...)`
        below it anyway -- so the visible output ends up correct by
        accident, but the dead code should still be removed."""
        with patch.object(prothesists_module, "ProthesistDics", return_value={"Pro1": 3}):
            conn, cursor = mock_db
            cursor.fetchall.return_value = []  # triggers the dead `if not result:` branch
            resp = logged_in_session.get("/prothesists/ProLessKhedma")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_pro_khedma_page_redirects(self, client):
        resp = client.get("/prothesists/ProKhedma")
        assert resp.status_code == 302

    def test_stat_by_period_401_when_not_logged_in(self, client):
        resp = client.get("/prothesists/ProStatByPeriod?month=1&year=2026")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

class TestCSRF:
    def test_add_prothesist_rejects_missing_token(self, logged_in_session, mock_db):
        resp = logged_in_session.post("/prothesists/AddProthesist", data={"prothesistName": "Pro1"})
        assert resp.status_code == 403

    def test_delete_pro_khedma_old_style_csrf_rejects_missing_token(self, logged_in_session, mock_db):
        """DeleteProKhedma uses the older `token != check` pattern
        (no secrets.compare_digest) -- still safe from the None/None
        crash because it checks `not token` first, but worth
        standardizing to compare_digest like the rest of the file."""
        resp = logged_in_session.post("/prothesists/DeleteProthesistKhedma", data={"ProName": "Pro1"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# AddProthesist
# ---------------------------------------------------------------------------

class TestAddProthesist:
    def test_rejects_digit_name(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/prothesists/AddProthesist")
        resp = logged_in_session.post(
            "/prothesists/AddProthesist",
            data={"prothesistName": "12345", "prothesistNumber": "1234567890", "csrf_token": token},
        )
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_invalid_number_length(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/prothesists/AddProthesist")
        resp = logged_in_session.post(
            "/prothesists/AddProthesist",
            data={"prothesistName": "Pro1", "prothesistNumber": "123", "csrf_token": token},
        )
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_duplicate(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1,)
        token = get_csrf_token(logged_in_session, "/prothesists/AddProthesist")
        resp = logged_in_session.post(
            "/prothesists/AddProthesist",
            data={"prothesistName": "Pro1", "prothesistNumber": "1234567890", "csrf_token": token},
        )
        assert "existe déjà" in resp.get_data(as_text=True)

    def test_adds_new_prothesist(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        token = get_csrf_token(logged_in_session, "/prothesists/AddProthesist")
        resp = logged_in_session.post(
            "/prothesists/AddProthesist",
            data={"prothesistName": "Pro1", "prothesistNumber": "1234567890", "csrf_token": token},
        )
        assert "ajouté avec succès" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# ProthesistHistory
# ---------------------------------------------------------------------------

class TestProthesistHistory:
    def test_get_with_no_results(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/prothesists/ProthesistHistory")
        assert resp.status_code == 200

    def test_post_search_by_number(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("row",)]
        token = get_csrf_token(logged_in_session, "/prothesists/ProthesistHistory")
        resp = logged_in_session.post(
            "/prothesists/ProthesistHistory",
            data={"SearchName": "1234567890", "csrf_token": token},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# khedmaProMkemla (ProFinished)
# ---------------------------------------------------------------------------

class TestProFinished:
    def test_rejects_invalid_prothesist_number(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/prothesists/ProFinished")
        resp = logged_in_session.post(
            "/prothesists/ProFinished",
            data={"ProthesistName": "Pro1", "ProthesistNumber": "123", "Choice": "patient", "csrf_token": token},
        )
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_prothesist_not_found(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        token = get_csrf_token(logged_in_session, "/prothesists/ProFinished")
        resp = logged_in_session.post(
            "/prothesists/ProFinished",
            data={
                "ProthesistName": "Pro1", "ProthesistNumber": "1234567890",
                "Choice": "patient", "csrf_token": token,
            },
        )
        assert "introuvable" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# KhedmaProKhalsa (ProKhalsa)
# ---------------------------------------------------------------------------

class TestKhedmaProKhalsa:
    def test_rejects_invalid_pro_number(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/prothesists/ProKhalsa")
        resp = logged_in_session.post(
            "/prothesists/ProKhalsa",
            data={"ProthesistChoice": "Pro1", "ProthesistNumber": "abc", "Choice": "patient", "csrf_token": token},
        )
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_prothesist_not_found(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        token = get_csrf_token(logged_in_session, "/prothesists/ProKhalsa")
        resp = logged_in_session.post(
            "/prothesists/ProKhalsa",
            data={
                "ProthesistChoice": "Pro1", "ProthesistNumber": "1234567890",
                "Choice": "patient", "csrf_token": token,
            },
        )
        assert "introuvable" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# GetProthesistKhedma (ProGetKhedma) -- a few validation checks
# (the datetime.strptime path itself is covered in TestKnownBugs)
# ---------------------------------------------------------------------------

class TestGetProthesistKhedma:
    def test_rejects_invalid_pro_number(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/prothesists/ProGetKhedma")
        resp = logged_in_session.post(
            "/prothesists/ProGetKhedma",
            data={"ProthesistNumber": "123", "khedmaSource": "patient", "PriceValue": "100",
                  "CheckKhalsa": "yes", "GetDate": "2026-01-01", "GetDeadLine": "2026-02-01", "csrf_token": token},
        )
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_negative_price(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/prothesists/ProGetKhedma")
        resp = logged_in_session.post(
            "/prothesists/ProGetKhedma",
            data={"ProthesistNumber": "1234567890", "khedmaSource": "patient", "PriceValue": "-100",
                  "CheckKhalsa": "yes", "GetDate": "2026-01-01", "GetDeadLine": "2026-02-01", "csrf_token": token},
        )
        assert "négatif" in resp.get_data(as_text=True)

    def test_rejects_invalid_khalsa_value(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/prothesists/ProGetKhedma")
        resp = logged_in_session.post(
            "/prothesists/ProGetKhedma",
            data={"ProthesistNumber": "1234567890", "khedmaSource": "patient", "PriceValue": "100",
                  "CheckKhalsa": "maybe", "GetDate": "2026-01-01", "GetDeadLine": "2026-02-01", "csrf_token": token},
        )
        assert "Khalsa doit être" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# DeleteProKhedma
# ---------------------------------------------------------------------------

class TestDeleteProKhedma:
    def _payload(self, **overrides):
        payload = {
            "ProName": "Pro1", "CheckProName": "Pro1",
            "ProNumber": "1234567890", "CheckProNumber": "1234567890",
            "PatientNumber": "123456789", "CheckPatientNumber": "123456789",
        }
        payload.update(overrides)
        return payload

    def test_rejects_mismatched_confirmation(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/prothesists/DeleteProthesistKhedma")
        payload = self._payload(CheckProName="Different", csrf_token=token)
        resp = logged_in_session.post("/prothesists/DeleteProthesistKhedma", data=payload)
        assert "confirmation doit être identique" in resp.get_data(as_text=True).lower()

    def test_service_not_found(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        token = get_csrf_token(logged_in_session, "/prothesists/DeleteProthesistKhedma")
        payload = self._payload(csrf_token=token)
        resp = logged_in_session.post("/prothesists/DeleteProthesistKhedma", data=payload)
        assert "introuvable" in resp.get_data(as_text=True)

    def test_already_finished_service(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        # id, pVersa, pB9aw, month, year, pFinished='yes'
        cursor.fetchone.return_value = (1, 1000, 0, 1, 2026, "yes")
        cursor.fetchall.return_value = []
        token = get_csrf_token(logged_in_session, "/prothesists/DeleteProthesistKhedma")
        payload = self._payload(csrf_token=token)
        resp = logged_in_session.post("/prothesists/DeleteProthesistKhedma", data=payload)
        assert "déjà terminé" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# ProModifyVersement
# ---------------------------------------------------------------------------

class TestProModifyVersement:
    def test_rejects_invalid_pro_number(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/prothesists/ProModifyVersement")
        resp = logged_in_session.post(
            "/prothesists/ProModifyVersement",
            data={"ProthesistNumber": "123", "khedmaSource": "patient", "VersaValue": "100", "csrf_token": token},
        )
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_non_numeric_versa(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/prothesists/ProModifyVersement")
        resp = logged_in_session.post(
            "/prothesists/ProModifyVersement",
            data={"ProthesistNumber": "1234567890", "khedmaSource": "patient", "VersaValue": "abc", "csrf_token": token},
        )
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_prothesist_not_found(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        token = get_csrf_token(logged_in_session, "/prothesists/ProModifyVersement")
        resp = logged_in_session.post(
            "/prothesists/ProModifyVersement",
            data={
                "ProthesistNumber": "1234567890", "khedmaSource": "patient",
                "VersaValue": "100", "csrf_token": token,
            },
        )
        assert "introuvable" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Read-only routes (spot checks)
# ---------------------------------------------------------------------------

class TestReadOnlyRoutes:
    def test_pro_khedma_page(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/prothesists/ProKhedma")
        assert resp.status_code == 200

    def test_all_khedma(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/prothesists/ProAllkhedma")
        assert resp.status_code == 200

    def test_by_date_asc(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/prothesists/ProKhedmaByDateASC")
        assert resp.status_code == 200

    def test_by_date_desc(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/prothesists/ProKhedmaByDateDESC")
        assert resp.status_code == 200

    def test_most_khedma(self, logged_in_session, client):
        with client.session_transaction() as sess:
            sess["id"] = 1
            sess["csrf_token"] = "seed"
        with patch.object(prothesists_module, "ProthesistDics", return_value={"Pro1": 4}):
            conn = MagicMock()
            cursor = MagicMock()
            conn.cursor.return_value = cursor
            cursor.fetchall.return_value = []
            with patch.object(prothesists_module, "get_connection", lambda: conn):
                resp = client.get("/prothesists/ProMostKhedma")
        assert resp.status_code == 200

    def test_total(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = ("Pro1", "1234567890", 500.0, 0.0)
        with patch.object(prothesists_module, "GetAllProthesists", return_value=[("1234567890", "Pro1")]):
            resp = logged_in_session.get("/prothesists/ProTotal")
        assert resp.status_code == 200

    def test_pro_stat(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.side_effect = [[], []]
        with patch.object(prothesists_module, "GetAllProthesists", return_value=[]):
            resp = logged_in_session.get("/prothesists/ProStat")
        assert resp.status_code == 200

    def test_search_page_found(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1,)
        cursor.fetchall.return_value = [("row",)]
        token = get_csrf_token(logged_in_session, "/prothesists/ProSearch")
        resp = logged_in_session.post(
            "/prothesists/ProSearch",
            data={"SearchBar": "Pro1", "csrf_token": token},
        )
        assert resp.status_code == 200

    def test_search_page_not_found(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        token = get_csrf_token(logged_in_session, "/prothesists/ProSearch")
        resp = logged_in_session.post(
            "/prothesists/ProSearch",
            data={"SearchBar": "Ghost", "csrf_token": token},
        )
        assert "introuvable" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# ProStatByPeriod (JSON)
# ---------------------------------------------------------------------------

class TestProStatByPeriod:
    def test_invalid_month_returns_400(self, logged_in_session):
        resp = logged_in_session.get("/prothesists/ProStatByPeriod?month=13&year=2026")
        assert resp.status_code == 400

    def test_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("Pro1", "1234567890", 3, 2, 1, 1500.0, 500.0)]
        resp = logged_in_session.get("/prothesists/ProStatByPeriod?month=1&year=2026")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["prothesists"][0]["name"] == "Pro1"


# ---------------------------------------------------------------------------
# ProthesistFacture (redirects on bad input instead of 400/404)
# ---------------------------------------------------------------------------

class TestProthesistFacture:
    def test_missing_params_redirects_to_stat(self, logged_in_session, mock_db):
        resp = logged_in_session.get("/prothesists/ProthesistFacture")
        assert resp.status_code == 302
        assert "/prothesists/ProStat" in resp.headers["Location"]

    def test_invalid_month_redirects(self, logged_in_session, mock_db):
        resp = logged_in_session.get("/prothesists/ProthesistFacture?prothesist=Pro1&month=13&year=2026")
        assert resp.status_code == 302

    def test_no_results_redirects(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/prothesists/ProthesistFacture?prothesist=Pro1&month=1&year=2026")
        assert resp.status_code == 302

    def test_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("Pro1", "1234567890", "couronne", 1000.0, 0.0, "2026-01-05", "finished")]
        resp = logged_in_session.get("/prothesists/ProthesistFacture?prothesist=Pro1&month=1&year=2026")
        assert resp.status_code == 200