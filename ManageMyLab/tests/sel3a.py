"""
Tests for the `products` Flask blueprint (ManageMyLab.routes.sel3a),
covering the "Sel3a" stock/inventory feature.

Run with:
    pytest test_sel3a.py -v

Same mocking approach as the other test files in this set. This one
surfaces four real bugs found while writing it -- see TestKnownBugs.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from ManageMyLab.routes.sel3a import products as products_bp
import ManageMyLab.routes.sel3a as sel3a_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["TESTING"] = True
    app.register_blueprint(products_bp)

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
    monkeypatch.setattr(sel3a_module, "render_template", fake_render_template)


@pytest.fixture
def mock_db(monkeypatch):
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(sel3a_module, "get_connection", lambda: conn)
    return conn, cursor


@pytest.fixture
def logged_in_session(client):
    with client.session_transaction() as sess:
        sess["id"] = 1
        sess["username"] = "abderrahmen"
    return client


def get_csrf_token(client, path="/products/AddSel3a"):
    client.get(path)
    with client.session_transaction() as sess:
        return sess["csrf_token"]


# ---------------------------------------------------------------------------
# KNOWN BUGS
# ---------------------------------------------------------------------------

class TestKnownBugs:
    def test_bug1_sel3a_stat_redirect_is_broken(self, logged_in_session):
        """BUG: `Sel3aStat` does `redirect(url_for('Sel3aPage'))`. But
        `Sel3aPage` is registered on the `products` blueprint
        (url_prefix="/products"), so its real endpoint name is
        `products.Sel3aPage`, not bare `Sel3aPage`. `url_for('Sel3aPage')`
        will raise `werkzeug.routing.BuildError` because no endpoint by
        that exact name exists at the top level.

        If this test fails with BuildError, fix all four occurrences in
        sel3a.py: `url_for('Sel3aPage')` -> `url_for('products.Sel3aPage')`.
        This route is currently broken for every real user who visits it.
        """
        resp = logged_in_session.get("/products/Sel3aStat")
        assert resp.status_code == 302

    def test_bug1b_show_by_price_redirect_is_broken(self, logged_in_session):
        """Same bug as above, second occurrence."""
        resp = logged_in_session.get("/products/ShowByPrice")
        assert resp.status_code == 302

    def test_bug1c_show_by_date_redirect_is_broken(self, logged_in_session):
        """Same bug as above, third occurrence."""
        resp = logged_in_session.get("/products/ShowByDateASC")
        assert resp.status_code == 302

    def test_bug1d_add_sel3a_success_redirect_is_broken(self, logged_in_session, mock_db):
        """Same bug, fourth occurrence: the SUCCESS path of AddSel3a also
        does `redirect(url_for('Sel3aPage'))`. So right now, successfully
        adding a product crashes with BuildError instead of taking the
        user back to the stock page -- this is the highest-impact copy of
        the bug since it's hit on every successful add."""
        token = get_csrf_token(logged_in_session)
        payload = {
            "SName": "Résine", "SPrice": "100", "SQuantity": "2", "SUnit": "kg",
            "SDate": "2026-01-01", "SKhalsa": "yes", "Versement": "",
            "csrf_token": token,
        }
        resp = logged_in_session.post("/products/AddSel3a", data=payload)
        assert resp.status_code == 302

    def test_bug2_delete_sel3a_leaks_raw_exception(self, logged_in_session, mock_db):
        """BUG (info leak): unlike every other route in this project
        (which catch the exception and return a generic "database error"
        message), DeleteSel3a does:
            return {"success": False, "error": str(e)}, 500
        -- putting the raw exception text directly in the JSON response.
        This is the exact leak pattern we fixed everywhere else; it was
        missed here."""
        conn, cursor = mock_db
        cursor.execute.side_effect = Exception("Table 'sel3a' doesn't exist, schema: labdb")
        resp = logged_in_session.post("/products/DeleteSel3a/5")
        body = resp.get_json()
        assert body["success"] is False
        # This assertion documents the CURRENT (buggy) leak:
        assert "labdb" in body["error"]
        # What it SHOULD look like once fixed (uncomment after fixing):
        # assert "labdb" not in json.dumps(body)

    def test_bug3_modify_versement_full_payment_never_commits(self, logged_in_session, mock_db):
        """BUG: in ModifySel3aVersement, the branch where the new
        versement exactly equals the price (`final == price`, i.e. fully
        paid) runs the UPDATE but never calls `conn.commit()` -- every
        other branch does. Since autocommit is off by default for a
        fresh MySQL connector cursor, this UPDATE is silently discarded
        when the connection closes. Marking an item "fully paid" never
        actually persists.

        This test proves the missing commit call; it does NOT prove data
        was lost (the cursor is mocked), but the assertion on
        conn.commit() is exactly what would tell you data was never
        saved for real.
        """
        conn, cursor = mock_db
        # sel3a_price=500, versement=0, b9aw=500, khalsa='no'
        cursor.fetchone.return_value = (500, 0, 500, "no")
        resp = logged_in_session.post(
            "/products/ModifySel3aVersement/7",
            json={"versement": 500},  # 0 + 500 == price -> "fully paid" branch
        )
        assert resp.status_code == 200
        # This is the bug: commit is never called on this branch.
        conn.commit.assert_not_called()

    def test_bug4_add_sel3a_crashes_on_missing_khalsa(self, logged_in_session, mock_db):
        """BUG: `khalsa = request.form.get("SKhalsa")` is used directly as
        `khalsa.lower()` with no None-check first, and this happens
        BEFORE any try/except in the route. If the form doesn't send
        SKhalsa at all, `.lower()` on None raises an unhandled
        AttributeError -- a raw 500, not a clean validation message.
        (Same class of risk as leaving debug=True on: an unhandled crash
        here would show a stack trace to the visitor if debug mode is
        ever on.)
        """
        token = get_csrf_token(logged_in_session)
        payload = {
            "SName": "Résine", "SPrice": "100", "SQuantity": "2", "SUnit": "kg",
            "SDate": "2026-01-01",
            # SKhalsa intentionally omitted
            "csrf_token": token,
        }
        # No assertion needed: if the bug is present, this line itself
        # raises AttributeError and pytest will show it directly.
        logged_in_session.post("/products/AddSel3a", data=payload)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_sel3a_page_redirects_when_not_logged_in(self, client):
        resp = client.get("/products/Sel3a")
        assert resp.status_code == 302

    def test_modify_quantity_401_when_not_logged_in(self, client):
        resp = client.post("/products/ModifySel3aQuantity/1", json={"used": 1})
        assert resp.status_code == 401

    def test_delete_401_when_not_logged_in(self, client):
        resp = client.post("/products/DeleteSel3a/1")
        assert resp.status_code == 401

    def test_paid_401_when_not_logged_in(self, client):
        resp = client.post("/products/Sel3aPaid/1")
        assert resp.status_code == 401

    def test_modify_versement_401_when_not_logged_in(self, client):
        resp = client.post("/products/ModifySel3aVersement/1", json={"versement": 10})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

