"""
Tests for the `patients` Flask blueprint (ManageMyLab.routes.patients).

Run with:
    pip install pytest --break-system-packages   # if not already installed
    pytest test_patients.py -v

These tests mock the database layer (get_connection) and render_template,
so no real MySQL connection or real HTML templates are needed. The helper
functions imported via `from ManageMyLab.FunctionFile import *`
(checkValue, checkExistPatient, PatientStats, Patient_History,
ProthesistsStat, Prothesist_History, CheckData, ...) are patched
individually in the tests that reach them — adjust those patches if your
real implementations behave differently or raise custom exceptions.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from ManageMyLab.routes.patients import patients as patients_bp
import ManageMyLab.routes.patients as patients_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["TESTING"] = True
    app.register_blueprint(patients_bp)

    # Fake "home" endpoint used by redirect(url_for('home')) when not logged in
    @app.route("/")
    def home():
        return "home", 200

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def no_real_templates(monkeypatch):
    """Avoid needing the real Jinja templates: render_template just
    returns a plain string built from its arguments, so assertions can
    check for the expected message/error text inside it."""
    def fake_render_template(name, **kwargs):
        return f"TEMPLATE:{name}|{kwargs}"
    monkeypatch.setattr(patients_module, "render_template", fake_render_template)


@pytest.fixture
def mock_db(monkeypatch):
    """Patch get_connection() to return a MagicMock connection/cursor
    pair that each test can configure freely (fetchone, fetchall,
    execute.side_effect, ...)."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(patients_module, "get_connection", lambda: conn)
    return conn, cursor


@pytest.fixture
def logged_in_session(client):
    with client.session_transaction() as sess:
        sess["id"] = 1
        sess["username"] = "abderrahmen"
    return client


def get_csrf_token(client, path="/patients/Patient"):
    """Perform the GET that seeds session['csrf_token'] and return it,
    so POST tests can send a valid token."""
    client.get(path)
    with client.session_transaction() as sess:
        return sess["csrf_token"]


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_patient_page_redirects_when_not_logged_in(self, client):
        resp = client.get("/patients/Patient")
        assert resp.status_code == 302

    def test_update_status_401_when_not_logged_in(self, client):
        resp = client.post(
            "/patients/UpdatePatientStatus",
            json={"patient_number": "1", "status": "finished"},
        )
        assert resp.status_code == 401
        assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------

