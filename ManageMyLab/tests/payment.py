import json
import pytest
from flask import Flask
from unittest.mock import MagicMock
import ManageMyLab.routes.payment as payments_module


# =========================================================
# FIXTURES
# =========================================================

@pytest.fixture
def app(monkeypatch):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    app.config["TESTING"] = True

    app.register_blueprint(payments_module.payments)

    # Routes needed by redirect(url_for(...))
    @app.route("/")
    def home():
        return "Home"

    @app.route("/home")
    def getHome():
        return "Dashboard"

    # Avoid depending on real HTML templates
    monkeypatch.setattr(
        payments_module,
        "render_template",
        lambda template, **kwargs: f"Rendered: {template}"
    )

    monkeypatch.setattr(
        payments_module,
        "PUBLIC_BASE_URL",
        "https://example.com"
    )

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_db(monkeypatch):
    conn = MagicMock()
    cursor = MagicMock()

    conn.cursor.return_value = cursor

    monkeypatch.setattr(
        payments_module,
        "get_connection",
        lambda: conn
    )

    return conn, cursor


@pytest.fixture
def logged_in_client(client):
    with client.session_transaction() as sess:
        sess["id"] = 1

    return client



def get_csrf_token(client):
    token = "test-csrf-token"

    with client.session_transaction() as sess:
        sess["csrf_token"] = token

    return token



def valid_webhook(client, checkout_id="checkout_123"):
    payload = json.dumps({
        "type": "checkout.paid",
        "data": {
            "id": checkout_id
        }
    })

    return client.post(
        "/payments/chargily/webhook",
        data=payload,
        content_type="application/json",
        headers={"signature": "valid_signature"}
    )


# =========================================================
# AUTHENTICATION
# =========================================================

class TestPaymentAuth:

    def test_payment_redirects_when_not_logged_in(self, client):
        response = client.get("/payments/payment")

        assert response.status_code == 302
        assert response.location.endswith("/")

    def test_create_payment_redirects_when_not_logged_in(self, client):
        response = client.post("/payments/create_payment")

        assert response.status_code == 302

    def test_success_redirects_when_not_logged_in(self, client):
        response = client.get("/payments/success")

        assert response.status_code == 302

    def test_failure_redirects_when_not_logged_in(self, client):
        response = client.get("/payments/failure")

        assert response.status_code == 302

    def test_webhook_does_not_require_login(self, client):
        response = client.post("/payments/chargily/webhook")

        assert response.status_code == 400
        assert b"Missing signature" in response.data


# =========================================================
# PAYMENT PAGE
# =========================================================

class TestPaymentPage:

    def test_get_payment_page(self, logged_in_client, mock_db):
        conn, cursor = mock_db

        cursor.fetchone.return_value = ("active", False)

        response = logged_in_client.get("/payments/payment")

        assert response.status_code == 200
        assert b"payment.html" in response.data

        cursor.execute.assert_called_once()
        cursor.close.assert_called_once()
        conn.close.assert_called_once()

        with logged_in_client.session_transaction() as sess:
            assert "csrf_token" in sess

    def test_redirects_when_user_not_found(self, logged_in_client, mock_db):
        conn, cursor = mock_db

        cursor.fetchone.return_value = None

        response = logged_in_client.get("/payments/payment")

        assert response.status_code == 302

        with logged_in_client.session_transaction() as sess:
            assert "id" not in sess

        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_redirects_when_account_blocked(self, logged_in_client, mock_db):
        conn, cursor = mock_db

        cursor.fetchone.return_value = ("block", False)

        response = logged_in_client.get("/payments/payment")

        assert response.status_code == 302

        with logged_in_client.session_transaction() as sess:
            assert "id" not in sess

    def test_redirects_when_already_paid(self, logged_in_client, mock_db):
        conn, cursor = mock_db

        cursor.fetchone.return_value = ("active", True)

        response = logged_in_client.get("/payments/payment")

        assert response.status_code == 302
        assert response.location.endswith("/home")


# =========================================================
# CSRF
# =========================================================

class TestPaymentCSRF:

    def test_create_payment_rejects_missing_token(self, logged_in_client):
        response = logged_in_client.post(
            "/payments/create_payment",
            data={}
        )

        assert response.status_code == 403
        assert b"CSRF" in response.data

    def test_create_payment_rejects_invalid_token(self, logged_in_client):
        with logged_in_client.session_transaction() as sess:
            sess["csrf_token"] = "correct_token"

        response = logged_in_client.post(
            "/payments/create_payment",
            data={"csrf_token": "wrong_token"}
        )

        assert response.status_code == 403


# =========================================================
# CREATE PAYMENT
# =========================================================