class TestCSRF:
    def test_add_sel3a_rejects_missing_token(self, logged_in_session, mock_db):
        resp = logged_in_session.post("/products/AddSel3a", data={"SName": "Résine"})
        assert resp.status_code == 403

    def test_add_sel3a_rejects_wrong_token(self, logged_in_session, mock_db):
        get_csrf_token(logged_in_session)
        resp = logged_in_session.post(
            "/products/AddSel3a",
            data={"SName": "Résine", "csrf_token": "wrong"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Sel3aPage
# ---------------------------------------------------------------------------

class TestSel3aPage:
    def test_renders_with_data(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchall.return_value = []
        resp = logged_in_session.get("/products/Sel3a")
        assert resp.status_code == 200
        conn.commit.assert_called()  # the DELETE-old-rows cleanup commits


# ---------------------------------------------------------------------------
# AddSel3a validations
# ---------------------------------------------------------------------------

class TestAddSel3a:
    def _payload(self, **overrides):
        payload = {
            "SName": "Résine", "SPrice": "100", "SQuantity": "2", "SUnit": "kg",
            "SDate": "2026-01-01", "SKhalsa": "yes", "Versement": "",
        }
        payload.update(overrides)
        return payload

    def test_rejects_empty_name(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session)
        payload = self._payload(SName="", csrf_token=token)
        resp = logged_in_session.post("/products/AddSel3a", data=payload)
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_non_numeric_price(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session)
        payload = self._payload(SPrice="abc", csrf_token=token)
        resp = logged_in_session.post("/products/AddSel3a", data=payload)
        assert "prix invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_zero_price(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session)
        payload = self._payload(SPrice="0", csrf_token=token)
        resp = logged_in_session.post("/products/AddSel3a", data=payload)
        assert "invalide" in resp.get_data(as_text=True).lower()

    def test_rejects_missing_unit(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session)
        payload = self._payload(SUnit="", csrf_token=token)
        resp = logged_in_session.post("/products/AddSel3a", data=payload)
        assert "obligatoires" in resp.get_data(as_text=True)

    def test_rejects_invalid_khalsa_value(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session)
        payload = self._payload(SKhalsa="maybe", csrf_token=token)
        resp = logged_in_session.post("/products/AddSel3a", data=payload)
        assert "yes" in resp.get_data(as_text=True).lower()

    def test_rejects_versement_greater_than_price(self, logged_in_session, mock_db):
        token = get_csrf_token(logged_in_session)
        payload = self._payload(SKhalsa="no", Versement="999999", csrf_token=token)
        resp = logged_in_session.post("/products/AddSel3a", data=payload)
        assert "versement invalide" in resp.get_data(as_text=True).lower()

    def test_db_error_returns_generic_message(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.execute.side_effect = Exception("Unknown column 'xyz'")
        token = get_csrf_token(logged_in_session)
        payload = self._payload(csrf_token=token)
        resp = logged_in_session.post("/products/AddSel3a", data=payload)
        body = resp.get_data(as_text=True)
        assert "Unknown column" not in body
        assert "database error" in body.lower()


# ---------------------------------------------------------------------------
# ModifySel3aQuantity
# ---------------------------------------------------------------------------

class TestModifySel3aQuantity:
    def test_rejects_non_numeric_used(self, logged_in_session):
        resp = logged_in_session.post("/products/ModifySel3aQuantity/1", json={"used": "abc"})
        assert resp.status_code == 400

    def test_rejects_insufficient_stock(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (5,)  # current stock = 5
        resp = logged_in_session.post("/products/ModifySel3aQuantity/1", json={"used": 10})
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (10,)
        resp = logged_in_session.post("/products/ModifySel3aQuantity/1", json={"used": 3})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        conn.commit.assert_called_once()

    def test_item_not_found_for_user_crashes_generically(self, logged_in_session, mock_db):
        """There's no explicit `if not result:` check here either -- a
        sel3a_id that doesn't belong to this user (filtered out by the
        WHERE user_id = %s clause, so no IDOR risk) returns None from
        fetchone(), and `float(result[0])` then crashes with TypeError.
        Caught by the generic except, so the user just sees
        "Erreur database error" instead of a proper 404 "produit
        introuvable" message. Worth adding that explicit check for a
        cleaner UX, even though it's not a security issue."""
        conn, cursor = mock_db
        cursor.fetchone.return_value = None
        resp = logged_in_session.post("/products/ModifySel3aQuantity/999", json={"used": 1})
        assert resp.status_code == 500
        assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# DeleteSel3a
# ---------------------------------------------------------------------------

class TestDeleteSel3a:
    def test_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        resp = logged_in_session.post("/products/DeleteSel3a/1")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        conn.commit.assert_called_once()

    # See TestKnownBugs.test_bug2_delete_sel3a_leaks_raw_exception for the
    # raw str(e) leak in this route's except-block.


# ---------------------------------------------------------------------------
# Sel3aPaid
# ---------------------------------------------------------------------------

class TestSel3aPaid:
    def test_success(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1000,)
        resp = logged_in_session.post("/products/Sel3aPaid/1")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        conn.commit.assert_called_once()

    def test_db_error_returns_generic_message(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (1000,)
        cursor.execute.side_effect = [None, Exception("secret detail")]
        resp = logged_in_session.post("/products/Sel3aPaid/1")
        body = resp.get_json()
        assert body["success"] is False
        assert "secret detail" not in json.dumps(body)


# ---------------------------------------------------------------------------
# ModifySel3aVersement
# ---------------------------------------------------------------------------

class TestModifySel3aVersement:
    def test_rejects_non_numeric_versement(self, logged_in_session):
        resp = logged_in_session.post("/products/ModifySel3aVersement/1", json={"versement": "abc"})
        assert resp.status_code == 400

    def test_rejects_negative_versement(self, logged_in_session):
        resp = logged_in_session.post("/products/ModifySel3aVersement/1", json={"versement": -5})
        assert resp.status_code == 400

    def test_rejects_overpayment(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        # price=500, versement=0, b9aw=500, khalsa='no'
        cursor.fetchone.return_value = (500, 0, 500, "no")
        resp = logged_in_session.post("/products/ModifySel3aVersement/1", json={"versement": 9999})
        assert resp.status_code == 401  # NOTE: this branch returns 401, not 400 -- inconsistent but current behavior
        assert resp.get_json()["success"] is False

    def test_partial_payment_commits(self, logged_in_session, mock_db):
        conn, cursor = mock_db
        cursor.fetchone.return_value = (500, 0, 500, "no")
        resp = logged_in_session.post("/products/ModifySel3aVersement/1", json={"versement": 200})
        assert resp.status_code == 200
        conn.commit.assert_called_once()

    # See TestKnownBugs.test_bug3_modify_versement_full_payment_never_commits
    # for the missing commit() on the exact-payment branch.