from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from FlaskTry.FunctionFile import *
from FlaskTry.ConnectToSql import get_connection
import os
from dotenv import load_dotenv
from datetime import datetime , timedelta , date
import time
from chargily_pay import ChargilyClient
import hmac , hashlib
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets
from waitress import serve
from flask_caching import Cache
from FlaskTry.routes.users import users

load_dotenv()

# =============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
limiter = Limiter(get_remote_address, app=app)

app.register_blueprint(users)


def SearcheTable(cursor, DentistName):
    cursor.execute("""
        SELECT 1 FROM dentist_registry
        WHERE user_id = %s AND dentist_name = %s
    """, (session['id'], DentistName))
    exist = cursor.fetchone()
    return exist


def is_logged_in():
    return "id" in session

def login_required():
    if not is_logged_in():
        return redirect(url_for('home'))
    return None


# ============================== HOME =========================================

@app.route("/log_in", methods=["POST", "GET"])
@limiter.limit("10 per minute")
def home():
    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "Log-in.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        email    = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")

        try:
            CheckData(email, username, password)
        except InvalideNameException:
            return render_template("Log-in.html", error="Invalide Name", csrf_token= new_token)
        except InvalidePasswordException:
            return render_template("Log-in.html", error="Invalide Password", csrf_token= new_token)
        except InvalideEmailException:
            return render_template("Log-in.html", error="Invalide Email", csrf_token= new_token)

        row = ConfirmLogIn(email, username)

        if row and check_password_hash(row[1], password):
            session['id']       = row[0]
            session['username'] = username

            if row and check_password_hash(row[1], password):
                session['id'] = row[0]
                session['username'] = username

            conn = get_connection()
            cursor = conn.cursor()

            try :
                cursor.execute("""
                                SELECT status 
                                FROM users 
                                WHERE id = %s """,(session['id'],))
                found = cursor.fetchone()

                if found[0] == 'block' :
                    session.clear()
                    return render_template("Log-in.html", error="No access to log-in", csrf_token=new_token)

                return redirect(url_for('getHome'))

            finally :
                cursor.close()
                conn.close()
        else:
            return render_template("Log-in.html", error="Invalid Information", csrf_token= new_token)


@app.route("/HomePage")
def getHome():
    if not is_logged_in():
        return redirect(url_for('home'))

    name = session.get('username')
    letter = name[0].upper()

    return render_template(
            "HomePage.html",
            message=f"WELCOME {name}",
            username=name,
            letter=letter
        )


# ============================ CREATE ACCOUNT =================================