class TestCreatePayment:

    def test_successfully_creates_payment(
        self, logged_in_client, mock_db, monkeypatch
    ):
        conn, cursor = mock_db

        cursor.fetchone.return_value = ("active", False)
        cursor.lastrowid = 42

        payments_module.chargily.create_checkout.return_value = {
            "id": "checkout_123",
            "checkout_url": "https://chargily.example/checkout/123"
        }

        token = get_csrf_token(logged_in_client)

        # Patch Checkout so no real API object is created
        checkout_mock = MagicMock()
        monkeypatch.setattr(
            payments_module,
            "Checkout",
            lambda **kwargs: checkout_mock
        )

        response = logged_in_client.post(
            "/payments/create_payment",
            data={"csrf_token": token}
        )

        assert response.status_code == 302
        assert response.location == (
            "https://chargily.example/checkout/123"
        )

        assert cursor.execute.call_count == 3
        conn.commit.assert_called_once()

        cursor.close.assert_called_once()
        conn.close.assert_called_once()

        payments_module.chargily.create_checkout.assert_called_once()

    def test_rejects_blocked_account(
        self, logged_in_client, mock_db
    ):
        conn, cursor = mock_db

        cursor.fetchone.return_value = ("block", False)

        token = get_csrf_token(logged_in_client)

        response = logged_in_client.post(
            "/payments/create_payment",
            data={"csrf_token": token}
        )

        assert response.status_code == 403
        assert b"Account blocked" in response.data

        payments_module.chargily.create_checkout.assert_not_called()

    def test_redirects_if_already_paid(
        self, logged_in_client, mock_db
    ):
        conn, cursor = mock_db

        cursor.fetchone.return_value = ("active", True)

        token = get_csrf_token(logged_in_client)

        response = logged_in_client.post(
            "/payments/create_payment",
            data={"csrf_token": token}
        )

        assert response.status_code == 302
        assert response.location.endswith("/home")

        payments_module.chargily.create_checkout.assert_not_called()

    def test_handles_chargily_error(
        self, logged_in_client, mock_db
    ):
        conn, cursor = mock_db

        cursor.fetchone.return_value = ("active", False)

        payments_module.chargily.create_checkout.side_effect = Exception(
            "Chargily unavailable"
        )

        token = get_csrf_token(logged_in_client)

        response = logged_in_client.post(
            "/payments/create_payment",
            data={"csrf_token": token}
        )

        assert response.status_code == 500
        assert b"payment_error.html" in response.data

        conn.rollback.assert_called_once()
        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_handles_database_error(
        self, logged_in_client, mock_db
    ):
        conn, cursor = mock_db

        cursor.execute.side_effect = Exception("Database error")

        token = get_csrf_token(logged_in_client)

        response = logged_in_client.post(
            "/payments/create_payment",
            data={"csrf_token": token}
        )

        assert response.status_code == 500
        assert b"payment_error.html" in response.data

        conn.rollback.assert_called_once()
        cursor.close.assert_called_once()
        conn.close.assert_called_once()


# =========================================================
# WEBHOOK VALIDATION
# =========================================================

class TestWebhookValidation:

    def test_rejects_missing_signature(self, client):
        response = client.post(
            "/payments/chargily/webhook",
            data="{}"
        )

        assert response.status_code == 400
        assert b"Missing signature" in response.data

    def test_rejects_invalid_signature(self, client, monkeypatch):
        monkeypatch.setattr(
            payments_module.chargily,
            "validate_signature",
            lambda signature, payload: False
        )

        response = client.post(
            "/payments/chargily/webhook",
            data="{}",
            headers={"signature": "invalid"}
        )

        assert response.status_code == 403
        assert b"Invalid signature" in response.data

    def test_handles_signature_validation_exception(
        self, client, monkeypatch
    ):
        def raise_error(*args):
            raise Exception("Signature error")

        monkeypatch.setattr(
            payments_module.chargily,
            "validate_signature",
            raise_error
        )

        response = client.post(
            "/payments/chargily/webhook",
            data="{}",
            headers={"signature": "invalid"}
        )

        assert response.status_code == 403

    def test_rejects_invalid_json(self, client, monkeypatch):
        monkeypatch.setattr(
            payments_module.chargily,
            "validate_signature",
            lambda signature, payload: True
        )

        response = client.post(
            "/payments/chargily/webhook",
            data="invalid json",
            headers={"signature": "valid"}
        )

        assert response.status_code == 400
        assert b"Invalid JSON" in response.data

    def test_rejects_missing_checkout_id(self, client, monkeypatch):
        monkeypatch.setattr(
            payments_module.chargily,
            "validate_signature",
            lambda signature, payload: True
        )

        response = client.post(
            "/payments/chargily/webhook",
            json={"data": {}},
            headers={"signature": "valid"}
        )

        assert response.status_code == 400
        assert b"Missing checkout ID" in response.data

    def test_handles_invalid_event_data(self, client, monkeypatch):
        monkeypatch.setattr(
            payments_module.chargily,
            "validate_signature",
            lambda signature, payload: True
        )

        response = client.post(
            "/payments/chargily/webhook",
            json={"data": "invalid"},
            headers={"signature": "valid"}
        )

        assert response.status_code == 400
        assert b"Invalid event" in response.data

    def test_handles_chargily_retrieval_error(
        self, client, monkeypatch
    ):
        monkeypatch.setattr(
            payments_module.chargily,
            "validate_signature",
            lambda signature, payload: True
        )

        payments_module.chargily.retrieve_checkout.side_effect = Exception(
            "Chargily API error"
        )

        response = valid_webhook(client)

        assert response.status_code == 500
        assert b"Unable to retrieve checkout" in response.data


