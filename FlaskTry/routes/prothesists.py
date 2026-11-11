import secrets
from flask import Blueprint, request, render_template, redirect, url_for, session, jsonify
from FlaskTry.FunctionFile import *
from FlaskTry.ConnectToSql import get_connection
from datetime import date

prothesists = Blueprint("prothesists", __name__, url_prefix="/prothesists")

def is_logged_in():
    return "id" in session

@prothesists.route("/ProKhedma", methods=["GET"])
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

@prothesists.route("/AddProthesist", methods=["POST", "GET"])
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
                return "Attaque CSRF détectée", 403

            new_token = secrets.token_hex(16)
            session["csrf_token"] = new_token

            prothesist_name = request.form.get("prothesistName")
            prothesist_number = request.form.get('prothesistNumber')

            if not prothesist_name or prothesist_name.isdigit():
                return render_template("AddProthesist.html", message="Nom du prothésiste invalide", csrf_token=new_token)

            if not prothesist_number or not prothesist_number.isdigit() or len(prothesist_number) != 10:
                return render_template("AddProthesist.html", message="Numéro du prothésiste invalide", csrf_token=new_token)

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
                return render_template("AddProthesist.html", message=f"Prothésiste {prothesist_name} ajouté avec succès", csrf_token=new_token)
            else:
                return render_template("AddProthesist.html", message=f"Le prothésiste {prothesist_name} - {prothesist_number} existe déjà", csrf_token=new_token)
    finally:
        cursor.close()
        conn.close()


@prothesists.route("/ProthesistHistory", methods=["POST", "GET"])
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

        try :
            cursor.execute("""
                            DELETE FROM other_prothesists_history 
                            WHERE 
                                pDate <= DATE_SUB(CURDATE() , INTERVAL 25 MONTH) AND user_id = %s
                                AND ( (b9aw = 0 AND status = 'finished') OR (status = 'deleted'))""",
                           (session['id'],))
            conn.commit()

        except Exception as e :
            conn.rollback()
            return f"Erreur : {str(e)}"

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
                message="Tableau introuvable",
                csrf_token=token
            )

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        print("FORM TOKEN --> ",form_token)
        print("SESSION TOKEN --> ",session['csrf_token'])
        print(form_token == session['csrf_token'])

        if not form_token or form_token != session_token:
            return "Attaque CSRF détectée", 403

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
                    return render_template("ProthesistHistory.html", message="Prothésiste introuvable", csrf_token=new_token)

            cursor.execute("""
                        SELECT * FROM other_prothesists_history
                        WHERE user_id = %s AND prothesist = %s
                    """, (session['id'], prothesist_name.lower()))
            result = cursor.fetchall()
            if result:
                return render_template("ProthesistHistory.html", HistoryProthesist=result, csrf_token=new_token)
            else:
                return render_template("ProthesistHistory.html",
                                       message="Prothésiste introuvable", csrf_token=new_token)
        finally:
            cursor.close()
            conn.close()


