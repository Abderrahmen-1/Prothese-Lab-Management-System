import os
import json
import secrets
import uuid
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, current_app)
from chargily_pay import ChargilyClient
from chargily_pay.settings import CHARGILIY_TEST_URL
from chargily_pay.entity import Checkout

from ManageMyLab.ConnectToSql import get_connection

load_dotenv()

payments = Blueprint("payments", __name__, url_prefix="/payments")


# =========================================================
# CONFIGURATION (fail fast if something is missing)
# =========================================================

def _require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


PUBLIC_BASE_URL = _require_env("PUBLIC_BASE_URL").rstrip("/")
CHARGILY_KEY = _require_env("CHARGILY_API_KEY")
CHARGILY_SECRET = _require_env("CHARGILY_API_SECRET")

CHARGILY_MODE = os.getenv("CHARGILY_MODE", "test").lower()

if CHARGILY_MODE == "live":
    if not PUBLIC_BASE_URL.startswith("https://"):
        raise RuntimeError("PUBLIC_BASE_URL must use https in live mode")
    CHARGILY_API_URL = os.getenv("CHARGILY_API_URL", "https://pay.chargily.net/api/v2/")
else:
    CHARGILY_API_URL = CHARGILIY_TEST_URL

chargily = ChargilyClient(CHARGILY_KEY, CHARGILY_SECRET, CHARGILY_API_URL)

DENTAFLOW_PRICE = int(os.getenv("DENTAFLOW_PRICE"))
CURRENCY = "dzd"


# =========================================================
# HELPERS
# =========================================================

def is_logged_in():
    return bool(session.get("id") and session.get("email_confirmed"))


def generate_csrf_token():
    token = secrets.token_hex(16)
    session["csrf_token"] = token
    return token


def verify_csrf():
    token = request.form.get("csrf_token")
    session_token = session.get("csrf_token")

    if not token or not session_token:
        return False

    return secrets.compare_digest(token, session_token)


