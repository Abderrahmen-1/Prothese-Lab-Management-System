from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from FlaskTry.FunctionFile import *
from FlaskTry.ConnectToSql import get_connection
import os
from dotenv import load_dotenv
from datetime import datetime , timedelta , date
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets
from FlaskTry.routes.users import users
from FlaskTry.routes.patients import patients
from FlaskTry.routes.dentists import dentists
from FlaskTry.routes.prothesists import prothesists

load_dotenv()

# =============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
limiter = Limiter(get_remote_address, app=app)

app.register_blueprint(users)
app.register_blueprint(patients)
app.register_blueprint(dentists)
app.register_blueprint(prothesists)

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