@prothesists.route("/AllProthesistHistory")
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
                            pDate <= DATE_SUB(CURDATE() , INTERVAL 25 MONTH) AND user_id = %s
                            AND ( (b9aw = 0 AND status = 'finished') OR (status = 'deleted'))""",
                       (session['id'],))
        conn.commit()

        cursor.execute("SELECT * FROM other_prothesists_history WHERE user_id = %s", (session['id'],))
        result = cursor.fetchall()
        if result:
            return render_template("ProthesistHistory.html", History=result, csrf_token=session['csrf_token'])
        else:
            return render_template("ProthesistHistory.html", message="Tableau introuvable", csrf_token=session['csrf_token'])
    finally:
        cursor.close()
        conn.close()


@prothesists.route("/ProFinished", methods=["POST", "GET"])
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
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        ProthesistName   = request.form.get('ProthesistName')
        ProthesistNumber = request.form.get('ProthesistNumber')
        choice           = request.form.get('Choice')

        if not ProthesistNumber or not ProthesistNumber.isdigit() or len(ProthesistNumber) != 10:
            return render_template("FinishedProKhedma.html", error="Numéro du prothésiste invalide", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute("""
                SELECT 1 FROM other_prothesists
                WHERE user_id = %s AND pName = %s AND pNumber = %s
            """, (session['id'], ProthesistName, ProthesistNumber))
            row = cursor.fetchone()
            if not row:
                return render_template("FinishedProKhedma.html", message="Prothésiste introuvable", csrf_token=new_token)

            if choice.lower() == "patient":
                patientId = request.form.get('PatientID')
                khedmaID = request.form.get('ServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) != 10:
                    return render_template("FinishedProKhedma.html", error="ID du patient invalide", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("FinishedProKhedma.html", error="ID du service invalide", csrf_token=new_token)

                cursor.execute("""
                    SELECT 1 FROM patient_history
                    WHERE id = %s AND pNumber = %s
                """, (khedmaID, patientId))

                result = cursor.fetchone()

                if not result:
                    return render_template("FinishedProKhedma.html", message="Patient introuvable", csrf_token=new_token)

                cursor.execute("""
                               SELECT ph.id, pr.id  
                               FROM patient_history ph  
                               JOIN other_prothesists_khedma pr ON pr.patient_number = ph.pNumber AND pr.user_id = ph.user_id
                               WHERE ph.pNumber = %s AND ph.user_id = %s
                               """,(patientId,session['id']))
                result = cursor.fetchone()

                if not result :
                    return render_template("FinishedProKhedma.html" , message="Service introuvable", csrf_token=new_token)

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
                    return render_template("FinishedProKhedma.html", error="ID du patient invalide", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("FinishedProKhedma.html", error="ID du service invalide", csrf_token=new_token)

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
                    return render_template("FinishedProKhedma.html", message="Patient introuvable",
                                           csrf_token=new_token)

                cursor.execute("""
                                SELECT dh.id, pr.id 
                                FROM dentist_history dh
                                JOIN other_prothesists_khedma pr ON pr.patient_number = dh.pNumber AND pr.user_id = dh.user_id
                                WHERE dh.pNumber = %s AND dh.user_id = %s AND dh.dentistname = %s
                                """,(patientId, session['id'], dentistName))

                result = cursor.fetchone()

                if not result:
                    return render_template("FinishedProKhedma.html", message="Service introuvable", csrf_token=new_token)

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
                return render_template("FinishedProKhedma.html", error="Vous devez saisir « patient » ou « dentist »", csrf_token=new_token)

            conn.commit()
            cursor.execute("""
                            SELECT * FROM other_prothesists_khedma 
                            WHERE user_id = %s """, (session['id'],))
            result = cursor.fetchall()
            return render_template("ALLProKhedma.html", message="Informations mises à jour avec succès", result=result, csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("FinishedProKhedma.html", error=f"Erreur : {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@prothesists.route("/ProKhalsa", methods=["POST", "GET"])
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
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        ProName = request.form.get('ProthesistChoice')
        ProNumber = request.form.get('ProthesistNumber')
        choice    = request.form.get('Choice')

        if not ProNumber or not ProNumber.isdigit() or len(ProNumber) != 10:
            return render_template("KhedmaProKhalsa.html", error="Numéro du prothésiste invalide", csrf_token=new_token)

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
                return render_template("KhedmaProKhalsa.html" , message="Prothésiste introuvable" , csrf_token=new_token)


            if choice.lower() == "patient":
                patientId = request.form.get('PatientID')
                khedmaID = request.form.get('ServiceID')

                if not patientId or not patientId.isdigit() or len(patientId) != 10:
                    return render_template("KhedmaProKhalsa.html", error="ID du patient invalide", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("KhedmaProKhalsa.html", error="ID du service invalide", csrf_token=new_token)

                cursor.execute("""
                    SELECT 1 
                    FROM patient_history  
                    WHERE id = %s  AND pNumber = %s AND user_id = %s
                """, (khedmaID, patientId, session['id']))
                result = cursor.fetchone()

                if not result:
                    return render_template("KhedmaProKhalsa.html", message="Patient introuvable", csrf_token=new_token)

                cursor.execute("""
                                SELECT ph.id, pr.id 
                                FROM patient_history ph  
                                JOIN other_prothesists_khedma pr ON pr.patient_number = ph.pNumber AND pr.user_id = ph.user_id 
                                WHERE ph.pNumber = %s AND ph.user_id = %s 
                               """, (patientId, session['id']))

                result = cursor.fetchone()

                print(result)

                if not result:
                    return render_template("KhedmaProKhalsa.html", message="Service introuvable", csrf_token=new_token)

                cursor.execute("""
                                SELECT pPrice, pDate, pKhalsa, pB9aw 
                                FROM other_prothesists_khedma 
                                WHERE pName = %s AND pNumber = %s AND patient_number = %s AND user_id = %s
                                """,(ProName, ProNumber, patientId, session['id']))
                data = cursor.fetchone()

                print(result)
                if not data :
                    return render_template("KhedmaProKhalsa.html", message="Patient introuvable", csrf_token=new_token)

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
                    return render_template("KhedmaProKhalsa.html", message="Service déjà payé", csrf_token=new_token)

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
                    return render_template("KhedmaProKhalsa.html", error="ID du patient invalide", csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("KhedmaProKhalsa.html", error="ID du service invalide", csrf_token=new_token)

                if not SearcheTable(cursor, Dentistname):
                    return render_template("KhedmaProKhalsa.html", error="Nom du dentiste incorrect", csrf_token=new_token)

                cursor.execute("""
                    SELECT 1 FROM dentist_history
                    WHERE id = %s AND pNumber = %s AND dentistname = %s AND user_id = %s
                """, (khedmaID, patientId, Dentistname, session['id']))
                result = cursor.fetchone()

                if not result:
                    return render_template("KhedmaProKhalsa.html", message="Patient introuvable", csrf_token=new_token)

                cursor.execute("""
                                    SELECT d.id, k.id, pr.id 
                                    FROM dentists d 
                                    JOIN khedma k ON k.khedma_patient = d.patient_number AND k.user_id = d.user_id 
                                    JOIN other_prothesists_khedma pr ON pr.patient_number = d.patient_number AND pr.user_id = d.user_id 
                                    WHERE d.patient_number = %s AND d.user_id = %s AND d.dentist_name = %s""",
                               (patientId, session['id'], Dentistname))

                result = cursor.fetchone()

                if not result :
                    return render_template("KhedmaProKhalsa.html", message="Service introuvable", csrf_token=new_token)


                cursor.execute("""
                                SELECT pPrice, pDate, pKhalsa, pB9aw
                                FROM other_prothesists_khedma 
                                WHERE pName = %s AND pNumber = %s AND dentist_name = %s AND patient_number = %s AND user_id = %s
                                """,(ProName, ProNumber, Dentistname, patientId, session['id']))
                data = cursor.fetchone()

                if not result :
                    return render_template("KhedmaProKhalsa.html", message="Patient introuvable", csrf_token=new_token)

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
                    return render_template("KhedmaProKhalsa.html", message="Service déjà payé", csrf_token=new_token)

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
                return render_template("KhedmaProKhalsa.html", error="Vous devez saisir (patient / dentist)", csrf_token=new_token)

            conn.commit()
            cursor.execute("""
                            SELECT * FROM other_prothesists_khedma 
                            WHERE user_id = %s """,(session['id'],))
            result = cursor.fetchall()

            return render_template("ALLProKhedma.html", message="Paiement mis à jour avec succès", result=result, csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("KhedmaProKhalsa.html", error=f"Erreur : {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


# Assuming this is part of your main prothesists file or blueprint

@prothesists.route("/ProGetKhedma", methods=["POST", "GET"])
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
            return "Attaque CSRF détectée", 403

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
                                   error="❌ Numéro du prothésiste invalide ! Il doit comporter exactement 10 chiffres.",
                                   csrf_token=new_token)

        try:
            price = float(price)
        except (ValueError, TypeError):
            return render_template("ProthesistGetKhedma.html",
                                   error="❌ Valeur du prix invalide !",
                                   csrf_token=new_token)

        if price < 0:
            return render_template("ProthesistGetKhedma.html",
                                   error="❌ Le prix ne peut pas être négatif !",
                                   csrf_token=new_token)

        if khalsa.lower() not in ["yes", "no"]:
            return render_template("ProthesistGetKhedma.html",
                                   error="❌ Khalsa doit être « yes » ou « no » !",
                                   csrf_token=new_token)

        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()
            deadLine = datetime.strptime(deadLine, "%Y-%m-%d").date()
        except ValueError:
            return render_template(
                "ProthesistGetKhedma.html",
                error="❌ Date invalide ! Utilisez le format MM-JJ-AAAA.",
                csrf_token=new_token
            )

        # Validate dates
        if deadLine < date:
            return render_template("ProthesistGetKhedma.html", error="❌ La date limite doit être postérieure à la date de début !", csrf_token=new_token)

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
                return render_template("ProthesistGetKhedma.html", error="Prothésiste introuvable", csrf_token=new_token)


            # ========== PATIENT SOURCE ==========
            if source.lower() == "patient":
                patientNumber = request.form.get('PatientSource')

                # Validate patient number
                if not patientNumber or not patientNumber.isdigit() or len(patientNumber) != 10:
                    return render_template("ProthesistGetKhedma.html",
                                           error="❌ Numéro du patient invalide ! Il doit comporter 10 chiffres."
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
                                           error="❌ Patient introuvable ! Vérifiez le numéro du patient."
                                           , csrf_token=new_token)

                if result[0].lower() == "yes":
                    return render_template("ProthesistGetKhedma.html",
                                           message="⚠️ Le travail de ce patient est déjà terminé !"
                                           , csrf_token=new_token)

                if result[2] > date :
                    return render_template("ProthesistGetKhedma.html",
                                           error="⚠️ Date d'entrée incorrecte."
                                           , csrf_token=new_token)

                if deadLine >= result[3] :
                    return render_template("ProthesistGetKhedma.html",
                                           error="⚠️ Date limite incorrecte."
                                           , csrf_token=new_token)


                # Calculate payment amounts
                if khalsa.lower() == "no":
                    versaChoice = request.form.get("VersaChoice", "no")

                    if versaChoice.lower() == "yes":
                        try:
                            versaValue = float(request.form.get("VersementValue"))
                        except (ValueError, KeyError, TypeError):
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Montant du paiement invalide ! Veuillez saisir un nombre valide."
                                                   , csrf_token=new_token)

                        if versaValue < 0:
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Le montant du paiement ne peut pas être négatif !"
                                                   , csrf_token=new_token)

                        if versaValue == price:
                            b9aw = 0
                            khalsa = "yes"
                        elif versaValue > price:
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Le montant du paiement ne peut pas dépasser le prix total !"
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
                                           message=f"Ce service est déjà attribué à {found[0]}"
                                           , csrf_token=new_token)

                # Insert the work order
                cursor.execute("""
                    INSERT INTO other_prothesists_khedma 
                    (user_id, patient_number, dentist_name, pName, pNumber, pKhedma, pPrice, pVersa, pB9aw, pKhalsa, pFinished, pDate, DeadLine)  
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """,
                               (session['id'], patientNumber, None, ProthesistName, ProthesistNumber, result[1], price,
                                versaValue, b9aw, khalsa, "no", date, deadLine))

                Prothesist_History(cursor, conn, ProthesistName, ProthesistNumber,
                                   patientNumber, result[4], result[5])

                cursor.execute("""
                                UPDATE patient 
                                SET status = 'prothesist' 
                                WHERE patient_number = %s AND user_id = %s """
                               ,(patientNumber, session['id']))

                cursor.execute("""
                                SELECT ph.id 
                                FROM patient_history ph
                                JOIN patient p ON p.user_id = ph.user_id AND DATE(p.la_date) = DATE(ph.pDate) = 0 AND p.patient_number = ph.pNumber
                                WHERE ph.user_id = %s AND ph.pNumber = %s
                                """,(session['id'], patientNumber))
                ph_id = cursor.fetchone()

                cursor.execute("""
                                UPDATE patient_history
                                SET status = 'prothesist' 
                                WHERE id = %s AND user_id = %s """
                               , (ph_id[0], session['id']))

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
                                       message="✅ Travail créé avec succès ! Le travail du patient a été ajouté à la liste de " + ProthesistName + "."
                                       , csrf_token=new_token)

            # ========== DENTIST SOURCE ==========
            else:
                dentistName = request.form.get("DentistSource", "")
                patientNumber = request.form.get("Dentistnumber", "")

                if not dentistName or not patientNumber:
                    return render_template("ProthesistGetKhedma.html",
                                           error="❌ Le nom du dentiste et le numéro du patient sont obligatoires !", csrf_token=new_token)

                if not patientNumber.isdigit() or len(patientNumber) > 10 :
                    return render_template("ProthesistGetKhedma.html",
                                           error="❌ Numéro du patient invalide !",
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
                                           error="❌ Travail introuvable ! Vérifiez le nom du dentiste et le numéro du patient.", csrf_token=new_token)

                if result[0].lower() == "yes":
                    return render_template("ProthesistGetKhedma.html",
                                           message="⚠️ Ce travail est déjà terminé !", csrf_token=new_token)

                if result[2] > date :
                    return render_template("ProthesistGetKhedma.html",
                                           error="⚠️ Date d'entrée incorrecte."
                                           , csrf_token=new_token)

                if result[3] < deadLine :
                    return render_template("ProthesistGetKhedma.html",
                                           error="⚠️ Date limite incorrecte."
                                           , csrf_token=new_token)

                # Calculate payment amounts
                if khalsa.lower() == "no":
                    versaChoice = request.form.get("VersaChoice", "no")

                    if versaChoice.lower() == "yes":
                        try:
                            versaValue = float(request.form.get("VersementValue"))
                        except (ValueError, KeyError, TypeError):
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Montant du paiement invalide ! Veuillez saisir un nombre valide.", csrf_token=new_token)

                        if versaValue < 0:
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Le montant du paiement ne peut pas être négatif !", csrf_token=new_token)

                        if versaValue == price:
                            b9aw = 0
                            khalsa = "yes"
                        elif versaValue > price:
                            return render_template("ProthesistGetKhedma.html",
                                                   error="❌ Le montant du paiement ne peut pas dépasser le prix total !", csrf_token=new_token)
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
                                           message=f"Ce service est déjà attribué à {found[0]}"
                                           , csrf_token=new_token)

                # Insert the work order
                cursor.execute("""
                                INSERT INTO other_prothesists_khedma 
                                (user_id, patient_number, dentist_name, pName, pNumber, pKhedma, pPrice, pVersa, pB9aw, pKhalsa, pFinished, pDate, DeadLine)  
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """,
                               (session['id'], patientNumber, dentistName, ProthesistName, ProthesistNumber, result[1], price,
                                versaValue, b9aw, khalsa, "no", date, deadLine))

                Prothesist_History(cursor, conn, ProthesistName, ProthesistNumber,
                                   patientNumber, result[4], result[5])

                cursor.execute("""
                                UPDATE dentists 
                                SET status = 'prothesist' 
                                WHERE dentist_name = %s AND patient_number = %s AND user_id = %s """,
                               (dentistName, patientNumber, session['id']))

                cursor.execute("""
                                SELECT ph.id 
                                FROM dentist_history dh
                                JOIN dentists d ON d.user_id = dh.user_id AND DATE(d.date) = DATE(dh.pDate) = 0 AND d.patient_number = dh.pNumber AND d.dentist_name = dh.dentistname
                                WHERE dh.user_id = %s AND dh.pNumber = %s AND dh.dentistname = %s
                                """, (session['id'], patientNumber, dentistName))
                ph_id = cursor.fetchone()

                cursor.execute("""
                                UPDATE dentist_history
                                SET status = 'prothesist' 
                                WHERE id = %s AND user_id = %s """
                               , (ph_id[0], session['id']))

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
                                       message="✅ Travail créé avec succès ! Le travail provenant du dentiste a été ajouté à la liste de " + ProthesistName + "."
                                       , csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            return render_template("ProthesistGetKhedma.html",
                                   error=f"❌ Erreur de base de données : {str(e)}", csrf_token=new_token)
        finally:
            cursor.close()
            conn.close()




@prothesists.route("/DeleteProthesistKhedma", methods=["POST", "GET"])
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
            return "Erreur : attaque CSRF détectée",403

        new_token = secrets.token_hex(16)
        session['csrf_token'] = new_token

        ProName = request.form.get('ProName')
        checkProName = request.form.get('CheckProName')
        ProNumber = request.form.get('ProNumber')
        checkProNumber = request.form.get('CheckProNumber')
        PatientNumber = request.form.get('PatientNumber')
        checkPatientNumber = request.form.get('CheckPatientNumber')

        if not ProName or not checkProName :
            return render_template("DeleteProthesistPatient.html", error="Le nom du prothésiste et sa confirmation sont obligatoires", csrf_token=new_token)

        if not ProNumber or not checkProNumber :
            return render_template("DeleteProthesistPatient.html", error="Le numéro du prothésiste et sa confirmation sont obligatoires", csrf_token=new_token)

        if not PatientNumber or not checkPatientNumber :
            return render_template("DeleteProthesistPatient.html", error="Le numéro du patient et sa confirmation sont obligatoires", csrf_token=new_token)

        if not ProNumber.isdigit() or len(ProNumber) != 10 :
            return render_template("DeleteProthesistPatient.html", error="Numéro du prothésiste invalide ! Il doit comporter exactement 10 chiffres", csrf_token=new_token)

        if not PatientNumber.isdigit() or len(PatientNumber) > 10 :
            return render_template("DeleteProthesistPatient.html", error="Numéro du patient invalide ! Il doit comporter exactement 10 chiffres", csrf_token=new_token)

        if ProName != checkProName or ProNumber != checkProNumber or PatientNumber != checkPatientNumber :
            return render_template("DeleteProthesistPatient.html",
                                   error="La confirmation doit être identique aux informations saisies",
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
                return render_template("DeleteProthesistPatient.html", message=f"Service introuvable pour le prothésiste {ProName}", csrf_token=new_token)

            if found[5] == 'yes' :
                cursor.execute("""
                                SELECT * FROM other_prothesists_khedma WHERE user_id = %s """,(session['id'],))
                result = cursor.fetchall()
                return render_template("ALLProKhedma.html", result=result, message=f"Service déjà terminé", csrf_token=new_token)

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

            return render_template("ALLProKhedma.html", result=result, message="Service supprimé avec succès", csrf_token=new_token)


        except Exception as e :
            conn.rollback()
            return render_template("DeleteProthesistPatient.html", error=f"Erreur : {str(e)}", csrf_token=new_token)

        finally :
            cursor.close()
            conn.close()


@prothesists.route("/ProModifyVersement" , methods=["POST" , "GET"])
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
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token


        ProthesistName = request.form.get("ProthesistName")
        ProthesistNumber = request.form.get("ProthesistNumber")
        khedmaSource = request.form.get("khedmaSource")
        versaValue = request.form.get("VersaValue")

        if not ProthesistNumber or not ProthesistNumber.isdigit() or len(ProthesistNumber) != 10:
            return render_template("ProthesistModifyVersement.html",
                                   error="Numéro du prothésiste invalide ! Il doit comporter exactement 10 chiffres",
                                   csrf_token=new_token)

        try:
            versaValue = float(versaValue)
        except (ValueError, TypeError):
            return render_template("ProthesistModifyVersement.html",
                                   error="Montant du versement invalide",
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
                return render_template("ProthesistModifyVersement.html" , message="Prothésiste introuvable", csrf_token=new_token)

            if khedmaSource.lower() == "patient" :
                PatientNumber = request.form.get("PatientNumber")
                DentistName = None
                khedmaID = request.form.get('ServiceID')

                if not PatientNumber or not PatientNumber.isdigit() or len(PatientNumber) != 10:
                    return render_template("ProthesistModifyVersement.html",
                                           error="Numéro du patient invalide ! Il doit comporter exactement 10 chiffres",
                                           csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("ProthesistModifyVersement.html",
                                           error="ID du service invalide",
                                           csrf_token=new_token)

                cursor.execute("""
                                SELECT 1 
                                FROM patient_history 
                                WHERE id = %s AND pNumber = %s AND user_id = %s """
                               ,(khedmaID, PatientNumber, session['id']))
                found = cursor.fetchone()

                if not found :
                    return render_template("ProthesistModifyVersement.html", message="Patient introuvable",
                                           csrf_token=new_token)

                cursor.execute("""
                                SELECT pVersa , pPrice , pKhalsa , MONTH(pDate) , YEAR(pDate) 
                                FROM other_prothesists_Khedma 
                                WHERE user_id = %s AND pName = %s AND pNumber = %s AND patient_number = %s """,
                               (session['id'], ProthesistName, ProthesistNumber, PatientNumber))

                result = cursor.fetchone()

                if not result :
                    return render_template("ProthesistModifyVersement.html" , message="Service introuvable", csrf_token=new_token)

            else :
                DentistName = request.form.get("DentistName")
                PatientNumber = request.form.get("DentistNumber")
                khedmaID = request.form.get('DServiceID')

                if not PatientNumber or not PatientNumber.isdigit() or len(PatientNumber) > 10:
                    return render_template("ProthesistModifyVersement.html",
                                           error="Numéro du patient invalide",
                                           csrf_token=new_token)

                if not khedmaID or not khedmaID.isdigit():
                    return render_template("ProthesistModifyVersement.html",
                                           error="ID du service invalide",
                                           csrf_token=new_token)

                cursor.execute("""
                                    SELECT 1 
                                    FROM dentist_history 
                                    WHERE id = %s AND pNumber = %s AND dentistname = %s AND user_id = %s """
                               , (khedmaID, PatientNumber, DentistName, session['id']))
                found = cursor.fetchone()

                if not found :
                    return render_template("ProthesistModifyVersement.html", message="Patient introuvable",
                                           csrf_token=new_token)

                cursor.execute("""
                                 SELECT pVersa , pPrice , pKhalsa , MONTH(pDate) , YEAR(pDate) 
                                 FROM other_prothesists_Khedma 
                                 WHERE user_id = %s AND pName = %s AND pNumber = %s AND patient_number = %s AND dentist_name = %s """,
                (session['id'], ProthesistName, ProthesistNumber, PatientNumber, DentistName))

                result = cursor.fetchone()

                if not result:
                    return render_template("ProthesistModifyVersement.html", message="Service introuvable", csrf_token=new_token)

            oldVersa = result[0]
            price = result[1]
            khalsa = result[2]
            month = result[3]
            year = result[4]

            newVersa = float(oldVersa) + versaValue
            b9aw = float(price) - newVersa

            if b9aw > float(price):
                return render_template("ProthesistModifyVersement.html", error="Montant du versement invalide",
                                       csrf_token=new_token)

            if khalsa == "yes" and versaValue > 0 :
                return render_template("ProthesistModifyVersement.html" , message="Service déjà payé", csrf_token=new_token)

            if newVersa > price :
                return render_template("ProthesistModifyVersement.html" , error="Montant du versement invalide", csrf_token=new_token)

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

            return render_template("KhedmaProFile.html" , message="Informations mises à jour avec succès", csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("ProthesistModifyVersement.html", error=f"Erreur : {str(e)}", csrf_token=new_token )

        finally :
            cursor.close()
            conn.close()


@prothesists.route("/ProAllkhedma", methods=["GET"])
def Proallkhedma():

    if not is_logged_in():
        return redirect(url_for('home'))

    token = secrets.token_hex(16)
    session['csrf_token'] = token

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:

        cursor.execute("""
            SELECT *
            FROM other_prothesists_khedma
            WHERE user_id = %s
        """, (session['id'],))

        rows = cursor.fetchall()

        return render_template(
            "ALLProKhedma.html",
            result=rows,
            csrf_token=token
        )

    finally:
        cursor.close()
        conn.close()


@prothesists.route("/ProKhedmaByDateASC")
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


@prothesists.route("/ProKhedmaByDateDESC")
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


@prothesists.route("/ProMostKhedma", methods=["GET"])
def FindMostProKhedma():
    if not is_logged_in():
        return redirect(url_for('home'))

    new_token = session['csrf_token']

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        Pro_dics = ProthesistDics(cursor)
        if not Pro_dics:
            return render_template("ALLProKhedma.html", error="Aucun tableau de prothésiste trouvé.", csrf_toke= new_token)
        name, count = max(Pro_dics.items(), key=lambda x: x[1], default=('none', 0))
        if count == 0:
            return render_template("ALLProKhedma.html", message="Tous les tableaux sont vides.", csrf_token= new_token)
        cursor.execute("SELECT * FROM other_prothesists_khedma WHERE user_id = %s AND pName = %s",
                       (session['id'], name))
        result = cursor.fetchall()
        return render_template("ALLProKhedma.html", most=result, most_name=name, csrf_token= new_token)
    finally:
        cursor.close()
        conn.close()


@prothesists.route("/ProLessKhedma", methods=["GET"])
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
            return render_template("ALLProKhedma.html", message="Tous les prothésistes ont actuellement 0 service.", csrf_token= new_token)
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


@prothesists.route("/ProTotal", methods=["GET"])
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
        return render_template("ProStats.html", message="Aucune donnée sur les prothésistes trouvée.", csrf_token= token)
    finally:
        cursor.close()
        conn.close()


@prothesists.route("/ProStat")
def ProStat():
    if not is_logged_in():
        return redirect(url_for('home'))

    token = secrets.token_hex(16)
    session['csrf_token'] = token

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
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
                SELECT p.prothesist_name, p.prothesist_number, p.total_khedma, SUM(CASE WHEN o.status = 'finished' THEN 1 ELSE 0 END) AS total_finished,
                        SUM(CASE WHEN o.status NOT IN ('finished' , 'deleted') THEN 1 ELSE 0 END) AS total_not_finished,
                        p.khalsin, p.machi_khalsin, p.month, p.year
                FROM prothesist_stat p
                JOIN other_prothesists_history o ON p.user_id = o.user_id AND p.prothesist_name = o.prothesist 
                                                AND p.prothesist_number = o.pNumber AND MONTH(o.pDate) = p.month AND YEAR(o.pDate) = p.year
                WHERE p.user_id = %s
                  AND p.prothesist_name = %s
                  AND p.prothesist_number = %s
                GROUP BY p.month, p.year 
                ORDER BY p.year DESC, p.month DESC
            """, (session['id'], Pro[1], Pro[0]))

            rows = cursor.fetchall()

            print(rows[0])

            # Only add the prothesist if statistics exist
            if rows:
                result[Pro] = rows

        if result:
            return render_template(
                "ProStats.html",
                message="Tableau des statistiques",
                result=result,
                csrf_token=token
            )


        return render_template(
            "ProStats.html",
            message="Tableau introuvable (aucune statistique disponible)",
            csrf_token=token
        )

    except Exception as e:
        conn.rollback()
        return render_template(
            "ProStats.html",
            message=f"Erreur : {str(e)}",
            csrf_token=token
        )

    finally:
        cursor.close()
        conn.close()

