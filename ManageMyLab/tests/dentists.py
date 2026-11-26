"""
Tests for the `dentists` Flask blueprint (ManageMyLab.routes.dentists).

Run with:
    pytest test_dentists.py -v

Mocks get_connection() and render_template, same approach as
test_patients.py. Helper functions from
`from ManageMyLab.FunctionFile import *` (SearcheTable, AddDentistTable,
DentistsDics, GetAllDentistTables, Prothesist_History, ProthesistsStat,
Dentist_History, DentistStats, checkValue, ...) are patched per-test via
patch.object(dentists_module, "<name>", ...).

NOTE ON LIMITS OF THESE TESTS: the mocked cursor accepts any SQL string
you throw at it (it's a MagicMock, not a real MySQL connection), so a
syntax error in a raw SQL string --- e.g. a stray trailing comma before
WHERE --- will NOT be caught here. Mocked unit tests verify your Python
control flow (validation, status codes, error leakage), not your SQL
syntax. Catching SQL bugs needs either a real test DB or a human/code
review of the query strings. One such bug is already flagged below
(see TestDeleteDentistKhedma) so you don't forget it exists even though
pytest will not catch it for you.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from ManageMyLab.routes.dentists import dentists as dentists_bp
import ManageMyLab.routes.dentists as dentists_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["TESTING"] = True
    app.register_blueprint(dentists_bp)

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
    monkeypatch.setattr(dentists_module, "render_template", fake_render_template)


@pytest.fixture
def mock_db(monkeypatch):
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(dentists_module, "get_connection", lambda: conn)
    return conn, cursor


@pytest.fixture
def logged_in_session(client):
    with client.session_transaction() as sess:
        sess["id"] = 1
        sess["username"] = "abderrahmen"
    return client


def get_csrf_token(client, path="/dentists/Dentist"):
    client.get(path)
    with client.session_transaction() as sess:
        return sess["csrf_token"]


# ---------------------------------------------------------------------------
# Auth guard (spot checks across a few routes with different return shapes)
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_dentist_page_redirects_when_not_logged_in(self, client):
        resp = client.get("/dentists/Dentist")
        assert resp.status_code == 302

    def test_update_status_not_logged_in_returns_403(self, client):
        """NOTE: patients.py's equivalent endpoint returns 401 for the
        same case (not logged in) -- this one returns 403. Worth making
        consistent across both blueprints."""
        resp = client.post(
            "/dentists/UpdateDentistStatus",
            json={"patient_number": "1", "status": "finished", "dentist_name": "x"},
        )
        assert resp.status_code == 403

    def test_stat_by_period_not_logged_in_returns_401(self, client):
        resp = client.get("/dentists/DentistsStatByPeriod?month=1&year=2026")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CSRF protection -- already null-safe in this file, should 403 cleanly
# ---------------------------------------------------------------------------

class TestCSRF:
    def test_post_without_token_is_rejected_cleanly(self, logged_in_session, mock_db):
        """Regression test for the None/None crash found in patients.py:
        this file already guards with `not form_token or not session_token`,
        so this must return 403, never a 500."""
        resp = logged_in_session.post("/dentists/Dentist", data={"SearchBar": "Dupont"})
        assert resp.status_code == 403

    def test_post_with_wrong_token_is_rejected(self, logged_in_session, mock_db):
        get_csrf_token(logged_in_session)
        resp = logged_in_session.post(
            "/dentists/Dentist",
            data={"SearchBar": "Dupont", "csrf_token": "wrong-token"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DentistPage (search)
# ---------------------------------------------------------------------------

class TestDentistPage:
    def test_search_by_existing_name(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("row",)]
        token = get_csrf_token(logged_in_session)

        with patch.object(dentists_module, "SearcheTable", return_value=True):
            resp = logged_in_session.post(
                "/dentists/Dentist",
                data={"SearchBar": "Dupont", "csrf_token": token},
            )
        assert resp.status_code == 200

    def test_search_by_unknown_name_not_digit(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session)
        with patch.object(dentists_module, "SearcheTable", return_value=False):
            resp = logged_in_session.post(
                "/dentists/Dentist",
                data={"SearchBar": "Unknown", "csrf_token": token},
            )
        assert "introuvable" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# AddDentist
# ---------------------------------------------------------------------------

class TestAddDentist:
    def test_rejects_digit_name(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/dentists/AddDentist")
        resp = logged_in_session.post(
            "/dentists/AddDentist",
            data={"AddDentists": "12345", "csrf_token": token},
        )
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_existing_dentist(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/dentists/AddDentist")
        with patch.object(dentists_module, "SearcheTable", return_value=True):
            resp = logged_in_session.post(
                "/dentists/AddDentist",
                data={"AddDentists": "DrDupont", "csrf_token": token},
            )
        assert "existe déjà" in resp.get_data(as_text=True)

    def test_adds_new_dentist(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/dentists/AddDentist")
        with patch.object(dentists_module, "SearcheTable", return_value=False), \
             patch.object(dentists_module, "AddDentistTable") as mock_add:
            resp = logged_in_session.post(
                "/dentists/AddDentist",
                data={"AddDentists": "DrDupont", "csrf_token": token},
            )
        assert "ajouté avec succès" in resp.get_data(as_text=True)
        mock_add.assert_called_once()


# ---------------------------------------------------------------------------
# DeleteDentist
# ---------------------------------------------------------------------------

class TestDeleteDentist:
    def test_rejects_mismatched_confirmation(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/dentists/DeleteDentist")
        with patch.object(dentists_module, "SearcheTable", return_value=True):
            resp = logged_in_session.post(
                "/dentists/DeleteDentist",
                data={"DeleteDentist": "DrDupont", "ConfirmDeleteDentist": "DrSomeoneElse", "csrf_token": token},
            )
        assert "Confirmation invalide" in resp.get_data(as_text=True)

    def test_dentist_not_found(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/dentists/DeleteDentist")
        with patch.object(dentists_module, "SearcheTable", return_value=False):
            resp = logged_in_session.post(
                "/dentists/DeleteDentist",
                data={"DeleteDentist": "Ghost", "ConfirmDeleteDentist": "Ghost", "csrf_token": token},
            )
        assert "n'existe pas" in resp.get_data(as_text=True)

    def test_successful_delete(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        token = get_csrf_token(logged_in_session, "/dentists/DeleteDentist")
        with patch.object(dentists_module, "SearcheTable", return_value=True):
            resp = logged_in_session.post(
                "/dentists/DeleteDentist",
                data={"DeleteDentist": "DrDupont", "ConfirmDeleteDentist": "DrDupont", "csrf_token": token},
            )
        assert "supprimé avec succès" in resp.get_data(as_text=True)
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# GetFromDentist
# ---------------------------------------------------------------------------

class TestGetFromDentist:
    def _payload(self, **overrides):
        payload = {
            "Dentistinput": "DrDupont",
            "PatientFirstName": "Sara",
            "PatientLastName": "Ben",
            "PatientUnique": "123456789",  # 9 digits: see test below about the >= 10 check
            "KhedmaChoice": "couronne",
            "KhedmaPrice": "3000",
            "Khalsa": "yes",
            "date": "2026-01-01",
            "DeadLine": "2026-02-01",
            "OtherPro": "no",
        }
        payload.update(overrides)
        return payload

    def test_rejects_empty_dentist_name(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/dentists/GetFromDentist")
        payload = self._payload(Dentistinput="", csrf_token=token)
        resp = logged_in_session.post("/dentists/GetFromDentist", data=payload)
        assert "ne peut pas être vide" in resp.get_data(as_text=True)

    def test_rejects_ten_digit_unique_id(self, logged_in_session, mock_db):
        """BUG CHECK: the validation here is `len(unique) >= 10`, so a
        10-digit ID (the format used everywhere else in the app, e.g.
        patients.py requires exactly 10 digits) is rejected as invalid.
        This test documents the current (inconsistent) behavior; if you
        fix the `>= 10` to `!= 10`, flip this assertion."""
        token = get_csrf_token(logged_in_session, "/dentists/GetFromDentist")
        payload = self._payload(PatientUnique="1234567890", csrf_token=token)
        resp = logged_in_session.post("/dentists/GetFromDentist", data=payload)
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_unknown_dentist(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/dentists/GetFromDentist")
        payload = self._payload(csrf_token=token)
        with patch.object(dentists_module, "SearcheTable", return_value=False):
            resp = logged_in_session.post("/dentists/GetFromDentist", data=payload)
        assert "n'existe pas" in resp.get_data(as_text=True)

    def test_rejects_duplicate_unique_number(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1,)  # "SELECT id FROM dentists WHERE ... unique already used"
        token = get_csrf_token(logged_in_session, "/dentists/GetFromDentist")
        payload = self._payload(csrf_token=token)
        with patch.object(dentists_module, "SearcheTable", return_value=True), \
             patch.object(dentists_module, "checkValue", return_value=True):
            resp = logged_in_session.post("/dentists/GetFromDentist", data=payload)
        assert "existe déjà" in resp.get_data(as_text=True)

    def test_db_error_returns_generic_message(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        cursor.execute.side_effect = Exception("Table 'dentists' doesn't exist")
        token = get_csrf_token(logged_in_session, "/dentists/GetFromDentist")
        payload = self._payload(csrf_token=token)
        with patch.object(dentists_module, "SearcheTable", return_value=True), \
             patch.object(dentists_module, "checkValue", return_value=True):
            resp = logged_in_session.post("/dentists/GetFromDentist", data=payload)
        body = resp.get_data(as_text=True)
        assert "doesn't exist" not in body
        assert "An internal error occurred" in body.lower()


# ---------------------------------------------------------------------------
# ModifyDentistVersement (route: /DentistVersement)
# ---------------------------------------------------------------------------

class TestModifyDentistVersement:
    def test_rejects_empty_versement(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/dentists/DentistVersement")
        resp = logged_in_session.post(
            "/dentists/DentistVersement",
            data={"DName": "DrDupont", "KhedmaId": "1234567890", "Versement": "", "csrf_token": token},
        )
        assert "ne peut pas être vide" in resp.get_data(as_text=True)

    def test_rejects_non_numeric_versement(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/dentists/DentistVersement")
        resp = logged_in_session.post(
            "/dentists/DentistVersement",
            data={"DName": "DrDupont", "KhedmaId": "1234567890", "Versement": "abc", "csrf_token": token},
        )
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_task_not_found(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        token = get_csrf_token(logged_in_session, "/dentists/DentistVersement")
        resp = logged_in_session.post(
            "/dentists/DentistVersement",
            data={"DName": "DrDupont", "KhedmaId": "1234567890", "Versement": "500", "csrf_token": token},
        )
        assert "introuvable" in resp.get_data(as_text=True)

    def test_rejects_overpayment(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        # price=1000, khalsa='no', versement=0, b9aw=1000, month=1, year=2026
        cursor.fetchone.return_value = (1000, "no", 0, 1000, 1, 2026)
        token = get_csrf_token(logged_in_session, "/dentists/DentistVersement")
        resp = logged_in_session.post(
            "/dentists/DentistVersement",
            data={"DName": "DrDupont", "KhedmaId": "1234567890", "Versement": "5000", "csrf_token": token},
        )
        assert "Versement invalide" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# DeleteDentistKhedma (route: /DeleteDentistPatient)
# ---------------------------------------------------------------------------

class TestDeleteDentistKhedma:
    def _payload(self, **overrides):
        payload = {
            "DentistName": "DrDupont",
            "DeleteF": "Sara",
            "ConfirmDeletePatientF": "Sara",
            "DeleteL": "Ben",
            "ConfirmDeletePatientL": "Ben",
            "uniquepatient": "123456789",
            "confirmunique": "123456789",
        }
        payload.update(overrides)
        return payload

    def test_rejects_ten_digit_unique(self, logged_in_session, mock_db):
        """Same >= 10 quirk as GetFromDentist -- a 10-digit id is rejected here."""
        token = get_csrf_token(logged_in_session, "/dentists/DeleteDentistPatient")
        payload = self._payload(uniquepatient="1234567890", confirmunique="1234567890", csrf_token=token)
        resp = logged_in_session.post("/dentists/DeleteDentistPatient", data=payload)
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_mismatched_confirmation(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/dentists/DeleteDentistPatient")
        payload = self._payload(ConfirmDeletePatientF="NotSara", csrf_token=token)
        resp = logged_in_session.post("/dentists/DeleteDentistPatient", data=payload)
        assert "Confirmation invalide" in resp.get_data(as_text=True)

    def test_patient_not_found(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        token = get_csrf_token(logged_in_session, "/dentists/DeleteDentistPatient")
        payload = self._payload(csrf_token=token)
        resp = logged_in_session.post("/dentists/DeleteDentistPatient", data=payload)
        assert "introuvable" in resp.get_data(as_text=True)

    def test_khalsa_yes_path_does_not_crash_the_route(self, logged_in_session, mock_db):
        """This exercises the branch containing the known SQL bug
        (trailing comma before WHERE in the dentist_stat UPDATE, see the
        earlier code review). Because cursor.execute() is a mock here,
        it will NOT raise on bad SQL syntax -- so this only proves your
        Python code doesn't crash around it, it does NOT prove the SQL
        itself is valid. You still need to fix that comma, and ideally
        verify it against a real (or test) MySQL instance."""
        conn, cursor = mock_db
        cursor.fetchone.side_effect = [
            (1000, "yes", 1, 2026, 1000, 0),  # price, khalsa, month, year, versement, b9aw
            None,                              # no other_prothesists_khedma link
        ]
        token = get_csrf_token(logged_in_session, "/dentists/DeleteDentistPatient")
        payload = self._payload(csrf_token=token)
        resp = logged_in_session.post("/dentists/DeleteDentistPatient", data=payload)
        assert resp.status_code == 200
        assert "supprimé avec succès" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# DentistHistory
# ---------------------------------------------------------------------------

class TestDentistHistory:
    def test_get_with_results(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("row",)]
        resp = logged_in_session.get("/dentists/DentistHistory")
        assert resp.status_code == 200

    def test_post_search_by_patient_number(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("row",)]
        token = get_csrf_token(logged_in_session, "/dentists/DentistHistory")
        resp = logged_in_session.post(
            "/dentists/DentistHistory",
            data={"SearchName": "123456789", "csrf_token": token},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Read-only listing routes (spot checks)
# ---------------------------------------------------------------------------

class TestReadOnlyRoutes:
    def test_all_dentist_history(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/dentists/AllDentistHistory")
        assert resp.status_code == 200

    def test_main_table(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/dentists/DentistMainTable")
        assert resp.status_code == 200

    def test_most_khedma(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("row",)]
        with patch.object(dentists_module, "DentistsDics", return_value={"DrDupont": 5}):
            resp = logged_in_session.get("/dentists/DentistMostKhedma")
        assert resp.status_code == 200

    def test_less_khedma_all_zero(self, logged_in_session, mock_db):
        with patch.object(dentists_module, "DentistsDics", return_value={"DrDupont": 0}):
            resp = logged_in_session.get("/dentists/DentistLessKhedma")
        assert "0 service" in resp.get_data(as_text=True)

    def test_deadline_listing(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/dentists/DentistDeadLine")
        assert resp.status_code == 200

    def test_total(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (250.0,)
        with patch.object(dentists_module, "GetAllDentistTables", return_value=["DrDupont"]):
            resp = logged_in_session.get("/dentists/DentistTotal")
        assert resp.status_code == 200

    def test_stat(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.side_effect = [[], ["row"]]  # deleted-check query, then per-dentist stat rows
        with patch.object(dentists_module, "GetAllDentistTables", return_value=["DrDupont"]):
            resp = logged_in_session.get("/dentists/DentistsStat")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# DentistsStatByPeriod (JSON endpoint)
# ---------------------------------------------------------------------------

class TestDentistsStatByPeriod:
    def test_invalid_month_returns_400(self, logged_in_session):
        resp = logged_in_session.get("/dentists/DentistsStatByPeriod?month=13&year=2026")
        assert resp.status_code == 400

    def test_invalid_year_returns_400(self, logged_in_session):
        resp = logged_in_session.get("/dentists/DentistsStatByPeriod?month=1&year=1999")
        assert resp.status_code == 400

    def test_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("DrDupont", 3, 1500.0, 500.0)]
        resp = logged_in_session.get("/dentists/DentistsStatByPeriod?month=1&year=2026")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["dentists"][0]["name"] == "DrDupont"


# ---------------------------------------------------------------------------
# UpdateDentistStatus (JSON endpoint)
# ---------------------------------------------------------------------------

class TestUpdateDentistStatus:
    def test_missing_data_returns_403(self, logged_in_session):
        resp = logged_in_session.post("/dentists/UpdateDentistStatus", json={})
        assert resp.status_code == 403

    def test_invalid_status_returns_403(self, logged_in_session):
        resp = logged_in_session.post(
            "/dentists/UpdateDentistStatus",
            json={"patient_number": "1234567890", "status": "bogus", "dentist_name": "DrDupont"},
        )
        assert resp.status_code == 403

    def test_not_found_returns_400(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        resp = logged_in_session.post(
            "/dentists/UpdateDentistStatus",
            json={"patient_number": "1234567890", "status": "finished", "dentist_name": "DrDupont"},
        )
        assert resp.status_code == 400

    def test_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1,)
        resp = logged_in_session.post(
            "/dentists/UpdateDentistStatus",
            json={"patient_number": "1234567890", "status": "finished", "dentist_name": "DrDupont"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        conn.commit.assert_called_once()

    def test_db_exception_does_not_leak(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1,)
        cursor.execute.side_effect = Exception("secret schema detail")
        resp = logged_in_session.post(
            "/dentists/UpdateDentistStatus",
            json={"patient_number": "1234567890", "status": "finished", "dentist_name": "DrDupont"},
        )
        body = resp.get_json()
        assert body["success"] is False
        assert "secret schema detail" not in json.dumps(body)


# ---------------------------------------------------------------------------
# DentistFacture
# ---------------------------------------------------------------------------

class TestDentistFacture:
    def test_missing_params_returns_400(self, logged_in_session):
        resp = logged_in_session.get("/dentists/DentistFacture")
        assert resp.status_code == 400

    def test_invalid_month_returns_400(self, logged_in_session):
        resp = logged_in_session.get("/dentists/DentistFacture?dentist=DrDupont&month=13&year=2026")
        assert resp.status_code == 400

    def test_no_results_returns_404(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/dentists/DentistFacture?dentist=DrDupont&month=1&year=2026")
        assert resp.status_code == 404

    def test_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [
            ("DrDupont", "1234567890", "couronne", 1000.0, 0.0, "2026-01-05", "finished"),
        ]
        resp = logged_in_session.get("/dentists/DentistFacture?dentist=DrDupont&month=1&year=2026")
        assert resp.status_code == 200