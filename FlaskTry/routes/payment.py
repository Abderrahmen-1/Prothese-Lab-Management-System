from flask import (Blueprint, render_template, request, redirect, url_for, session)
import os
import json
import secrets
from dotenv import load_dotenv
from FlaskTry.FunctionFile import *
from chargily_pay import ChargilyClient
from chargily_pay.settings import CHARGILIY_TEST_URL
from chargily_pay.entity import Checkout

payments = Blueprint("payments", __name__, url_prefix="/payments")
load_dotenv()

CHARGILY_KEY = os.getenv("CHARGILY_API_KEY")
CHARGILY_SECRET = os.getenv("CHARGILY_API_SECRET")
chargily = ChargilyClient( CHARGILY_KEY, CHARGILY_SECRET, CHARGILIY_TEST_URL)

DENTAFLOW_PRICE = int(os.getenv("DENTAFLOW_PRICE", "70000"))

def is_logged_in():
    return "id" in session

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

        status = user[0]
        is_paid = user[1]

        if status == "block":
            session.clear()
            return redirect(url_for("home"))

        if is_paid:
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

        status = user[0]
        is_paid = user[1]

        if status == "block":
            return "Account blocked", 403

        if is_paid:
            return redirect(url_for("getHome"))

        cursor.execute("""
            INSERT INTO payments(user_id, chargily_id, amount, currency, status)
            VALUES(%s, %s, %s, %s, 'pending')
            """, (session["id"], "TEMP", DENTAFLOW_PRICE, "dzd"))
        payment_id = cursor.lastrowid

        webhook_url = url_for("payments.chargily_webhook", _external=True)
        success_url = url_for("payments.payment_success", _external=True)
        failure_url = url_for("payments.payment_failure", _external=True)

        checkout = Checkout(
            success_url=success_url,
            amount=DENTAFLOW_PRICE,
            currency="dzd",
            failure_url=failure_url,
            description=(
                "DentaFlow Permanent License"
            ),
            locale="en",
            webhook_endpoint=webhook_url,
            metadata=[
                {
                    "payment_id": str(payment_id)
                }
            ]
        )

        response = chargily.create_checkout(checkout)

        if isinstance(response, dict):
            chargily_id = response.get("id")
            checkout_url = response.get("checkout_url")

        else:
            chargily_id = getattr(response, "id", None)
            checkout_url = getattr(response, "checkout_url", None)

        if not chargily_id:
            raise Exception("Chargily checkout ID missing")

        if not checkout_url:
            raise Exception("Chargily checkout URL missing")


        cursor.execute("""
            UPDATE payments
            SET chargily_id = %s
            WHERE id = %s
            """, (chargily_id, payment_id))
        conn.commit()

        return redirect(checkout_url)

    except Exception as e:
        conn.rollback()

        print("================================")
        print("CHARGILY ERROR")
        print("TYPE:", type(e))
        print("ERROR:", e)

        if hasattr(e, "response") and e.response is not None:
            print("STATUS:", e.response.status_code)
            print("BODY:", e.response.text)

        print("================================")

        return render_template(
            "payment_error.html",
            error=str(e)
        ), 500

    finally:
        cursor.close()
        conn.close()


@payments.route("/success")
def payment_success():
    if not is_logged_in():
        return redirect(url_for("home"))

    return render_template("payment_success.html")

@payments.route("/failure")
def payment_failure():
    if not is_logged_in():
        return redirect(url_for("home"))

    return render_template("payment_failure.html")

@payments.route("/chargily/webhook", methods=["POST"])
def chargily_webhook():
    signature = request.headers.get("signature")

    if not signature:
        return "Missing signature", 400

    payload = request.get_data(as_text=True)

    try:
        valid = chargily.validate_signature(signature, payload)

    except Exception as e:
        print("Webhook signature error:", e)
        return "Invalid signature", 403

    if not valid:
        return "Invalid signature", 403

    try:
        event = json.loads(payload)

    except json.JSONDecodeError:
        return "Invalid JSON", 400
    print("Chargily webhook received:", event)

    data = event.get("data", {})
    if not isinstance(data, dict):
        return "Invalid event", 400

    checkout_id = data.get("id")

    if not checkout_id:
        return "Missing checkout ID", 400

    try:
        checkout = chargily.retrieve_checkout(checkout_id)

    except Exception as e:
        print("Could not retrieve checkout:", e)
        return ("Unable to retrieve checkout",500)

    if isinstance(checkout, dict):
        checkout_status = checkout.get("status")
        metadata = checkout.get("metadata", [])

    else:
        checkout_status = getattr(checkout, "status", None)
        metadata = getattr(checkout, "metadata", [])

    if checkout_status != "paid":
        return "Webhook received", 200

    payment_id = None
    if isinstance(metadata, list):
        for item in metadata:
            if isinstance(item, dict):
                if "payment_id" in item:
                    payment_id = item["payment_id"]
                    break

    if not payment_id:
        print("No payment_id in Chargily metadata")
        return ("Missing payment metadata",400)

    try:
        payment_id = int(payment_id)

    except (TypeError, ValueError):
        return ("Invalid payment ID", 400)

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("""
            SELECT user_id, amount, currency, status
            FROM payments
            WHERE id = %s
            FOR UPDATE
            """, (payment_id,))
        payment_row = cursor.fetchone()

        if not payment_row:
            conn.rollback()
            return ("Payment not found",404)

        user_id = payment_row[0]
        amount = payment_row[1]
        currency = payment_row[2]
        local_status = payment_row[3]

        if local_status == "paid":
            conn.commit()
            return ("Already processed", 200)

        if float(amount) != float(DENTAFLOW_PRICE):
            conn.rollback()
            print("Payment amount mismatch")
            return ("Amount mismatch", 400)

        if currency.lower() != "dzd":
            conn.rollback()
            return ("Currency mismatch",400)

        cursor.execute("""
            UPDATE payments
            SET
                status = 'paid',
                paid_at = NOW()
            WHERE id = %s
            """, (payment_id,))

        cursor.execute("""
            UPDATE users
            SET
                is_paid = TRUE,
                paid_at = NOW(),
                status = 'active'
            WHERE id = %s
            """, (user_id,))

        conn.commit()

        print(f"Payment {payment_id} successfully processed")
        return "OK", 200

    except Exception as e:
        conn.rollback()
        print("Webhook database error:", e)
        return ("Database error", 500)

    finally:
        cursor.close()
        conn.close()