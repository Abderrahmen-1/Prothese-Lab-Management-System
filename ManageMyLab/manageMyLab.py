import time
from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from ManageMyLab.FunctionFile import *
from ManageMyLab.ConnectToSql import get_connection
import os
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets
from ManageMyLab.routes.users import users
from ManageMyLab.routes.patients import patients
from ManageMyLab.routes.dentists import dentists
from ManageMyLab.routes.prothesists import prothesists
from ManageMyLab.routes.payment import payments
from ManageMyLab.routes.sel3a import products
from ManageMyLab.routes.services import services
from flask_mail import Mail, Message
from flask_compress import Compress

load_dotenv()

# =============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per hour"])

#============== Compression Configuration ==============================
app.config['COMPRESS_LEVEL'] = os.getenv('COMPRESS_LEVEL')
app.config['COMPRESS_MIN_SIZE'] = int(os.getenv('COMPRESS_MIN_SIZE'))
Compress(app)

#============== Cookeis Session Configuration ===========================
app.config['SESSION_COOKIE_SECURE']=True
app.config['SESSION_COOKIE_HTTPONLY']=True
app.config['SESSION_COOKIE_SAMESITE']="Lax"

#======================== BluePrints Declaration ========================
app.register_blueprint(users)
app.register_blueprint(patients)
app.register_blueprint(dentists)
app.register_blueprint(prothesists)
app.register_blueprint(services)
app.register_blueprint(payments)
app.register_blueprint(products)

# ============== Email configuration ====================================
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("email_account")
app.config["MAIL_PASSWORD"] = os.getenv("email_password")
mail = Mail(app)



def is_logged_in():
    return "id" in session


def login_required():
    if not is_logged_in():
        return redirect(url_for('home'))
    return None


# ============================== HOME =========================================

@app.route("/", methods=["POST", "GET"])
@limiter.limit("10 per minute")
def home():
    if request.method == "GET":
        session.clear()
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "Log-in.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")

        try:
            CheckData(email, username, password)

        except InvalideNameException:
            return render_template(
                "Log-in.html",
                error="Nom d'utilisateur invalide",
                csrf_token=new_token
            )

        except InvalidePasswordException:
            return render_template(
                "Log-in.html",
                error="Mot de passe invalide",
                csrf_token=new_token
            )

        except InvalideEmailException:
            return render_template(
                "Log-in.html",
                error="Adresse e-mail invalide",
                csrf_token=new_token
            )

        UserAccess = ConfirmLogIn(email, username)

        if not UserAccess or not check_password_hash(UserAccess[1], password):
            return render_template(
                "Log-in.html",
                error="Informations invalides",
                csrf_token=new_token
            )

        session["id"] = UserAccess[0]
        session["username"] = username

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute(""" 
                DELETE FROM users 
                WHERE date_inscription <= DATE_SUB(CURDATE(), INTERVAL 2 DAY) 
                  AND email_confirmed = %s 
                  AND is_paid = %s 
            """, (False, False))

            cursor.execute("""
                            SELECT is_paid, status, date_inscription, paid_at
                            FROM users 
                            WHERE id = %s """,(session['id'],))
            UserPaimentStatus = cursor.fetchone()

            if UserPaimentStatus[3] == None:
                cursor.execute(""" 
                            UPDATE users 
                            SET status = 'out of limits' , is_paid = %s
                            WHERE date_inscription <= DATE_SUB(CURDATE(), INTERVAL 1 MONTH) 
                              AND status != 'block' 
                              AND id != %s 
                        """, (False, 1))

            else :
                cursor.execute(""" 
                                UPDATE users 
                                SET status = 'out of limits' , is_paid = %s 
                                WHERE paid_at <= DATE_SUB(CURDATE(), INTERVAL 1 MONTH) 
                                    AND status != 'block' 
                                    AND id != %s  
                                """, (False, 1))
            conn.commit()

            if not UserAccess[2]:
                return render_template(
                    "Log-in.html",
                    error="Veuillez d'abord vérifier votre adresse e-mail Va dans la creation du nouveau compte et insere exactement votre informations",
                    csrf_token=new_token
                )

            cursor.execute(""" 
                SELECT status, is_paid 
                FROM users 
                WHERE id = %s 
            """, (session["id"],))
            UserStatus = cursor.fetchone()

            if not UserStatus:
                session.clear()
                return render_template(
                    "Log-in.html",
                    error="Utilisateur introuvable.",
                    csrf_token=new_token
                )

            status = UserStatus[0]
            is_paid = UserStatus[1]

            if status == "block":
                session.clear()
                return render_template(
                    "Log-in.html",
                    error="Accès à la connexion refusé",
                    csrf_token=new_token
                )

            if status == "out of limits" and not is_paid:
                return redirect(url_for("payments.payment"))

            return redirect(url_for("getHome"))

        except Exception as e:
            conn.rollback()
            print(f"{str(e)}")
            return render_template(
                "Log-in.html",
                error=f"Erreur de base de données : database error",
                csrf_token=new_token
            )

        finally:
            cursor.close()
            conn.close()


@app.route("/HomePage")
def getHome():
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
        result = cursor.fetchone()

        if not result:
            session.clear()
            return redirect(url_for("home"))

        status = result[0]
        is_paid = result[1]

        if status == "block":
            session.clear()
            token = secrets.token_hex(16)
            session["csrf_token"] = token

            return render_template(
                "Log-in.html",
                error="Le compte est bloqué. Contactez-nous pour plus d'informations.",
                csrf_token=token
            )

    except Exception as e:
        conn.rollback()
        print(f"{str(e)}")
        return render_template(
            "Log-in.html",
            message=f"Erreur : database error"
        )

    finally:
        cursor.close()
        conn.close()

    name = session.get("username") if session['username'] else "User"
    letter = name[0].upper() if name else "U"


    return render_template(
        "HomePage.html",
        message=f"BIENVENUE {name}",
        username=name,
        letter=letter
    )


# ============================ CREATE ACCOUNT =================================