def _get(obj, name, default=None):
    """Read a field from a dict or from an SDK object."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


# =========================================================
# PAYMENT PAGE
# =========================================================

@payments.route("/payment", methods=["GET"])
def payment():
    if not is_logged_in():
        return redirect(url_for("home"))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("""
            SELECT status, is_paid
            FROM users
            WHERE id = %s
            """, (session["id"],))
        user = cursor.fetchone()

        if not user:
            session.clear()
            return redirect(url_for("home"))

        status, is_paid = user[0], user[1]

        if status == "block":
            session.clear()
            return redirect(url_for("home"))

        if is_paid:
            session.pop("payment_required", None)
            return redirect(url_for("getHome"))

        token = generate_csrf_token()

        return render_template("payment.html", price=DENTAFLOW_PRICE, csrf_token=token)

    finally:
        cursor.close()
        conn.close()


# =========================================================
# CREATE CHARGILY PAYMENT
# =========================================================

@payments.route("/create_payment", methods=["POST"])
def create_payment():
    if not is_logged_in():
        return redirect(url_for("home"))

    if not verify_csrf():
        return "CSRF attack detected", 403

    generate_csrf_token()

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("""
            SELECT status, is_paid
            FROM users
            WHERE id = %s
            """, (session["id"],))
        user = cursor.fetchone()

        if not user:
            session.clear()
            return redirect(url_for("home"))

        status, is_paid = user[0], user[1]

        if status == "block":
            session.clear()
            return "Account blocked", 403

        if is_paid:
            session.pop("payment_required", None)
            return redirect(url_for("getHome"))

        # Unique placeholder: avoids collisions if chargily_id has a UNIQUE index.
        cursor.execute("""
            INSERT INTO payments(user_id, chargily_id, amount, currency, status)
            VALUES(%s, %s, %s, %s, 'pending')
            """, (session["id"], f"TEMP-{uuid.uuid4().hex[:16]}", DENTAFLOW_PRICE, CURRENCY))
        payment_id = cursor.lastrowid

        checkout = Checkout(
            success_url=f"{PUBLIC_BASE_URL}/payments/success",
            amount=DENTAFLOW_PRICE,
            currency=CURRENCY,
            failure_url=f"{PUBLIC_BASE_URL}/payments/failure",
            description="DentaFlow Permanent License",
            locale="en",
            webhook_endpoint=f"{PUBLIC_BASE_URL}/payments/chargily/webhook",
            metadata=[{"payment_id": str(payment_id)}]
        )

        response = chargily.create_checkout(checkout)

        chargily_id = _get(response, "id")
        checkout_url = _get(response, "checkout_url")

        if not chargily_id:
            raise ValueError("Chargily checkout ID missing")

        if not checkout_url:
            raise ValueError("Chargily checkout URL missing")

        parsed = urlparse(str(checkout_url))
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Unexpected checkout URL")

        cursor.execute("""
            UPDATE payments
            SET chargily_id = %s
            WHERE id = %s
            """, (chargily_id, payment_id))
        conn.commit()

        return redirect(checkout_url)

    except Exception:
        conn.rollback()
        current_app.logger.exception("create_payment failed")

        # Never show str(e) to the user: it can leak internals.
        return render_template(
            "payment_error.html",
            error="Le paiement n'a pas pu être initialisé. Veuillez réessayer plus tard."
        ), 500

    finally:
        cursor.close()
        conn.close()


# =========================================================
# RETURN PAGES
# =========================================================

@payments.route("/success")
def payment_success():
    if not is_logged_in():
        return redirect(url_for("home"))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("SELECT is_paid FROM users WHERE id = %s", (session["id"],))
        row = cursor.fetchone()
        paid = bool(row and row[0])

        # The webhook may not have arrived yet: `paid` tells the template which message to show.
        if paid:
            session.pop("payment_required", None)

        return render_template("payment_success.html", paid=paid)

    finally:
        cursor.close()
        conn.close()


@payments.route("/failure")
def payment_failure():
    if not is_logged_in():
        return redirect(url_for("home"))

    return render_template("payment_failure.html")


# =========================================================
# CHARGILY WEBHOOK
# =========================================================

@payments.route("/chargily/webhook", methods=["POST"])
def chargily_webhook():
    signature = request.headers.get("signature")

    if not signature:
        return "Missing signature", 400

    payload = request.get_data(as_text=True)

    try:
        valid = chargily.validate_signature(signature, payload)
    except Exception:
        return "Invalid signature", 403

    if not valid:
        return "Invalid signature", 403

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return "Invalid JSON", 400

    data = event.get("data") if isinstance(event, dict) else None
    if not isinstance(data, dict):
        return "Invalid event", 400

    checkout_id = data.get("id")
    if not checkout_id:
        return "Missing checkout ID", 400

    # Never trust the webhook body alone: ask Chargily for the real state.
    try:
        checkout = chargily.retrieve_checkout(checkout_id)
    except Exception:
        current_app.logger.exception("Unable to retrieve Chargily checkout")
        return "Unable to retrieve checkout", 500

    remote_status = _get(checkout, "status")
    remote_amount = _to_decimal(_get(checkout, "amount"))
    remote_currency = str(_get(checkout, "currency", "") or "").lower()
    metadata = _get(checkout, "metadata", []) or []

    payment_id = None
    if isinstance(metadata, list):
        for item in metadata:
            if isinstance(item, dict) and "payment_id" in item:
                payment_id = item["payment_id"]
                break
    elif isinstance(metadata, dict):
        payment_id = metadata.get("payment_id")

    if not payment_id:
        return "Missing payment metadata", 400

    try:
        payment_id = int(payment_id)
    except (TypeError, ValueError):
        return "Invalid payment ID", 400

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("""
            SELECT user_id, amount, currency, status, chargily_id
            FROM payments
            WHERE id = %s
            FOR UPDATE
            """, (payment_id,))
        row = cursor.fetchone()

        if not row:
            conn.rollback()
            return "Payment not found", 404

        user_id, amount, currency, local_status, local_chargily_id = row

        # The checkout must be the one we created for this payment.
        if str(local_chargily_id) != str(checkout_id):
            conn.rollback()
            current_app.logger.warning(
                "Webhook checkout mismatch for payment %s", payment_id)
            return "Checkout mismatch", 400

        if local_status == "paid":
            conn.commit()
            return "Already processed", 200

        if remote_status != "paid":
            conn.rollback()
            return "Webhook received", 200

        # Compare Chargily's data with what we stored when creating the payment.
        if remote_amount is None:
            current_app.logger.warning(
                "Chargily amount missing for payment %s: amount not verified", payment_id)
        elif remote_amount != _to_decimal(amount):
            conn.rollback()
            current_app.logger.error("Amount mismatch for payment %s", payment_id)
            return "Amount mismatch", 400

        if remote_currency and remote_currency != str(currency).lower():
            conn.rollback()
            current_app.logger.error("Currency mismatch for payment %s", payment_id)
            return "Currency mismatch", 400

        cursor.execute("""
            UPDATE payments
            SET
                status = 'paid',
                paid_at = NOW()
            WHERE id = %s
            """, (payment_id,))

        # A blocked account stays blocked: paying must not lift an admin block.
        cursor.execute("""
            UPDATE users
            SET
                is_paid = TRUE,
                paid_at = NOW(),
                status = CASE WHEN status = 'block' THEN status ELSE 'active' END
            WHERE id = %s
            """, (user_id,))

        conn.commit()

        return "OK", 200

    except Exception:
        conn.rollback()
        current_app.logger.exception("Webhook An internal error occurred")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()