@prothesists.route("/ProSearch", methods=["POST", "GET"])
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
                return "Attaque CSRF détectée", 403

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
                return render_template("ProStats.html", error=f"Prothésiste {ProName} introuvable", csrf_token=new_token)

    finally:
        cursor.close()
        conn.close()


@prothesists.route("/ProthesistFacture", methods=["GET"])
def ProthesistFacture():

    if not is_logged_in():
        return redirect(url_for("home"))

    prothesist = request.args.get("prothesist")
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    patientNumberShow = request.args.get("PatientNumberShow", "non")

    if not prothesist or month is None or year is None:
        return redirect(url_for("prothesists.ProStat"))

    if not 1 <= month <= 12 or year < 2000:
        return redirect(url_for("prothesists.ProStat"))

    if patientNumberShow not in ("oui", "non"):
        return redirect(url_for("prothesists.ProStat"))

    conn = get_connection()
    cursor = conn.cursor()

    try:

        if patientNumberShow == "oui":

            cursor.execute("""
                SELECT prothesist, pNumber, patient_number, pKhedma, versement, b9aw,
                    pDate, STATUS
                FROM other_prothesists_history
                WHERE 
                user_id = %s AND prothesist = %s AND MONTH(pDate) = %s AND YEAR(pDate) = %s
            """, (session["id"], prothesist, month, year))

            results = cursor.fetchall()

            details = []

            for row in results:

                details.append({
                    "prothesistName": row[0],
                    "prothesistNumber": row[1],
                    "patientNumber": row[2],
                    "service": row[3],
                    "versement": float(row[4] or 0),
                    "remaining": float(row[5] or 0),
                    "date": row[6],
                    "status": row[7]
                })

        else:

            cursor.execute("""
                SELECT prothesist, pNumber, pKhedma, versement, b9aw, pDate, STATUS
                FROM other_prothesists_history
                WHERE 
                user_id = %s AND prothesist = %s AND MONTH(pDate) = %s AND YEAR(pDate) = %s
            """, (session["id"], prothesist, month, year))

            results = cursor.fetchall()

            details = []

            for row in results:

                details.append({
                    "prothesistName": row[0],
                    "prothesistNumber": row[1],
                    "patientNumber": None,
                    "service": row[2],
                    "versement": float(row[3] or 0),
                    "remaining": float(row[4] or 0),
                    "date": row[5],
                    "status": row[6]
                })

        if not details:
            return redirect(url_for("prothesists.ProStat"))

        total_versement = sum(d["versement"] for d in details if d['status'] != 'deleted')
        total = sum(d["remaining"] for d in details if d['status'] != 'deleted')

        month_names = [
            "Janvier", "Février", "Mars", "Avril",
            "Mai", "Juin", "Juillet", "Août",
            "Septembre", "Octobre", "Novembre", "Décembre"
        ]

        return render_template(
            "ProthesistFacture.html",
            prothesistName=prothesist,
            month=month,
            year=year,
            month_name=month_names[month - 1],
            invoice_number=f"PL-{session['id']}-{year}{month:02d}",
            emission_date=date.today().strftime("%d/%m/%Y"),
            details=details,
            total_versement=total_versement,
            total=total,
            show_patient_numbers=(patientNumberShow == "oui")
        )

    except Exception as e:

        conn.rollback()
        print("Prothesist invoice error:", e)

        return redirect(url_for("prothesists.ProStat"))

    finally:
        cursor.close()
        conn.close()