# =========================================================
# WEBHOOK PAYMENT PROCESSING
# =========================================================

class TestWebhookProcessing:

    def test_unpaid_checkout_does_not_update_database(
            self, client, monkeypatch
    ):
        payments_module.chargily.retrieve_checkout.return_value = {
            "status": "pending",
            "metadata": []
        }

        def database_should_not_be_called():
            raise AssertionError("Database should not be accessed")

        monkeypatch.setattr(
            payments_module,
            "get_connection",
            database_should_not_be_called
        )

        response = valid_webhook(client)

        assert response.status_code == 200
        assert b"Webhook received" in response.data

    def test_successfully_processes_paid_checkout(
        self, client, mock_db
    ):
        conn, cursor = mock_db

        payments_module.chargily.retrieve_checkout.return_value = {
            "status": "paid",
            "metadata": [
                {"payment_id": "42"}
            ]
        }

        cursor.fetchone.return_value = (
            1,
            payments_module.DENTAFLOW_PRICE,
            "dzd",
            "pending"
        )

        response = valid_webhook(client)

        assert response.status_code == 200
        assert response.data == b"OK"

        assert cursor.execute.call_count == 3
        conn.commit.assert_called_once()

        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_already_processed_payment(
        self, client, mock_db
    ):
        conn, cursor = mock_db

        payments_module.chargily.retrieve_checkout.return_value = {
            "status": "paid",
            "metadata": [
                {"payment_id": "42"}
            ]
        }

        cursor.fetchone.return_value = (
            1,
            payments_module.DENTAFLOW_PRICE,
            "dzd",
            "paid"
        )

        response = valid_webhook(client)

        assert response.status_code == 200
        assert b"Already processed" in response.data

        conn.commit.assert_called_once()
        cursor.execute.assert_called_once()

    def test_payment_not_found(self, client, mock_db):
        conn, cursor = mock_db

        payments_module.chargily.retrieve_checkout.return_value = {
            "status": "paid",
            "metadata": [
                {"payment_id": "42"}
            ]
        }

        cursor.fetchone.return_value = None

        response = valid_webhook(client)

        assert response.status_code == 404
        assert b"Payment not found" in response.data

        conn.rollback.assert_called_once()

    def test_rejects_amount_mismatch(self, client, mock_db):
        conn, cursor = mock_db

        payments_module.chargily.retrieve_checkout.return_value = {
            "status": "paid",
            "metadata": [
                {"payment_id": "42"}
            ]
        }

        cursor.fetchone.return_value = (
            1,
            100,
            "dzd",
            "pending"
        )

        response = valid_webhook(client)

        assert response.status_code == 400
        assert b"Amount mismatch" in response.data

        conn.rollback.assert_called_once()

    def test_rejects_currency_mismatch(self, client, mock_db):
        conn, cursor = mock_db

        payments_module.chargily.retrieve_checkout.return_value = {
            "status": "paid",
            "metadata": [
                {"payment_id": "42"}
            ]
        }

        cursor.fetchone.return_value = (
            1,
            payments_module.DENTAFLOW_PRICE,
            "eur",
            "pending"
        )

        response = valid_webhook(client)

        assert response.status_code == 400
        assert b"Currency mismatch" in response.data

        conn.rollback.assert_called_once()

    def test_rejects_missing_payment_metadata(self, client):
        payments_module.chargily.retrieve_checkout.return_value = {
            "status": "paid",
            "metadata": []
        }

        response = valid_webhook(client)

        assert response.status_code == 400
        assert b"Missing payment metadata" in response.data

    def test_rejects_invalid_payment_id(self, client):
        payments_module.chargily.retrieve_checkout.return_value = {
            "status": "paid",
            "metadata": [
                {"payment_id": "invalid"}
            ]
        }

        response = valid_webhook(client)

        assert response.status_code == 400
        assert b"Invalid payment ID" in response.data

    def test_handles_database_error(self, client, mock_db):
        conn, cursor = mock_db

        payments_module.chargily.retrieve_checkout.return_value = {
            "status": "paid",
            "metadata": [
                {"payment_id": "42"}
            ]
        }

        cursor.execute.side_effect = Exception("Database error")

        response = valid_webhook(client)

        assert response.status_code == 500
        assert b"Database error" in response.data

        conn.rollback.assert_called_once()
        cursor.close.assert_called_once()
        conn.close.assert_called_once()



@pytest.fixture(autouse=True)
def mock_chargily(monkeypatch):
    chargily_mock = MagicMock()

    chargily_mock.create_checkout.return_value = {
        "id": "checkout_123",
        "checkout_url": "https://chargily.example/checkout/123"
    }

    chargily_mock.validate_signature.return_value = True

    chargily_mock.retrieve_checkout.return_value = {
        "status": "paid",
        "metadata": [{"payment_id": "42"}]
    }

    monkeypatch.setattr(
        payments_module,
        "chargily",
        chargily_mock
    )

    return chargily_mock