@app.route("/CreateAnAccount", methods=["POST", "GET"])
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

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        email       = request.form.get('email')
        phone       = request.form.get('phone')
        username    = request.form.get('username')
        password    = request.form.get('password')
        confirmpass = request.form.get('confirmation')

        if password != confirmpass:
            return render_template("CreateAccount.html", error="Invalide Confirmation", csrf_token=new_token)

        try:
            CheckData(email, username, password)
        except InvalideNameException:
            return render_template("CreateAccount.html", error="Invalide Name", csrf_token=new_token)
        except InvalidePasswordException:
            return render_template("CreateAccount.html", error="Invalide Password", csrf_token=new_token)
        except InvalideEmailException:
            return render_template("CreateAccount.html", error="Invalide Email", csrf_token=new_token)


        if not phone.isdigit() or not phone.strip() or len(phone) != 10:
            return render_template("CreateAccount.html", error="Invalide Phone Number", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)
        try:
            password = generate_password_hash(password)

            cursor.execute("""
                           SELECT id FROM users 
                           WHERE user_name = %s AND user_phoneNumber = %s AND user_email = %s 
                           """,(username, phone, email))
            result = cursor.fetchone()

            if not result:
                cursor.execute("""
                    INSERT INTO users (user_name, user_password, user_email, user_phoneNumber, date_inscription )
                    VALUES (%s, %s, %s, %s, NOW())
                """, (username, password, email, phone))
                conn.commit()
                return render_template("Log-in.html", message=f"Account Created Welcome {username}", csrf_token=new_token)

            else :
                return render_template("Log-in.html" , message="Account Already exist", csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("CreateAccount.html", error=f"error {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


# ===================================== Change password =======================

@app.route("/ForgotPassword" , methods=["POST" , "GET"])
def ChangePassword():

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "ForgotPassword.html",
            csrf_token=token
        )

    if request.method == "POST" :
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        email = request.form.get('email')
        phone = request.form.get('phoneNumber')
        name = request.form.get('userName')

        try :
            CheckData(email, name, None, phone)
        except InvalideNameException as e :
            return render_template("ForgotPassword.html" , error="Invalide User name", csrf_token=new_token)
        except InvalideEmailException as e :
            return render_template("ForgotPassword.html" , error="Invalide Email ", csrf_token=new_token)
        except InvalidePhoneNumberException as e:
            return render_template("ForgotPassword.html", error="Invalide phone Number ", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try :
            cursor.execute("""
                            SELECT id FROM users 
                            WHERE user_name = %s AND user_email = %s AND user_phoneNumber = %s """,
                           (name, email, phone))
            result = cursor.fetchone()
            if not result :
                return render_template("ForgotPassword.html" , error="User Not Found ", csrf_token=new_token)

            session['user_infos'] = {
                'username' : name,
                'email' : email,
                'phoneNumber' : phone
            }

            return redirect(url_for('NewPassword'))

        finally :
            cursor.close()
            conn.close()


@app.route("/NewPassword" , methods=["POST" , "GET"])
def NewPassword():

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "NewPassword.html",
            csrf_token=token
        )

    if request.method == "POST" :
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        data = session.get('user_infos')

        password = request.form.get('password')
        confirmP = request.form.get('confirmP')

        username = data['username']
        email = data['email']
        phoneNumber = data['phone']

        if password != confirmP :
            return render_template("NewPassword.html", error="Incorrect confirmation", csrf_token=new_token)

        try :
            CheckData(None, None, password, None)

        except InvalidePasswordException :
            return render_template("NewPassword.html" , error="Invalid Password ", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try :
            NewPassword = generate_password_hash(password)

            cursor.execute("""
                            SELECT id 
                            FROM users
                            WHERE user_name = %s AND user_email = %s AND user_phoneNumber = %s AND id = %s 
                            """,(username, email, phoneNumber, session['id']))
            found = cursor.fetchone()

            if found :
                cursor.execute("""
                                UPDATE users 
                                SET 
                                user_password = %s
                                WHERE id = %s
                                """,(found[0],) )
                conn.commit()
                return render_template("Log-in.html", message="Information Updated ", csrf_token=new_token)

            else :
                return render_template("Log-in.html", error="User not found", csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("NewPassword.html", error=f"error {str(e)}", csrf_token=new_token)

        finally :
            cursor.close()
            conn.close()

# ============================== PATIENTS =====================================

@app.route("/Patient", methods=["POST" , "GET"])
def PatientPage():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":

        token = secrets.token_hex(16)
        session['csrf_token'] = token

        conn = get_connection()
        cursor = conn.cursor(buffered=True)


        try:
            cursor.execute("DELETE FROM patient WHERE finished = %s AND khalsa = %s AND user_id = %s",
                           ('yes', 'yes', session['id']))
            conn.commit()
            cursor.execute("SELECT * FROM patient WHERE user_id = %s", (session['id'],))
            rows = cursor.fetchall()
            return render_template("PatientsFile.html", data=rows, csrf_token=token)

        finally:
            cursor.close()
            conn.close()


    if request.method == "POST" :
        token = request.form.get('csrf_token')
        check = session.get('csrf_token')

        if not token or token != check :
            return "error CSRF attack", 403

        new_token = secrets.token_hex(16)
        session['csrf_token'] = new_token

        patient = request.form.get('SearchBar')

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try :

            if patient.isdigit():
                cursor.execute("""
                                SELECT * FROM patient
                                WHERE user_id = %s AND patient_number = %s """,
                               (session['id'], patient))
                data = cursor.fetchall()

                if data :
                    return render_template("PatientsFile.html", data=data, csrf_token=new_token)
                else :
                    return render_template("PatientsFile.html", message="Patient not found", csrf_toke=new_token)

            else :
                cursor.execute("""
                                SELECT * FROM patient
                                WHERE user_id = %s AND patient_firstname = %s """,
                               (session['id'], patient.lower()))
                data = cursor.fetchall()

                if data :
                    return render_template("PatientsFile.html", data=data, csrf_token=new_token)

                else :
                    cursor.execute("""
                                    SELECT * FROM patient
                                    WHERE user_id = %s AND patient_lastname = %s """,
                                   (session['id'], patient.lower()))
                    data = cursor.fetchall()

                    if data:
                        return render_template("PatientsFile.html", data=data, csrf_token=new_token)

                    else :
                        return render_template("PatientsFile.html", message="Patient not found", csrf_token=new_token)

        finally :
            cursor.close()
            conn.close()

@app.route("/AddPatient", methods=["POST", "GET"])
def AddPatient():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "AddPatient.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        firstName = request.form.get('PatientFirstName', '').strip()
        lastName  = request.form.get('PatientLastName', '').strip()
        unique    = request.form.get('PatientUnique', '').strip()
        choice    = request.form.get('KhedmaChoice', '').strip()
        date      = request.form.get('date', '').strip()
        deadLine  = request.form.get('DeadLine', '').strip()
        price     = request.form.get('KhedmaPrice', '').strip()
        khalsa    = request.form.get('Khalsa', '').strip().lower()
        versa     = request.form.get('versa', '').strip().lower()
        Versa     = request.form.get('Versa', '').strip()
        ProCheck  = request.form.get('OtherPro', '').strip().lower()

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:

            if not firstName or not lastName or firstName.isdigit() or lastName.isdigit():
                return render_template("AddPatient.html", error="Invalide Name", csrf_token=new_token)

            if not unique or not unique.isdigit() or len(unique) != 10:
                return render_template("AddPatient.html", error="Invalide Unique number", csrf_token=new_token)

            if not choice:
                return render_template("AddPatient.html", error="Invalide Choice", csrf_token=new_token)

            if not date or not deadLine:
                return render_template("AddPatient.html", error="Date and Deadline are required", csrf_token=new_token)

            if deadLine < date:
                return render_template("AddPatient.html", error="Invalide Dead Line", csrf_token=new_token)

            if not khalsa or khalsa not in ['yes', 'no']:
                return render_template("AddPatient.html", error="You must put 'yes' or 'no' in Khalsa", csrf_token=new_token)

            if khalsa == 'no' :
                if not versa or versa not in ['yes', 'no']:
                    return render_template("AddPatient.html", error="In versa insert 'yes' or 'no'", csrf_token=new_token)

            if not ProCheck or ProCheck not in ['yes', 'no']:
                return render_template("AddPatient.html", error="You must enter 'yes' or 'no' in the Prothesists check part", csrf_token=new_token)

            cursor.execute("""
                            SELECT id FROM patient WHERE user_id = %s AND patient_number = %s"""
                           , (session['id'], unique))

            if cursor.fetchone():
                return render_template("AddPatient.html", message="Unique number already exists", csrf_token=new_token)

            if not price:
                return render_template("AddPatient.html", error="Price cannot be empty", csrf_token=new_token)

            if not checkValue(price):
                return render_template("AddPatient.html", error="Invalide price", csrf_token=new_token)

            price = float(price)

            if khalsa == 'yes':
                Versa = price
            else:
                if versa == 'no':
                    Versa = 0
                else:
                    if not Versa:
                        return render_template("AddPatient.html", error="Please enter the versement amount", csrf_token=new_token)

                    if not checkValue(Versa):
                        return render_template("AddPatient.html", error="Invalide versement", csrf_token=new_token)

                    Versa = float(Versa)

            if Versa > price:
                return render_template("AddPatient.html", error="Versa must not be bigger than price", csrf_token=new_token)

            if khalsa == 'yes':
                Versa = price
                b9aw = 0
            else:
                b9aw = round(price - Versa, 2)

            patient_khalsa = 'yes' if b9aw == 0 else 'no'

            status = 'in process'
            patient_infos = [session['id'], firstName, lastName, unique, choice, date, 'no', price, patient_khalsa, Versa, b9aw, deadLine, status]

            ProName = None
            ProNumber = 0
            ProPrice = 0
            ProDate = None
            ProKhalsa = None
            Proversa = "no"
            ProVersa = 0
            Prob9aw = 0
            ProDeadLine = None

            if ProCheck == "yes":
                patient_infos[12] = 'prothesist'

                ProName   = request.form.get('ProName', '').strip()
                ProNumber = request.form.get('ProNumber', '').strip()
                ProPrice  = request.form.get('ProPrice', '').strip()
                ProDate   = request.form.get('ProDate', '').strip()
                ProKhalsa = request.form.get('ProKhalsa', '').strip().lower()
                Proversa  = request.form.get('Proversa', '').strip().lower()
                ProVersa  = request.form.get('ProVersa', '').strip()
                ProDeadLine = request.form.get('ProDeadLine', '').strip()

                if not ProName:
                    return render_template("AddPatient.html", error="Prothesist Name must not be empty", csrf_token=new_token)

                if ProName.isdigit():
                    return render_template("AddPatient.html", error="Invalide Prothesist Name", csrf_token=new_token)

                if not ProNumber or not ProNumber.isdigit() or len(ProNumber) != 10:
                    return render_template("AddPatient.html", error="Prothesist Number must contain exactly 10 digits", csrf_token=new_token)

                if not ProKhalsa or ProKhalsa not in ['yes', 'no']:
                    return render_template("AddPatient.html", error="You must put 'yes' or 'no' in Prothesist Khalsa", csrf_token=new_token)

                if ProKhalsa == 'no':
                    if not Proversa or Proversa not in ['yes', 'no']:
                        return render_template("AddPatient.html", error="In Prothesist versa insert 'yes' or 'no'", csrf_token=new_token)

                if not ProDate or not ProDeadLine:
                    return render_template("AddPatient.html", error="Prothesist Date and Deadline are required", csrf_token=new_token)

                if ProDate < date:
                    return render_template("AddPatient.html", error="Invalide Prothesist Date", csrf_token=new_token)

                if ProDeadLine < ProDate:
                    return render_template("AddPatient.html", error="Invalide Prothesist Dead Line", csrf_token=new_token)

                if ProDeadLine > deadLine:
                    return render_template("AddPatient.html", error="Prothesist Deadline cannot be after Patient Deadline", csrf_token=new_token)

                if not ProPrice:
                    return render_template("AddPatient.html", error="Prothesist price cannot be empty", csrf_token=new_token)

                if not checkValue(ProPrice):
                    return render_template("AddPatient.html", error="Invalide Prothesist price", csrf_token=new_token)

                ProPrice = float(ProPrice)

                if ProKhalsa == 'yes':
                    ProVersa = ProPrice
                else:
                    if Proversa == 'no':
                        ProVersa = 0
                    else:
                        if not ProVersa:
                            return render_template("AddPatient.html", error="Please enter the Prothesist versement amount", csrf_token=new_token)

                        if not checkValue(ProVersa):
                            return render_template("AddPatient.html", error="Invalide prothesist versement", csrf_token=new_token)

                        ProVersa = float(ProVersa)

                if ProVersa > ProPrice:
                    return render_template("AddPatient.html", error="Prothesist Versa must not be bigger than his price", csrf_token=new_token)

                if ProKhalsa == 'yes':
                    ProVersa = ProPrice
                    Prob9aw = 0
                else:
                    Prob9aw = round(ProPrice - ProVersa, 2)

                cursor.execute("""
                    SELECT id FROM other_prothesists
                    WHERE pName = %s AND pNumber = %s AND user_id = %s
                """, (ProName, ProNumber, session['id']))

                if not cursor.fetchone():
                    return render_template("AddPatient.html", error="Prothesist not found", csrf_token=new_token)

                cursor.execute("""
                    INSERT INTO other_prothesists_khedma
                        (patient_number, dentist_name, pName, pNumber, pDate, pKhedma, pPrice, pVersa, pB9aw, pKhalsa, pFinished, user_id, DeadLine)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (unique, None, ProName, ProNumber, ProDate, choice, ProPrice, ProVersa, Prob9aw, ProKhalsa, 'no', session['id'], ProDeadLine))

                ProthesistsStat(cursor, conn, ProPrice, ProNumber, ProName, ProKhalsa, ProDate, ProVersa)

                Prothesist_History(cursor, conn, ProName, ProNumber, unique )

            exist = checkExistPatient(cursor, firstName, unique, choice)

            if not exist:
                cursor.execute("""
                    INSERT IGNORE INTO patient(
                        user_id, patient_firstname, patient_lastname, patient_number,
                        T_ype, la_date, finished, price, khalsa, versa, b9aw, DeadLine, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, tuple(patient_infos))

                cursor.execute("""
                    INSERT INTO khedma(
                        khedman, khedma_price, khedma_date,
                        khedma_dentist, khedma_patient, khedma_wajda, khedma_khalsa, prothesist_name, prothesist_number, user_id, DeadLine
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (choice, price, date, 'NO', unique, 'no', patient_khalsa, ProName, ProNumber, session['id'], deadLine))

                Patient_History(cursor, conn, unique)
                PatientStats(cursor, conn, price, khalsa, date, Versa)

                conn.commit()

                cursor.execute("""
                                SELECT * FROM patient 
                                WHERE user_id = %s """,(session['id'],))
                data = cursor.fetchall()

                return render_template("PatientsFile.html", message="Patient Added Successfully", data=data, csrf_token=new_token)

            else:
                return render_template("PatientsFile.html", message="Patient already exists", csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            return render_template("AddPatient.html", error=f"error {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@app.route("/DeletePatient", methods=["POST", "GET"])
def DeletePatient():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "DeletePatient.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        PatientF_deleted = request.form.get("DeleteF", "").strip()
        Confirm_PatientF = request.form.get("ConfirmDeletePatientF", "").strip()
        PatientL_deleted = request.form.get("DeleteL", "").strip()
        Confirm_PatientL = request.form.get("ConfirmDeletePatientL", "").strip()
        Patient_unique   = request.form.get("uniquepatient", "").strip()
        Confirm_Unique   = request.form.get("confirmunique", "").strip()

        if not Patient_unique or not Patient_unique.isdigit() or len(Patient_unique) != 10:
            return render_template("DeletePatient.html", error="Invalid Unique number", csrf_token=new_token)

        if not Confirm_Unique or not Confirm_Unique.isdigit() or len(Confirm_Unique) != 10:
            return render_template("DeletePatient.html", error="Invalid Unique number", csrf_token=new_token)

        if (PatientF_deleted != Confirm_PatientF or
                PatientL_deleted != Confirm_PatientL or
                Patient_unique != Confirm_Unique):
            return render_template("DeletePatient.html", error="Invalid Confirmation", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute("""
                            SELECT p.patient_firstname, p.patient_lastname, pr.pName 
                            FROM other_prothesists_khedma pr 
                            JOIN patient p ON pr.user_id = p.user_id AND pr.patient_number = p.patient_number
                            WHERE 
                            pr.user_id = %s AND pr.patient_number = %s """,(session['id'], Patient_unique))
            found = cursor.fetchone()

            if found :
                if found[0] == PatientF_deleted and found[1] == PatientL_deleted :
                    return render_template("DeletePatient.html", message=f"This Service is still with {found[2]} we can't delete it", csrf_token=new_token)

            cursor.execute("""
                    SELECT versa , b9aw , MONTH(la_date) , YEAR(la_date)  
                    FROM patient 
                    WHERE patient_firstname = %s AND patient_lastname = %s 
                    AND patient_number = %s AND user_id = %s 
                    """,(PatientF_deleted, PatientL_deleted, Patient_unique, session['id']))

            result = cursor.fetchone()

            if not result:
                return render_template("DeletePatient.html", message="Patient doesn't exist", csrf_token=new_token)

            versa = result[0]
            b9aw = result[1]
            month = result[2]
            year = result[3]

            cursor.execute("""
                                UPDATE patient_stat 
                                SET 
                                patient_number = patient_number - 1 ,
                                khalsin = khalsin - %s ,
                                machi_khalsin = machi_khalsin - %s 
                                WHERE user_id = %s AND month = %s AND year = %s 
                                """, (versa, b9aw, session['id'], month, year))

            cursor.execute("DELETE FROM khedma WHERE user_id = %s AND khedma_patient = %s",
                           (session['id'], Patient_unique))

            cursor.execute("""
                DELETE FROM patient
                WHERE patient_firstname = %s AND patient_lastname = %s
                  AND patient_number = %s AND user_id = %s
            """, (PatientF_deleted, PatientL_deleted, Patient_unique, session['id']))

            cursor.execute("""
                            UPDATE patient_history 
                            SET status = 'deleted' 
                            WHERE firstname = %s AND lastname = %s
                            AND pNumber = %s AND user_id = %s
            """, (PatientF_deleted, PatientL_deleted, Patient_unique, session['id']))

            conn.commit()

            cursor.execute("""
                            SELECT * FROM patient 
                            WHERE user_id = %s """, (session['id'],))
            data = cursor.fetchall()

            return render_template("PatientsFile.html", message="Patient Deleted Successfully", data=data, csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            return render_template("DeletePatient.html", error=f"error {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@app.route("/ModifyVersaPatient", methods=["POST", "GET"])
def ModifyVersaPatient():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "ModifyPatientVersa.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        Patient_Id = request.form.get("PatientId", "").strip()
        VersaValue = request.form.get("VersaValue", "").strip()
        ConfirmVersa = request.form.get("ConfirmVersaValue", "").strip()

        if not Patient_Id or not Patient_Id.isdigit() or len(Patient_Id) != 10:
            return render_template(
                "ModifyPatientVersa.html",
                error="Invalide ID",
                csrf_token=new_token
            )

        if not VersaValue or not ConfirmVersa:
            return render_template("ModifyDentistVersement.html", error="Versement cannot be empty",
                                   csrf_token=new_token)

        try:
            VersaValue = float(VersaValue)
            ConfirmVersa = float(ConfirmVersa)
        except (ValueError, TypeError):
            return render_template("ModifyDentistVersement.html", error="Invalid Versement value", csrf_token=new_token)

        if VersaValue != ConfirmVersa:
            return render_template(
                "ModifyPatientVersa.html",
                error="The Versa and its Confirmation must be the same value",
                csrf_token=new_token
            )

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute("""
                            SELECT versa, b9aw, khalsa, MONTH(la_date), YEAR(la_date)
                            FROM patient
                            WHERE user_id = %s AND patient_number = %s
                           """,
                           (session['id'], Patient_Id))

            result = cursor.fetchone()

            if not result:
                return render_template(
                    "ModifyPatientVersa.html",
                    error="Patient Not Found",
                    csrf_token=new_token
                )

            total = round(float(result[0]) + float(result[1]), 2)
            oldVersa = round(float(result[0]), 2)
            oldB9aw = round(float(result[1]), 2)
            oldKhalsa = result[2]
            month = result[3]
            year = result[4]

            if oldKhalsa.lower() == "yes" and VersaValue > 0:
                return render_template(
                    "ModifyPatientVersa.html",
                    message="The Patient already paid his Service",
                    csrf_token=new_token
                )

            new_versa = round(oldVersa + VersaValue, 2)

            if new_versa > total:
                return render_template(
                    "ModifyPatientVersa.html",
                    error="Invalide Versa Amount",
                    csrf_token=new_token
                )

            if new_versa == total:
                b9aw = 0

                cursor.execute("""
                                UPDATE patient
                                SET
                                khalsa = "yes",
                                b9aw = %s,
                                versa = %s
                                WHERE user_id = %s AND patient_number = %s
                               """,
                               (b9aw, new_versa, session['id'], Patient_Id))

                cursor.execute("""
                                UPDATE patient_history
                                SET
                                versement = %s,
                                b9aw = %s
                                WHERE user_id = %s AND pNumber = %s
                               """,
                               (new_versa, b9aw, session['id'], Patient_Id))

                cursor.execute("""
                                UPDATE patient_stat
                                SET
                                khalsin = khalsin + %s,
                                machi_khalsin = machi_khalsin - %s
                                WHERE user_id = %s AND month = %s AND year = %s
                               """,
                               (VersaValue, VersaValue, session['id'], month, year))

                cursor.execute("""
                                UPDATE khedma
                                SET khedma_khalsa = 'yes'
                                WHERE user_id = %s AND khedma_patient = %s
                               """,
                               (session['id'], Patient_Id))

            else:
                b9aw = round(total - new_versa, 2)
                if b9aw > total :
                    return render_template("ModifyDentistVersement.html", message="Invalid Versement",
                                           csrf_token=new_token)

                cursor.execute("""
                                UPDATE patient
                                SET
                                b9aw = %s,
                                versa = %s,
                                khalsa = 'no'
                                WHERE user_id = %s AND patient_number = %s
                               """,
                               (b9aw, new_versa, session['id'], Patient_Id))

                cursor.execute("""
                                UPDATE patient_history
                                SET
                                versement = %s,
                                b9aw = %s
                                WHERE user_id = %s AND pNumber = %s
                               """,
                               (new_versa, b9aw, session['id'], Patient_Id))

                cursor.execute("""
                                UPDATE patient_stat
                                SET
                                khalsin = khalsin + %s,
                                machi_khalsin = machi_khalsin - %s
                                WHERE user_id = %s AND month = %s AND year = %s
                               """,
                               (VersaValue, VersaValue, session['id'], month, year))

                cursor.execute("""
                                DELETE FROM patient 
                                WHERE finished = %s AND khalsa = %s AND user_id = %s 
                                """, ('yes', 'yes', session['id']))

            conn.commit()

            cursor.execute("""
                            SELECT * FROM patient
                            WHERE user_id = %s
                           """,
                           (session['id'],))
            data = cursor.fetchall()

            return render_template(
                "PatientsFile.html",
                message="Informations Updated",
                data=data,
                csrf_token=new_token
            )

        except Exception as e:
            conn.rollback()
            return render_template(
                "ModifyPatientVersa.html",
                error=f"error {str(e)}",
                csrf_token=new_token
            )

        finally:
            cursor.close()
            conn.close()


@app.route("/PatientStat")
def PatietStat():

    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:

        cursor.execute("""
            DELETE FROM patient_stat
            WHERE
                user_id = %s
                AND (
                    year < YEAR(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                    OR (
                        year = YEAR(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                        AND month <= MONTH(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                    )
                )
        """, (session['id'],))

        conn.commit()

        cursor.execute("""
            SELECT *
            FROM patient_stat
            WHERE user_id = %s
            ORDER BY year DESC, month DESC
        """, (session['id'],))

        row = cursor.fetchall()

        print("PATIENT STAT:", row)

        return render_template(
            "PatientsFile.html",
            stat=row
        )

    finally:
        cursor.close()
        conn.close()


@app.route("/PatientHistory", methods=["POST", "GET"])
def getHistory():
    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:

        if request.method == "GET":
            token = secrets.token_hex(16)
            session["csrf_token"] = token

            conn = get_connection()
            cursor = conn.cursor()

            try :
                cursor.execute("""
                                SELECT * FROM patient_history 
                                WHERE user_id = %s """,(session['id'],))
                result = cursor.fetchall()

                if result :
                    return render_template(
                        "PatientHistory.html",
                        History=result,
                        csrf_token=token
                    )
                else :
                    return render_template(
                        "PatientHistory.html",
                        message="No History",
                        csrf_token=token
                    )

            finally :
                cursor.close()
                conn.close()

        if request.method == "POST":
            form_token = request.form.get("csrf_token")
            session_token = session.get("csrf_token")

            #print("FORM TOKEN --> ",form_token)
            #print("SESSION TOKEN --> ",session['csrf_token'])

            #print( form_token == session['csrf_token'])

            if not form_token or form_token != session_token:
                return "CSRF attack detected", 403

            new_token = secrets.token_hex(16)
            session["csrf_token"] = new_token


            patientName = request.form.get("SearchName")

            if patientName.isdigit():
                if not patientName or not patientName.isdigit() or int(patientName) < 0 or len(patientName) < 10:
                    return render_template("PatientHistory.html",
                                           message="Invalide ID ",
                                           csrf_token=new_token)
                # here the patientName is the patient number because the condition is True
                cursor.execute("""
                                SELECT * FROM patient_history 
                                WHERE pNumber = %s AND user_id = %s 
                                """,(patientName, session['id']))
                result = cursor.fetchall()
                if result:
                    return render_template("PatientHistory.html", HistoryPatient=result, csrf_token=new_token)
                else:
                    return render_template("PatientHistory.html", message="Patient Not Found", csrf_token=new_token)

            cursor.execute("""
                SELECT * FROM patient_history
                WHERE user_id = %s AND LOWER(firstname) = LOWER(%s)
            """, (session['id'], patientName))
            result = cursor.fetchall()

            if not result :
                cursor.execute("""
                                SELECT * FROM patient_history
                                WHERE user_id = %s AND LOWER(lastname) = LOWER(%s)
                            """, (session['id'], patientName))
                result = cursor.fetchall()

            if result:
                return render_template("PatientHistory.html", HistoryPatient=result, csrf_token=new_token)
            else:
                return render_template("PatientHistory.html", message="Patient Not Found", csrf_token=new_token)

    finally:
        cursor.close()
        conn.close()


@app.route("/AllPatientsHistory")
def getAllHistory():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    token = secrets.token_hex(16)
    session['csrf_token'] = token

    try:
        cursor.execute("""
                        DELETE FROM patient_history 
                        WHERE 
                            pDate <= DATE_SUB(CURDATE() , INTERVAL 6 MONTH) AND user_id = %s """,
                       (session['id'],))
        conn.commit()

        cursor.execute("SELECT * FROM patient_history WHERE user_id = %s", (session['id'],))
        resultAll = cursor.fetchall()
        if resultAll:
            return render_template("PatientHistory.html", History=resultAll, csrf_token=token)
        else:
            return render_template("PatientHistory.html", message="Table not found", csrf_token=token)
    finally:
        cursor.close()
        conn.close()


@app.route("/PatientByDateASC")
def ShowByDateASC():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("SELECT * FROM patient WHERE user_id = %s ORDER BY la_date ASC", (session['id'],))
        rows = cursor.fetchall()
        return render_template("PatientsFile.html", dataASC=rows)
    finally:
        cursor.close()
        conn.close()


@app.route("/PatientByDateDESC")
def ShowByDateDESC():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("SELECT * FROM patient WHERE user_id = %s ORDER BY la_date DESC", (session['id'],))
        rows = cursor.fetchall()
        return render_template("PatientsFile.html", dataDESC=rows)
    finally:
        cursor.close()
        conn.close()

@app.route("/PatientByDeadLine")
def ShowByDeadLine():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try :
        cursor.execute("""
                       SELECT * FROM patient 
                       WHERE user_id = %s 
                       ORDER BY DeadLine ASC """,(session['id'],))
        dateDeadLine = cursor.fetchall()
        return render_template("PatientsFile.html", dateDeadLine=dateDeadLine)

    finally:
        cursor.close()
        conn.close()



@app.route("/PatientByB9aw")
def ShowByB9aw():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("SELECT * FROM patient WHERE user_id = %s ORDER BY b9aw DESC", (session['id'],))
        rows = cursor.fetchall()
        return render_template("PatientsFile.html", dataPrice=rows)
    finally:
        cursor.close()
        conn.close()


@app.route("/UpdatePatientStatus" , methods=["POST" , "GET"])
def UpdatePatientStatus():
    if not is_logged_in():
        return jsonify({
            'success' :False,
            'message' : "user not allowed"
        }),401


    data = request.get_json()

    if not data :
        return jsonify({
            'success' : False,
            'message' : 'data not recieved'
        }),401

    patientID = data.get('patient_number')
    status = data.get('status')

    if not patientID or not status :
        return jsonify({
            'success' : False,
            'message' : 'Patient number and status are required'
        }),403

    allowed_status = [
        'in process',
        'prothesist',
        'montage',
        'esseyage',
        'finished'
    ]

    if status not in allowed_status :
        return jsonify({
            'success' : False,
            'message' : 'Invalide status value'
        }),403

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try :

        cursor.execute("""
                        SELECT 1 
                        FROM patient 
                        WHERE user_id = %s AND patient_number = %s """,
                       (session['id'], patientID))

        found = cursor.fetchone()

        if not found :
            return jsonify({
                'success' : False,
                'message' : 'Patient not found'
            }),403

        cursor.execute("""
                        UPDATE patient 
                        SET status = %s 
                        WHERE user_id = %s AND patient_number = %s """,
                       (status, session['id'], patientID))
        conn.commit()

        print("Patient ID:", patientID)
        print("New status:", status)
        print("Rows updated:", cursor.rowcount)

    except Exception as e:
        conn.rollback()
        return jsonify({
            'success' : False,
            'message' : f'error {str(e)}'
        })

    finally :
        cursor.close()
        conn.close()

    return jsonify({
        'success' : True,
        'message' : 'Status updated successfully'
    })




# ============================== DENTISTS =====================================

@app.route("/Dentist", methods=["POST", "GET"])
def DentistPage():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token
        print(f"GET - Generated token: {token}")# Debug

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try :

            cursor.execute("""
                            DELETE FROM dentists 
                            WHERE 
                            finished = %s AND khalsa = %s AND user_id = %s """,
                           ('yes', 'yes', session['id']))
            conn.commit()

            cursor.execute("SELECT * FROM dentists WHERE user_id = %s ",
                           (session["id"],))
            rows = cursor.fetchall()

        finally :
            cursor.close()
            conn.close()

        return render_template("DentistFile.html", result=rows, csrf_token=token)

    # POST request handling
    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:

        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        # Debug prints
        print(f"POST - Form token: {form_token}")
        print(f"POST - Session token: {session_token}")
        print(f"POST - Tokens match: {form_token == session_token}")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        token = secrets.token_hex(16)
        session["csrf_token"] = token

        DentistName = request.form.get("SearchBar")
        if SearcheTable(cursor, DentistName):
            cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                           (session["id"], DentistName))
            rows = cursor.fetchall()

            return render_template("DentistFile.html", result=rows, csrf_token=token)

        elif DentistName.isdigit() :
            if not DentistName or not DentistName.isdigit() or int(DentistName) < 0 :
                return render_template("DentistFile.html",
                                       message="Invalide ID ", csrf_token=token)

            cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND patient_number = %s",
                           (session['id'], DentistName))
            rows = cursor.fetchall()

            return render_template("DentistFile.html", result=rows, csrf_token=token)

        else:
            return render_template("DentistFile.html", error=f"Dentist {DentistName} Not Found or Patient not found", csrf_token=token)
    finally:
        cursor.close()
        conn.close()


@app.route("/AddDentist", methods=["POST", "GET"])
def AddDentist():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "AddDentist.html",
            csrf_token=token
        )

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        if request.method == "POST":
            form_token = request.form.get("csrf_token")
            session_token = session.get("csrf_token")

            if not form_token or form_token != session_token:
                return "CSRF attack detected", 403

            new_token = secrets.token_hex(16)
            session["csrf_token"] = new_token


            dentist_name = request.form.get("AddDentists")
            if not dentist_name or dentist_name.isdigit():
                return render_template("AddDentist.html", message="Invalide Dentist name", csrf_token=new_token)


            if not SearcheTable(cursor, dentist_name):
                AddDentistTable(cursor, conn, dentist_name)
                return render_template("AddDentist.html", message=f"Dentist {dentist_name} Added Successfully", csrf_token=new_token)
            else:
                return render_template("AddDentist.html", message="Dentist Already exists", csrf_token=new_token)
    finally:
        cursor.close()
        conn.close()


@app.route("/DeleteDentist", methods=["POST", "GET"])
def DeleteDentist():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "DeleteDentist.html",
            csrf_token=token
        )

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        if request.method == "POST":
            form_token = request.form.get("csrf_token")
            session_token = session.get("csrf_token")

            if not form_token or form_token != session_token:
                return "CSRF attack detected", 403

            new_token = secrets.token_hex(16)
            session["csrf_token"] = new_token


            Dentist_deleted = request.form.get("DeleteDentist")
            Confirm_Dentist = request.form.get("ConfirmDeleteDentist")

            if SearcheTable(cursor, Dentist_deleted):
                if Dentist_deleted != Confirm_Dentist:
                    return render_template("DeleteDentist.html", message="Invalide Confirmation", csrf_token=new_token)

                cursor.execute("DELETE FROM dentists WHERE user_id = %s AND dentist_name = %s",
                               (session['id'], Dentist_deleted))

                cursor.execute("DELETE FROM dentist_registry WHERE user_id = %s AND dentist_name = %s",
                               (session['id'], Dentist_deleted))

                cursor.execute("DELETE FROM khedma WHERE user_id = %s AND khedma_dentist = %s",
                               (session['id'], f"Dr.{Dentist_deleted}"))

                conn.commit()
                return render_template("DeleteDentist.html", message="Dentist Deleted Successfully", csrf_token=new_token)
            else:
                return render_template("DeleteDentist.html", message="Dentist doesn't exist", csrf_token=new_token)

    except Exception as e:
        conn.rollback()
        return render_template("DeleteDentist.html", message=f"error {str(e)}", csrf_token=new_token)

    finally:
        cursor.close()
        conn.close()


@app.route("/GetFromDentist", methods=["POST", "GET"])
def Get_From_Dentist():

    # ==========================================
    # CHECK LOGIN
    # ==========================================

    if not is_logged_in():
        return redirect(url_for('home'))


    # ==========================================
    # GET REQUEST
    # ==========================================

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token
        print("GET - Generated token:", token)
        return render_template(
            "GetFromDentist.html",
            csrf_token=token)


    # ==========================================
    # POST REQUEST
    # ==========================================

    if request.method == "POST":

        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        print("POST - Form token:", form_token)
        print("POST - Session token:", session_token)

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        # ======================================
        # GET BASIC FORM VALUES
        # ======================================

        dentist = request.form.get("Dentistinput")
        firstName = request.form.get("PatientFirstName")
        lastName = request.form.get("PatientLastName")
        unique = request.form.get("PatientUnique")
        choice = request.form.get("KhedmaChoice")
        price = request.form.get("KhedmaPrice")
        khalsa = request.form.get("Khalsa")
        date = request.form.get("date")
        deadLine = request.form.get("DeadLine")

        # IMPORTANT:
        # This is now .get() instead of ['OtherPro']
        ProCheck = request.form.get("OtherPro")


        print("FORM DATA:", request.form)


        # ======================================
        # BASIC VALIDATION
        # ======================================

        if not dentist or not dentist.strip():

            return render_template(
                "GetFromDentist.html",
                error="Dentist name cannot be empty",
                csrf_token=new_token
            )


        if not firstName or not firstName.strip():

            return render_template(
                "GetFromDentist.html",
                error="Patient first name cannot be empty",
                csrf_token=new_token
            )


        if not lastName or not lastName.strip():

            return render_template(
                "GetFromDentist.html",
                error="Patient last name cannot be empty",
                csrf_token=new_token
            )

        if not unique or not unique.isdigit() or len(unique) >= 10:
            return render_template("GetFromDentist.html",
                                   message="Invalide Patient ID ",
                                   csrf_token=new_token)

        if not choice or not choice.strip():

            return render_template(
                "GetFromDentist.html",
                error="Invalid Choice",
                csrf_token=new_token
            )


        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            if not SearcheTable(cursor, dentist):
                return render_template(
                    "GetFromDentist.html",
                    error="Dentist doesn't exist",
                    csrf_token=new_token
                )

            if not price:
                return render_template(
                    "GetFromDentist.html",
                    error="Price cannot be empty",
                    csrf_token=new_token
                )

            try:

                if not checkValue(price):
                    return render_template(
                        "GetFromDentist.html",
                        error="Invalid Price value",
                        csrf_token=new_token
                    )

                price = float(price)

            except (ValueError, TypeError):
                return render_template(
                    "GetFromDentist.html",
                    error="Invalid Price Value",
                    csrf_token=new_token
                )

            if not khalsa or khalsa.strip().lower() not in ["yes", "no"]:
                return render_template(
                    "GetFromDentist.html",
                    error="You must put 'yes' or 'no' in Khalsa",
                    csrf_token=new_token
                )


            if not date or not deadLine:
                return render_template(
                    "GetFromDentist.html",
                    error="Date and deadline are required",
                    csrf_token=new_token
                )


            if deadLine < date:
                return render_template(
                    "GetFromDentist.html",
                    error="Invalid Deadline",
                    csrf_token=new_token
                )


            cursor.execute(
                """
                SELECT id
                FROM dentists
                WHERE user_id = %s AND patient_number = %s AND dentist_name = %s
                """,( session["id"], unique, dentist ))

            if cursor.fetchone():
                return render_template("GetFromDentist.html", message="Unique number already exists")


            # ==================================
            # CHECK OTHER PROTHESIST
            # ==================================

            if not ProCheck or ProCheck.strip().lower() not in ["yes", "no"]:
                return render_template(
                    "GetFromDentist.html",
                    error="You must select Yes or No in the Prothesist check part",
                    csrf_token=new_token
                )


            # ==================================
            # DENTIST PAYMENT VALUES
            # ==================================

            if khalsa.lower() == "yes":
                versement = price
                b9aw = 0
            else:
                versement = 0
                b9aw = price

            dentist_khalsa = 'yes' if b9aw == 0 else 'no'


            # ==================================
            # DEFAULT PROTHESIST VALUES
            # ==================================

            ProName = None
            ProNumber = 0
            ProPrice = 0
            ProDate = None
            ProDeadLine = None
            ProKhalsa = None
            Proversa = "no"
            ProVersa = 0
            Prob9aw = 0


            # ==================================
            # OTHER PROTHESIST = YES
            # ==================================

            if ProCheck.lower() == "yes":

                # ----------------------------------
                # GET PROTHESIST FORM VALUES
                # ----------------------------------

                ProName = request.form.get("ProName")
                ProNumber = request.form.get("ProNumber")
                ProPrice = request.form.get("ProPrice")
                ProDate = request.form.get("ProDate")
                ProDeadLine = request.form.get("ProDeadLine")
                ProKhalsa = request.form.get("ProKhalsa")
                Proversa = request.form.get("Proversa")

                # IMPORTANT:
                # This can be missing/empty depending on
                # the user's selections.
                ProVersa = request.form.get("ProVersaAmount")


                # ----------------------------------
                # PROTHESIST NAME
                # ----------------------------------

                if not ProName or not ProName.strip():

                    return render_template(
                        "GetFromDentist.html",
                        error="Prothesist Name must not be empty",
                        csrf_token=new_token
                    )


                # ----------------------------------
                # PROTHESIST NUMBER
                # ----------------------------------

                if not ProNumber or not ProNumber.isdigit():

                    return render_template(
                        "GetFromDentist.html",
                        error="Prothesist Number must be a positive number",
                        csrf_token=new_token
                    )


                if int(ProNumber) < 0:

                    return render_template(
                        "GetFromDentist.html",
                        error="Prothesist Number must be a positive number",
                        csrf_token=new_token
                    )


                # ----------------------------------
                # PROTHESIST PRICE
                # ----------------------------------

                if not ProPrice:
                    return render_template(
                        "GetFromDentist.html",
                        error="Prothesist Price cannot be empty",
                        csrf_token=new_token
                    )

                try:
                    ProPrice = float(ProPrice)

                    if ProPrice < 0:
                        raise ValueError

                except (ValueError, TypeError):

                    return render_template(
                        "GetFromDentist.html",
                        error="Invalid Prothesist Price",
                        csrf_token=new_token
                    )


                # ----------------------------------
                # PROTHESIST DATES
                # ----------------------------------

                if not ProDate or not ProDeadLine:
                    return render_template("GetFromDentist.html",error="Prothesist Date and Deadline are required",
                        csrf_token=new_token
                    )

                if ProDate < date:
                    return render_template("GetFromDentist.html",error="Invalid Prothesist Date",
                        csrf_token=new_token
                    )


                if ProDeadLine < ProDate:
                    return render_template("GetFromDentist.html",error="Invalid Prothesist Dead Line",
                        csrf_token=new_token
                    )


                if ProDeadLine > deadLine:
                    return render_template("GetFromDentist.html",error="Prothesist Deadline cannot be after Dentist Deadline",
                        csrf_token=new_token
                    )


                # ----------------------------------
                # PROTHESIST KHALSA
                # ----------------------------------

                if not ProKhalsa or ProKhalsa.lower() not in ["yes", "no"]:
                    return render_template(
                        "GetFromDentist.html",
                        error="You must put 'yes' or 'no' in Prothesist Khalsa",
                        csrf_token=new_token
                    )


                # ==================================
                # PROTHESIST FULLY PAID
                # ==================================

                if ProKhalsa.lower() == "yes":
                    # Fully paid
                    ProVersa = ProPrice
                    Proversa = "yes"
                    Prob9aw = 0


                # ==================================
                # PROTHESIST NOT FULLY PAID
                # ==================================

                else:
                    # ----------------------------------
                    # CHECK VERSEMENT
                    # ----------------------------------

                    if not Proversa or Proversa.lower() not in ["yes", "no"]:
                        return render_template(
                            "GetFromDentist.html",
                            error="Please select Yes or No for Prothesist Versa",
                            csrf_token=new_token
                        )

                    # ----------------------------------
                    # NO VERSEMENT
                    # ----------------------------------

                    if Proversa.lower() == "no":
                        ProVersa = 0
                        Prob9aw = ProPrice

                    # ----------------------------------
                    # VERSEMENT = YES
                    # ----------------------------------

                    else:

                        if not ProVersa:
                            return render_template("GetFromDentist.html", error="Please enter the Prothesist Versa amount",
                                csrf_token=new_token
                            )


                        try:
                            ProVersa = float(ProVersa)

                        except (ValueError, TypeError):

                            return render_template(
                                "GetFromDentist.html",
                                error="Invalid Prothesist Versa amount",
                                csrf_token=new_token
                            )

                        if ProVersa < 0:
                            return render_template("GetFromDentist.html", error="Prothesist Versa cannot be negative",
                                csrf_token=new_token
                            )


                        if ProVersa > ProPrice:
                            return render_template("GetFromDentist.html", message="Prothesist Versa must not be bigger than his price",
                                csrf_token=new_token
                            )

                        Prob9aw = round( ProPrice - ProVersa, 2 )

                # ==================================
                # CHECK PROTHESIST EXISTENCE
                # ==================================

                cursor.execute("""
                                SELECT id
                                FROM other_prothesists
                                WHERE pName = %s
                                AND pNumber = %s
                                AND user_id = %s
                                """, ( ProName, ProNumber, session["id"] ))

                # ==================================
                # INSERT PROTHESIST IF NOT EXISTS
                # ==================================

                if not cursor.fetchone():
                    return render_template("GetFromDentist.html", error="Prothesist not found", csrf_token=new_token)

                cursor.execute(
                    """
                    INSERT INTO other_prothesists_khedma
                    ( user_id, patient_number, dentist_name, pName, pNumber, pDate, pKhedma, pPrice, pVersa, pB9aw, 
                    pKhalsa, pFinished, DeadLine )
                    VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s ) """,( session['id'], unique, dentist, ProName, ProNumber, ProDate, choice, ProPrice, ProVersa,
                          Prob9aw, ProKhalsa, "no", ProDeadLine ))

                Prothesist_History(cursor,conn,ProName,ProNumber,unique)

                ProthesistsStat( cursor, conn, ProPrice, ProNumber, ProName,
                                 ProKhalsa, ProDate, ProVersa )

            status = 'in process'
            infos = [ session["id"], dentist, firstName, lastName, unique, choice, price,
                      versement, b9aw, "no", dentist_khalsa, date, deadLine, status ]

            if ProCheck == 'yes':
                infos[13] = 'prothesist'

            cursor.execute(
                """
                INSERT INTO dentists
                    ( user_id, dentist_name, patient_firstname, patient_lastname, patient_number, 
                    Dkhedma, price, versement, b9aw, finished, khalsa, date, DeadLine, status )
                VALUES
                    ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s ) """
                , tuple(infos) )

            if ProCheck.lower() == "yes":
                prothesist_name = ProName
                prothesist_number = ProNumber
            else:
                prothesist_name = None
                prothesist_number = 0


            cursor.execute(
                """
                INSERT INTO khedma
                    ( khedman, khedma_price, khedma_date, khedma_dentist, khedma_patient, 
                    khedma_wajda, khedma_khalsa, prothesist_name, prothesist_number, user_id, DeadLine )
                VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s )
                """,
                ( choice, price, date, f"Dr.{dentist}", unique, "no", dentist_khalsa,
                  prothesist_name, prothesist_number, session["id"], deadLine ) )

            Dentist_History( cursor, conn, dentist )

            DentistStats( cursor, conn, dentist, price, khalsa, date )


            conn.commit()

            cursor.execute(
                """
                SELECT *
                FROM dentists
                WHERE user_id = %s
                """,
                (session["id"],)
            )

            result = cursor.fetchall()


            return render_template(
                "DentistFile.html",
                message="Khedma Added Successfully",
                result=result
            )

        except Exception as e:
            conn.rollback()
            print("ERROR IN /GetFromDentist:", e)
            return render_template(
                "GetFromDentist.html",
                error=f"An error occurred: {str(e)}",
                csrf_token=new_token
            )

        finally:
            cursor.close()
            conn.close()


@app.route("/DentistVersement" , methods=["POST" , "GET"])
def ModifyDentistVersement():
    if not is_logged_in():
        return redirect(url_for("home"))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "ModifyDentistVersement.html",
            csrf_token=token
        )

    if request.method == "POST" :
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        DentistName = request.form.get('DName')
        KhedmaId = request.form.get('KhedmaId')
        Versement = request.form.get('Versement')

        if not Versement:
            return render_template("ModifyDentistVersement.html", error="Versement cannot be empty", csrf_token=new_token)

        try:
            Versement = float(Versement)
        except (ValueError, TypeError):
            return render_template("ModifyDentistVersement.html", error="Invalid Versement value", csrf_token=new_token)

        #if Versement < 0:
         #   return render_template("ModifyDentistVersement.html", error="Versement cannot be negative", csrf_token=new_token)


        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try :
            cursor.execute("""
                            SELECT price, khalsa, versement, b9aw, MONTH(date), YEAR(date) 
                            FROM dentists 
                            WHERE user_id = %s AND dentist_name = %s AND patient_number = %s """
                           ,(session['id'] , DentistName , KhedmaId ))
            result = cursor.fetchone()

            if not result :
                return render_template("ModifyDentistVersement.html" , message="Khedma not found ", csrf_token=new_token)

            price = result[0]
            oldkhalsa = result[1]
            oldversement = float(result[2])
            month = result[4]
            year = result[5]

            if oldkhalsa.lower() == "yes" and Versement > 0 :
                cursor.execute("SELECT * FROM dentists WHERE user_id = %s ",(session['id'],))
                result = cursor.fetchall()
                return render_template("DentistFile.html" , message="Khedma Already Khalsa", result=result, csrf_token=new_token)

            NewVersement = oldversement + Versement

            if NewVersement > price :
                return render_template("ModifyDentistVersement.html" , error="Invalide versement", csrf_token=new_token)

            elif NewVersement == price :
                b9aw = 0

                cursor.execute("""
                                UPDATE dentists 
                                SET 
                                khalsa = "yes",  
                                versement = %s ,
                                b9aw = %s 
                                WHERE user_id = %s AND dentist_name = %s AND patient_number = %s
                                """,(NewVersement, b9aw, session['id'], DentistName, KhedmaId ))

                cursor.execute("""
                                UPDATE dentist_history 
                                SET 
                                versement = %s , b9aw = %s  
                                WHERE user_id = %s AND dentistname = %s AND pNumber = %s 
                                """,(NewVersement, b9aw, session['id'], DentistName, KhedmaId))

                cursor.execute("""
                                UPDATE khedma 
                                SET khedma_khalsa = 'yes' 
                                WHERE user_id = %s AND khedma_patient = %s """,(session['id'], KhedmaId))

                cursor.execute("""
                                UPDATE dentist_stat 
                                SET 
                                khalsin = khalsin + %s ,
                                machi_khalsin = machi_khalsin - %s
                                WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s """
                               ,(Versement, Versement, session['id'], DentistName, month, year ) )


                cursor.execute("""
                                SELECT * FROM dentists
                                WHERE user_id = %s """, (session['id'],))

                result = cursor.fetchall()
                conn.commit()

                return render_template("DentistFile.html", message="Informations Updated Successeful", result=result,
                                       csrf_token=new_token)

            else:
                b9aw = price - NewVersement

                if b9aw > price :
                    return render_template("ModifyDentistVersement.html", message="Invalid Versement",
                                           csrf_token=new_token)


                cursor.execute("""
                                 UPDATE dentists 
                                 SET 
                                 khalsa = "no",  
                                 versement = %s ,
                                 b9aw = %s 
                                 WHERE user_id = %s AND dentist_name = %s AND patient_number = %s
                                 """, (NewVersement, b9aw, session['id'], DentistName, KhedmaId))

                cursor.execute("""
                                UPDATE dentist_history 
                                SET 
                                versement = %s , b9aw = %s 
                                WHERE user_id = %s AND dentistname = %s AND pNumber = %s 
                                """, (NewVersement, b9aw, session['id'], DentistName, KhedmaId))

                cursor.execute("""
                                UPDATE dentist_stat 
                                SET 
                                khalsin = khalsin + %s ,
                                machi_khalsin = machi_khalsin - %s
                                WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s """
                               , (Versement, Versement, session['id'], DentistName, month, year))

                conn.commit()

                cursor.execute("""
                                SELECT * FROM dentists
                                 WHERE user_id = %s """,(session['id'],))

                result = cursor.fetchall()

                return render_template("DentistFile.html" , message="Information Updated Sucssufully", result=result, csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("ModifyDentistVersement.html", error=f"error {str(e)}", csrf_token=new_token)

        finally :
            cursor.close()
            conn.close()


@app.route("/DeleteDentistPatient", methods=["POST" , "GET"])
def DeleteDentistKhedma():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "DeleteDentistPatient.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        Dentist_name = request.form.get("DentistName")
        PatientF_deleted = request.form.get("DeleteF")
        Confirm_PatientF = request.form.get("ConfirmDeletePatientF")
        PatientL_deleted = request.form.get("DeleteL")
        Confirm_PatientL = request.form.get("ConfirmDeletePatientL")
        Patient_unique   = request.form.get("uniquepatient")
        Confirm_Unique   = request.form.get("confirmunique")

        if not Patient_unique.isdigit() or len(Patient_unique) >= 10:
            return render_template("DeleteDentistPatient.html", error="Invalid Unique number", csrf_token=new_token)

        if (PatientF_deleted != Confirm_PatientF or
                PatientL_deleted != Confirm_PatientL or
                Patient_unique != Confirm_Unique):
            return render_template("DeleteDentistPatient.html", error="Invalid Confirmation", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)
        try:

            cursor.execute("""
                    SELECT price, khalsa, MONTH(date), YEAR(date), versement, b9aw  
                    FROM dentists 
                    WHERE dentist_name = %s AND patient_firstname = %s AND patient_lastname = %s 
                    AND patient_number = %s AND user_id = %s 
                    """,(Dentist_name , PatientF_deleted, PatientL_deleted, Patient_unique, session['id']))

            result = cursor.fetchone()

            if not result :
                return render_template("DeleteDentistPatient.html"
                                       ,message="Patient not found", csrf_token=new_token )

            price = result[0]
            khalsa = result[1]
            month = result[2]
            year = result[3]
            versement = result[4]
            b9aw = result[5]

            cursor.execute("""
                            SELECT d.patient_firstname, d.patient_lastname, pr.pName 
                            FROM other_prothesists_khedma pr 
                            JOIN dentists d ON pr.user_id = d.user_id AND pr.patient_number = d.patient_number
                            WHERE 
                            pr.user_id = %s AND pr.patient_number = %s """, (session['id'], Patient_unique))
            found = cursor.fetchone()

            if found :
                if found[0] == PatientF_deleted and found[1] == PatientL_deleted:
                    return render_template("DeleteDentistPatient.html",
                                           message=f"This Service is still with {found[2]} we can't delete it",
                                           csrf_token=new_token)

            if khalsa.lower() == "yes":
                cursor.execute("""
                                UPDATE dentist_stat 
                                SET 
                                total_khedma = total_khedma - 1 ,
                                khalsin = khalsin - %s , 
                                WHERE dentist_name = %s AND user_id = %s AND month = %s AND year = %s 
                                """, (price, price, Dentist_name , session['id'], month, year))
            else :
                cursor.execute("""
                                UPDATE dentist_stat 
                                SET 
                                total_khedma = total_khedma - 1 ,
                                khalsin = khalsin - %s ,
                                machi_khalsin = machi_khalsin - %s 
                                WHERE dentist_name = %s AND user_id = %s AND month = %s AND year = %s """,
                                (versement, b9aw, Dentist_name , session['id'] , month , year))

            cursor.execute("""
                            UPDATE dentist_history 
                            SET status = 'deleted' 
                            WHERE 
                            user_id = %s AND dentistname = %s AND pFirstname = %s AND pLastname = %s AND pNumber = %s  """,
                           (session['id'], Dentist_name, PatientF_deleted, PatientL_deleted, Patient_unique))


            cursor.execute("DELETE FROM khedma WHERE user_id = %s AND khedma_patient = %s AND khedma_dentist = %s " ,
                           (session['id'], Patient_unique, f"Dr.{Dentist_name}"))

            cursor.execute("""
                DELETE FROM dentists
                WHERE dentist_name = %s AND patient_firstname = %s AND patient_lastname = %s
                  AND patient_number = %s AND user_id = %s
            """, (Dentist_name, PatientF_deleted, PatientL_deleted, Patient_unique, session['id']))
            conn.commit()

            cursor.execute("SELECT * FROM dentists WHERE user_id = %s ",
                           (session["id"],))
            rows = cursor.fetchall()

            return render_template("DentistFile.html", message="Patient Deleted Successfully", result=rows, csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("DeleteDentistPatient.html", error=f"error {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@app.route("/DentistHistory", methods=["POST", "GET"])
def getDentistHistory():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        print("========== GET /DentistHistory ==========")
        print("GENERATED TOKEN:", repr(token))
        print("SESSION TOKEN:", repr(session.get("csrf_token")))

        conn = get_connection()
        cursor = conn.cursor()

        try :
            cursor.execute("SELECT * FROM dentist_history WHERE user_id = %s", (session['id'],))
            result = cursor.fetchall()
            if result:
                return render_template(
                    "DentistHistory.html",
                    History=result,
                    csrf_token=token,
                    my_test_token=token
                )
            else:
                return render_template(
                    "DentistHistory.html",
                    message="Table not found",
                    csrf_token=token,
                    my_test_token=token
                )
        finally :
            cursor.close()
            conn.close()

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        print("FORM TOKEN --> ",form_token)
        print("SESSION TOKEN --> ",session['csrf_token'])
        print(form_token == session['csrf_token'])

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        dentist_name = request.form.get("SearchName")

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            if dentist_name.isdigit():
                # dentist name here is the patient number because dentist_name.isdigit() True
                cursor.execute("""
                                SELECT * FROM dentist_history 
                                WHERE user_id = %s AND pNumber = %s 
                                """, (session['id'], dentist_name))
                result = cursor.fetchall()

                if result:
                    return render_template("DentistHistory.html", HistoryDentist=result, csrf_token=new_token)
                else:
                    return render_template("DentistHistory.html", message="Patient not found", csrf_token=new_token)

            cursor.execute("""
                        SELECT * FROM dentist_history
                        WHERE user_id = %s AND dentistname = %s
                    """, (session['id'], dentist_name.lower()))
            result = cursor.fetchall()
            if result:
                return render_template("DentistHistory.html", HistoryDentist=result, csrf_token=new_token)
            else:
                return render_template("DentistHistory.html",
                                       message="Dentist not found", csrf_token=new_token)
        finally:
            cursor.close()
            conn.close()


@app.route("/AllDentistHistory")
def getAllDentistHistory():
    if not is_logged_in():
        return redirect(url_for('home'))

    token = secrets.token_hex(16)
    session['csrf_token'] = token

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("""
                        DELETE FROM dentist_history 
                        WHERE 
                            pDate <= DATE_SUB(CURDATE() , INTERVAL 6 MONTH) AND user_id = %s """,
                       (session['id'],))
        conn.commit()

        cursor.execute("SELECT * FROM dentist_history WHERE user_id = %s", (session['id'],))
        result = cursor.fetchall()
        if result:
            return render_template("DentistHistory.html", History=result, csrf_token=session['csrf_token'])
        else:
            return render_template("DentistHistory.html", message="Table not found", csrf_token=session['csrf_token'])
    finally:
        cursor.close()
        conn.close()


@app.route("/DentistMainTable")
def MainTable():
    if not is_logged_in():
        return redirect(url_for('home'))

    token = secrets.token_hex(16)
    session["csrf_token"] = token

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("SELECT * FROM dentists WHERE user_id = %s", (session['id'],))
        main = cursor.fetchall()
        if main:
            return render_template("DentistFile.html", message="Main Table", main=main, csrf_token=token)  # ✅ Pass token
        else:
            return render_template("DentistFile.html", message="Empty Table", csrf_token=token)  # ✅ Pass token

    finally:
        cursor.close()
        conn.close()


@app.route("/DentistMostKhedma", methods=["GET"])
def FindMostDentistKhedma():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        dentist_dics = DentistsDics(cursor)
        if not dentist_dics:
            return render_template("DentistFile.html", error="No dentist tables found.")
        name, count = max(dentist_dics.items(), key=lambda x: x[1], default=('none', 0))
        if count == 0:
            return render_template("DentistFile.html", message="All tables are empty.")
        cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                       (session['id'], name))
        result = cursor.fetchall()
        return render_template("DentistFile.html", most=result, most_name=name)
    finally:
        cursor.close()
        conn.close()


@app.route("/DentistLessKhedma", methods=["GET"])
def FindLessDentistKhedma():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        dentist_dics = DentistsDics(cursor)
        active_dentists = {n: c for n, c in dentist_dics.items() if c > 0}
        if not active_dentists:
            return render_template("DentistFile.html", message="All dentists currently have 0 Services.")
        name, count = min(active_dentists.items(), key=lambda x: x[1])
        cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                       (session['id'], name))
        result = cursor.fetchall()
        return render_template("DentistFile.html", less=result, less_name=name)
    finally:
        cursor.close()
        conn.close()

@app.route("/DentistDeadLine")
def ShowDeadLine():
    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try :
        cursor.execute("""
                        SELECT * FROM dentists WHERE user_id = %s 
                        ORDER BY DeadLine ASC """,(session['id'],))
        dateDeadLine = cursor.fetchall()
        return render_template("DentistFile.html" , dateDeadLine=dateDeadLine)

    finally:
        cursor.close()
        conn.close()


@app.route("/DentistTotal", methods=["GET"])
def ShowTotal():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        current_dentists = GetAllDentistTables(cursor)
        result = {}
        for dentist_name in current_dentists:
            try:
                cursor.execute("""
                    SELECT SUM(b9aw) FROM dentists
                    WHERE user_id = %s AND khalsa = %s AND dentist_name = %s
                """, (session['id'], "no", dentist_name))
                row = cursor.fetchone()
                cursor.fetchall()
                result[dentist_name] = row[0] if row and row[0] is not None else 0
            except Exception as e:
                print(f"Error on {dentist_name}: {e}")
                result[dentist_name] = 0
        if result:
            return render_template("DentistFile.html", total=result)
        return render_template("DentistFile.html", message="No dentist data found.")
    finally:
        cursor.close()
        conn.close()



@app.route("/DentistsStat")
def DentistsStat():

    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        # Delete statistics older than 12 months
        cursor.execute("""
            DELETE FROM dentist_stat
            WHERE user_id = %s
              AND (
                    year < YEAR(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                    OR (
                        year = YEAR(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                        AND month <= MONTH(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                    )
              )
        """, (session['id'],))
        conn.commit()

        # Delete empty statistics
        cursor.execute("""
            DELETE FROM dentist_stat
            WHERE total_khedma = 0
              AND khalsin = 0
              AND machi_khalsin = 0
              AND user_id = %s
        """, (session['id'],))

        conn.commit()

        # Get all dentists
        dentists_list = GetAllDentistTables(cursor)
        result = {}
        for dentist in dentists_list:

            cursor.execute("""
                SELECT *
                FROM dentist_stat
                WHERE user_id = %s
                  AND dentist_name = %s
                ORDER BY year DESC, month DESC
            """, (session['id'], dentist))

            rows = cursor.fetchall()

            # Only add dentist if statistics exist
            if rows:
                result[dentist] = rows

        # Statistics found
        if result:
            return render_template(
                "DentistFile.html",
                message="The Stat Table",
                result=result)

        # No statistics found
        return render_template(
            "DentistFile.html",
            message="Table Not Found (There are no statistics)")

    except Exception as e:
        conn.rollback()
        return render_template(
            "DentistFile.html",
            message=f"error {str(e)}")

    finally:
        cursor.close()
        conn.close()


@app.route("/UpdateDentistStatus", methods=['POST' , 'GET'])
def UpdateDentistStatus():
    if not is_logged_in():
        return jsonify({
            'success': False,
            'message': 'User not allowed'
        }),403

    data = request.get_json()

    if not data :
        return jsonify({
            'success': False,
            'message' : 'No data recieved'
        }),403

    patientNumber = data.get('patient_number')
    status = data.get('status')
    dentistName = data.get('dentist_name')

    allowed_status = [
        'in process',
        'prothesist',
        'montage',
        'esseyage',
        'finished'
    ]

    if status not in allowed_status :
        return jsonify({
            'success' : False,
            'message' : 'Invalide status value'
        }),403

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try :

        cursor.execute("""
                        SELECT 1 FROM dentists 
                        WHERE dentist_name = %s AND patient_number = %s AND user_id = %s """
                       ,(dentistName, patientNumber, session['id']))
        found = cursor.fetchone()

        if not found :
            return jsonify({
                'success' : False,
                'message' : 'Patient not found'
            }),400

        cursor.execute("""
                        UPDATE dentists 
                        SET status = %s 
                        WHERE dentist_name = %s AND patient_number = %s AND user_id = %s """
                       ,(status, dentistName, patientNumber, session['id']))
        conn.commit()

    except Exception as e:
        conn.rollback()
        return jsonify({
            'success' : False,
            'message' : f'error {str(e)}'
        })

    finally :
        cursor.close()
        conn.close()

    return jsonify({
        'success' : True,
        'message' : 'Status updated successfully'
    })

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

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

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

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

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
                    return render_template("FinishedKhedma.html", error="Invalid Patient ID", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("FinishedKhedma.html", error="Invalid Service ID", csrf_token=new_token)

                # Verify patient record exists
                cursor.execute("""
                    SELECT 1 
                    FROM patient_history
                    WHERE id = %s AND user_id = %s AND pNumber = %s
                """, (khedmaID, session['id'], patientId))
                patient_row = cursor.fetchone()

                if not patient_row:
                    return render_template("FinishedKhedma.html", message="Patient Not Found", csrf_token=new_token)

                # Verify service entry
                cursor.execute("""
                    SELECT p.id, k.id 
                    FROM patient p 
                    LEFT JOIN khedma k ON p.patient_number = k.khedma_patient AND k.user_id = p.user_id
                    WHERE p.user_id = %s AND p.patient_number = %s
                """, (session['id'], patientId))

                result = cursor.fetchone()

                if not result:
                    return render_template("FinishedKhedma.html", message="Service Not Found", csrf_token=new_token)


                cursor.execute("""
                                SELECT prothesist_name, prothesist_number 
                                FROM khedma 
                                WHERE id = %s AND khedma_patient = %s AND user_id = %s """
                               ,(result[1], patientId, session['id']))
                found = cursor.fetchone()

                if found :
                    cursor.execute("""
                                    SELECT k.id, p.pFinished 
                                    FROM khedma k
                                    JOIN other_prothesists_khedma p ON p.patient_number = k.khedma_patient AND p.user_id = k.user_id
                                    WHERE k.khedma_patient = %s AND k.user_id = %s  
                                    """,(patientId, session['id'] ))
                    found2 = cursor.fetchall()

                    for find in found2 :
                        if find[0] == result[1] :
                            if find[1] == 'no' :
                                return render_template("FinishedKhedma.html", message=f"Le service et toujours avec le prothesist {find[0]} ", csrf_token=new_token)

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
                                    WHERE id = %s AND user_id = %s AND pNumber = %s """, (khedmaID, session['id'], patientId))
                else:
                    return render_template("PatientHistory.html",
                                           message="Service not found in history get the Service ID from the patient-history table ",
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
                    WHERE id = %s AND khedma_patient = %s
                """, (result[1], patientId))

                # Clean up finished & paid patients
                cursor.execute("""
                    DELETE FROM patient 
                    WHERE finished = %s AND khalsa = %s AND user_id = %s
                """, ('yes', 'yes', session['id']))


            elif choice == "dentist":
                patientId = request.form.get('DPatientID')
                khedmaID = request.form.get('DServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) > 10:
                    return render_template("FinishedKhedma.html", error="Invalid Patient ID", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("FinishedKhedma.html", error="Invalid Service ID", csrf_token=new_token)

                cursor.execute("""
                                SELECT 1 
                                FROM dentist_history 
                                WHERE id = %s AND pNumber = %s AND user_id = %s """
                               ,(khedmaID, patientId, session['id']))

                found = cursor.fetchone()

                if not found :
                    return render_template("FinishedKhedma.html",
                                           message="Patient Not Found in Dentist Records", csrf_token=new_token)

                # Verify dentist record
                cursor.execute("""
                    SELECT d.id, k.id 
                    FROM dentists d
                    LEFT JOIN khedma k ON k.khedma_patient = d.patient_number AND k.user_id = d.user_id 
                    WHERE d.patient_number = %s AND d.user_id = %s 
                """, (patientId, session['id']))

                result = cursor.fetchone()

                if not result:
                    return render_template("FinishedKhedma.html", message="Service Not Found in Dentist Records", csrf_token=new_token)


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
                                                       message=f"Le service et toujours avec le prothesist {find[0]} ", csrf_token=new_token)

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
                                    WHERE id = %s AND user_id = %s AND pNumber = %s """, (khedmaID, session['id'], patientId))
                else:
                    return render_template("DentistHistory.html",
                                           message="Service not found in history get the Service ID from the dentists-history table ",
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
                    WHERE id = %s AND khedma_patient = %s
                """, (result[1], patientId))

                # Clean up finished & paid dentist records
                cursor.execute("""
                    DELETE FROM dentists
                    WHERE finished = %s AND khalsa = %s AND user_id = %s 
                """, ('yes', 'yes', session['id']))

            else:
                return render_template("FinishedKhedma.html", error="Please select 'patient' or 'dentist'", csrf_token=new_token)

            conn.commit()
            return render_template("FinishedKhedma.html", message="Information Updated Successfully", csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("FinishedKhedma.html", error=f"error {str(e)}", csrf_token=new_token)

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

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

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
                    return render_template("KhedmaKhalsa.html", error="Invalid Patient ID", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("KhedmaKhalsa.html", error="Invalid Service ID", csrf_token=new_token)

                cursor.execute("""
                    SELECT price, b9aw, la_date, khalsa 
                    FROM patient
                    WHERE patient_number = %s AND user_id = %s 
                """, ( patientId, session['id']))
                result = cursor.fetchone()

                if not result:
                    return render_template("KhedmaKhalsa.html", message="Patient Not Found", csrf_token=new_token)

                print("DONE 1")

                patient_price = result[0]
                patient_b9aw = result[1]
                patient_date  = result[2]
                old_khalsa    = result[3]

                if old_khalsa == 'yes' :
                    return render_template("KhedmaKhalsa.html", message="Service already payed", csrf_token=new_token)

                cursor.execute("""
                                SELECT p.id, k.id 
                                FROM patient p
                                LEFT JOIN khedma k ON k.khedma_patient = p.patient_number AND k.user_id = p.user_id
                                WHERE p.patient_number = %s AND p.user_id = %s """,
                               (patientId, session['id']))

                service = cursor.fetchone()

                if not service :
                    return render_template("KhedmaKhalsa.html", message="Service Not Found", csrf_token=new_token)


                #cursor.execute("""
                 #               SELECT T_ype FROM patient WHERE id = %s AND user_id = %s """, (khedmaID, session['id']))
                #result = cursor.fetchall()

                #data = [ r for r in result if khedma.lower() == r[0].lower() ]

                #if len(data) > 1:
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
                                           message="Service not found in history get the Service ID from the patient-history table ",
                                           csrf_token=new_token)

                cursor.execute("""
                            UPDATE patient 
                            SET khalsa = %s, b9aw = %s, versa = %s
                            WHERE id = %s AND user_id = %s
                        """, ('yes', 0, patient_price, service[0], session['id']))

                print("DONE 2")

                cursor.execute("""
                            UPDATE khedma 
                            SET khedma_khalsa = %s
                            WHERE id = %s 
                        """, ('yes', service[1]))

                print("DONE 3")

                cursor.execute("""
                            DELETE FROM patient
                            WHERE user_id = %s AND finished = %s AND khalsa = %s
                        """, (session['id'], 'yes', 'yes'))

                print("DONE 4 ")

                cursor.execute("""
                            DELETE FROM khedma
                            WHERE khedma_wajda = %s AND user_id = %s
                        """, ('yes', session['id']))

                print("DONE 5")

                if old_khalsa.lower() == 'no':
                    UpdateKhalsaStat(cursor, conn, table="patient", b9aw=patient_b9aw, date=patient_date)

            elif choice.lower() == "dentist":
                name      = request.form.get('Dentist')
                patientId = request.form.get('DPatientID')
                khedmaID = request.form.get('DServiceID')
                if not patientId or not patientId.isdigit() or len(patientId) > 10:
                    return render_template("KhedmaKhalsa.html", error="Invalid Patient ID", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("KhedmaKhalsa.html", error="Invalid Service ID", csrf_token=new_token)

               # if not SearcheTable(cursor, name):
                #    return render_template("KhedmaKhalsa.html", message="Incorrect dentist name", csrf_token=new_token)

                cursor.execute("""
                    SELECT price, b9aw, date, khalsa 
                    FROM dentists
                    WHERE patient_number = %s AND user_id = %s AND dentist_name = %s 
                """, ( patientId, session['id'], name))
                result = cursor.fetchone()

                if not result:
                    return render_template("KhedmaKhalsa.html", message="Patient Not Found", csrf_token=new_token)

                dentist_price = result[0]
                dentist_b9aw = result[1]
                dentist_date  = result[2]
                old_khalsa    = result[3]

                if old_khalsa == 'yes' :
                    return render_template("KhedmaKhalsa.html", message="Service already payed", csrf_token=new_token)

                cursor.execute("""
                                SELECT d.id, k.id 
                                FROM dentists d 
                                LEFT JOIN khedma k ON k.khedma_patient = d.patient_number AND k.user_id = d.user_id 
                                WHERE d.patient_number = %s AND d.user_id = %s
                                """,(patientId, session['id']))

                service = cursor.fetchone()

                #cursor.execute("""
                 #               SELECT Dkhedma FROM dentists WHERE dentist_name = %s AND patient_number = %s AND user_id = %s """
                  #             , (name, patientId, session['id']))

                #result = cursor.fetchall()
                #data = [ r for r in result if khedma.lower() == r[0].lower() ]

                #if len(data) > 1:
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
                                           message="Service not found in history get the Service ID from the dentists-history table ",
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
                return render_template("KhedmaKhalsa.html", error="You have to enter (patient / dentist)", csrf_token=new_token)

            conn.commit()
            return render_template("KhedmaKhalsa.html", message="Payment Updated Successfully", csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("KhedmaKhalsa.html", error=f"error {str(e)}", csrf_token=new_token)

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
        # Fetch all 4 datasets at once

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

# ============================== SEL3A ========================================

@app.route("/Sel3a", methods=["GET"])
def Sel3aPage():
    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)


    try:
        cursor.execute("""
                        DELETE FROM sel3a 
                        WHERE 
                        buy_date <= DATE_SUB(CURDATE() , INTERVAL 6 MONTH) AND user_id = %s 
                        """,(session['id'],))
        conn.commit()

        # Main Table - All items
        cursor.execute("SELECT * FROM sel3a WHERE user_id = %s", (session['id'],))
        table = cursor.fetchall()

        # Sorted by Price (Expensive to Cheap) - CHANGED from ASC to DESC
        cursor.execute("SELECT * FROM sel3a WHERE user_id = %s "
                       "ORDER BY sel3a_price DESC", (session['id'],))
        Pricetable = cursor.fetchall()

        # Sorted by Date (Newest First) - CHANGED from ASC to DESC
        cursor.execute("SELECT * FROM sel3a WHERE user_id = %s "
                       "ORDER BY buy_date DESC", (session['id'],))
        Datetable = cursor.fetchall()

        # Statistics
        cursor.execute("""
                       SELECT SUM(versement) AS payed , SUM(b9aw) AS rest, MONTH(buy_date) AS month , YEAR(buy_date) AS year  
                       FROM sel3a WHERE user_id = %s 
                       GROUP BY year , month 
                       ORDER BY year DESC, month DESC 
                       """,(session['id'],))
        stat_table = cursor.fetchall()

        # Return template with ALL variables at once
        return render_template("Sel3a.html",
                               table=table,
                               Pricetable=Pricetable,
                               Datetable=Datetable,
                               stat_table=stat_table)
    finally:
        cursor.close()
        conn.close()


@app.route("/AddSel3a", methods=["POST", "GET"])
def addsel3a():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "AddSel3a.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        name  = request.form.get("SName")
        price = request.form.get("SPrice")
        date  = request.form.get("SDate")
        khalsa = request.form.get("SKhalsa")
        versa = request.form.get("Versement")

        try:
            price = float(price)
        except (ValueError, TypeError):
            return render_template("AddSel3a.html", error="Invalid Price Value", csrf_token=new_token)

        if price < 0 or not name.strip():
            return render_template("AddSel3a.html", error="Invalide Informations", csrf_token=new_token)



        if khalsa.lower() not in ['yes' , 'no']:
            return render_template("AddSel3a.html" , error="In khalsa case enter 'yes' or 'no' ", csrf_token=new_token)

        if khalsa == 'no' :

            try:
                versa = float(versa)
            except (ValueError, TypeError):
                return render_template("AddSel3a.html" , error="Invalide Versement Value", csrf_token=new_token)

            if versa < 0 or price < versa:
                return render_template("AddSel3a.html" , error="Invalide Versement Value", csrf_token=new_token)

        if khalsa.lower() == 'yes' :
            versa = price
            b9aw = 0
        else :
            b9aw = float(price) - float(versa)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)
        try:
            cursor.execute("""
                INSERT INTO sel3a (user_id, sel3a_name, sel3a_price, buy_date, khalsa, versement, b9aw)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (session['id'], name, price, date, khalsa, versa, b9aw))
            conn.commit()

            return redirect(url_for("Sel3aPage"))

        except Exception as e :
            conn.rollback()
            return render_template("AddSel3a.html",
                                   error=f"error {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@app.route("/DeleteSel3a/<int:sel3a_id>", methods=["POST"])
def DeleteSel3a(sel3a_id):
    if not is_logged_in():
        return {"success": False, "error": "Unauthorized"}, 401

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        # Delete item ensuring it belongs to the active logged-in user session
        cursor.execute("DELETE FROM sel3a WHERE id = %s AND user_id = %s", (sel3a_id, session['id']))
        conn.commit()
        return {"success": True, "message": "Product deleted successfully"}, 200
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}, 500
    finally:
        cursor.close()
        conn.close()


@app.route("/Sel3aStat")
def Sel3aStat():
    if not is_logged_in():
        return redirect(url_for('home'))
    return redirect(url_for('Sel3aPage'))


@app.route("/ShowByPrice")
def ShowSel3aByPrice():
    if not is_logged_in():
        return redirect(url_for('home'))
    return redirect(url_for('Sel3aPage'))


@app.route("/ShowByDateASC")
def ShowSel3aByDate():
    if not is_logged_in():
        return redirect(url_for('home'))
    return redirect(url_for('Sel3aPage'))


@app.route("/Sel3aPaid/<int:sel3a_id>", methods=["POST"] )
def Sel3aPaid(sel3a_id):
    if not is_logged_in():
        return {"success": False, "error": "Unauthorized"}, 401

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try :
        cursor.execute("""
                        SELECT sel3a_price
                        FROM sel3a
                        WHERE user_id = %s AND id = %s """,(session['id'], sel3a_id))
        result = cursor.fetchone()

        cursor.execute("""
                        UPDATE sel3a 
                        SET versement = %s , b9aw = %s, khalsa = 'yes' 
                        WHERE user_id = %s AND id = %s """,(result[0], 0, session['id'], sel3a_id))
        conn.commit()

        return jsonify({
            'success' : True,
            'message' : 'Operation Done'
        }),200

    except Exception as e :
        conn.rollback()
        return jsonify({
            'success' : False,
            'message' : f'error {str(e)}'
        }),500

    finally :
        cursor.close()
        conn.close()


@app.route("/ModifySel3aVersement/<int:sel3a_id>", methods=["POST"])
def ModifySel3aVersement(sel3a_id):
    if not is_logged_in():
        return jsonify({
            'success' : False,
            "error": "Unauthorized"
        }), 401

    data = request.get_json()
    new_versement = data.get('versement')

    try:
        new_versement = float(new_versement)
    except (ValueError, TypeError):
        return jsonify({
            'success': False,
            'error': 'The versement must be a valid number'
        }), 400

    if new_versement < 0:
        return jsonify({
            'success': False,
            'error': 'The versement must be a positive value'
        }), 400

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try :

        cursor.execute("""
                        SELECT sel3a_price, versement, b9aw, khalsa
                        FROM sel3a 
                        WHERE user_id = %s AND id = %s """,(session['id'], sel3a_id))
        result = cursor.fetchone()

        final = float(new_versement) + float(result[1])

        if final == float(result[0]) :
            cursor.execute("""
                            UPDATE sel3a 
                            SET versement = %s , b9aw = %s , khalsa = 'yes' 
                            WHERE user_id = %s AND id = %s """,
                           (result[0], 0, session['id'], sel3a_id))


            return jsonify({
                'success': True,
                'message' : 'Data Updated'
            }), 200

        elif final > float(result[0]) :

            return jsonify({
                'success': False,
                'error': 'Invalide versement value'
            }), 401

        else :
            b9aw = float(result[0]) - final
            cursor.execute("""
                            UPDATE sel3a 
                            SET versement = %s , b9aw = %s 
                            WHERE user_id = %s AND id = %s """,
                           (final, b9aw, session['id'], sel3a_id))
            conn.commit()

            return jsonify({
                'success': True,
                'message': 'Data Updated'
            }), 200

    except Exception as e :
        conn.rollback()
        return jsonify({
            'success' : False,
            'error' : f'error {str(e)}'
        }),500

    finally :
        cursor.close()
        conn.close()

# ===================================== PROTHESISTS ===========================

@app.route("/ProKhedma", methods=["GET"])
def ProKhedmaPage():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("SELECT * FROM other_prothesists_khedma WHERE user_id = %s", (session['id'],))
        rows = cursor.fetchall()
        return render_template("KhedmaProFile.html", result=rows)
    finally:
        cursor.close()
        conn.close()

@app.route("/AddProthesist", methods=["POST", "GET"])
def AddProthesist():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "AddProthesist.html",
            csrf_token=token
        )

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        if request.method == "POST":
            form_token = request.form.get("csrf_token")
            session_token = session.get("csrf_token")

            if not form_token or form_token != session_token:
                return "CSRF attack detected", 403

            new_token = secrets.token_hex(16)
            session["csrf_token"] = new_token

            prothesist_name = request.form.get("prothesistName")
            prothesist_number = request.form.get('prothesistNumber')

            if not prothesist_name or prothesist_name.isdigit():
                return render_template("AddProthesist.html", message="Invalide Prothesist name", csrf_token=new_token)

            if not prothesist_number or not prothesist_number.isdigit() or len(prothesist_number) != 10:
                return render_template("AddProthesist.html", message="Invalide Prothesist number", csrf_token=new_token)

            cursor.execute("""
                            SELECT 1 
                            FROM other_prothesists
                            WHERE 
                            pName = %s AND pNumber = %s AND user_id = %s  
                            """,(prothesist_name, prothesist_number, session['id']))
            found = cursor.fetchone()

            if not found:
                cursor.execute("""
                                INSERT INTO other_prothesists (pName, pNumber, user_id)
                                VALUES(%s, %s, %s)""",(prothesist_name, prothesist_number, session['id']))
                return render_template("AddProthesist.html", message=f"Prothesist {prothesist_name} Added Successfully", csrf_token=new_token)
            else:
                return render_template("AddProthesist.html", message=f"Prothesist {prothesist_name} - {prothesist_number} Already exists", csrf_token=new_token)
    finally:
        cursor.close()
        conn.close()


@app.route("/ProthesistHistory", methods=["POST", "GET"])
def getProthesistHistory():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        print("========== GET /ProthesistHistory ==========")
        print("GENERATED TOKEN:", repr(token))
        print("SESSION TOKEN:", repr(session.get("csrf_token")))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM other_prothesists_history WHERE user_id = %s", (session['id'],))
        result = cursor.fetchall()
        if result:
            return render_template(
                "ProthesistHistory.html",
                History=result,
                csrf_token=token
            )
        else :
            return render_template(
                "ProthesistHistory.html",
                HistoryProthesist=result,
                message="Table not found",
                csrf_token=token
            )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        print("FORM TOKEN --> ",form_token)
        print("SESSION TOKEN --> ",session['csrf_token'])
        print(form_token == session['csrf_token'])

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        prothesist_name = request.form.get("SearchName")

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            if prothesist_name.isdigit():
                # prothesist name here is the prothesist number because dentist_name.isdigit() True
                cursor.execute("""
                                SELECT * FROM other_prothesists_history 
                                WHERE user_id = %s AND pNumber = %s
                                """, (session['id'], prothesist_name))
                result = cursor.fetchall()

                if result:
                    return render_template("ProthesistHistory.html", HistoryProthesist=result, csrf_token=new_token)
                else:
                    return render_template("ProthesistHistory.html", message="Prothesist not found", csrf_token=new_token)

            cursor.execute("""
                        SELECT * FROM other_prothesists_history
                        WHERE user_id = %s AND prothesist = %s
                    """, (session['id'], prothesist_name.lower()))
            result = cursor.fetchall()
            if result:
                return render_template("ProthesistHistory.html", HistoryProthesist=result, csrf_token=new_token)
            else:
                return render_template("ProthesistHistory.html",
                                       message="Prothesist not found", csrf_token=new_token)
        finally:
            cursor.close()
            conn.close()


@app.route("/AllProthesistHistory")
def getAllProthesistHistory():
    if not is_logged_in():
        return redirect(url_for('home'))

    token = secrets.token_hex(16)
    session['csrf_token'] = token

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("""
                        DELETE FROM other_prothesists_history 
                        WHERE 
                            pDate <= DATE_SUB(CURDATE() , INTERVAL 6 MONTH) AND user_id = %s """,
                       (session['id'],))
        conn.commit()

        cursor.execute("SELECT * FROM other_prothesists_history WHERE user_id = %s", (session['id'],))
        result = cursor.fetchall()
        if result:
            return render_template("ProthesistHistory.html", History=result, csrf_token=session['csrf_token'])
        else:
            return render_template("ProthesistHistory.html", message="Table not found", csrf_token=session['csrf_token'])
    finally:
        cursor.close()
        conn.close()



@app.route("/ProFinished", methods=["POST", "GET"])
def khedmaProMkemla():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "FinishedProKhedma.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        ProthesistName   = request.form.get('ProthesistName')
        ProthesistNumber = request.form.get('ProthesistNumber')
        choice           = request.form.get('Choice')

        if not ProthesistNumber or not ProthesistNumber.isdigit() or len(ProthesistNumber) != 10:
            return render_template("FinishedProKhedma.html", error="Invalid Prothesist Number", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute("""
                SELECT 1 FROM other_prothesists
                WHERE user_id = %s AND pName = %s AND pNumber = %s
            """, (session['id'], ProthesistName, ProthesistNumber))
            row = cursor.fetchone()
            if not row:
                return render_template("FinishedProKhedma.html", message="Prothesist not found", csrf_token=new_token)

            if choice.lower() == "patient":
                patientId = request.form.get('PatientID')
                khedmaID = request.form.get('ServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) != 10:
                    return render_template("FinishedProKhedma.html", error="Invalid Patient ID", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("FinishedProKhedma.html", error="Invalid Service ID", csrf_token=new_token)

                cursor.execute("""
                    SELECT 1 FROM patient_history
                    WHERE id = %s AND pNumber = %s
                """, (khedmaID, patientId))

                result = cursor.fetchone()

                if not result:
                    return render_template("FinishedProKhedma.html", message="Patient Not Found", csrf_token=new_token)

                cursor.execute("""
                               SELECT ph.id, pr.id  
                               FROM patient_history ph  
                               JOIN other_prothesists_khedma pr ON pr.patient_number = ph.pNumber AND pr.user_id = ph.user_id
                               WHERE ph.pNumber = %s AND ph.user_id = %s
                               """,(patientId,session['id']))
                result = cursor.fetchone()

                if not result :
                    return render_template("FinishedProKhedma.html" , message="Service not found", csrf_token=new_token)

                cursor.execute("""
                                UPDATE patient 
                                SET status = %s 
                                WHERE patient_number = %s AND user_id = %s""",
                               ('Finished proth', patientId, session['id']))

                cursor.execute("""
                                UPDATE other_prothesists_khedma 
                                SET pFinished = %s
                                WHERE id = %s """, ('yes', result[1]))

                cursor.execute("""
                                UPDATE other_prothesists_history 
                                SET status = 'finished' 
                                WHERE id = %s """,(result[1],))

                cursor.execute("""
                                SELECT p.id, k.id 
                                FROM patient p
                                JOIN khedma k ON k.khedma_patient = p.patient_number AND k.user_id = p.user_id 
                                WHERE p.patient_number = %s AND p.user_id = %s """,
                               (patientId, session['id']))
                result = cursor.fetchone()

                if result :
                    cursor.execute("""
                                    DELETE FROM khedma 
                                    WHERE id = %s """,
                                    (result[1], ))

                cursor.execute("""
                            DELETE FROM other_prothesists_khedma 
                            WHERE user_id = %s AND pFinished = %s AND pKhalsa = %s
                        """, (session['id'], 'yes', 'yes'))

            elif choice.lower() == "dentist":
                dentistName = request.form.get('Dentist')
                patientId   = request.form.get('DPatientID')
                khedmaID      = request.form.get('DServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) > 10:
                    return render_template("FinishedProKhedma.html", error="Invalid Patient ID", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("FinishedProKhedma.html", error="Invalid Service ID", csrf_token=new_token)

                #if not SearcheTable(cursor, dentistName):
                 #   return render_template("FinishedProKhedma.html", message="Incorrect dentist name", csrf_token=new_token)

                cursor.execute("""
                                SELECT 1 
                                FROM dentist_history 
                                WHERE 
                                id = %s AND pNumber = %s AND dentistname = %s """,
                               (khedmaID, patientId, dentistName))
                found = cursor.fetchone()

                if not found :
                    return render_template("FinishedProKhedma.html", message="Patient Not Found",
                                           csrf_token=new_token)

                cursor.execute("""
                                SELECT dh.id, pr.id 
                                FROM dentist_history dh
                                JOIN other_prothesists_khedma pr ON pr.patient_number = dh.pNumber AND pr.user_id = dh.user_id
                                WHERE dh.pNumber = %s AND dh.user_id = %s AND dh.dentistname = %s
                                """,(patientId, session['id'], dentistName))

                result = cursor.fetchone()

                if not result:
                    return render_template("FinishedProKhedma.html", message="Service Not Found", csrf_token=new_token)

                cursor.execute("""
                                UPDATE dentists 
                                SET status = %s 
                                WHERE patient_number = %s AND dentist_name = %s AND user_id = %s""",
                               ('finished proth', patientId, dentistName, session['id']))

                cursor.execute("""
                            UPDATE other_prothesists_khedma 
                            SET pFinished = %s
                            WHERE id = %s
                        """, ('yes', result[1]))

                cursor.execute("""
                                UPDATE other_prothesists_history 
                                SET status = 'finished' 
                                WHERE id = %s """, (result[1],))

                cursor.execute("""
                                 SELECT d.id, k.id 
                                 FROM dentists d
                                 JOIN khedma k ON k.khedma_patient = d.patient_number AND k.user_id = d.user_id 
                                 WHERE d.patient_number = %s AND d.user_id = %s """,
                               (patientId, session['id']))
                result = cursor.fetchone()

                if result :
                    cursor.execute("""
                                      DELETE FROM khedma 
                                      WHERE id = %s """,
                                           (result[1],))

                cursor.execute("""
                            DELETE FROM dentists
                            WHERE finished = %s AND khalsa = %s AND user_id = %s 
                        """, ('yes', 'yes', session['id']))

                cursor.execute("""
                            DELETE FROM other_prothesists_khedma 
                            WHERE user_id = %s AND pFinished = %s AND pKhalsa = %s
                        """, (session['id'], 'yes', 'yes'))

            else:
                return render_template("FinishedProKhedma.html", error="You have to enter 'patient' or 'dentist'", csrf_token=new_token)

            conn.commit()
            cursor.execute("""
                            SELECT * FROM other_prothesists_khedma 
                            WHERE user_id = %s """, (session['id'],))
            result = cursor.fetchall()
            return render_template("ALLProKhedma.html", message="Information Updated Successfully", result=result, csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("FinishedProKhedma.html", error=f"error {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@app.route("/ProKhalsa", methods=["POST", "GET"])
def KhedmaProKhalsa():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "KhedmaProKhalsa.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        ProName = request.form.get('ProthesistChoice')
        ProNumber = request.form.get('ProthesistNumber')
        choice    = request.form.get('Choice')

        if not ProNumber or not ProNumber.isdigit() or len(ProNumber) != 10:
            return render_template("KhedmaProKhalsa.html", error="Invalid Prothesist Number", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:

            cursor.execute("""
                            SELECT 1 
                            FROM other_prothesists  
                            WHERE pName = %s AND pNumber = %s AND user_id = %s 
                            """,(ProName, ProNumber, session['id']))
            result = cursor.fetchone()

            if not result :
                return render_template("KhedmaProKhalsa.html" , message="Prothesist not found " , csrf_token=new_token)


            if choice.lower() == "patient":
                patientId = request.form.get('PatientID')
                khedmaID = request.form.get('ServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) != 10:
                    return render_template("KhedmaProKhalsa.html", error="Invalid Patient ID", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("KhedmaProKhalsa.html", error="Invalid Service ID", csrf_token=new_token)

                cursor.execute("""
                    SELECT 1 
                    FROM patient_history  
                    WHERE id = %s  AND pNumber = %s AND user_id = %s
                """, (khedmaID, patientId, session['id']))
                result = cursor.fetchone()

                if not result:
                    return render_template("KhedmaProKhalsa.html", message="Patient Not Found", csrf_token=new_token)

                cursor.execute("""
                                SELECT ph.id, pr.id 
                                FROM patient_history ph  
                                JOIN other_prothesists_khedma pr ON pr.patient_number = ph.pNumber AND pr.user_id = ph.user_id 
                                WHERE ph.pNumber = %s AND ph.user_id = %s 
                               """, (patientId, session['id']))

                result = cursor.fetchone()

                print(result)

                if not result:
                    return render_template("KhedmaProKhalsa.html", message="Service Not Found", csrf_token=new_token)

                cursor.execute("""
                                SELECT pPrice, pDate, pKhalsa, pB9aw 
                                FROM other_prothesists_khedma 
                                WHERE pName = %s AND pNumber = %s AND patient_number = %s AND user_id = %s
                                """,(ProName, ProNumber, patientId, session['id']))
                data = cursor.fetchone()

                print(result)
                if not data :
                    return render_template("KhedmaProKhalsa.html", message="Patient Not Found", csrf_token=new_token)

                prothesist_price = data[0]
                prothesist_date  = data[1]
                old_khalsa       = data[2]
                old_b9aw         = data[3]

                cursor.execute("""
                                SELECT pKhalsa, pPrice 
                                FROM other_prothesists_khedma 
                                WHERE id = %s """,(result[1],))

                old = cursor.fetchone()

                if old[0] == 'no' :
                    cursor.execute("""
                                UPDATE other_prothesists_khedma
                                SET pKhalsa = %s, pVersa = %s, pB9aw = %s
                                WHERE id = %s
                            """, ('yes', old[1], 0, result[1]))

                    cursor.execute("""
                                UPDATE other_prothesists_history 
                                SET versement = %s , b9aw = %s 
                                WHERE 
                                user_id = %s AND prothesist = %s AND pNumber = %s AND patient_number = %s  """
                                ,(old[1], 0, session['id'], ProName, ProNumber, patientId))

                else :
                    return render_template("KhedmaProKhalsa.html", message="Service Already paid", csrf_token=new_token)

                cursor.execute("""
                            DELETE FROM patient
                            WHERE user_id = %s AND finished = %s AND khalsa = %s
                        """, (session['id'], 'yes', 'yes'))


                cursor.execute("""
                            DELETE FROM khedma
                            WHERE khedma_wajda = %s AND user_id = %s
                        """, ('yes', session['id']))

                if old_khalsa.lower() == 'no':
                    UpdateProKhalsaStat(cursor, conn, ProName=ProName, ProNumber=ProNumber,
                                        b9aw=old_b9aw, date=prothesist_date)

            elif choice.lower() == "dentist":
                Dentistname      = request.form.get('Dentist')
                patientId = request.form.get('DPatientID')
                khedmaID = request.form.get('DServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) > 10:
                    return render_template("KhedmaProKhalsa.html", error="Invalid Patient ID", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("KhedmaProKhalsa.html", error="Invalid Service ID", csrf_token=new_token)

                if not SearcheTable(cursor, Dentistname):
                    return render_template("KhedmaProKhalsa.html", error="Incorrect dentist name", csrf_token=new_token)

                cursor.execute("""
                    SELECT 1 FROM dentist_history
                    WHERE id = %s AND pNumber = %s AND dentistname = %s AND user_id = %s
                """, (khedmaID, patientId, Dentistname, session['id']))
                result = cursor.fetchone()

                if not result:
                    return render_template("KhedmaProKhalsa.html", message="Patient Not Found", csrf_token=new_token)

                cursor.execute("""
                                    SELECT d.id, k.id, pr.id 
                                    FROM dentists d 
                                    JOIN khedma k ON k.khedma_patient = d.patient_number AND k.user_id = d.user_id 
                                    JOIN other_prothesists_khedma pr ON pr.patient_number = d.patient_number AND pr.user_id = d.user_id 
                                    WHERE d.patient_number = %s AND d.user_id = %s AND d.dentist_name = %s""",
                               (patientId, session['id'], Dentistname))

                result = cursor.fetchone()

                if not result :
                    return render_template("KhedmaProKhalsa.html", message="Service Not Found", csrf_token=new_token)


                cursor.execute("""
                                SELECT pPrice, pDate, pKhalsa, pB9aw
                                FROM other_prothesists_khedma 
                                WHERE pName = %s AND pNumber = %s AND dentist_name = %s AND patient_number = %s AND user_id = %s
                                """,(ProName, ProNumber, Dentistname, patientId, session['id']))
                data = cursor.fetchone()

                if not result :
                    return render_template("KhedmaProKhalsa.html", message="Patient Not Found", csrf_token=new_token)

                prothesist_price = data[0]
                prothesist_date  = data[1]
                old_khalsa       = data[2]
                old_b9aw         = data[3]

                cursor.execute("""
                                SELECT pKhalsa, pPrice
                                FROM other_prothesists_khedma 
                                WHERE id = %s """,(result[2],))

                old = cursor.fetchone()

                if old[0] == 'no' :
                    cursor.execute("""
                                UPDATE other_prothesists_khedma
                                SET pKhalsa = %s, pVersa = %s, pB9aw = %s
                                WHERE id = %s
                            """, ('yes', 0, old[1], result[2]))

                    cursor.execute("""
                                    UPDATE other_prothesists_history 
                                    SET versement = %s , b9aw = %s 
                                    WHERE 
                                    user_id = %s AND prothesist = %s AND pNumber = %s AND patient_number = %s AND dentistname = %s  """
                                   , (old[1], 0, session['id'], ProName, ProNumber, patientId, Dentistname))


                else :
                    return render_template("KhedmaProKhalsa.html", message="Service Already paid", csrf_token=new_token)

                print(result)


                cursor.execute("""
                            DELETE FROM dentists
                            WHERE finished = %s AND khalsa = %s AND user_id = %s AND dentist_name = %s
                        """, ('yes', 'yes', session['id'], Dentistname))


                cursor.execute("""
                            DELETE FROM khedma
                            WHERE user_id = %s AND khedma_wajda = %s 
                        """, (session['id'], 'yes'))


                if old_khalsa.lower() == 'no':
                    UpdateProKhalsaStat(cursor, conn, ProName=ProName, ProNumber=ProNumber,
                                        b9aw=old_b9aw, date=prothesist_date)
            else:
                return render_template("KhedmaProKhalsa.html", error="You have to enter (patient / dentist)", csrf_token=new_token)

            conn.commit()
            cursor.execute("""
                            SELECT * FROM other_prothesists_khedma 
                            WHERE user_id = %s """,(session['id'],))
            result = cursor.fetchall()

            return render_template("ALLProKhedma.html", message="Payment Updated Successfully", result=result, csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("KhedmaProKhalsa.html", error=f"error {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


# Assuming this is part of your main app file or blueprint

@app.route("/ProGetKhedma", methods=["POST", "GET"])
def GetProthesistKhedma():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "ProthesistGetKhedma.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        ProthesistName = request.form.get("ProthesistName")
        ProthesistNumber = request.form.get("ProthesistNumber")
        source = request.form.get("khedmaSource")
        date = request.form.get("GetDate")
        deadLine = request.form.get("GetDeadLine")
        khalsa = request.form.get("CheckKhalsa")
        price = request.form.get("PriceValue")

        if not ProthesistNumber or not ProthesistNumber.isdigit() or len(ProthesistNumber) != 10:
            return render_template("ProthesistGetKhedma.html",
                                   error="❌ Invalid Prothesist Number! Must be exactly 10 digits.",
                                   csrf_token=new_token)

        try:
            price = float(price)
        except (ValueError, TypeError):
            return render_template("ProthesistGetKhedma.html",
                                   error="❌ Invalid price value!",
                                   csrf_token=new_token)

        if price < 0:
            return render_template("ProthesistGetKhedma.html",
                                   error="❌ Price cannot be negative!",
                                   csrf_token=new_token)

        if khalsa.lower() not in ["yes", "no"]:
            return render_template("ProthesistGetKhedma.html",
                                   error="❌ Khalsa must be yes or no!",
                                   csrf_token=new_token)

        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()
            deadLine = datetime.strptime(deadLine, "%Y-%m-%d").date()
        except ValueError:
            return render_template(
                "ProthesistGetKhedma.html",
                error="❌ Invalid date! Use MM-DD-YYYY.",
                csrf_token=new_token
            )

        # Validate dates
        if deadLine < date:
            return render_template("ProthesistGetKhedma.html", error="❌ Deadline must be after the start date!", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            # Check if prosthesist exists
            cursor.execute("""
                SELECT id FROM other_prothesists
                WHERE user_id = %s AND pName = %s AND pNumber = %s """,
                           (session['id'], ProthesistName, ProthesistNumber))

            resultP = cursor.fetchone()
            if not resultP:
                return render_template("ProthesistGetKhedma.html", error="Prothesist not found", csrf_token=new_token)


            # ========== PATIENT SOURCE ==========
            if source.lower() == "patient":
                patientNumber = request.form.get('PatientSource')

                # Validate patient number
                if not patientNumber or not patientNumber.isdigit() or len(patientNumber) != 10:
                    return render_template("ProthesistGetKhedma.html",
                                           error="❌ Invalid patient number! Must be a 10-digit number."
                                           , csrf_token=new_token)

                # Check if patient exists
                cursor.execute("""
                    SELECT finished, T_ype, la_date, DeadLine, patient_firstname, patient_lastname
                    FROM patient 
                    WHERE 
                    user_id = %s AND patient_number = %s """,
                               (session['id'], patientNumber))

                result = cursor.fetchone()

                if not result:
                    return render_template("ProthesistGetKhedma.html",
                                           error="❌ Patient not found! Check the patient number."
                                           , csrf_token=new_token)

                if result[0].lower() == "yes":
                    return render_template("ProthesistGetKhedma.html",
                                           message="⚠️ This patient's work order is already completed!"
                                           , csrf_token=new_token)

                if result[2] > date :
                    return render_template("ProthesistGetKhedma.html",
                                           error="⚠️ Incorrect Enter date "
                                           , csrf_token=new_token)

                if deadLine >= result[3] :
                    return render_template("ProthesistGetKhedma.html",
                                           error="⚠️ Incorrect DeadLine date"
                                           , csrf_token=new_token)


                # Calculate payment amounts
                if khalsa.lower() == "no":
                    versaChoice = request.form.get("VersaChoice", "no")

                    if versaChoice.lower() == "yes":
                        try:
                            versaValue = float(request.form.get("VersementValue"))
                        except (ValueError, KeyError, TypeError):
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Invalid payment amount! Please enter a valid number."
                                                   , csrf_token=new_token)

                        if versaValue < 0:
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Payment amount cannot be negative!"
                                                   , csrf_token=new_token)

                        if versaValue == price:
                            b9aw = 0
                            khalsa = "yes"
                        elif versaValue > price:
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Payment amount cannot exceed the total price!"
                                                   , csrf_token=new_token)
                        else:
                            b9aw = price - versaValue
                    else:
                        versaValue = 0
                        b9aw = price
                else:
                    versaValue = price
                    b9aw = 0

                cursor.execute("""
                                SELECT pName 
                                FROM other_prothesists_khedma 
                                WHERE patient_number = %s AND user_id = %s 
                                """,(patientNumber, session['id']))

                found = cursor.fetchone()

                if found :
                    return render_template("ProthesistGetKhedma.html",
                                           message=f"This service is already with {found[0]}"
                                           , csrf_token=new_token)

                # Insert the work order
                cursor.execute("""
                    INSERT INTO other_prothesists_khedma 
                    (user_id, patient_number, dentist_name, pName, pNumber, pKhedma, pPrice, pVersa, pB9aw, pKhalsa, pFinished, pDate, DeadLine)  
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """,
                               (session['id'], patientNumber, None, ProthesistName, ProthesistNumber, result[1], price,
                                versaValue, b9aw, khalsa, "no", date, deadLine))

                Prothesist_History(cursor, conn, ProthesistName, ProthesistNumber,
                                   patientNumber)

                cursor.execute("""
                                UPDATE patient 
                                SET status = 'prothesist' 
                                WHERE patient_number = %s AND user_id = %s """
                               ,(patientNumber, session['id']))

                # Update statistics
                month = date.month
                year = date.year

                cursor.execute("""
                    SELECT id FROM prothesist_stat 
                    WHERE user_id = %s AND month = %s AND year = %s AND prothesist_name = %s AND prothesist_number = %s """,
                               (session['id'], month, year, ProthesistName, ProthesistNumber))

                found2 = cursor.fetchone()

                if found2:
                    print("FOUND")
                    cursor.execute("""
                        UPDATE prothesist_stat 
                        SET 
                            total_khedma = total_khedma + 1,
                            khalsin = khalsin + %s,
                            machi_khalsin = machi_khalsin + %s
                        WHERE user_id = %s AND month = %s AND year = %s AND prothesist_name = %s AND prothesist_number = %s """,
                                   (versaValue, b9aw, session['id'], month, year, ProthesistName, ProthesistNumber))
                else:
                    print("NOT FOUND")
                    cursor.execute("""
                        INSERT INTO prothesist_stat(prothesist_name, prothesist_number, total_khedma, khalsin, machi_khalsin, month, year, user_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """,
                                   (ProthesistName, ProthesistNumber, 1, versaValue, b9aw, month, year, session['id']))

                cursor.execute("""
                                UPDATE khedma 
                                SET prothesist_name = %s , prothesist_number = %s 
                                WHERE khedma_patient = %s AND user_id = %s """,
                               (ProthesistName, ProthesistNumber, patientNumber, session['id']))

                conn.commit()
                return render_template("KhedmaProFile.html",
                                       message="✅ Work order created successfully! Patient order added to " + ProthesistName + "'s list."
                                       , csrf_token=new_token)

            # ========== DENTIST SOURCE ==========
            else:
                dentistName = request.form.get("DentistSource", "")
                patientNumber = request.form.get("Dentistnumber", "")

                if not dentistName or not patientNumber:
                    return render_template("ProthesistGetKhedma.html",
                                           error="❌ Dentist name and patient number are required!", csrf_token=new_token)

                if not patientNumber.isdigit() or len(patientNumber) > 10 :
                    return render_template("ProthesistGetKhedma.html",
                                           error="❌ Invalid patient number!",
                                           csrf_token=new_token)

                # Check if work order exists
                cursor.execute("""
                    SELECT finished, Dkhedma, date, DeadLine, patient_firstname, patient_lastname 
                    FROM dentists 
                    WHERE user_id = %s AND dentist_name = %s AND patient_number = %s """,
                               (session['id'], dentistName, patientNumber))

                result = cursor.fetchone()

                if not result:
                    return render_template("ProthesistGetKhedma.html",
                                           error="❌ Work order not found! Check dentist name and patient number.", csrf_token=new_token)

                if result[0].lower() == "yes":
                    return render_template("ProthesistGetKhedma.html",
                                           message="⚠️ This work order is already finished!", csrf_token=new_token)

                if result[2] > date :
                    return render_template("ProthesistGetKhedma.html",
                                           error="⚠️ Incorrect Enter date "
                                           , csrf_token=new_token)

                if result[3] < deadLine :
                    return render_template("ProthesistGetKhedma.html",
                                           error="⚠️ Incorrect DeadLine date"
                                           , csrf_token=new_token)

                # Calculate payment amounts
                if khalsa.lower() == "no":
                    versaChoice = request.form.get("VersaChoice", "no")

                    if versaChoice.lower() == "yes":
                        try:
                            versaValue = float(request.form.get("VersementValue"))
                        except (ValueError, KeyError, TypeError):
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Invalid payment amount! Please enter a valid number.", csrf_token=new_token)

                        if versaValue < 0:
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Payment amount cannot be negative!", csrf_token=new_token)

                        if versaValue == price:
                            b9aw = 0
                            khalsa = "yes"
                        elif versaValue > price:
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Payment amount cannot exceed the total price!", csrf_token=new_token)
                        else:
                            b9aw = price - versaValue
                    else:
                        versaValue = 0
                        b9aw = price
                else:
                    versaValue = price
                    b9aw = 0

                cursor.execute("""
                                SELECT pName 
                                FROM other_prothesists_khedma 
                                WHERE patient_number = %s AND user_id = %s AND dentist_name = %s 
                                """, (patientNumber, session['id'], dentistName))

                found = cursor.fetchone()

                if found:
                    return render_template("ProthesistGetKhedma.html",
                                           message=f"This service is already with {found[0]}"
                                           , csrf_token=new_token)

                # Insert the work order
                cursor.execute("""
                                INSERT INTO other_prothesists_khedma 
                                (user_id, patient_number, dentist_name, pName, pNumber, pKhedma, pPrice, pVersa, pB9aw, pKhalsa, pFinished, pDate, DeadLine)  
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """,
                               (session['id'], patientNumber, dentistName, ProthesistName, ProthesistNumber, result[1], price,
                                versaValue, b9aw, khalsa, "no", date, deadLine))

                Prothesist_History(cursor, conn, ProthesistName, ProthesistNumber,
                                   patientNumber)

                cursor.execute("""
                                UPDATE dentists 
                                SET status = 'prothesist' 
                                WHERE dentist_name = %s AND patient_number = %s AND user_id = %s """,
                               (dentistName, patientNumber, session['id']))

                # Update statistics
                month = date.month
                year = date.year

                cursor.execute("""
                    SELECT id FROM prothesist_stat 
                    WHERE user_id = %s AND month = %s AND year = %s AND prothesist_name = %s AND prothesist_number = %s """,
                               (session['id'], month, year, ProthesistName, ProthesistNumber))

                found2 = cursor.fetchone()

                if found2:
                    cursor.execute("""
                        UPDATE prothesist_stat 
                        SET 
                            total_khedma = total_khedma + 1,
                            khalsin = khalsin + %s,
                            machi_khalsin = machi_khalsin + %s
                        WHERE user_id = %s AND month = %s AND year = %s AND prothesist_name = %s AND prothesist_number = %s """,
                                   (versaValue, b9aw, session['id'], month, year, ProthesistName, ProthesistNumber))
                else:
                    cursor.execute("""
                        INSERT INTO prothesist_stat(prothesist_name, prothesist_number, total_khedma, khalsin, machi_khalsin, month, year, user_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """,
                                   (ProthesistName, ProthesistNumber, 1, versaValue, b9aw, month, year, session['id']))

                cursor.execute("""
                                UPDATE khedma 
                                SET prothesist_name = %s , prothesist_number = %s 
                                WHERE khedma_patient = %s AND user_id = %s AND khedma_dentist = %s """,
                               (ProthesistName, ProthesistNumber, patientNumber, session['id'], dentistName))

                conn.commit()

                return render_template("KhedmaProFile.html",
                                       message="✅ Work order created successfully! Dentist referral added to " + ProthesistName + "'s list."
                                       , csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            return render_template("ProthesistGetKhedma.html",
                                   error=f"❌ Database error: {str(e)}", csrf_token=new_token)
        finally:
            cursor.close()
            conn.close()




@app.route("/DeleteProthesistKhedma", methods=["POST", "GET"])
def DeleteProKhedma():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET" :
        token = secrets.token_hex(16)
        session['csrf_token'] = token

        return render_template("DeleteProthesistPatient.html", csrf_token=token)

    if request.method == "POST" :
        token = request.form.get('csrf_token')
        check = session.get('csrf_token')

        if not token or token != check :
            return "error CSRF attack",403

        new_token = secrets.token_hex(16)
        session['csrf_token'] = new_token

        ProName = request.form.get('ProName')
        checkProName = request.form.get('CheckProName')
        ProNumber = request.form.get('ProNumber')
        checkProNumber = request.form.get('CheckProNumber')
        PatientNumber = request.form.get('PatientNumber')
        checkPatientNumber = request.form.get('CheckPatientNumber')

        if not ProName or not checkProName :
            return render_template("DeleteProthesistPatient.html", error="The prothesist-name and its confirmation are required", csrf_token=new_token)

        if not ProNumber or not checkProNumber :
            return render_template("DeleteProthesistPatient.html", error="The prothesist-number and its confirmation are required", csrf_token=new_token)

        if not PatientNumber or not checkPatientNumber :
            return render_template("DeleteProthesistPatient.html", error="The patient-number and its confirmation are required", csrf_token=new_token)

        if not ProNumber.isdigit() or len(ProNumber) != 10 :
            return render_template("DeleteProthesistPatient.html", error="Invalid prothesist number! Must be exactly 10 digits", csrf_token=new_token)

        if not PatientNumber.isdigit() or len(PatientNumber) > 10 :
            return render_template("DeleteProthesistPatient.html", error="Invalid patient number! Must be exactly 10 digits", csrf_token=new_token)

        if ProName != checkProName or ProNumber != checkProNumber or PatientNumber != checkPatientNumber :
            return render_template("DeleteProthesistPatient.html",
                                   error="The confirmation must be the same as the information",
                                   csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try :

            cursor.execute("""
                            SELECT id, pVersa, pB9aw, MONTH(pDate) AS month, YEAR(pDate) AS year, pFinished 
                            FROM other_prothesists_khedma 
                            WHERE 
                            user_id = %s AND patient_number = %s AND pName = %s AND pNumber = %s 
                            """,(session['id'], PatientNumber, ProName, ProNumber))
            found = cursor.fetchone()

            if not found :
                return render_template("DeleteProthesistPatient.html", message=f"Service not found for the prothesist {ProName}", csrf_token=new_token)

            if found[5] == 'yes' :
                cursor.execute("""
                                SELECT * FROM other_prothesists_khedma WHERE user_id = %s """,(session['id'],))
                result = cursor.fetchall()
                return render_template("ALLProKhedma.html", result=result, message=f"Service Already finished", csrf_token=new_token)

            cursor.execute("""
                            SELECT k.khedma_patient, k.khedma_dentist, k.prothesist_name, k.prothesist_number,
                                    pr.id, k.id 
                            FROM other_prothesists_khedma pr 
                            JOIN khedma k ON k.user_id = pr.user_id AND k.khedma_patient = pr.patient_number 
                                            AND k.prothesist_name = pr.pName  AND k.prothesist_number = pr.pNumber 
                            WHERE 
                            pr.user_id = %s AND pr.patient_number = %s AND pr.pName = %s AND pr.pNumber = %s
                            """,(session['id'], PatientNumber, ProName, ProNumber))
            dentist = cursor.fetchone()

            cursor.execute("""
                            DELETE FROM other_prothesists_khedma 
                            WHERE id = %s AND user_id = %s """,(found[0], session['id']))

            cursor.execute("""
                            UPDATE prothesist_stat 
                            SET 
                            total_khedma = total_khedma - 1 ,
                            khalsin = khalsin - %s , 
                            machi_khalsin = machi_khalsin - %s 
                            WHERE 
                            user_id = %s AND prothesist_name = %s AND prothesist_number = %s AND month = %s AND year = %s
                            """,(found[1], found[2], session['id'], ProName, ProNumber, found[3], found[4]))

            cursor.execute("""
                            UPDATE other_prothesists_history 
                            SET status = 'deleted' 
                            WHERE 
                            user_id = %s AND patient_number = %s AND prothesist = %s AND pNumber = %s 
                            """,(session['id'], PatientNumber, ProName, ProNumber))

            cursor.execute("""
                            UPDATE khedma
                            SET 
                            prothesist_name = %s, prothesist_number = 0
                            WHERE 
                            id = %s AND user_id = %s 
                            """, (None, dentist[5], session['id']))

            if dentist[1] == 'NO':
                cursor.execute("""
                                UPDATE patient 
                                SET status = %s 
                                WHERE patient_number = %s AND user_id = %s""",('in process', PatientNumber, session['id']))

            else :
                name = dentist[1][3:]
                cursor.execute("""
                                UPDATE dentists 
                                SET status = %s 
                                WHERE patient_number = %s AND dentist_name = %s AND user_id = %s""",
                               ('in process', PatientNumber, name, session['id']))

            conn.commit()

            cursor.execute(""" SELECT * FROM other_prothesists_khedma WHERE user_id = %s """,
                           (session['id'],))
            result = cursor.fetchall()

            return render_template("ALLProKhedma.html", result=result, message="Service Deleted successfully", csrf_token=new_token)


        except Exception as e :
            conn.rollback()
            return render_template("DeleteProthesistPatient.html", error=f"error {str(e)}", csrf_token=new_token)

        finally :
            cursor.close()
            conn.close()


@app.route("/ProModifyVersement" , methods=["POST" , "GET"])
def ProModifyVersement():

    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "ProthesistModifyVersement.html",
            csrf_token=token
        )

    if request.method == "POST" :
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        ProthesistName = request.form.get("ProthesistName")
        ProthesistNumber = request.form.get("ProthesistNumber")
        khedmaSource = request.form.get("khedmaSource")
        versaValue = request.form.get("VersaValue")

        if not ProthesistNumber or not ProthesistNumber.isdigit() or len(ProthesistNumber) != 10:
            return render_template("ProthesistModifyVersement.html",
                                   error="Invalid Prothesist Number! Must be exactly 10 digits",
                                   csrf_token=new_token)

        try:
            versaValue = float(versaValue)
        except (ValueError, TypeError):
            return render_template("ProthesistModifyVersement.html",
                                   error="Invalid Versement value",
                                   csrf_token=new_token)

        #if versaValue < 0:
         #   return render_template("ProthesistModifyVersement.html",
          #                         error="Versement cannot be negative",
           #                        csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try :

            cursor.execute("""
                            SELECT id FROM other_prothesists
                            WHERE     
                            user_id = %s AND pName = %s AND pNumber = %s  """,
                           (session['id'], ProthesistName, ProthesistNumber))

            found = cursor.fetchone()

            if not found :
                return render_template("ProthesistModifyVersement.html" , message="Prothesist not Found ", csrf_token=new_token)

            if khedmaSource.lower() == "patient" :
                PatientNumber = request.form.get("PatientNumber")
                DentistName = None
                khedmaID = request.form.get('ServiceID')

                if not PatientNumber or not PatientNumber.isdigit() or len(PatientNumber) != 10:
                    return render_template("ProthesistModifyVersement.html",
                                           error="Invalid Patient Number! Must be exactly 10 digits",
                                           csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("ProthesistModifyVersement.html",
                                           error="Invalid Service ID",
                                           csrf_token=new_token)

                cursor.execute("""
                                SELECT 1 
                                FROM patient_history 
                                WHERE id = %s AND pNumber = %s AND user_id = %s """
                               ,(khedmaID, PatientNumber, session['id']))
                found = cursor.fetchone()

                if not found :
                    return render_template("ProthesistModifyVersement.html", message="Patient not found ",
                                           csrf_token=new_token)

                cursor.execute("""
                                SELECT pVersa , pPrice , pKhalsa , MONTH(pDate) , YEAR(pDate) 
                                FROM other_prothesists_Khedma 
                                WHERE user_id = %s AND pName = %s AND pNumber = %s AND patient_number = %s """,
                               (session['id'], ProthesistName, ProthesistNumber, PatientNumber))

                result = cursor.fetchone()

                if not result :
                    return render_template("ProthesistModifyVersement.html" , message="Service not found ", csrf_token=new_token)

            else :
                DentistName = request.form.get("DentistName")
                PatientNumber = request.form.get("DentistNumber")
                khedmaID = request.form.get('DServiceID')

                if not PatientNumber or not PatientNumber.isdigit() or len(PatientNumber) > 10:
                    return render_template("ProthesistModifyVersement.html",
                                           error="Invalid Patient Number",
                                           csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("ProthesistModifyVersement.html",
                                           error="Invalid Service ID",
                                           csrf_token=new_token)

                cursor.execute("""
                                    SELECT 1 
                                    FROM dentist_history 
                                    WHERE id = %s AND pNumber = %s AND dentistname = %s AND user_id = %s """
                               , (khedmaID, PatientNumber, DentistName, session['id']))
                found = cursor.fetchone()

                if not found :
                    return render_template("ProthesistModifyVersement.html", message="Patient not found ",
                                           csrf_token=new_token)

                cursor.execute("""
                                 SELECT pVersa , pPrice , pKhalsa , MONTH(pDate) , YEAR(pDate) 
                                 FROM other_prothesists_Khedma 
                                 WHERE user_id = %s AND pName = %s AND pNumber = %s AND patient_number = %s AND dentist_name = %s """,
                (session['id'], ProthesistName, ProthesistNumber, PatientNumber, DentistName))

                result = cursor.fetchone()

                if not result:
                    return render_template("ProthesistModifyVersement.html", message="Service not found ", csrf_token=new_token)

            oldVersa = result[0]
            price = result[1]
            khalsa = result[2]
            month = result[3]
            year = result[4]

            newVersa = float(oldVersa) + versaValue
            b9aw = float(price) - newVersa

            if b9aw > float(price):
                return render_template("ProthesistModifyVersement.html", error="Invalid Versement ",
                                       csrf_token=new_token)

            if khalsa == "yes" and versaValue > 0 :
                return render_template("ProthesistModifyVersement.html" , message="Service already payed ", csrf_token=new_token)

            if newVersa > price :
                return render_template("ProthesistModifyVersement.html" , error="Invalide Versement value ", csrf_token=new_token)

            if newVersa == price :
                khalsa = "yes"


            if newVersa < price :
                khalsa = 'no'

                if khedmaSource.strip() == "patient" :

                    cursor.execute("""
                                    UPDATE other_prothesists_khedma 
                                    SET    
                                    pVersa = %s , 
                                    pB9aw = %s ,
                                    pKhalsa = %s
                                    WHERE user_id = %s AND pName = %s AND pNumber = %s AND patient_number = %s                                         
                                    """,(newVersa, b9aw, khalsa, session['id'], ProthesistName, ProthesistNumber, PatientNumber))

                    cursor.execute("""
                                    UPDATE other_prothesists_history 
                                    SET 
                                    versement = %s , 
                                    b9aw = %s 
                                    WHERE user_id = %s AND prothesist = %s AND pNumber = %s AND patient_number = %s 
                                    """,(newVersa, b9aw, session['id'], ProthesistName, ProthesistNumber, PatientNumber))

                else :

                    cursor.execute("""
                                    UPDATE other_prothesists_khedma 
                                    SET    
                                    pVersa = %s , 
                                    pB9aw = %s ,
                                    pKhalsa = %s
                                    WHERE user_id = %s AND pName = %s AND pNumber = %s AND patient_number = %s AND  dentist_name = %s                                        
                    """, (
                    newVersa, b9aw, khalsa, session['id'], ProthesistName, ProthesistNumber, PatientNumber,
                    DentistName))

                    cursor.execute("""
                                    UPDATE other_prothesists_history 
                                    SET 
                                    versement = %s , 
                                    b9aw = %s 
                                    WHERE user_id = %s AND prothesist = %s AND pNumber = %s AND patient_number = %s AND dentistname = %s
                                    """,
                                   (newVersa, b9aw, session['id'], ProthesistName, ProthesistNumber, PatientNumber, DentistName))



            cursor.execute("""
                            UPDATE prothesist_stat 
                            SET 
                            khalsin = khalsin + %s , 
                            machi_khalsin = machi_khalsin - %s 
                            WHERE 
                            user_id = %s AND prothesist_name = %s AND prothesist_number = %s AND month = %s AND year = %s
                            """,(versaValue, versaValue, session['id'], ProthesistName, ProthesistNumber, month, year))

            conn.commit()

            return render_template("KhedmaProFile.html" , message="Informations Updated Succesfuly", csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("ProthesistModifyVersement.html", error=f"error {str(e)}", csrf_token=new_token )

        finally :
            cursor.close()
            conn.close()


@app.route("/ProAllkhedma", methods=["POST" , "GET"])
def Proallkhedma():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET" :
        token = secrets.token_hex(16)
        session['csrf_token'] = token

        conn = get_connection()
        cursor = conn.cursor(buffered=True)
        try:
            cursor.execute("SELECT * FROM other_prothesists_khedma WHERE user_id = %s", (session['id'],))
            rows = cursor.fetchall()
            return render_template("ALLProKhedma.html", result=rows, csrf_token=token)
        finally:
            cursor.close()
            conn.close()

    if request.method == "POST" :
        token = request.form.get('csrf_token')
        check = session.get('csrf_token')

        if not token or token != check :
            return "error CSRF attack ",403

        new_token = secrets.token_hex(16)
        session['csrf_token'] = new_token

        prothesist = request.form.get('SearchBar')

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try :

            if prothesist.isdigit():
                cursor.execute("""
                                SELECT * FROM other_prothesists_khedma
                                WHERE user_id = %s AND pNumber = %s """,(session['id'], prothesist))
                result = cursor.fetchall()

                if result :
                    return render_template("ALLProKhedma.html", result=result, csrf_token=new_token)
                else :
                    return render_template("ALLProKhedma.html", message="Prothesist not found", csrf_token=new_token)

            else :
                cursor.execute("""
                                SELECT * FROM other_prothesists_khedma
                                WHERE user_id = %s AND pName = %s """, (session['id'], prothesist.lower()))
                result = cursor.fetchall()

                if result:
                    return render_template("ALLProKhedma.html", result=result, csrf_token=new_token)
                else:
                    return render_template("ALLProKhedma.html", message="Prothesist not found", csrf_token=new_token)

        finally :
            cursor.close()
            conn.close()



@app.route("/ProKhedmaByDateASC")
def ProKhedmaByDateASC():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT * FROM other_prothesists_khedma
            WHERE user_id = %s ORDER BY pDate ASC
        """, (session['id'],))
        rows = cursor.fetchall()
        return render_template("ALLProKhedma.html", asc=rows)
    finally:
        cursor.close()
        conn.close()


@app.route("/ProKhedmaByDateDESC")
def ProKhedmaByDateDESC():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT * FROM other_prothesists_khedma
            WHERE user_id = %s ORDER BY pDate DESC
        """, (session['id'],))
        rows = cursor.fetchall()
        return render_template("ALLProKhedma.html", desc=rows)
    finally:
        cursor.close()
        conn.close()


@app.route("/ProMostKhedma", methods=["GET"])
def FindMostProKhedma():
    if not is_logged_in():
        return redirect(url_for('home'))

    new_token = session['csrf_token']

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        Pro_dics = ProthesistDics(cursor)
        if not Pro_dics:
            return render_template("ALLProKhedma.html", error="No Prothesist tables found.", csrf_toke= new_token)
        name, count = max(Pro_dics.items(), key=lambda x: x[1], default=('none', 0))
        if count == 0:
            return render_template("ALLProKhedma.html", message="All tables are empty.", csrf_token= new_token)
        cursor.execute("SELECT * FROM other_prothesists_khedma WHERE user_id = %s AND pName = %s",
                       (session['id'], name))
        result = cursor.fetchall()
        return render_template("ALLProKhedma.html", most=result, most_name=name, csrf_token= new_token)
    finally:
        cursor.close()
        conn.close()


@app.route("/ProLessKhedma", methods=["GET"])
def FindLessProKhedma():
    if not is_logged_in():
        return redirect(url_for('home'))

    new_token = session['csrf_token']

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        Pro_dics = ProthesistDics(cursor)
        active_Pros = {n: c for n, c in Pro_dics.items() if c > 0}
        if not active_Pros:
            return render_template("ALLProKhedma.html", message="All prothesists currently have 0 Services.", csrf_token= new_token)
        name, count = min(active_Pros.items(), key=lambda x: x[1])
        cursor.execute("SELECT * FROM other_prothesists_khedma WHERE user_id = %s AND pName = %s",
                       (session['id'], name))
        result = cursor.fetchall()
        if not result :
            print("Invalide result")
        return render_template("ALLProKhedma.html", less=result, less_name=name, csrf_token= new_token)
    finally:
        print("DONE")
        cursor.close()
        conn.close()


@app.route("/ProTotal", methods=["GET"])
def ShowProTotal():
    if not is_logged_in():
        return redirect(url_for('home'))

    token = secrets.token_hex(16)
    session['csrf_token'] = token

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        current_Pros = GetAllProthesists(cursor)
        result = {}
        for Pro in current_Pros:
            try:
                cursor.execute("""
                    SELECT pName, pNumber,
                           COALESCE(SUM(pVersa), 0),
                           COALESCE(SUM(pB9aw), 0)
                    FROM other_prothesists_khedma
                    WHERE user_id = %s AND pName = %s AND pNumber = %s
                    GROUP BY pName , pNumber 
                """, (session['id'], Pro[1] , Pro[0] ))
                row = cursor.fetchone()
                result[Pro] = row if row[0] else (Pro[1], '-', 0, 0)
            except Exception as e:
                print(f"Error on {Pro[1]}: {e}")
                result[Pro[1]] = (Pro[1], '-', 0, 0)
        if result:
            return render_template("ProStats.html", total=result, csrf_token= token)
        return render_template("ProStats.html", message="No Prothesist data found.", csrf_token= token)
    finally:
        cursor.close()
        conn.close()


@app.route("/ProStat")
def ProStat():
    if not is_logged_in():
        return redirect(url_for('home'))

    token = secrets.token_hex(16)
    session['csrf_token'] = token

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("""
            DELETE FROM other_services_stats
            WHERE
                user_id = %s
                AND (
                    year < YEAR(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                    OR (
                        year = YEAR(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                        AND month <= MONTH(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                    )
                )
        """, (session['id'],))
        conn.commit()

        cursor.execute("""
            DELETE FROM prothesist_stat
            WHERE
                user_id = %s
                AND total_khedma = 0
                AND khalsin = 0
                AND machi_khalsin = 0
        """, (session['id'],))

        conn.commit()

        Pro_list = GetAllProthesists(cursor)
        result = {}
        for Pro in Pro_list:

            cursor.execute("""
                SELECT *
                FROM prothesist_stat
                WHERE user_id = %s
                  AND prothesist_name = %s
                  AND prothesist_number = %s
                ORDER BY year DESC, month DESC
            """, (session['id'], Pro[1], Pro[0]))

            rows = cursor.fetchall()

            # Only add the prothesist if statistics exist
            if rows:
                result[Pro] = rows

        if result:
            return render_template(
                "ProStats.html",
                message="The Stat Table",
                result=result,
                csrf_token=token
            )


        return render_template(
            "ProStats.html",
            message="Table Not Found (There are no statistics)",
            csrf_token=token
        )

    except Exception as e:
        conn.rollback()
        return render_template(
            "ProStats.html",
            message=f"error {str(e)}",
            csrf_token=token
        )

    finally:
        cursor.close()
        conn.close()

@app.route("/ProSearch", methods=["POST", "GET"])
def ProSearchPage():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "ProStats.html",
            csrf_token=token
        )

    try:
        if request.method == "POST":
            form_token = request.form.get("csrf_token")
            session_token = session.get("csrf_token")

            if not form_token or form_token != session_token:
                return "CSRF attack detected", 403

            new_token = secrets.token_hex(16)
            session["csrf_token"] = new_token


            ProName = request.form.get("SearchBar")
            cursor.execute("""
                SELECT id FROM other_prothesists
                WHERE user_id = %s AND pName = %s
            """, (session['id'], ProName))
            exists = cursor.fetchone()
            cursor.fetchall()
            if exists:
                cursor.execute("SELECT * FROM other_prothesists_khedma WHERE user_id = %s AND pName = %s",
                               (session["id"], ProName))
                rows = cursor.fetchall()
                return render_template("ProStats.html", result=rows, csrf_token=new_token)
            else:
                return render_template("ProStats.html", error=f"Prothesist {ProName} Not Found", csrf_token=new_token)

    finally:
        cursor.close()
        conn.close()

# =================================== ALL TOTAL ===============================


@app.route("/AllTotalAccount")
def AllTotal():
    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try :

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
                SUM(CASE WHEN khalsa='yes' THEN versement ELSE 0 END) AS khalsa,
                SUM(CASE WHEN khalsa='no' THEN b9aw ELSE 0 END) AS b9aw,
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

        result = cursor.fetchall()
        return render_template("AllTotalStats.html", result=result)

    finally :
        cursor.close()
        conn.close()

# ======================================== Other Services ================================
@app.route("/OtherServices")
def OtherServices():
    if not is_logged_in():
        return redirect(url_for('home'))

    token = secrets.token_hex(16)
    session['csrf_token'] = token

    conn = get_connection()
    cursor = conn.cursor()

    try :
        cursor.execute("""
                        DELETE FROM others_services 
                        WHERE 
                        date <= DATE_SUB(CURDATE() , INTERVAL 6 MONTH) AND user_id = %s """
                       ,(session['id'],))
        conn.commit()

        cursor.execute("""
                        SELECT * FROM others_services
                        WHERE user_id = %s """, (session['id'],))
        result = cursor.fetchall()

        return render_template("OtherServices.html", result=result, csrf_token=token)

    finally :
        cursor.close()
        conn.close()

# -------------------------------
# DISPLAY TABLE
# -------------------------------
@app.route("/OtherServicesTable")
def OtherServicesTable():
    if not is_logged_in():
        return redirect(url_for('home'))

    token = secrets.token_hex(16)
    session['csrf_token'] = token

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("""
            SELECT * FROM others_services 
            WHERE user_id = %s
        """, (session['id'],))

        result = cursor.fetchall()

        if result:
            return render_template("OtherServices.html", result=result, message="The Other Services Table", csrf_token=token)
        else:
            return render_template("OtherServices.html", error="Empty Table", csrf_token=token)

    finally:
        cursor.close()
        conn.close()

@app.route("/OtherSearchBar" , methods=["POST" , "GET"])
def SearchBar():

    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "OtherServices.html",
            csrf_token=token
        )

    if request.method == "POST" :
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        SearchBar = request.form.get("SearchBar")

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try :

            cursor.execute("""
                            SELECT * FROM others_services 
                            WHERE user_id = %s AND name = %s """,
                           (session['id'], SearchBar))

            result = cursor.fetchall()

            if not result :
                return render_template("OtherServices.html" , error="Service not Found ", csrf_token=new_token)

            return render_template("OtherServices.html", result=result,  message=f"{SearchBar} Table", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()

# -------------------------------
# ADD SERVICE
# -------------------------------
@app.route("/AddService", methods=["GET", "POST"])
def AddService():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        return render_template(
            "AddService.html",
            csrf_token=token
        )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "CSRF attack detected", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        name = request.form.get('ServiceName', '').strip()
        number = request.form.get('ServiceNumber', '').strip()
        function = request.form.get('ServiceFunction', '').strip()
        date = request.form.get('ServiceDate')
        khalsa = request.form.get('ServiceKhalsa', 'no').lower()
        price = float(request.form.get('ServicePrice', 0))

        # ---------------- VALIDATION ----------------
        if not name:
            return render_template("AddService.html", error="Invalid Name", csrf_token=new_token)

        if not number.isdigit() or len(number) != 10:
            return render_template("AddService.html", error="Invalid Number", csrf_token=new_token)

        if not function:
            return render_template("AddService.html", error="Invalid Function", csrf_token=new_token)

        if khalsa not in ['yes', 'no']:
            return render_template("AddService.html", error="Khalsa must be yes or no", csrf_token=new_token)

        if price < 0:
            return render_template("AddService.html", error="Invalid Price", csrf_token=new_token)

        if khalsa == 'no':
            versa = request.form.get('ServiceVersa', 'no').lower()

            if versa not in ['yes', 'no']:
                return render_template("AddService.html", error="Versa must be yes or no", csrf_token=new_token)

            if versa == 'yes':
                Vprice = float(request.form.get('VersaService', '0'))

                if Vprice < 0:
                    return render_template("AddService.html", error="Invalid Price", csrf_token=new_token)

                if Vprice > price:
                    return render_template("AddService.html", error="Versa > Price not allowed", csrf_token=new_token)

                if Vprice == price :
                    b9aw = 0
                    khalsa = "yes"

                b9aw = price - Vprice
            else:
                Vprice = 0
                b9aw = price
        else:
            Vprice = price
            b9aw = 0

        # ---------------- DATABASE ----------------
        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute("""
                INSERT INTO others_services
                (name, number, date, price, khalsa, versement, b9aw, user_id, k_function)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, number, date, price, khalsa, Vprice, b9aw, session['id'], function))



            d = datetime.strptime(date, "%Y-%m-%d")
            month = d.month
            year = d.year

            cursor.execute("""
                SELECT id FROM other_services_stats
                WHERE user_id = %s AND month = %s AND year = %s AND number = %s
            """, (session['id'], month, year, number))

            result = cursor.fetchone()

            if result:
                cursor.execute("""
                    UPDATE other_services_stats
                    SET
                        machi_khalsin = machi_khalsin + %s,
                        khalsin = khalsin + %s,
                        total_khedma = total_khedma + 1
                    WHERE user_id = %s AND number = %s AND month = %s AND year = %s
                """, (b9aw, Vprice, session['id'], number, month, year))
            else:
                cursor.execute("""
                    INSERT INTO other_services_stats
                    (Name, Number, total_khedma, khalsin, machi_khalsin, month, year, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (name, number, 1, Vprice, b9aw, month, year, session['id']))

            conn.commit()

            cursor.execute("""
                            SELECT * FROM others_services
                            WHERE user_id = %s """,(session['id'],))
            result = cursor.fetchall()

            return render_template("OtherServices.html", result=result, message="Service Added Successfully", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()

# -------------------------------
# MARK AS PAID
# -------------------------------

@app.route("/ServicePaid/<int:service_id>", methods=["POST"])
def ServicePaid(service_id):
    if not is_logged_in():
        return jsonify({
            'success': False,
            'error': 'You have to log-in '
        }),401

    data = request.get_json()
    name = data.get('name')
    number = data.get('number')

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try :

        cursor.execute("""
                        SELECT price, versement, b9aw, khalsa, MONTH(date) AS month, YEAR(date) AS year
                        FROM others_services 
                        WHERE user_id = %s AND id = %s """,(session['id'], service_id))

        result = cursor.fetchone()

        if result[3] == 'yes' :
            return jsonify({
                'success': False,
                'message': 'Service already paid'
            })

        cursor.execute("""
                        UPDATE others_services
                        SET
                        versement = %s , b9aw = %s , khalsa = 'yes'
                        WHERE 
                        user_id = %s AND id = %s 
                         """,(result[0], 0, session['id'], service_id))

        cursor.execute("""
                        UPDATE other_services_stats
                        SET 
                        khalsin = khalsin + %s ,
                        machi_khalsin = machi_khalsin - %s 
                        WHERE 
                        user_id = %s AND name = %s AND number = %s AND month = %s AND year = %s 
                        """,(result[2], result[2], session['id'], name, number, result[4], result[5]))

        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Informations Updated'
        }),200

    except Exception as e :
        conn.rollback()
        return jsonify({
            'success': False,
            'error': f'error {str(e)}'
        }),500

    finally:
        cursor.close()
        conn.close()


@app.route("/ModifyServiceVersement/<int:service_id>", methods=["POST"])
def ModifyServiceVersement(service_id):
    if not is_logged_in():
        return jsonify({
            'success': False,
            'error': 'You have to log-in '
        }),401

    data = request.get_json()
    name = data.get('name')
    number = data.get('number')
    newVersement = data.get('newVersement')

    conn = get_connection()
    cursor = conn.cursor()

    try :
        cursor.execute("""
                        SELECT price, versement, b9aw, khalsa, MONTH(date) AS month, YEAR(date) AS year
                        FROM others_services
                        WHERE user_id = %s AND id = %s
                        """,(session['id'], service_id))
        result = cursor.fetchone()

        if result[3] == 'yes':
            return jsonify({
                'success': False,
                'message': 'Service already paid'
            }),401

        final = float(newVersement) + float(result[1])

        if final == float(result[0]) :
            cursor.execute("""
                            UPDATE others_services
                            SET
                            versement = %s , b9aw = %s , khalsa = 'yes'
                            WHERE 
                            user_id = %s AND id = %s 
                            """, (result[0], 0, session['id'], service_id))

            cursor.execute("""
                            UPDATE other_services_stats
                            SET 
                            khalsin = khalsin + %s ,
                            machi_khalsin = machi_khalsin - %s 
                            WHERE 
                            user_id = %s AND name = %s AND number = %s AND month = %s AND year = %s 
                            """, (result[2], result[2], session['id'], name, number, result[4], result[5]))

        elif final < float(result[0]) :
            b9aw = float(result[0]) - final
            if b9aw > float(result[0]):
                return jsonify({
                    'success': False ,
                    'message' : 'Invalide Versement'
                }),402

            cursor.execute("""
                            UPDATE others_services
                            SET
                            versement = %s , b9aw = %s , khalsa = 'no' 
                            WHERE 
                            user_id = %s AND id = %s 
                            """, (final, b9aw, session['id'], service_id))

            cursor.execute("""
                            UPDATE other_services_stats
                            SET 
                            khalsin = khalsin + %s ,
                            machi_khalsin = machi_khalsin - %s 
                            WHERE 
                            user_id = %s AND name = %s AND number = %s AND month = %s AND year = %s 
                            """, (newVersement, newVersement, session['id'], name, number, result[4], result[5]))

        else :
            return jsonify({
                'success': False,
                'message': "Invalde versement value"
            }),401

        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Informations Updated'
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': f'error {str(e)}'
        }),500

    finally:
        cursor.close()
        conn.close()


@app.route("/DeleteService/<int:service_id>", methods=["POST"])
def DeleteService(service_id):
    if not is_logged_in():
        return jsonify({
            'success': False,
            'error': 'You have to log-in '
        }),401

    data = request.get_json()
    name = data.get('name')
    number = data.get('number')

    conn = get_connection()
    cursor = conn.cursor()


    try :

        cursor.execute("""
                        SELECT price, versement, b9aw, khalsa, MONTH(date) AS month, YEAR(date) AS year
                        FROM others_services
                        WHERE user_id = %s AND id = %s
                        """, (session['id'], service_id))
        result = cursor.fetchone()

        cursor.execute("""
                        DELETE FROM others_services
                        WHERE user_id = %s AND id = %s """,(session['id'], service_id))

        cursor.execute("""
                        UPDATE other_services_stats
                        SET 
                        khalsin = khalsin - %s ,
                        machi_khalsin = machi_khalsin - %s 
                        WHERE 
                        user_id = %s AND name = %s AND number = %s AND month = %s AND year = %s 
                    """, (result[1], result[2], session['id'], name, number, result[4], result[5]))

        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Informations Updated'
        }),200

    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': f'error {str(e)}'
        }),500

    finally:
        cursor.close()
        conn.close()


# -------------------------------
# STATS
# -------------------------------
@app.route("/ServicesStats")
def ServicesStat():
    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("""
                        DELETE FROM other_services_stats
                        WHERE
                            user_id = %s
                            AND (
                                year < YEAR(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                                OR (
                                    year = YEAR(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                                    AND month <= MONTH(DATE_SUB(CURDATE(), INTERVAL 12 MONTH))
                                )
                            )
                        """,(session['id'],))
        conn.commit()

        cursor.execute("""
            SELECT * FROM other_services_stats
            WHERE user_id = %s
        """, (session['id'],))

        result = cursor.fetchall()

        if result:
            return render_template("OtherServices.html", stats=result, message="Services Stats")
        else:
            return render_template("OtherServices.html", error="Empty Table")

    finally:
        cursor.close()
        conn.close()

# ========================================================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
