import secrets
from flask import Blueprint, request, render_template, redirect, url_for, session, jsonify
from FlaskTry.FunctionFile import *
from FlaskTry.ConnectToSql import get_connection

patients = Blueprint("patients", __name__, url_prefix="/patients")


def is_logged_in():
    return "id" in session


@patients.route("/Patient", methods=["POST", "GET"])
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

    if request.method == "POST":
        token = request.form.get('csrf_token')
        check = session.get('csrf_token')

        print('toke ->',token)
        print('check ->',check)
        print( token == check)

        if not token or token != check:
            return "Erreur : attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session['csrf_token'] = new_token

        patient = request.form.get('SearchBar')

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:

            if patient.isdigit():
                cursor.execute(""" 
                                SELECT * FROM patient 
                                WHERE user_id = %s AND patient_number = %s """,
                               (session['id'], patient))
                data = cursor.fetchall()

                if data:
                    return render_template("PatientsFile.html", data=data, csrf_token=new_token)
                else:
                    return render_template("PatientsFile.html", message="Patient introuvable", csrf_toke=new_token)

            else:
                cursor.execute(""" 
                                SELECT * FROM patient 
                                WHERE user_id = %s AND patient_firstname = %s """,
                               (session['id'], patient.lower()))
                data = cursor.fetchall()

                if data:
                    return render_template("PatientsFile.html", data=data, csrf_token=new_token)

                else:
                    cursor.execute(""" 
                                    SELECT * FROM patient 
                                    WHERE user_id = %s AND patient_lastname = %s """,
                                   (session['id'], patient.lower()))
                    data = cursor.fetchall()

                    if data:
                        return render_template("PatientsFile.html", data=data, csrf_token=new_token)

                    else:
                        return render_template("PatientsFile.html", message="Patient introuvable", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@patients.route("/AddPatient", methods=["POST", "GET"])
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
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        firstName = request.form.get('PatientFirstName', '').strip()
        lastName = request.form.get('PatientLastName', '').strip()
        unique = request.form.get('PatientUnique', '').strip()
        choice = request.form.get('KhedmaChoice', '').strip()
        date = request.form.get('date', '').strip()
        deadLine = request.form.get('DeadLine', '').strip()
        price = request.form.get('KhedmaPrice', '').strip()
        khalsa = request.form.get('Khalsa', '').strip().lower()
        versa = request.form.get('versa', '').strip().lower()
        Versa = request.form.get('Versa', '').strip()
        ProCheck = request.form.get('OtherPro', '').strip().lower()

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:

            if not firstName or not lastName or firstName.isdigit() or lastName.isdigit():
                return render_template("AddPatient.html", error="Nom invalide", csrf_token=new_token)

            if not unique or not unique.isdigit() or len(unique) != 10:
                return render_template("AddPatient.html", error="Numéro d'identification invalide",
                                       csrf_token=new_token)

            if not choice:
                return render_template("AddPatient.html", error="Choix invalide", csrf_token=new_token)

            if not date or not deadLine:
                return render_template("AddPatient.html", error="La date et la date limite sont obligatoires",
                                       csrf_token=new_token)

            if deadLine < date:
                return render_template("AddPatient.html", error="Date limite invalide", csrf_token=new_token)

            if not khalsa or khalsa not in ['yes', 'no']:
                return render_template("AddPatient.html", error="Vous devez saisir « yes » ou « no » dans Khalsa",
                                       csrf_token=new_token)

            if khalsa == 'no':
                if not versa or versa not in ['yes', 'no']:
                    return render_template("AddPatient.html", error="Dans le versement, saisissez « yes » ou « no »",
                                           csrf_token=new_token)

            if not ProCheck or ProCheck not in ['yes', 'no']:
                return render_template("AddPatient.html",
                                       error="Vous devez saisir « yes » ou « no » dans la partie de vérification du prothésiste",
                                       csrf_token=new_token)

            cursor.execute(""" 
                            SELECT id FROM patient WHERE user_id = %s AND patient_number = %s"""
                           , (session['id'], unique))

            if cursor.fetchone():
                return render_template("AddPatient.html", message="Le numéro d'identification existe déjà",
                                       csrf_token=new_token)

            if not price:
                return render_template("AddPatient.html", error="Le prix ne peut pas être vide", csrf_token=new_token)

            if not checkValue(price):
                return render_template("AddPatient.html", error="Prix invalide", csrf_token=new_token)

            price = float(price)

            if khalsa == 'yes':
                Versa = price
            else:
                if versa == 'no':
                    Versa = 0
                else:
                    if not Versa:
                        return render_template("AddPatient.html", error="Veuillez saisir le montant du versement",
                                               csrf_token=new_token)

                    if not checkValue(Versa):
                        return render_template("AddPatient.html", error="Versement invalide", csrf_token=new_token)

                    Versa = float(Versa)

            if Versa > price:
                return render_template("AddPatient.html", error="Le versement ne doit pas être supérieur au prix",
                                       csrf_token=new_token)

            if khalsa == 'yes':
                Versa = price
                b9aw = 0
            else:
                b9aw = round(price - Versa, 2)

            patient_khalsa = 'yes' if b9aw == 0 else 'no'

            status = 'in process'
            patient_infos = [session['id'], firstName, lastName, unique, choice, date, 'no', price, patient_khalsa,
                             Versa, b9aw, deadLine, status]

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

                ProName = request.form.get('ProName', '').strip()
                ProNumber = request.form.get('ProNumber', '').strip()
                ProPrice = request.form.get('ProPrice', '').strip()
                ProDate = request.form.get('ProDate', '').strip()
                ProKhalsa = request.form.get('ProKhalsa', '').strip().lower()
                Proversa = request.form.get('Proversa', '').strip().lower()
                ProVersa = request.form.get('ProVersa', '').strip()
                ProDeadLine = request.form.get('ProDeadLine', '').strip()

                if not ProName:
                    return render_template("AddPatient.html", error="Le nom du prothésiste ne peut pas être vide",
                                           csrf_token=new_token)

                if ProName.isdigit():
                    return render_template("AddPatient.html", error="Nom du prothésiste invalide", csrf_token=new_token)

                if not ProNumber or not ProNumber.isdigit() or len(ProNumber) != 10:
                    return render_template("AddPatient.html",
                                           error="Le numéro du prothésiste doit contenir exactement 10 chiffres",
                                           csrf_token=new_token)

                if not ProKhalsa or ProKhalsa not in ['yes', 'no']:
                    return render_template("AddPatient.html",
                                           error="Vous devez saisir « yes » ou « no » pour Khalsa du prothésiste",
                                           csrf_token=new_token)

                if ProKhalsa == 'no':
                    if not Proversa or Proversa not in ['yes', 'no']:
                        return render_template("AddPatient.html",
                                               error="Dans le versement du prothésiste, saisissez « yes » ou « no »",
                                               csrf_token=new_token)

                if not ProDate or not ProDeadLine:
                    return render_template("AddPatient.html",
                                           error="La date et la date limite du prothésiste sont obligatoires",
                                           csrf_token=new_token)

                if ProDate < date:
                    return render_template("AddPatient.html", error="Date du prothésiste invalide",
                                           csrf_token=new_token)

                if ProDeadLine < ProDate:
                    return render_template("AddPatient.html", error="Date limite du prothésiste invalide",
                                           csrf_token=new_token)

                if ProDeadLine > deadLine:
                    return render_template("AddPatient.html",
                                           error="La date limite du prothésiste ne peut pas être postérieure à celle du patient",
                                           csrf_token=new_token)

                if not ProPrice:
                    return render_template("AddPatient.html", error="Le prix du prothésiste ne peut pas être vide",
                                           csrf_token=new_token)

                if not checkValue(ProPrice):
                    return render_template("AddPatient.html", error="Prix du prothésiste invalide",
                                           csrf_token=new_token)

                ProPrice = float(ProPrice)

                if ProKhalsa == 'yes':
                    ProVersa = ProPrice
                else:
                    if Proversa == 'no':
                        ProVersa = 0
                    else:
                        if not ProVersa:
                            return render_template("AddPatient.html",
                                                   error="Veuillez saisir le montant du versement du prothésiste",
                                                   csrf_token=new_token)

                        if not checkValue(ProVersa):
                            return render_template("AddPatient.html", error="Versement du prothésiste invalide",
                                                   csrf_token=new_token)

                        ProVersa = float(ProVersa)

                if ProVersa > ProPrice:
                    return render_template("AddPatient.html",
                                           error="Le versement du prothésiste ne doit pas être supérieur à son prix",
                                           csrf_token=new_token)

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
                    return render_template("AddPatient.html", error="Prothésiste introuvable", csrf_token=new_token)

                cursor.execute(""" 
                    INSERT INTO other_prothesists_khedma 
                        (patient_number, dentist_name, pName, pNumber, pDate, pKhedma, pPrice, pVersa, pB9aw, pKhalsa, pFinished, user_id, DeadLine) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
                """, (unique, None, ProName, ProNumber, ProDate, choice, ProPrice, ProVersa, Prob9aw, ProKhalsa, 'no',
                      session['id'], ProDeadLine))

                ProthesistsStat(cursor, conn, ProPrice, ProNumber, ProName, ProKhalsa, ProDate, ProVersa)

                Prothesist_History(cursor, conn, ProName, ProNumber, unique, firstName, lastName)

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
                """, (
                choice, price, date, 'NO', unique, 'no', patient_khalsa, ProName, ProNumber, session['id'], deadLine))

                Patient_History(cursor, conn, unique)
                PatientStats(cursor, conn, price, khalsa, date, Versa)

                conn.commit()

                cursor.execute(""" 
                                SELECT * FROM patient  
                                WHERE user_id = %s """, (session['id'],))
                data = cursor.fetchall()

                return render_template("PatientsFile.html", message="Patient ajouté avec succès", data=data,
                                       csrf_token=new_token)

            else:
                return render_template("PatientsFile.html", message="Le patient existe déjà", csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            return render_template("AddPatient.html", error=f"Erreur : {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@patients.route("/DeletePatient", methods=["POST", "GET"])
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
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        PatientF_deleted = request.form.get("DeleteF", "").strip()
        Confirm_PatientF = request.form.get("ConfirmDeletePatientF", "").strip()
        PatientL_deleted = request.form.get("DeleteL", "").strip()
        Confirm_PatientL = request.form.get("ConfirmDeletePatientL", "").strip()
        Patient_unique = request.form.get("uniquepatient", "").strip()
        Confirm_Unique = request.form.get("confirmunique", "").strip()

        if not Patient_unique or not Patient_unique.isdigit() or len(Patient_unique) != 10:
            return render_template("DeletePatient.html", error="Numéro d'identification invalide", csrf_token=new_token)

        if not Confirm_Unique or not Confirm_Unique.isdigit() or len(Confirm_Unique) != 10:
            return render_template("DeletePatient.html", error="Numéro d'identification invalide", csrf_token=new_token)

        if (PatientF_deleted != Confirm_PatientF or
                PatientL_deleted != Confirm_PatientL or
                Patient_unique != Confirm_Unique):
            return render_template("DeletePatient.html", error="Confirmation invalide", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute(""" 
                            SELECT p.patient_firstname, p.patient_lastname, pr.pName  
                            FROM other_prothesists_khedma pr  
                            JOIN patient p ON pr.user_id = p.user_id AND pr.patient_number = p.patient_number 
                            WHERE  
                            pr.user_id = %s AND pr.patient_number = %s """, (session['id'], Patient_unique))
            found = cursor.fetchone()

            if found:
                if found[0] == PatientF_deleted and found[1] == PatientL_deleted:
                    return render_template("DeletePatient.html",
                                           message=f"Ce service est toujours chez {found[2]}, nous ne pouvons pas le supprimer",
                                           csrf_token=new_token)

            cursor.execute(""" 
                    SELECT versa , b9aw , MONTH(la_date) , YEAR(la_date)   
                    FROM patient  
                    WHERE patient_firstname = %s AND patient_lastname = %s  
                    AND patient_number = %s AND user_id = %s  
                    """, (PatientF_deleted, PatientL_deleted, Patient_unique, session['id']))

            result = cursor.fetchone()

            if not result:
                return render_template("DeletePatient.html", message="Le patient n'existe pas", csrf_token=new_token)

            versa = result[0]
            b9aw = result[1]
            month = result[2]
            year = result[3]

            cursor.execute(""" 
                                UPDATE patient_stat  
                                SET  
                                patients_number = patients_number - 1 , 
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

            return render_template("PatientsFile.html", message="Patient supprimé avec succès", data=data,
                                   csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            return render_template("DeletePatient.html", error=f"Erreur : {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@patients.route("/ModifyVersaPatient", methods=["POST", "GET"])
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
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        Patient_Id = request.form.get("PatientId", "").strip()
        VersaValue = request.form.get("VersaValue", "").strip()
        ConfirmVersa = request.form.get("ConfirmVersaValue", "").strip()

        if not Patient_Id or not Patient_Id.isdigit() or len(Patient_Id) != 10:
            return render_template(
                "ModifyPatientVersa.html",
                error="Identifiant invalide",
                csrf_token=new_token
            )

        if not VersaValue or not ConfirmVersa:
            return render_template("ModifyDentistVersement.html", error="Le versement ne peut pas être vide",
                                   csrf_token=new_token)

        try:
            VersaValue = float(VersaValue)
            ConfirmVersa = float(ConfirmVersa)
        except (ValueError, TypeError):
            return render_template("ModifyDentistVersement.html", error="Valeur du versement invalide",
                                   csrf_token=new_token)

        if VersaValue != ConfirmVersa:
            return render_template(
                "ModifyPatientVersa.html",
                error="Le versement et sa confirmation doivent avoir la même valeur",
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
                    error="Patient introuvable",
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
                    message="Le patient a déjà payé son service",
                    csrf_token=new_token
                )

            new_versa = round(oldVersa + VersaValue, 2)

            if new_versa > total:
                return render_template(
                    "ModifyPatientVersa.html",
                    error="Montant du versement invalide",
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
                if b9aw > total:
                    return render_template("ModifyDentistVersement.html", message="Versement invalide",
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
                message="Informations mises à jour",
                data=data,
                csrf_token=new_token
            )

        except Exception as e:
            conn.rollback()
            return render_template(
                "ModifyPatientVersa.html",
                error=f"Erreur : {str(e)}",
                csrf_token=new_token
            )

        finally:
            cursor.close()
            conn.close()


@patients.route("/PatientStat")
def PatietStat():
    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute(""" 
                        DELETE FROM patient_stat  
                        WHERE  
                        patients_number = 0  
                        AND khalsin = 0  
                        AND machi_khalsin = 0  
                        AND user_id = %s  
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


@patients.route("/PatientHistory", methods=["POST", "GET"])
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

            try:

                cursor.execute(""" 
                                SELECT * FROM patient_history  
                                WHERE user_id = %s """, (session['id'],))
                result = cursor.fetchall()

                if result:
                    return render_template(
                        "PatientHistory.html",
                        History=result,
                        csrf_token=token
                    )
                else:
                    return render_template(
                        "PatientHistory.html",
                        message="Aucun historique",
                        csrf_token=token
                    )

            except Exception as e:
                conn.rollback()
                return f"Erreur : {str(e)}"

            finally:
                cursor.close()
                conn.close()

        if request.method == "POST":
            form_token = request.form.get("csrf_token")
            session_token = session.get("csrf_token")

            # print("FORM TOKEN --> ",form_token)
            # print("SESSION TOKEN --> ",session['csrf_token'])

            # print( form_token == session['csrf_token'])

            if not form_token or form_token != session_token:
                return "Attaque CSRF détectée", 403

            new_token = secrets.token_hex(16)
            session["csrf_token"] = new_token

            patientName = request.form.get("SearchName")

            if patientName.isdigit():
                if not patientName or not patientName.isdigit() or int(patientName) < 0 or len(patientName) < 10:
                    return render_template("PatientHistory.html",
                                           message="Identifiant invalide",
                                           csrf_token=new_token)
                    # here the patientName is the patient number because the condition is True
                cursor.execute(""" 
                                SELECT * FROM patient_history  
                                WHERE pNumber = %s AND user_id = %s  
                                """, (patientName, session['id']))
                result = cursor.fetchall()
                if result:
                    return render_template("PatientHistory.html", HistoryPatient=result, csrf_token=new_token)
                else:
                    return render_template("PatientHistory.html", message="Patient introuvable", csrf_token=new_token)

            cursor.execute(""" 
                SELECT * FROM patient_history 
                WHERE user_id = %s AND LOWER(firstname) = LOWER(%s) 
            """, (session['id'], patientName))
            result = cursor.fetchall()

            if not result:
                cursor.execute(""" 
                                SELECT * FROM patient_history 
                                WHERE user_id = %s AND LOWER(lastname) = LOWER(%s) 
                            """, (session['id'], patientName))
                result = cursor.fetchall()

            if result:
                return render_template("PatientHistory.html", HistoryPatient=result, csrf_token=new_token)
            else:
                return render_template("PatientHistory.html", message="Patient introuvable", csrf_token=new_token)

    finally:
        cursor.close()
        conn.close()


@patients.route("/AllPatientsHistory")
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
                            pDate <= DATE_SUB(CURDATE() , INTERVAL 25 MONTH) AND user_id = %s 
                            AND ( (b9aw = 0 AND status = 'finished') OR (status = 'deleted'))""",
                       (session['id'],))
        conn.commit()

        cursor.execute("SELECT * FROM patient_history WHERE user_id = %s", (session['id'],))
        resultAll = cursor.fetchall()
        if resultAll:
            return render_template("PatientHistory.html", History=resultAll, csrf_token=token)
        else:
            return render_template("PatientHistory.html", message="Table introuvable", csrf_token=token)
    finally:
        cursor.close()
        conn.close()


@patients.route("/PatientByDateASC")
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


@patients.route("/PatientByDateDESC")
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


@patients.route("/PatientByDeadLine")
def ShowByDeadLine():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute(""" 
                       SELECT * FROM patient  
                       WHERE user_id = %s  
                       ORDER BY DeadLine ASC """, (session['id'],))
        dateDeadLine = cursor.fetchall()
        return render_template("PatientsFile.html", dateDeadLine=dateDeadLine)

    finally:
        cursor.close()
        conn.close()


@patients.route("/PatientByB9aw")
def ShowByB9aw():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("SELECT * FROM patient WHERE user_id = %s ORDER BY b9aw DESC", (session['id'],))
        rows = cursor.fetchall()
        return render_template("PatientsFile.html", dataPrix=rows)
    finally:
        cursor.close()
        conn.close()


@patients.route("/UpdatePatientStatus", methods=["POST", "GET"])
def UpdatePatientStatus():
    if not is_logged_in():
        return jsonify({
            'success': False,
            'message': "utilisateur non autorisé"
        }), 401

    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'message': 'Données non reçues'
        }), 401

    patientID = data.get('patient_number')
    status = data.get('status')

    if not patientID or not status:
        return jsonify({
            'success': False,
            'message': 'Le numéro du patient et le statut sont obligatoires'
        }), 403

    allowed_status = ['in process', 'prothesist', 'montage', 'esseyage', 'finished']

    if status not in allowed_status:
        return jsonify({
            'success': False,
            'message': 'Valeur du statut invalide'
        }), 403

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:

        cursor.execute(""" 
                        SELECT 1  
                        FROM patient  
                        WHERE user_id = %s AND patient_number = %s """,
                       (session['id'], patientID))

        found = cursor.fetchone()

        if not found:
            return jsonify({
                'success': False,
                'message': 'Patient introuvable'
            }), 403

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
            'success': False,
            'message': f'Erreur : {str(e)}'
        })

    finally:
        cursor.close()
        conn.close()

    return jsonify({
        'success': True,
        'message': 'Statut mis à jour avec succès'
    })