class TestCSRF:
    def test_post_without_token_is_rejected(self, logged_in_session, mock_db):
        resp = logged_in_session.post("/patients/Patient", data={"SearchBar": "123"})
        assert resp.status_code == 403

    def test_post_with_wrong_token_is_rejected(self, logged_in_session, mock_db):
        get_csrf_token(logged_in_session)  # seeds a valid token in session
        resp = logged_in_session.post(
            "/patients/Patient",
            data={"SearchBar": "123", "csrf_token": "not-the-real-token"},
        )
        assert resp.status_code == 403

    def test_post_with_valid_token_is_accepted(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        token = get_csrf_token(logged_in_session)
        resp = logged_in_session.post(
            "/patients/Patient",
            data={"SearchBar": "123", "csrf_token": token},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# AddPatient validation
# ---------------------------------------------------------------------------

class TestAddPatient:
    def _valid_payload(self, **overrides):
        payload = {
            "PatientFirstName": "Sara",
            "PatientLastName": "Ben",
            "PatientUnique": "1234567890",
            "KhedmaChoice": "couronne",
            "date": "2026-01-01",
            "DeadLine": "2026-02-01",
            "KhedmaPrice": "5000",
            "Khalsa": "yes",
            "versa": "no",
            "Versa": "",
            "OtherPro": "no",
        }
        payload.update(overrides)
        return payload

    def test_rejects_digit_first_name(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/patients/AddPatient")
        payload = self._valid_payload(PatientFirstName="12345", csrf_token=token)
        resp = logged_in_session.post("/patients/AddPatient", data=payload)
        assert "Nom invalide" in resp.get_data(as_text=True)

    def test_rejects_invalid_unique_id_length(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/patients/AddPatient")
        payload = self._valid_payload(PatientUnique="123", csrf_token=token)
        resp = logged_in_session.post("/patients/AddPatient", data=payload)
        assert "Numéro d'identification invalide" in resp.get_data(as_text=True)

    def test_rejects_deadline_before_date(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/patients/AddPatient")
        payload = self._valid_payload(date="2026-05-01", DeadLine="2026-01-01", csrf_token=token)
        resp = logged_in_session.post("/patients/AddPatient", data=payload)
        assert "Date limite invalide" in resp.get_data(as_text=True)

    def test_rejects_duplicate_patient_number(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1,)  # patient already exists for this user
        token = get_csrf_token(logged_in_session, "/patients/AddPatient")
        payload = self._valid_payload(csrf_token=token)
        resp = logged_in_session.post("/patients/AddPatient", data=payload)
        assert "existe déjà" in resp.get_data(as_text=True)

    def test_db_error_returns_generic_message_not_raw_exception(self, logged_in_session, mock_db):
        """Regression test: a DB failure must never leak str(e) to the client."""
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        cursor.execute.side_effect = Exception("Unknown column 'xyz' in field list")

        token = get_csrf_token(logged_in_session, "/patients/AddPatient")
        payload = self._valid_payload(csrf_token=token)

        with patch.object(patients_module, "checkValue", return_value=True), \
             patch.object(patients_module, "checkExistPatient", return_value=False):
            resp = logged_in_session.post("/patients/AddPatient", data=payload)

        body = resp.get_data(as_text=True)
        assert "Unknown column" not in body          # raw exception text must never reach the client
        assert "An internal error occurred" in body.lower()


# ---------------------------------------------------------------------------
# DeletePatient
# ---------------------------------------------------------------------------

class TestDeletePatient:
    def _payload(self, **overrides):
        payload = {
            "DeleteF": "Sara",
            "ConfirmDeletePatientF": "Sara",
            "DeleteL": "Ben",
            "ConfirmDeletePatientL": "Ben",
            "uniquepatient": "1234567890",
            "confirmunique": "1234567890",
        }
        payload.update(overrides)
        return payload

    def test_rejects_mismatched_confirmation(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/patients/DeletePatient")
        payload = self._payload(ConfirmDeletePatientF="NotSara", csrf_token=token)
        resp = logged_in_session.post("/patients/DeletePatient", data=payload)
        assert "Confirmation invalide" in resp.get_data(as_text=True)

    def test_rejects_invalid_unique_number(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/patients/DeletePatient")
        payload = self._payload(uniquepatient="abc", confirmunique="abc", csrf_token=token)
        resp = logged_in_session.post("/patients/DeletePatient", data=payload)
        assert "Numéro d'identification invalide" in resp.get_data(as_text=True)

    def test_patient_not_found(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.side_effect = [None, None]  # no prothesist link, no patient found
        token = get_csrf_token(logged_in_session, "/patients/DeletePatient")
        payload = self._payload(csrf_token=token)
        resp = logged_in_session.post("/patients/DeletePatient", data=payload)
        assert "n'existe pas" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# ModifyVersaPatient
# ---------------------------------------------------------------------------

class TestModifyVersaPatient:
    def test_rejects_versa_mismatch(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/patients/ModifyVersaPatient")
        payload = {
            "PatientId": "1234567890",
            "VersaValue": "100",
            "ConfirmVersaValue": "200",
            "csrf_token": token,
        }
        resp = logged_in_session.post("/patients/ModifyVersaPatient", data=payload)
        assert "même valeur" in resp.get_data(as_text=True)

    def test_rejects_non_numeric_versa(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/patients/ModifyVersaPatient")
        payload = {
            "PatientId": "1234567890",
            "VersaValue": "abc",
            "ConfirmVersaValue": "abc",
            "csrf_token": token,
        }
        resp = logged_in_session.post("/patients/ModifyVersaPatient", data=payload)
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_overpayment(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        # versa=0, b9aw=1000, khalsa='no', month=1, year=2026 -> total=1000
        cursor.fetchone.return_value = (0, 1000, "no", 1, 2026)
        token = get_csrf_token(logged_in_session, "/patients/ModifyVersaPatient")
        payload = {
            "PatientId": "1234567890",
            "VersaValue": "5000",
            "ConfirmVersaValue": "5000",
            "csrf_token": token,
        }
        resp = logged_in_session.post("/patients/ModifyVersaPatient", data=payload)
        assert "invalide" in resp.get_data(as_text=True).lower()


# ---------------------------------------------------------------------------
# UpdatePatientStatus (JSON endpoint)
# ---------------------------------------------------------------------------

class TestUpdatePatientStatus:
    def test_missing_fields_returns_403(self, logged_in_session):
        resp = logged_in_session.post(
            "/patients/UpdatePatientStatus",
            json={"something_else": "value"},  # non-empty dict, but no patient_number/status
        )
        assert resp.status_code == 403

    def test_invalid_status_value_returns_403(self, logged_in_session):
        resp = logged_in_session.post(
            "/patients/UpdatePatientStatus",
            json={"patient_number": "1234567890", "status": "not-a-real-status"},
        )
        assert resp.status_code == 403

    def test_patient_not_found_returns_403(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        resp = logged_in_session.post(
            "/patients/UpdatePatientStatus",
            json={"patient_number": "1234567890", "status": "finished"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["success"] is False

    def test_success_updates_status(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1,)
        resp = logged_in_session.post(
            "/patients/UpdatePatientStatus",
            json={"patient_number": "1234567890", "status": "finished"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        conn.commit.assert_called_once()

    def test_db_exception_returns_generic_message(self, logged_in_session, mock_db):
        """Regression test: same leak check as AddPatient, for the JSON endpoint."""
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1,)
        cursor.execute.side_effect = Exception("duplicate entry boom")

        resp = logged_in_session.post(
            "/patients/UpdatePatientStatus",
            json={"patient_number": "1234567890", "status": "finished"},
        )
        body = resp.get_json()
        assert body["success"] is False
        assert "duplicate entry boom" not in json.dumps(body)


# ---------------------------------------------------------------------------
# IDOR check: a user must never read/modify another user's patient
# ---------------------------------------------------------------------------

class TestCrossUserIsolation:
    def test_update_status_scoped_to_session_user_id(self, logged_in_session, mock_db):
        """The SELECT/UPDATE must always include user_id = session['id'].
        This asserts the query sent to MySQL actually carries that scoping,
        catching a future regression where the filter gets dropped."""
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1,)

        logged_in_session.post(
            "/patients/UpdatePatientStatus",
            json={"patient_number": "1234567890", "status": "finished"},
        )

        for call in cursor.execute.call_args_list:
            args = call.args
            if args and "patient" in args[0].lower():
                assert 1 in args[1], f"user_id missing from query params: {args}"