"""
Tests for the `services` Flask blueprint (ManageMyLab.routes.services),
covering the "OtherServices" feature.

Run with:
    pytest test_services.py -v

Same mocking approach as the other test files. Surfaces three real bugs,
see TestKnownBugs -- the first one is the most important: an entire
route has no exception handling at all, unlike every other route in the
project.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from ManageMyLab.routes.services import services as services_bp
import ManageMyLab.routes.services as services_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["TESTING"] = True
    app.register_blueprint(services_bp)

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
    monkeypatch.setattr(services_module, "render_template", fake_render_template)


@pytest.fixture
def mock_db(monkeypatch):
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(services_module, "get_connection", lambda: conn)
    return conn, cursor


@pytest.fixture
def logged_in_session(client):
    with client.session_transaction() as sess:
        sess["id"] = 1
        sess["username"] = "abderrahmen"
    return client


def get_csrf_token(client, path="/services/OtherServices"):
    client.get(path)
    with client.session_transaction() as sess:
        return sess["csrf_token"]


# ---------------------------------------------------------------------------
# KNOWN BUGS
# ---------------------------------------------------------------------------
class TestKnownBugs:
    def test_bug1_other_services_post_has_no_except_block(self, logged_in_session, mock_db):
        """BUG (most important in this file): the POST branch of
                `OtherServices` wraps its DB work in `try: ... finally: ...`
                with NO `except Exception` at all -- unlike every single other
                route in this project, which catches the exception and returns
                a generic "An internal error occurred" message. Any DB failure here (a
                dropped connection, a bad query, anything) propagates as a raw,
                unhandled 500 straight to the client. Worse: a missing
                `SearchBar` field crashes with AttributeError even before any
                DB call, for the same reason (see test_bug1b below).

                This test forces a DB-level exception and checks whether it's
                caught. If this test fails (the exception propagates out, or
                Flask turns it into a bare 500 with no JSON/HTML body you can
                assert on), that confirms the missing except block. Fix: wrap
                the try body with `except Exception as e: conn.rollback();
                return render_template("OtherServices.html", error="Erreur
                An internal error occurred", csrf_token=new_token)` like every other route.
                """
        conn, cursor = mock_db

        # First obtain the CSRF token normally
        token = get_csrf_token(logged_in_session)

        # Now simulate a database failure during POST
        cursor.execute.side_effect = Exception(
            "Table 'others_services' doesn't exist"
        )

        resp = logged_in_session.post(
            "/services/OtherServices",
            data={
                "SearchBar": "123",
                "csrf_token": token
            }
        )

        assert resp.status_code == 200
        assert "doesn't exist" not in resp.get_data(as_text=True)

    def test_bug1b_other_services_post_crashes_on_missing_searchbar(self, logged_in_session, mock_db):
        """Same root cause as bug1: `SearchBar.isdigit()` is called with
        no None-check, and since there's no except block, a missing
        `SearchBar` field crashes with an unhandled AttributeError.
        """
        token = get_csrf_token(logged_in_session)
        # No assertion needed: if the bug is present, this line itself
        # raises AttributeError and pytest shows it directly.
        logged_in_session.post("/services/OtherServices", data={"csrf_token": token})

    def test_bug2_add_service_crashes_on_non_numeric_price(self, logged_in_session, mock_db):
        """BUG: `price = float(request.form.get('ServicePrice', 0))` runs
        BEFORE any validation or try/except. A non-numeric ServicePrice
        (e.g. a typo, or a malicious request) raises an unhandled
        ValueError instead of a clean "Prix invalide" message."""
        token = get_csrf_token(logged_in_session, "/services/AddService")
        payload = {
            "ServiceName": "Nettoyage", "ServiceNumber": "1234567890",
            "ServiceFunction": "entretien", "ServiceDate": "2026-01-01",
            "ServiceKhalsa": "yes", "ServicePrice": "not-a-number",
            "csrf_token": token,
        }
        # No assertion needed: if the bug is present, this raises
        # ValueError directly instead of returning a rendered error page.
        logged_in_session.post("/services/AddService", data=payload)

    def test_bug3_add_service_datetime_relies_on_wildcard_import(self, logged_in_session, mock_db):
        """BUG: same pattern already found in prothesists.py --
        services.py never imports `datetime` (no `import datetime`, no
        `from datetime import datetime`), yet AddService calls
        `datetime.strptime(date, "%Y-%m-%d")`. This only works if
        `datetime` leaks in via `from ManageMyLab.FunctionFile import *`.
        If this test fails with NameError, add an explicit
        `from datetime import datetime` to services.py -- don't rely on
        the wildcard import.
        """
        conn, cursor = mock_db
        cursor.fetchone.return_value = None  # no existing stats row
        token = get_csrf_token(logged_in_session, "/services/AddService")
        payload = {
            "ServiceName": "Nettoyage", "ServiceNumber": "1234567890",
            "ServiceFunction": "entretien", "ServiceDate": "2026-01-01",
            "ServiceKhalsa": "yes", "ServicePrice": "500",
            "csrf_token": token,
        }
        # No assertion needed: if `datetime` is undefined, this call
        # itself raises NameError and pytest reports it directly.
        logged_in_session.post("/services/AddService", data=payload)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_other_services_redirects_when_not_logged_in(self, client):
        resp = client.get("/services/OtherServices")
        assert resp.status_code == 302

    def test_service_paid_401_when_not_logged_in(self, client):
        resp = client.post("/services/ServicePaid/1", json={"name": "x", "number": "1"})
        assert resp.status_code == 401

    def test_modify_versement_401_when_not_logged_in(self, client):
        resp = client.post("/services/ModifyServiceVersement/1", json={"name": "x", "number": "1", "newVersement": 10})
        assert resp.status_code == 401

    def test_delete_service_401_when_not_logged_in(self, client):
        resp = client.post("/services/DeleteService/1", json={"name": "x", "number": "1"})
        assert resp.status_code == 401

    def test_services_stat_redirects_when_not_logged_in(self, client):
        resp = client.get("/services/ServicesStats")
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

class TestCSRF:
    def test_other_services_rejects_missing_token(self, logged_in_session, mock_db):
        resp = logged_in_session.post("/services/OtherServices", data={"SearchBar": "123"})
        assert resp.status_code == 403

    def test_add_service_rejects_missing_token(self, logged_in_session, mock_db):
        resp = logged_in_session.post("/services/AddService", data={"ServiceName": "x"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# OtherServices GET + valid POST
# ---------------------------------------------------------------------------

class TestOtherServices:
    def test_get_renders(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/services/OtherServices")
        assert resp.status_code == 200
        conn.commit.assert_called()

    def test_post_search_by_number(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("row",)]
        token = get_csrf_token(logged_in_session)
        resp = logged_in_session.post(
            "/services/OtherServices",
            data={"SearchBar": "1234567890", "csrf_token": token},
        )
        assert resp.status_code == 200

    def test_post_search_not_found(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        token = get_csrf_token(logged_in_session)
        resp = logged_in_session.post(
            "/services/OtherServices",
            data={"SearchBar": "Ghost", "csrf_token": token},
        )
        assert "introuvable" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# OtherServicesTable
# ---------------------------------------------------------------------------

class TestOtherServicesTable:
    def test_renders_with_data(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("row",)]
        resp = logged_in_session.get("/services/OtherServicesTable")
        assert resp.status_code == 200

    def test_renders_empty(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/services/OtherServicesTable")
        assert "vide" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# AddService validations (see TestKnownBugs for the crash-before-validation bugs)
# ---------------------------------------------------------------------------

class TestAddService:
    def _payload(self, **overrides):
        payload = {
            "ServiceName": "Nettoyage", "ServiceNumber": "1234567890",
            "ServiceFunction": "entretien", "ServiceDate": "2026-01-01",
            "ServiceKhalsa": "yes", "ServicePrice": "500",
        }
        payload.update(overrides)
        return payload

    def test_rejects_empty_name(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/services/AddService")
        payload = self._payload(ServiceName="", csrf_token=token)
        resp = logged_in_session.post("/services/AddService", data=payload)
        assert "Nom invalide" in resp.get_data(as_text=True)

    def test_rejects_invalid_number_length(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/services/AddService")
        payload = self._payload(ServiceNumber="123", csrf_token=token)
        resp = logged_in_session.post("/services/AddService", data=payload)
        assert "Numéro invalide" in resp.get_data(as_text=True)

    def test_rejects_empty_function(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/services/AddService")
        payload = self._payload(ServiceFunction="", csrf_token=token)
        resp = logged_in_session.post("/services/AddService", data=payload)
        assert "Fonction invalide" in resp.get_data(as_text=True)

    def test_rejects_negative_price(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/services/AddService")
        payload = self._payload(ServicePrice="-50", csrf_token=token)
        resp = logged_in_session.post("/services/AddService", data=payload)
        assert "Prix invalide" in resp.get_data(as_text=True)

    def test_rejects_versa_overpayment(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session, "/services/AddService")
        payload = self._payload(
            ServiceKhalsa="no", ServiceVersa="yes", VersaService="9999", csrf_token=token,
        )
        resp = logged_in_session.post("/services/AddService", data=payload)
        assert "ne peut pas être supérieur" in resp.get_data(as_text=True)

    def test_success_fully_paid(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []
        token = get_csrf_token(logged_in_session, "/services/AddService")
        payload = self._payload(csrf_token=token)
        resp = logged_in_session.post("/services/AddService", data=payload)
        assert "ajouté avec succès" in resp.get_data(as_text=True)
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# ServicePaid
# ---------------------------------------------------------------------------

class TestServicePaid:
    def test_already_paid(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        # price, versement, b9aw, khalsa='yes', month, year
        cursor.fetchone.return_value = (500, 500, 0, "yes", 1, 2026)
        resp = logged_in_session.post(
            "/services/ServicePaid/1", json={"name": "Nettoyage", "number": "1234567890"},
        )
        assert resp.get_json()["success"] is False
        assert "déjà payé" in resp.get_json()["message"]

    def test_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (500, 0, 500, "no", 1, 2026)
        resp = logged_in_session.post(
            "/services/ServicePaid/1", json={"name": "Nettoyage", "number": "1234567890"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        conn.commit.assert_called_once()

    def test_service_not_found_for_user_crashes_generically(self, logged_in_session, mock_db):
        """No `if not result:` check here either -- a service_id that
        doesn't belong to this user (filtered out by WHERE user_id = %s,
        so no IDOR) returns None, and `result[3]` crashes with
        TypeError. Caught by the except block, so it surfaces as a
        generic 500 "An internal error occurred" instead of a clean "not found"."""
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        resp = logged_in_session.post(
            "/services/ServicePaid/999", json={"name": "x", "number": "1"},
        )
        assert resp.status_code == 500
        assert resp.get_json()["success"] is False

    def test_db_error_returns_generic_message(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (500, 0, 500, "no", 1, 2026)
        cursor.execute.side_effect = [None, Exception("secret schema detail")]
        resp = logged_in_session.post(
            "/services/ServicePaid/1", json={"name": "Nettoyage", "number": "1234567890"},
        )
        body = resp.get_json()
        assert body["success"] is False
        assert "secret schema detail" not in json.dumps(body)


# ---------------------------------------------------------------------------
# ModifyServiceVersement
# ---------------------------------------------------------------------------

class TestModifyServiceVersement:
    def test_already_paid(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (500, 500, 0, "yes", 1, 2026)
        resp = logged_in_session.post(
            "/services/ModifyServiceVersement/1",
            json={"name": "x", "number": "1", "newVersement": 50},
        )
        assert resp.status_code == 401
        assert resp.get_json()["success"] is False

    def test_overpayment_returns_401(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (500, 0, 500, "no", 1, 2026)
        resp = logged_in_session.post(
            "/services/ModifyServiceVersement/1",
            json={"name": "x", "number": "1", "newVersement": 9999},
        )
        assert resp.status_code == 401
        assert resp.get_json()["success"] is False

    def test_partial_payment_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (500, 0, 500, "no", 1, 2026)
        resp = logged_in_session.post(
            "/services/ModifyServiceVersement/1",
            json={"name": "Nettoyage", "number": "1234567890", "newVersement": 200},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        conn.commit.assert_called_once()

    def test_full_payment_success_and_commits(self, logged_in_session, mock_db):
        """Unlike the sel3a.py equivalent, this exact-payment branch
        DOES call conn.commit() correctly (it's outside the if/elif/else
        in this file) -- good, no regression here."""
        conn, cursor = mock_db
        cursor.fetchone.return_value = (500, 0, 500, "no", 1, 2026)
        resp = logged_in_session.post(
            "/services/ModifyServiceVersement/1",
            json={"name": "Nettoyage", "number": "1234567890", "newVersement": 500},
        )
        assert resp.status_code == 200
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# DeleteService
# ---------------------------------------------------------------------------

class TestDeleteService:
    def test_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (500, 0, 500, "no", 1, 2026)
        resp = logged_in_session.post(
            "/services/DeleteService/1", json={"name": "Nettoyage", "number": "1234567890"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        conn.commit.assert_called_once()

    def test_service_not_found_crashes_generically(self, logged_in_session, mock_db):
        """Same missing `if not result:` pattern as ServicePaid --
        documented rather than silently accepted."""
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        resp = logged_in_session.post(
            "/services/DeleteService/999", json={"name": "x", "number": "1"},
        )
        assert resp.status_code == 500
        assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# ServicesStat
# ---------------------------------------------------------------------------

class TestServicesStat:
    def test_renders_with_data(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = [("row",)]
        resp = logged_in_session.get("/services/ServicesStats")
        assert resp.status_code == 200
        conn.commit.assert_called()

    def test_renders_empty(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/services/ServicesStats")
        assert "vide" in resp.get_data(as_text=True)