@app.route("/CreateAnAccount", methods=["POST", "GET"])
@limiter.limit("10 per 15 minute")
def Create():
    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "CreateAccount.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        email = request.form.get('email')
        phone = request.form.get('phone')
        username = request.form.get('username')
        password = request.form.get('password')
        confirmpass = request.form.get('confirmation')

        if password != confirmpass:
            return render_template("CreateAccount.html", error="Confirmation incorrecte", csrf_token=new_token)

        try:
            CheckData(email, username, password)
        except InvalideNameException:
            return render_template("CreateAccount.html", error="Nom d'utilisateur invalide", csrf_token=new_token)
        except InvalidePasswordException:
            return render_template("CreateAccount.html", error="Mot de passe invalide", csrf_token=new_token)
        except InvalideEmailException:
            return render_template("CreateAccount.html", error="Adresse e-mail invalide", csrf_token=new_token)

        if not (phone or '').isdigit() or len(phone) != 10:
            return render_template("CreateAccount.html", error="Numéro de téléphone invalide", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)
        try:
            password = generate_password_hash(password)
            code = str(secrets.randbelow(900000) + 100000)
            code_hash = generate_password_hash(code)

            cursor.execute("""
                            SELECT id, email_confirmed 
                            FROM users 
                            WHERE user_email = %s """,(email,))
            row = cursor.fetchone()

            if row and row[1]:
                return render_template("CreateAccount.html",
                                       error="Impossible de créer ce compte", csrf_token=new_token)

            if row:
                cursor.execute("""
                                UPDATE users 
                                SET 
                                    user_name = %s, user_phoneNumber = %s, user_password = %s, 
                                    verification_code = %s, verification_expires = DATE_ADD(NOW(), INTERVAL 5 MINUTE), 
                                    verification_attempts = 0 
                                WHERE id = %s """,(username, phone, password, code_hash, row[0]))
            else:
                cursor.execute("""
                                INSERT INTO users(user_name, user_password, user_email, user_phoneNumber, date_inscription, email_confirmed, verification_code,
                                                    verification_expires, verification_attempts)            
                                VALUES(%s, %s, %s, %s, NOW(), FALSE, %s, DATE_ADD(NOW() , INTERVAL 5 MINUTE) , 0)      
                                """,(username, password, email, phone, code_hash))

            conn.commit()

            # Send verification email
            msg = Message(
                subject="Code de vérification de l'adresse e-mail",
                sender=app.config["MAIL_USERNAME"],
                recipients=[email]
            )

            msg.body = f"""
                            Bonjour {username},
                            Votre code de vérification de l'adresse e-mail est :
                            {code}
                            Saisissez ce code dans la page de vérification pour activer votre compte.
                            Ne partagez ce code avec personne.
                            """
            mail.send(msg)
            session['email'] = email
            return redirect(url_for('verify_email', email=email))

        except Exception as e:
            conn.rollback()
            print(f"{str(e)}")
            return render_template("CreateAccount.html", error=f"Erreur : database error", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@app.route("/VerifyEmail/<email>", methods=["GET", "POST"])
@limiter.limit('10 per 15 minutes')
def verify_email(email):
    if not session.get('email') or 'email' not in session:
        return redirect(url_for('Create'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "VerifyEmail.html",
            email=email,
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        code = request.form.get("code")

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute(""" 
                SELECT id, verification_code, email_confirmed, verification_attempts 
                FROM users 
                WHERE user_email = %s AND verification_expires > NOW() 
            """, (session['email'],))

            user = cursor.fetchone()

            if not user:
                return render_template("VerifyEmail.html", email=email,
                    error="Utilisateur introuvable", csrf_token=new_token)

            if user[2]:
                return redirect(url_for('home'))

            if user[3] >= 5 :
                return render_template("VerifyEmail.html", email=email,
                                       error="Code expiré, recréez le compte", csrf_token=new_token)

            if not user[1] or not check_password_hash(user[1], (code or '').strip()):
                cursor.execute("UPDATE users SET verification_attempts = verification_attempts + 1 WHERE id = %s",
                               (user[0],))
                conn.commit()
                return render_template("VerifyEmail.html", email=email,
                                       error="Code de vérification invalide", csrf_token=new_token)

            cursor.execute(""" 
                UPDATE users 
                SET email_confirmed = TRUE, 
                    verification_code = NULL,
                    verification_expires = NULL  
                WHERE id = %s 
            """, (user[0],))

            conn.commit()

            return render_template(
                "Log-in.html",
                message="Adresse e-mail vérifiée avec succès. Vous pouvez maintenant vous connecter.",
                csrf_token=new_token
            )

        except Exception as e:
            conn.rollback()
            print(f"{str(e)}")
            return render_template(
                "VerifyEmail.html",
                email=email,
                error=f"Erreur : database error",
                csrf_token=new_token
            )

        finally:
            cursor.close()
            conn.close()

# ===================================== Change password =======================

@app.route("/ForgotPassword", methods=["POST", "GET"])
@limiter.limit('10 per 15 minutes')
def ChangePassword():
    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "ForgotPassword.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        email = request.form.get('email', None)
        phone = request.form.get('phoneNumber', None)
        name = request.form.get('userName', None)

        try:
            CheckData(email, name, None, phone)
        except InvalideNameException as e:
            return render_template("ForgotPassword.html", error="Nom d'utilisateur invalide", csrf_token=new_token)
        except InvalideEmailException as e:
            return render_template("ForgotPassword.html", error="Adresse e-mail invalide", csrf_token=new_token)
        except InvalidePhoneNumberException as e:
            return render_template("ForgotPassword.html", error="Numéro de téléphone invalide", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute(""" 
                            SELECT id 
                            FROM users  
                            WHERE user_name = %s AND user_email = %s AND user_phoneNumber = %s """,
                           (name, email, phone))
            result = cursor.fetchone()
            if not result:
                return render_template("ForgotPassword.html", error="Utilisateur introuvable", csrf_token=new_token)

            code = str(secrets.randbelow(900000) + 100000)
            code_hash = generate_password_hash(code)

            cursor.execute("""
                            DELETE FROM password_reset 
                             WHERE user_id = %s """,(result[0],))

            cursor.execute("""
                    INSERT INTO password_reset (user_id, code_hash, expired_at, attempts)
                    VALUES(%s, %s, DATE_ADD(NOW(), INTERVAL 5 MINUTE), 0) """
                ,(result[0], code_hash))

            msg = Message(
                subject="Le Code de verification pour le changement du mode de passe",
                sender=app.config['MAIL_USERNAME'],
                recipients=[email]
            )

            msg.body = f""" 
                            Bonjour {name}, 
                            Votre code de vérification de l'adresse e-mail est : 
                            {code} 
                            Saisissez ce code dans la page de vérification pour activer votre compte. 
                            Ne partagez ce code avec personne. 
                        """
            mail.send(msg)

            conn.commit()

            session.pop('reset_verified', None)
            session['reset_userID'] = result[0]

            return redirect(url_for('VerifyEmail'))

        finally:
            cursor.close()
            conn.close()


@app.route("/VerifyEmail", methods=["POST", "GET"])
@limiter.limit('10 per 15 minutes')
def VerifyEmail():
    if 'reset_userID' not in session:
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session['csrf_token'] = token
        return render_template("NewPassEmailCode.html", csrf_token=token)

    if request.method == "POST":
        form_token = request.form.get('csrf_token')
        session_token = session.get('csrf_token')

        if not form_token or not secrets.compare_digest(form_token, session_token):
            return "erreur CSRF attack!",403

        new_token = secrets.token_hex(16)
        session['csrf_token'] = new_token

        user_code = (request.form.get('code') or '').strip()

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try :
            cursor.execute("""
                            SELECT id, code_hash, attempts 
                            FROM password_reset 
                            WHERE user_id = %s AND expired_at > NOW() """
                           ,(session['reset_userID'],))
            row = cursor.fetchone()

            if not row or row[2] >= 5 :
                session.pop('reset_userID', None)
                return render_template("NewPassEmailCode.html",
                    message="Code expiré, recommencez", csrf_token=new_token)

            if not check_password_hash(row[1], (user_code or '').strip()):
                cursor.execute("""
                                UPDATE password_reset 
                                SET 
                                attempts = attempts + 1 
                                WHERE user_id = %s AND id = %s """,(session['reset_userID'], row[0]))
                conn.commit()
                return render_template("NewPassEmailCode.html",
                                       message="Code incorrect", csrf_token=new_token)

            cursor.execute("""
                            DELETE FROM password_reset 
                            WHERE id = %s AND user_id = %s """,(row[0], session['reset_userID']))
            conn.commit()
            session['reset_verified'] = True
            return redirect(url_for('NewPassword'))

        finally:
            cursor.close()
            conn.close()

@app.route("/NewPassword", methods=["POST", "GET"])
@limiter.limit('10 per 15 minutes')
def NewPassword():
    if not session.get('reset_verified') or 'reset_userID' not in session:
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "NewPassword.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        password = request.form.get('password')
        confirmP = request.form.get('confirmP')

        if password != confirmP:
            return render_template("NewPassword.html", error="Confirmation incorrecte", csrf_token=new_token)

        try:
            CheckData(None, None, password, None)

        except InvalidePasswordException:
            return render_template("NewPassword.html", error="Mot de passe invalide", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            password = generate_password_hash(password)

            cursor.execute(""" 
                            UPDATE users  
                            SET  
                            user_password = %s 
                            WHERE id = %s 
                    """, (password, session['reset_userID']))

            conn.commit()
            session.pop('reset_verified', None)
            session.pop('reset_userID', None)

            return render_template("Log-in.html", message="Informations mises à jour", csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            print(f"{str(e)}")
            return render_template("NewPassword.html", error=f"Erreur : database error", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


# ============================== KHEDMA =======================================
@app.route("/Khedma", methods=["POST", "GET"])
def KhedmaPage():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "KhedmaFile.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = secrets.token_hex(16)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        # Only try to get the form if it's a POST request
        if request.method == "POST":
            name = request.form.get('SearchBar', '').strip()  # safer access
        else:
            name = ''  # default empty string for GET requests

        try:
            if name.lower() in ['dentist', 'dentists']:
                cursor.execute(
                    "SELECT * FROM khedma WHERE user_id = %s AND khedma_dentist NOT IN ('NO', '')",
                    (session['id'],)
                )
            elif name:  # if some other search term is provided
                cursor.execute(
                    "SELECT * FROM khedma WHERE user_id = %s AND khedma_dentist = 'NO'",
                    (session['id'],)
                )
            else:  # default: show all
                cursor.execute("SELECT * FROM khedma WHERE user_id = %s", (session['id'],))

            rows = cursor.fetchall()
            return render_template("KhedmaFile.html", result=rows, csrf_token=new_token)
        finally:
            cursor.close()
            conn.close()


@app.route("/Finished", methods=["POST", "GET"])
def khedmaMkemla():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token
        return render_template("FinishedKhedma.html", csrf_token=token)

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        choice = request.form.get('Choice', '').lower()
        conn = get_connection()
        # Enable buffered cursor to automatically read and clear results
        cursor = conn.cursor(buffered=True)

        try:
            if choice == "patient":
                patientId = request.form.get('PatientID')
                khedmaID = request.form.get('ServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) != 10:
                    return render_template("FinishedKhedma.html", error="ID patient invalide", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("FinishedKhedma.html", error="ID du service invalide", csrf_token=new_token)

                    # Verify patient record exists
                cursor.execute(""" 
                    SELECT 1  
                    FROM patient_history 
                    WHERE id = %s AND user_id = %s AND pNumber = %s 
                """, (khedmaID, session['id'], patientId))
                patient_row = cursor.fetchone()

                if not patient_row:
                    return render_template("FinishedKhedma.html", message="Patient introuvable", csrf_token=new_token)

                    # Verify service entry
                cursor.execute(""" 
                    SELECT p.id, k.id  
                    FROM patient p  
                    LEFT JOIN khedma k ON p.patient_number = k.khedma_patient AND k.user_id = p.user_id 
                    WHERE p.user_id = %s AND p.patient_number = %s 
                """, (session['id'], patientId))

                result = cursor.fetchone()

                if not result:
                    return render_template("FinishedKhedma.html", message="Service introuvable", csrf_token=new_token)

                cursor.execute(""" 
                                SELECT prothesist_name, prothesist_number  
                                FROM khedma  
                                WHERE id = %s AND khedma_patient = %s AND user_id = %s """
                               , (result[1], patientId, session['id']))
                found = cursor.fetchone()

                if found:
                    cursor.execute(""" 
                                    SELECT k.id, p.pFinished  
                                    FROM khedma k 
                                    JOIN other_prothesists_khedma p ON p.patient_number = k.khedma_patient AND p.user_id = k.user_id 
                                    WHERE k.khedma_patient = %s AND k.user_id = %s   
                                    """, (patientId, session['id']))
                    found2 = cursor.fetchall()

                    for find in found2:
                        if find[0] == result[1]:
                            if find[1] == 'no':
                                return render_template("FinishedKhedma.html",
                                                       message=f"Le service est toujours chez le prothésiste {found[0]}",
                                                       csrf_token=new_token)

                cursor.execute(""" 
                                SELECT 1  
                                FROM patient_history  
                                WHERE id = %s AND pNumber = %s AND user_id = %s""",
                               (khedmaID, patientId, session['id']))
                found = cursor.fetchone()

                if found:
                    cursor.execute(""" 
                                    UPDATE patient_history  
                                    SET  
                                    status = 'finished'  
                                    WHERE id = %s AND user_id = %s AND pNumber = %s """,
                                   (khedmaID, session['id'], patientId))
                else:
                    return render_template("PatientHistory.html",
                                           message="Service introuvable dans l'historique. Récupérez l'ID du service depuis la table d'historique du patient.",
                                           csrf_token=new_token)

                    # Update patient status
                cursor.execute(""" 
                    UPDATE patient  
                    SET finished = %s, status = %s  
                    WHERE id = %s AND user_id = %s 
                """, ('yes', 'finished', result[0], session['id']))

                # Clean up khedma
                cursor.execute(""" 
                    DELETE FROM khedma  
                    WHERE id = %s AND khedma_patient = %s  AND user_id = %s
                """, (result[1], patientId, session['id']))

                # Clean up finished & paid patients
                cursor.execute(""" 
                    DELETE FROM patient  
                    WHERE finished = %s AND khalsa = %s AND user_id = %s 
                """, ('yes', 'yes', session['id']))


            elif choice == "dentist":
                patientId = request.form.get('DPatientID')
                khedmaID = request.form.get('DServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) > 10:
                    return render_template("FinishedKhedma.html", error="ID patient invalide", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("FinishedKhedma.html", error="ID du service invalide", csrf_token=new_token)

                cursor.execute(""" 
                                SELECT 1  
                                FROM dentist_history  
                                WHERE id = %s AND pNumber = %s AND user_id = %s """
                               , (khedmaID, patientId, session['id']))

                found = cursor.fetchone()

                if not found:
                    return render_template("FinishedKhedma.html",
                                           message="Patient introuvable dans les dossiers du dentiste",
                                           csrf_token=new_token)

                # Verify dentist record
                cursor.execute(""" 
                    SELECT d.id, k.id  
                    FROM dentists d 
                    LEFT JOIN khedma k ON k.khedma_patient = d.patient_number AND k.user_id = d.user_id  
                    WHERE d.patient_number = %s AND d.user_id = %s  
                """, (patientId, session['id']))

                result = cursor.fetchone()

                if not result:
                    return render_template("FinishedKhedma.html",
                                           message="Service introuvable dans les dossiers du dentiste",
                                           csrf_token=new_token)

                cursor.execute(""" 
                                SELECT prothesist_name, prothesist_number  
                                FROM khedma  
                                WHERE id = %s AND khedma_patient = %s AND user_id = %s """
                               , (result[1], patientId, session['id']))
                found = cursor.fetchone()

                if found:
                    cursor.execute(""" 
                                    SELECT k.id, p.pFinished  
                                    FROM khedma k 
                                    JOIN other_prothesists_khedma p ON p.patient_number = k.khedma_patient AND p.user_id = k.user_id 
                                    WHERE k.khedma_patient = %s AND k.user_id = %s   
                                    """, (patientId, session['id']))
                    found2 = cursor.fetchall()

                    for find in found2:
                        if find[0] == result[1]:
                            if find[1] == 'no':
                                return render_template("FinishedKhedma.html",
                                                       message=f"Le service est toujours chez le prothésiste {found[0]}",
                                                       csrf_token=new_token)

                cursor.execute(""" 
                                SELECT 1  
                                FROM dentist_history  
                                WHERE id = %s AND pNumber = %s AND user_id = %s""",
                               (khedmaID, patientId, session['id']))
                found = cursor.fetchone()

                if found:
                    cursor.execute(""" 
                                    UPDATE dentist_history  
                                    SET  
                                    status = 'finished'  
                                    WHERE id = %s AND user_id = %s AND pNumber = %s """,
                                   (khedmaID, session['id'], patientId))
                else:
                    return render_template("DentistHistory.html",
                                           message="Service introuvable dans l'historique. Récupérez l'ID du service depuis la table d'historique des dentistes.",
                                           csrf_token=new_token)

                    # Update dentist status
                cursor.execute(""" 
                    UPDATE dentists  
                    SET finished = %s, status = %s 
                    WHERE id = %s 
                """, ('yes', 'finished', result[0]))

                # Clean up khedma queue
                cursor.execute(""" 
                    DELETE FROM khedma  
                    WHERE id = %s AND khedma_patient = %s AND user_id = %s
                """, (result[1], patientId, session['id']))

                # Clean up finished & paid dentist records
                cursor.execute(""" 
                    DELETE FROM dentists 
                    WHERE finished = %s AND khalsa = %s AND user_id = %s  
                """, ('yes', 'yes', session['id']))

            else:
                return render_template("FinishedKhedma.html", error="Veuillez sélectionner « patient » ou « dentiste »",
                                       csrf_token=new_token)

            conn.commit()
            return render_template("FinishedKhedma.html", message="Informations mises à jour avec succès",
                                   csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            print(f"{str(e)}")
            return render_template("FinishedKhedma.html", error=f"Erreur : database error", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@app.route("/Khalsa", methods=["POST", "GET"])
def KhedmaKhalsa():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "KhedmaKhalsa.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        choice = request.form.get('Choice')
        conn = get_connection()
        cursor = conn.cursor(buffered=True)
        try:
            if choice.lower() == "patient":
                patientId = request.form.get('PatientID')
                khedmaID = request.form.get('ServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) != 10:
                    return render_template("KhedmaKhalsa.html", error="ID patient invalide", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("KhedmaKhalsa.html", error="ID du service invalide", csrf_token=new_token)

                cursor.execute(""" 
                    SELECT price, b9aw, la_date, khalsa  
                    FROM patient 
                    WHERE patient_number = %s AND user_id = %s  
                """, (patientId, session['id']))
                result = cursor.fetchone()

                if not result:
                    return render_template("KhedmaKhalsa.html", message="Patient introuvable", csrf_token=new_token)


                patient_price = result[0]
                patient_b9aw = result[1]
                patient_date = result[2]
                old_khalsa = result[3]

                if old_khalsa == 'yes':
                    return render_template("KhedmaKhalsa.html", message="Service déjà payé", csrf_token=new_token)

                cursor.execute(""" 
                                SELECT p.id, k.id  
                                FROM patient p 
                                LEFT JOIN khedma k ON k.khedma_patient = p.patient_number AND k.user_id = p.user_id 
                                WHERE p.patient_number = %s AND p.user_id = %s """,
                               (patientId, session['id']))

                service = cursor.fetchone()

                if not service:
                    return render_template("KhedmaKhalsa.html", message="Service introuvable", csrf_token=new_token)

                    # cursor.execute("""
                #               SELECT T_ype FROM patient WHERE id = %s AND user_id = %s """, (khedmaID, session['id']))
                # result = cursor.fetchall()

                # data = [ r for r in result if khedma.lower() == r[0].lower() ]

                # if len(data) > 1:
                #   return render_template("FinishedKhedma.html",
                #                         message=f"We found {len(result)} with that name plaise enter the full khedma name "
                #                        , csrf_token=new_token)

                cursor.execute(""" 
                                SELECT pPrice  
                                FROM patient_history  
                                WHERE id = %s AND user_id = %s AND pNumber = %s """,
                               (khedmaID, session['id'], patientId))

                found = cursor.fetchone()
                if found:
                    cursor.execute(""" 
                                    UPDATE patient_history  
                                    SET  
                                    versement = %s , b9aw = %s  
                                    WHERE id = %s AND user_id = %s """, (found[0], 0, khedmaID, session['id']))
                else:
                    return render_template("PatientHistory.html",
                                           message="Service introuvable dans l'historique. Récupérez l'ID du service depuis la table d'historique du patient.",
                                           csrf_token=new_token)

                cursor.execute(""" 
                            UPDATE patient  
                            SET khalsa = %s, b9aw = %s, versa = %s 
                            WHERE id = %s AND user_id = %s 
                        """, ('yes', 0, patient_price, service[0], session['id']))


                cursor.execute(""" 
                            UPDATE khedma  
                            SET khedma_khalsa = %s 
                            WHERE id = %s  
                        """, ('yes', service[1]))


                cursor.execute(""" 
                            DELETE FROM patient 
                            WHERE user_id = %s AND finished = %s AND khalsa = %s 
                        """, (session['id'], 'yes', 'yes'))


                cursor.execute(""" 
                            DELETE FROM khedma 
                            WHERE khedma_wajda = %s AND user_id = %s 
                        """, ('yes', session['id']))


                if old_khalsa.lower() == 'no':
                    UpdateKhalsaStat(cursor, conn, table="patient", b9aw=patient_b9aw, date=patient_date)

            elif choice.lower() == "dentist":
                name = request.form.get('Dentist')
                patientId = request.form.get('DPatientID')
                khedmaID = request.form.get('DServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) > 10:
                    return render_template("KhedmaKhalsa.html", error="ID patient invalide", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("KhedmaKhalsa.html", error="ID du service invalide", csrf_token=new_token)

                    # if not SearcheTable(cursor, name):
                #    return render_template("KhedmaKhalsa.html", message="Incorrect dentist name", csrf_token=new_token)

                cursor.execute(""" 
                    SELECT price, b9aw, date, khalsa  
                    FROM dentists 
                    WHERE patient_number = %s AND user_id = %s AND dentist_name = %s  
                """, (patientId, session['id'], name))
                result = cursor.fetchone()

                if not result:
                    return render_template("KhedmaKhalsa.html", message="Patient introuvable", csrf_token=new_token)

                dentist_price = result[0]
                dentist_b9aw = result[1]
                dentist_date = result[2]
                old_khalsa = result[3]

                if old_khalsa == 'yes':
                    return render_template("KhedmaKhalsa.html", message="Service déjà payé", csrf_token=new_token)

                cursor.execute(""" 
                                SELECT d.id, k.id  
                                FROM dentists d  
                                LEFT JOIN khedma k ON k.khedma_patient = d.patient_number AND k.user_id = d.user_id  
                                WHERE d.patient_number = %s AND d.user_id = %s 
                                """, (patientId, session['id']))

                service = cursor.fetchone()

                # cursor.execute("""
                #               SELECT Dkhedma FROM dentists WHERE dentist_name = %s AND patient_number = %s AND user_id = %s """
                #             , (name, patientId, session['id']))

                # result = cursor.fetchall()
                # data = [ r for r in result if khedma.lower() == r[0].lower() ]

                # if len(data) > 1:
                #   return render_template("FinishedKhedma.html",
                #                         message=
                #                       f"We found {len(result)} with that name plaise enter the full khedma name with dr.{name} "
                #                        , csrf_token=new_token)

                cursor.execute(""" 
                                SELECT pPrice  
                                FROM dentist_history  
                                WHERE id = %s AND user_id = %s AND pNumber = %s """,
                               (khedmaID, session['id'], patientId))

                found = cursor.fetchone()
                if found:
                    cursor.execute(""" 
                                UPDATE dentist_history  
                                SET  
                                versement = %s , b9aw = %s  
                                WHERE id = %s AND user_id = %s """,
                                   (found[0], 0, khedmaID, session['id']))
                else:
                    return render_template("DentistHistory.html",
                                           message="Service introuvable dans l'historique. Récupérez l'ID du service depuis la table d'historique des dentistes.",
                                           csrf_token=new_token)

                cursor.execute(""" 
                            UPDATE dentists  
                            SET  
                            khalsa = %s, versement = %s , b9aw = 0 
                            WHERE id = %s AND user_id = %s  
                        """, ('yes', dentist_price, service[0], session['id']))

                cursor.execute(""" 
                            DELETE FROM dentists 
                            WHERE finished = %s AND khalsa = %s AND user_id = %s  
                        """, ('yes', 'yes', session['id']))

                cursor.execute(""" 
                            UPDATE khedma  
                            SET khedma_khalsa = %s 
                            WHERE user_id = %s AND id = %s 
                        """, ('yes', session['id'], service[1]))

                cursor.execute(""" 
                            DELETE FROM khedma 
                            WHERE user_id = %s AND khedma_wajda = %s AND khedma_khalsa = %s 
                        """, (session['id'], 'yes', 'yes'))

                if old_khalsa.lower() == 'no':
                    UpdateKhalsaStat(cursor, conn, table="dentist", dentistName=name,
                                     b9aw=dentist_b9aw, date=dentist_date)
            else:
                return render_template("KhedmaKhalsa.html", error="Vous devez saisir « patient / dentiste »",
                                       csrf_token=new_token)

            conn.commit()
            return render_template("KhedmaKhalsa.html", message="Paiement mis à jour avec succès", csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            print(f"{str(e)}")
            return render_template("KhedmaKhalsa.html", error=f"Erreur : database error", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@app.route("/Allkhedma", methods=["GET"])
def allkhedma():
    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:

        # Main Table - All items
        cursor.execute("SELECT * FROM khedma WHERE user_id = %s", (session['id'],))
        result = cursor.fetchall()

        # Oldest to Newest (by date ASC)
        cursor.execute("SELECT * FROM khedma WHERE user_id = %s ORDER BY khedma_date ASC", (session['id'],))
        asc = cursor.fetchall()

        # Newest to Oldest (by date DESC)
        cursor.execute("SELECT * FROM khedma WHERE user_id = %s ORDER BY khedma_date DESC", (session['id'],))
        desc = cursor.fetchall()

        # By Deadline (oldest deadline first)
        cursor.execute("SELECT * FROM khedma WHERE user_id = %s ORDER BY DeadLine ASC", (session['id'],))
        DeadLine = cursor.fetchall()

        # Return template with ALL 4 variables
        return render_template("ALLKhedma.html",
                               result=result,
                               asc=asc,
                               desc=desc,
                               DeadLine=DeadLine)
    finally:
        cursor.close()
        conn.close()

    # Optional: Keep these routes for direct navigation (they redirect to main route)


@app.route("/KhedmaByDateASC")
def ShowKhedmaByDateASC():
    if not is_logged_in():
        return redirect(url_for('home'))
    return redirect(url_for('allkhedma'))


@app.route("/KhedmaByDeadLine")
def ShowKhedmaByDeadLine():
    if not is_logged_in():
        return redirect(url_for('home'))
    return redirect(url_for('allkhedma'))


@app.route("/KhedmaByDateDESC")
def ShowKhedmaByDateDESC():
    if not is_logged_in():
        return redirect(url_for('home'))
    return redirect(url_for('allkhedma'))


# =================================== ALL TOTAL ===============================

cach = {}
@app.route("/AllTotalAccount")
def AllTotal():
    if not is_logged_in():
        return redirect(url_for('home'))

    timestamp = time.time()

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:

        if session['id'] not in cach:
            cach[session['id']] = {}

        if 'result' not in cach[session['id']] or time.time() - cach[session['id']]['result']['time'] < 60:
            cursor.execute(""" 
            SELECT  
                month, 
                year, 
    
                SUM(CASE WHEN source='patients' THEN khalsin ELSE 0 END) AS patient_khalsin, 
                SUM(CASE WHEN source='patients' THEN b9aw ELSE 0 END) AS patient_b9aw, 
    
                SUM(CASE WHEN source='dentists' THEN khalsin ELSE 0 END) AS dentist_khalsin, 
                SUM(CASE WHEN source='dentists' THEN b9aw ELSE 0 END) AS dentist_b9aw, 
    
                SUM(CASE WHEN source='prothesists' THEN khalsin ELSE 0 END) AS pro_khalsin, 
                SUM(CASE WHEN source='prothesists' THEN b9aw ELSE 0 END) AS pro_b9aw, 
    
                SUM(CASE WHEN source='sel3a' THEN khalsin ELSE 0 END) AS sel3a_khalsa, 
                SUM(CASE WHEN source='sel3a' THEN b9aw ELSE 0 END) AS sel3a_b9aw, 
    
                SUM(CASE WHEN source='others' THEN khalsin ELSE 0 END) AS other_khalsin, 
                SUM(CASE WHEN source='others' THEN b9aw ELSE 0 END) AS other_b9aw,  
    
                SUM(CASE  
                        WHEN source='patients' THEN khalsin - b9aw   
                        WHEN source='dentists' THEN khalsin - b9aw  
                        WHEN source='prothesists' THEN -(khalsin + b9aw)  
                        WHEN source='sel3a' THEN -(khalsin + b9aw)  
                        WHEN source='others' THEN -(khalsin + b9aw)  
                        ELSE 0 END) AS Net_Profets  
            FROM ( 
    
                SELECT month, year, 
                       SUM(khalsin) AS khalsin, 
                       SUM(machi_khalsin) AS b9aw, 
                       'patients' AS source 
                FROM patient_stat 
                WHERE user_id = %s 
                GROUP BY month, year 
    
                UNION ALL 
    
                SELECT month, year, 
                       SUM(khalsin), 
                       SUM(machi_khalsin), 
                       'dentists' 
                FROM dentist_stat 
                WHERE user_id = %s 
                GROUP BY month, year 
    
                UNION ALL 
    
                SELECT month, year, 
                       SUM(khalsin), 
                       SUM(machi_khalsin), 
                       'prothesists' 
                FROM prothesist_stat 
                WHERE user_id = %s 
                GROUP BY month, year 
    
                UNION ALL 
    
                SELECT  
                    MONTH(buy_date), 
                    YEAR(buy_date), 
                    SUM(versement) AS khalsa, 
                    SUM(b9aw) AS b9aw, 
                    'sel3a' 
                FROM sel3a 
                WHERE user_id = %s 
                GROUP BY MONTH(buy_date), YEAR(buy_date) 
    
                UNION ALL  
    
                SELECT  
                     month , year , 
                     SUM(khalsin) AS khalsin ,  
                     SUM(machi_khalsin) AS b9aw , 
                     'others' AS source  
                     FROM other_services_stats  
                     WHERE user_id = %s  
                     GROUP BY month , year  
    
            ) AS combined 
    
            GROUP BY month, year 
            ORDER BY year, month 
            LIMIT 12 
            """, (session['id'], session['id'], session['id'], session['id'], session['id']))

            result = cursor.fetchall()
            cach[session['id']]['result'] = {
                'value': result,
                'time': time.time()
            }

        else :
            result = cach[session['id']]['result']['value']
            if time.time() - cach[session['id']]['result']['time'] > 60 :
                cach[session['id']].pop('result', None)


        if 'result_table' not in cach[session['id']] or time.time() - cach[session['id']]['result_table']['time'] < 60:
            cursor.execute(""" 
                    SELECT  
                        month, 
                        year, 
    
                        SUM(CASE WHEN source='patients' THEN khalsin ELSE 0 END) AS patient_khalsin, 
                        SUM(CASE WHEN source='patients' THEN b9aw ELSE 0 END) AS patient_b9aw, 
    
                        SUM(CASE WHEN source='dentists' THEN khalsin ELSE 0 END) AS dentist_khalsin, 
                        SUM(CASE WHEN source='dentists' THEN b9aw ELSE 0 END) AS dentist_b9aw, 
    
                        SUM(CASE WHEN source='prothesists' THEN khalsin ELSE 0 END) AS pro_khalsin, 
                        SUM(CASE WHEN source='prothesists' THEN b9aw ELSE 0 END) AS pro_b9aw, 
    
                        SUM(CASE WHEN source='sel3a' THEN khalsin ELSE 0 END) AS sel3a_khalsa, 
                        SUM(CASE WHEN source='sel3a' THEN b9aw ELSE 0 END) AS sel3a_b9aw, 
    
                        SUM(CASE WHEN source='others' THEN khalsin ELSE 0 END) AS other_khalsin, 
                        SUM(CASE WHEN source='others' THEN b9aw ELSE 0 END) AS other_b9aw,  
    
                        SUM(CASE  
                                WHEN source='patients' THEN khalsin - b9aw   
                                WHEN source='dentists' THEN khalsin - b9aw  
                                WHEN source='prothesists' THEN -(khalsin + b9aw)  
                                WHEN source='sel3a' THEN -(khalsin + b9aw)  
                                WHEN source='others' THEN -(khalsin + b9aw)  
                                ELSE 0 END) AS Net_Profets  
                    FROM ( 
    
                        SELECT month, year, 
                               SUM(khalsin) AS khalsin, 
                               SUM(machi_khalsin) AS b9aw, 
                               'patients' AS source 
                        FROM patient_stat 
                        WHERE user_id = %s 
                        GROUP BY month, year 
    
                        UNION ALL 
    
                        SELECT month, year, 
                               SUM(khalsin), 
                               SUM(machi_khalsin), 
                               'dentists' 
                        FROM dentist_stat 
                        WHERE user_id = %s 
                        GROUP BY month, year 
    
                        UNION ALL 
    
                        SELECT month, year, 
                               SUM(khalsin), 
                               SUM(machi_khalsin), 
                               'prothesists' 
                        FROM prothesist_stat 
                        WHERE user_id = %s 
                        GROUP BY month, year 
    
                        UNION ALL 
    
                        SELECT  
                            MONTH(buy_date), 
                            YEAR(buy_date), 
                            SUM(versement) AS khalsa, 
                            SUM(b9aw) AS b9aw, 
                            'sel3a' 
                        FROM sel3a 
                        WHERE user_id = %s 
                        GROUP BY MONTH(buy_date), YEAR(buy_date) 
    
                        UNION ALL  
    
                        SELECT  
                             month , year , 
                             SUM(khalsin) AS khalsin ,  
                             SUM(machi_khalsin) AS b9aw , 
                             'others' AS source  
                             FROM other_services_stats  
                             WHERE user_id = %s  
                             GROUP BY month , year  
    
                    ) AS combined 
    
                    GROUP BY month, year 
                    ORDER BY year, month 
                    """, (session['id'], session['id'], session['id'], session['id'], session['id']))
            result_table = cursor.fetchall()
            cach[session['id']]['result_table'] = {
                    'value': result_table,
                    'time': time.time()
            }

        else :
            result_table = cach[session['id']]['result_table']['value']
            if time.time() - cach[session['id']]['result_table']['time'] > 60:
                cach[session['id']].pop('result_table' , None)


        if 'total_patients' not in cach[session['id']] or time.time() - cach[session['id']]['total_patients']['time'] < 60:
            cursor.execute(""" 
                            SELECT SUM(patients_number) AS total_patients, month, year  
                            FROM patient_stat 
                            WHERE  
                             user_id = %s AND (  
                                            year > YEAR(DATE_SUB(CURDATE() , INTERVAL 13 MONTH))  
                                                OR ( year = YEAR(DATE_SUB(CURDATE() , INTERVAL 13 MONTH))  
                                                    AND month >= MONTH(DATE_SUB(CURDATE() , INTERVAL 13 MONTH)) 
                                                    ) 
                                                ) 
                            GROUP BY month, year 
                            ORDER BY month, year  
                            """, (session['id'],))
            total_patients = cursor.fetchall()
            cach[session['id']]['total_patients'] = {
                    'value': total_patients,
                    'time': time.time()
            }

        else :
            total_patients = cach[session['id']]['total_patients']['value']
            if time.time() - cach[session['id']]['total_patients']['time'] > 60 :
                cach[session['id']].pop('total_patients' , None)

        if 'total_dentists' not in cach[session['id']] or time.time() - cach[session['id']]['total_dentists']['time'] < 60:
            cursor.execute(""" 
                            SELECT SUM(total_khedma) AS total_khedma, month, year  
                            FROM dentist_stat 
                            WHERE  
                             user_id = %s AND (  
                                            year >= YEAR(DATE_SUB(CURDATE() , INTERVAL 13 MONTH))  
                                                OR ( year = YEAR(DATE_SUB(CURDATE() , INTERVAL 13 MONTH))  
                                                    AND month >= MONTH(DATE_SUB(CURDATE() , INTERVAL 13 MONTH)) 
                                                    )   
                                                ) 
                            GROUP BY month, year  
                            ORDER BY month, year  
                            """, (session['id'],))
            total_dentists = cursor.fetchall()
            cach[session['id']]['total_dentists'] = {
                    'value': total_dentists,
                    'time': time.time()
            }

        else :
            total_dentists = cach[session['id']]['total_dentists']['value']
            if time.time() - cach[session['id']]['total_dentists']['time'] > 60:
                cach[session['id']].pop('total_dentists' , None)

        if 'total_khedma' not in cach[session['id']] or time.time() - cach[session['id']]['total_khedma']['time'] < 60:
            cursor.execute(""" 
                            SELECT MONTH, YEAR ,  
                            SUM(CASE WHEN k_source = 'patient' THEN total_khedma ELSE 0 END) + 
                            SUM(CASE WHEN k_source = 'dentist' THEN total_khedma ELSE 0 END) AS TOTAL 
    
                            FROM ( 
                                    SELECT MONTH, YEAR , SUM(patients_number) AS total_khedma , 'patient' AS k_source 
                                    FROM patient_stat  
                                    WHERE user_id = %s AND (  
                                            year > YEAR(DATE_SUB(CURDATE() , INTERVAL 13 MONTH))  
                                                OR ( year = YEAR(DATE_SUB(CURDATE() , INTERVAL 13 MONTH))  
                                                    AND month >= MONTH(DATE_SUB(CURDATE() , INTERVAL 13 MONTH)) 
                                                    ) ) 
                                    GROUP BY MONTH, YEAR  
    
                                    UNION ALL  
    
                                    SELECT MONTH, YEAR , SUM(total_khedma) AS total_khedma , 'dentist' AS k_source  
                                    FROM dentist_stat  
                                    WHERE user_id = %s AND (  
                                            year > YEAR(DATE_SUB(CURDATE() , INTERVAL 13 MONTH))  
                                                OR ( year = YEAR(DATE_SUB(CURDATE() , INTERVAL 13 MONTH))  
                                                    AND month >= MONTH(DATE_SUB(CURDATE() , INTERVAL 13 MONTH)) 
                                                    ) ) 
                                    GROUP BY MONTH, YEAR  
                            ) AS stats  
                            GROUP BY MONTH, YEAR  
                            ORDER BY MONTH, YEAR   
                          """, (session['id'], session['id']))
            total_khedma = cursor.fetchall()
            cach[session['id']]['total_khedma'] = {
                    'value': total_khedma,
                    'time': time.time()
            }

        else :
            total_khedma = cach[session['id']]['total_khedma']['value']
            if time.time() - cach[session['id']]['total_khedma']['time'] > 60 :
                cach[session['id']].pop('total_khedma', None)

        if 'total_finished' not in cach[session['id']] or time.time() - cach[session['id']]['total_finished']['time'] < 60:
            cursor.execute(""" 
                            SELECT 
                            months.month, 
                            months.year, 
    
                            COALESCE(p.total_finished, 0) AS total_patient_finished, 
                            COALESCE(p.total_notFinished, 0) AS total_patient_notFinished, 
    
                            COALESCE(d.total_finished, 0) AS total_dentists_finished, 
                            COALESCE(d.total_notFinished, 0) AS total_dentists_notFinished, 
    
                            COALESCE(p.total_finished, 0) 
                            + COALESCE(d.total_finished, 0) AS total_finished, 
    
                            COALESCE(p.total_notFinished, 0) 
                            + COALESCE(d.total_notFinished, 0) AS total_notFinished, 
    
                            ( 
                                ( 
                                    COALESCE(p.total_finished, 0) 
                                    + COALESCE(d.total_finished, 0) 
                                ) * 100 
                            ) 
                            / 
                            NULLIF( 
                                COALESCE(p.total_finished, 0) 
                                + COALESCE(d.total_finished, 0) 
                                + COALESCE(p.total_notFinished, 0) 
                                + COALESCE(d.total_notFinished, 0), 
                                0 
                            ) AS Finished_Percentage_per100 
    
                        FROM 
                        ( 
                            SELECT DISTINCT MONTH(pDate) AS month, YEAR(pDate) AS year 
                            FROM patient_history 
                            WHERE user_id = %s 
    
                            UNION 
    
                            SELECT DISTINCT MONTH(pDate) AS month, YEAR(pDate) AS year 
                            FROM dentist_history 
                            WHERE user_id = %s 
                        ) AS months 
    
                        LEFT JOIN 
                        ( 
                            SELECT 
                                MONTH(pDate) AS month, 
                                YEAR(pDate) AS year, 
    
                                SUM(CASE 
                                    WHEN STATUS = 'finished' THEN 1 
                                    ELSE 0 
                                END) AS total_finished, 
    
                                SUM(CASE 
                                    WHEN STATUS NOT IN ('finished', 'deleted') THEN 1 
                                    ELSE 0 
                                END) AS total_notFinished 
    
                            FROM patient_history 
    
                            WHERE user_id = %s 
    
                            GROUP BY MONTH(pDate), YEAR(pDate) 
    
                        ) AS p 
                            ON p.month = months.month 
                            AND p.year = months.year 
    
                        LEFT JOIN 
                        ( 
                            SELECT 
                                MONTH(pDate) AS month, 
                                YEAR(pDate) AS year, 
    
                                SUM(CASE 
                                    WHEN STATUS = 'finished' THEN 1 
                                    ELSE 0 
                                END) AS total_finished, 
    
                                SUM(CASE 
                                    WHEN STATUS NOT IN ('finished', 'deleted') THEN 1 
                                    ELSE 0 
                                END) AS total_notFinished 
    
                            FROM dentist_history 
    
                            WHERE user_id = %s 
    
                            GROUP BY MONTH(pDate), YEAR(pDate) 
    
                        ) AS d 
                            ON d.month = months.month 
                            AND d.year = months.year 
    
                        ORDER BY months.year, months.month  
        """, (session['id'], session['id'], session['id'], session['id']))
            total_finished = cursor.fetchall()
            cach[session['id']]['total_finished'] = {
                    'value': total_finished,
                    'time': time.time()
            }

        else :
            total_finished = cach[session['id']]['total_finished']['value']
            if time.time() - cach[session['id']]['total_finished']['time'] > 60:
                cach[session['id']].pop('total_finished' , None)

        if 'patients_period' not in cach[session['id']] or time.time() - cach[session['id']]['patients_period']['time'] < 60 :
            cursor.execute("""
                            SELECT DISTINCT YEAR(pDate) AS year
                            FROM patient_history 
                            WHERE user_id = %s """,(session['id'],))
            patients_period = cursor.fetchall()
            cach[session['id']]['patients_period'] = {
                'value': patients_period,
                'time': time.time()
            }

        else :
            patients_period = cach[session['id']]['patients_period']['value']
            if time.time() - cach[session['id']]['patients_period']['time'] > 60:
                cach[session['id']].pop('patients_period' , None)

        if 'dentists_period' not in cach[session['id']] or time.time() - cach[session['id']]['dentists_period'][
            'time'] < 60:
            cursor.execute("""
                            SELECT DISTINCT YEAR(pDate) AS year
                            FROM dentist_history 
                            WHERE user_id = %s """, (session['id'],))
            dentists_period = cursor.fetchall()
            cach[session['id']]['dentists_period'] = {
                'value': dentists_period,
                'time': time.time()
            }

        else:
            dentists_period = cach[session['id']]['dentists_period']['value']
            if time.time() - cach[session['id']]['dentists_period']['time'] > 60:
                cach[session['id']].pop('dentists_period', None)

        if 'prothesists_period' not in cach[session['id']] or time.time() - cach[session['id']]['prothesists_period'][
            'time'] < 60:
            cursor.execute("""
                            SELECT DISTINCT YEAR(pDate) AS year
                            FROM other_prothesists_history 
                            WHERE user_id = %s """, (session['id'],))
            prothesists_period = cursor.fetchall()
            cach[session['id']]['prothesists_period'] = {
                'value': prothesists_period,
                'time': time.time()
            }

        else:
            prothesists_period = cach[session['id']]['prothesists_period']['value']
            if time.time() - cach[session['id']]['prothesists_period']['time'] > 60:
                cach[session['id']].pop('prothesists_period', None)


        return render_template("AllTotalStats.html", result=result, result_table=result_table, patients=total_patients,
                               dentists=total_dentists, Total_khedma=total_khedma, total_finished=total_finished,
                               patients_period=patients_period, dentists_period=dentists_period, prothesists_periode=prothesists_period)


    except Exception as e:
        app.logger.exception("AllTotalAccount failed")
        raise

    finally:
        cursor.close()
        conn.close()

# ========================================================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG" , 'false').lower() == 'true')