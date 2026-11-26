import secrets
from flask import Blueprint, request, render_template, redirect, url_for, session, jsonify
from ManageMyLab.FunctionFile import *
from ManageMyLab.ConnectToSql import get_connection
from datetime import date

dentists = Blueprint("dentists", __name__, url_prefix="/dentists")


def is_logged_in():
    return "id" in session and session['id'] and "email_confirmed" in session and session['email_confirmed'] 



@dentists.route("/Dentist", methods=["POST", "GET"])
def DentistPage():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:

            cursor.execute(""" 
                            DELETE FROM dentists  
                            WHERE  
                            finished = %s AND khalsa = %s AND user_id = %s """,
                           ('yes', 'yes', session['id']))
            conn.commit()

            cursor.execute("SELECT * FROM dentists WHERE user_id = %s ",
                           (session["id"],))
            rows = cursor.fetchall()

        finally:
            cursor.close()
            conn.close()

        return render_template("DentistFile.html", result=rows, csrf_token=token)

        # POST request handling
    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:

        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")


        if not form_token or not session_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        token = secrets.token_hex(16)
        session["csrf_token"] = token

        DentistName = request.form.get("SearchBar")
        if SearcheTable(cursor, DentistName):
            cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                           (session["id"], DentistName))
            rows = cursor.fetchall()

            return render_template("DentistFile.html", result=rows, csrf_token=token)

        elif DentistName.isdigit():
            if not DentistName or not DentistName.isdigit() or int(DentistName) < 0:
                return render_template("DentistFile.html",
                                       message="ID invalide ", csrf_token=token)

            cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND patient_number = %s",
                           (session['id'], DentistName))
            rows = cursor.fetchall()

            return render_template("DentistFile.html", result=rows, csrf_token=token)

        else:
            return render_template("DentistFile.html",
                                   error=f"Dentiste {DentistName} introuvable ou patient introuvable", csrf_token=token)
    finally:
        cursor.close()
        conn.close()


@dentists.route("/AddDentist", methods=["POST", "GET"])
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

            if not form_token or not session_token or not secrets.compare_digest(form_token, session_token):
                return "Attaque CSRF détectée", 403

            new_token = secrets.token_hex(16)
            session["csrf_token"] = new_token

            dentist_name = request.form.get("AddDentists")
            if not dentist_name or dentist_name.isdigit():
                return render_template("AddDentist.html", message="Nom du dentiste invalide", csrf_token=new_token)

            if not SearcheTable(cursor, dentist_name):
                AddDentistTable(cursor, dentist_name)
                conn.commit()
                return render_template("AddDentist.html", message=f"Dentiste {dentist_name} ajouté avec succès",
                                       csrf_token=new_token)
            else:
                return render_template("AddDentist.html", message="Le dentiste existe déjà", csrf_token=new_token)

    except Exception as e:
        conn.rollback()
        return render_template("AddDentist.html", message="Error de l'addition", csrf_token=new_token)
            
    finally:
        cursor.close()
        conn.close()


@dentists.route("/DeleteDentist", methods=["POST", "GET"])
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

            if not form_token or not session_token or not secrets.compare_digest(form_token, session_token):
                return "Attaque CSRF détectée", 403

            new_token = secrets.token_hex(16)
            session["csrf_token"] = new_token

            Dentist_deleted = request.form.get("DeleteDentist")
            Confirm_Dentist = request.form.get("ConfirmDeleteDentist")

            if SearcheTable(cursor, Dentist_deleted):
                if Dentist_deleted != Confirm_Dentist:
                    return render_template("DeleteDentist.html", message="Confirmation invalide", csrf_token=new_token)

                cursor.execute("DELETE FROM dentists WHERE user_id = %s AND dentist_name = %s",
                               (session['id'], Dentist_deleted))

                cursor.execute("DELETE FROM dentist_registry WHERE user_id = %s AND dentist_name = %s",
                               (session['id'], Dentist_deleted))

                cursor.execute("DELETE FROM khedma WHERE user_id = %s AND khedma_dentist = %s",
                               (session['id'], Dentist_deleted))

                conn.commit()
                return render_template("DeleteDentist.html", message="Dentiste supprimé avec succès",
                                       csrf_token=new_token)
            else:
                return render_template("DeleteDentist.html", message="Le dentiste n'existe pas", csrf_token=new_token)

    except Exception as e:
        conn.rollback()
        print(f"{str(e)}")
        return render_template("DeleteDentist.html", message="Erreur : An internal error occurred", csrf_token=new_token)

    finally:
        cursor.close()
        conn.close()


@dentists.route("/GetFromDentist", methods=["POST", "GET"])
def Get_From_Dentist():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token
        return render_template(
            "GetFromDentist.html",
            csrf_token=token)

    if request.method == "POST":

        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not session_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        # ======================================
        # GET BASIC FORM VALUES
        # ======================================

        dentist = request.form.get("Dentistinput")
        firstName = request.form.get("PatientFirstName")
        lastName = request.form.get("PatientLastName")
        unique = request.form.get("PatientUnique")
        choice = request.form.get("KhedmaChoice" , '')
        price = request.form.get("KhedmaPrice")
        khalsa = request.form.get("Khalsa")
        date = request.form.get("date")
        deadLine = request.form.get("DeadLine")

        # IMPORTANT:
        # This is now .get() instead of ['OtherPro']
        ProCheck = request.form.get("OtherPro")


        # ======================================
        # BASIC VALIDATION
        # ======================================

        if not dentist or not dentist.strip():
            return render_template(
                "GetFromDentist.html",
                error="Le nom du dentiste ne peut pas être vide",
                csrf_token=new_token
            )

        if not firstName or not firstName.strip():
            return render_template(
                "GetFromDentist.html",
                error="Le prénom du patient ne peut pas être vide",
                csrf_token=new_token
            )

        if not lastName or not lastName.strip():
            return render_template(
                "GetFromDentist.html",
                error="Le nom du patient ne peut pas être vide",
                csrf_token=new_token
            )

        if not unique or not unique.isdigit() or len(unique) >= 10:
            return render_template("GetFromDentist.html",
                                   message="ID du patient invalide ",
                                   csrf_token=new_token)

        if not choice or not choice.strip():
            return render_template(
                "GetFromDentist.html",
                error="Choix invalide",
                csrf_token=new_token
            )

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            if not SearcheTable(cursor, dentist):
                return render_template(
                    "GetFromDentist.html",
                    error="Le dentiste n'existe pas",
                    csrf_token=new_token
                )

            if not price:
                return render_template(
                    "GetFromDentist.html",
                    error="Le prix ne peut pas être vide",
                    csrf_token=new_token
                )

            try:

                if not checkValue(price):
                    return render_template(
                        "GetFromDentist.html",
                        error="Valeur du prix invalide",
                        csrf_token=new_token
                    )

                price = float(price)

            except (ValueError, TypeError):
                return render_template(
                    "GetFromDentist.html",
                    error="Valeur du prix invalide",
                    csrf_token=new_token
                )

            if not khalsa or khalsa.strip().lower() not in ["yes", "no"]:
                return render_template(
                    "GetFromDentist.html",
                    error="Vous devez saisir « yes » ou « no » dans Khalsa",
                    csrf_token=new_token
                )

            if not date or not deadLine:
                return render_template(
                    "GetFromDentist.html",
                    error="La date et la date limite sont obligatoires",
                    csrf_token=new_token
                )

            if deadLine < date:
                return render_template(
                    "GetFromDentist.html",
                    error="Date limite invalide",
                    csrf_token=new_token
                )

            cursor.execute(
                """ 
                SELECT id 
                FROM dentists 
                WHERE user_id = %s AND patient_number = %s AND dentist_name = %s 
                """, (session["id"], unique, dentist))

            if cursor.fetchone():
                return render_template("GetFromDentist.html", message="Le numéro unique existe déjà", csrf_token=new_token)

            # ==================================
            # CHECK OTHER PROTHESIST
            # ==================================

            if not ProCheck or ProCheck.strip().lower() not in ["yes", "no"]:
                return render_template(
                    "GetFromDentist.html",
                    error="Vous devez sélectionner Oui ou Non dans la partie de vérification du prothésiste",
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
                        error="Le nom du prothésiste ne peut pas être vide",
                        csrf_token=new_token
                    )

                    # ----------------------------------
                # PROTHESIST NUMBER
                # ----------------------------------

                if not ProNumber or not ProNumber.isdigit():
                    return render_template(
                        "GetFromDentist.html",
                        error="Le numéro du prothésiste doit être un nombre positif",
                        csrf_token=new_token
                    )

                if int(ProNumber) < 0:
                    return render_template(
                        "GetFromDentist.html",
                        error="Le numéro du prothésiste doit être un nombre positif",
                        csrf_token=new_token
                    )

                    # ----------------------------------
                # PROTHESIST PRICE
                # ----------------------------------

                if not ProPrice:
                    return render_template(
                        "GetFromDentist.html",
                        error="Le prix du prothésiste ne peut pas être vide",
                        csrf_token=new_token
                    )

                try:
                    ProPrice = float(ProPrice)

                    if ProPrice < 0:
                        raise ValueError

                except (ValueError, TypeError):

                    return render_template(
                        "GetFromDentist.html",
                        error="Prix du prothésiste invalide",
                        csrf_token=new_token
                    )

                    # ----------------------------------
                # PROTHESIST DATES
                # ----------------------------------

                if not ProDate or not ProDeadLine:
                    return render_template("GetFromDentist.html",
                                           error="La date et la date limite du prothésiste sont obligatoires",
                                           csrf_token=new_token
                                           )

                if ProDate < date:
                    return render_template("GetFromDentist.html", error="Date du prothésiste invalide",
                                           csrf_token=new_token
                                           )

                if ProDeadLine < ProDate:
                    return render_template("GetFromDentist.html", error="Date limite du prothésiste invalide",
                                           csrf_token=new_token
                                           )

                if ProDeadLine > deadLine:
                    return render_template("GetFromDentist.html",
                                           error="La date limite du prothésiste ne peut pas être postérieure à celle du dentiste",
                                           csrf_token=new_token
                                           )

                    # ----------------------------------
                # PROTHESIST KHALSA
                # ----------------------------------

                if not ProKhalsa or ProKhalsa.lower() not in ["yes", "no"]:
                    return render_template(
                        "GetFromDentist.html",
                        error="Vous devez saisir « yes » ou « no » dans Khalsa du prothésiste",
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
                            error="Veuillez sélectionner Oui ou Non pour le versement du prothésiste",
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
                            return render_template("GetFromDentist.html",
                                                   error="Veuillez saisir le montant du versement du prothésiste",
                                                   csrf_token=new_token
                                                   )

                        try:
                            ProVersa = float(ProVersa)

                        except (ValueError, TypeError):

                            return render_template(
                                "GetFromDentist.html",
                                error="Montant du versement du prothésiste invalide",
                                csrf_token=new_token
                            )

                        if ProVersa < 0:
                            return render_template("GetFromDentist.html",
                                                   error="Le versement du prothésiste ne peut pas être négatif",
                                                   csrf_token=new_token
                                                   )

                        if ProVersa > ProPrice:
                            return render_template("GetFromDentist.html",
                                                   message="Le versement du prothésiste ne doit pas être supérieur à son prix",
                                                   csrf_token=new_token
                                                   )

                        Prob9aw = round(ProPrice - ProVersa, 2)

                        # ==================================
                # CHECK PROTHESIST EXISTENCE
                # ==================================

                cursor.execute(""" 
                                SELECT id 
                                FROM other_prothesists 
                                WHERE pName = %s 
                                AND pNumber = %s 
                                AND user_id = %s 
                                """, (ProName, ProNumber, session["id"]))

                # ==================================
                # INSERT PROTHESIST IF NOT EXISTS
                # ==================================

                if not cursor.fetchone():
                    return render_template("GetFromDentist.html", error="Prothésiste introuvable", csrf_token=new_token)

                cursor.execute(
                    """ 
                    INSERT INTO other_prothesists_khedma 
                    ( user_id, patient_number, dentist_name, pName, pNumber, pDate, pKhedma, pPrice, pVersa, pB9aw,  
                    pKhalsa, pFinished, DeadLine ) 
                    VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s ) """,
                    (session['id'], unique, dentist, ProName, ProNumber, ProDate, choice, ProPrice, ProVersa,
                     Prob9aw, ProKhalsa, "no", ProDeadLine))

                Prothesist_History(cursor, ProName, ProNumber, unique, firstName, lastName)

                ProthesistsStat(cursor, ProPrice, ProNumber, ProName,
                                ProKhalsa, ProDate, ProVersa)

            status = 'in process'
            infos = [session["id"], dentist, firstName, lastName, unique, choice, price,
                     versement, b9aw, "no", dentist_khalsa, date, deadLine, status]

            if ProCheck == 'yes':
                infos[13] = 'prothesist'

            cursor.execute(
                """ 
                INSERT INTO dentists 
                    ( user_id, dentist_name, patient_firstname, patient_lastname, patient_number,  
                    Dkhedma, price, versement, b9aw, finished, khalsa, date, DeadLine, status ) 
                VALUES 
                    ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s ) """
                , tuple(infos))

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
                (choice, price, date, dentist, unique, "no", dentist_khalsa,
                 prothesist_name, prothesist_number, session["id"], deadLine))

            Dentist_History(cursor, dentist)

            DentistStats(cursor, dentist, price, khalsa, date)

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
                message="Tâche ajoutée avec succès",
                result=result
            )

        except Exception as e:
            conn.rollback()
            print(f"{str(e)}")
            return render_template(
                "GetFromDentist.html",
                error="Une erreur s'est produite : An internal error occurred",
                csrf_token=new_token
            )

        finally:
            cursor.close()
            conn.close()


@dentists.route("/DentistVersement", methods=["POST", "GET"])
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

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not session_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        DentistName = request.form.get('DName')
        KhedmaId = request.form.get('KhedmaId')
        Versement = request.form.get('Versement')

        if not Versement:
            return render_template("ModifyDentistVersement.html", error="Le versement ne peut pas être vide",
                                   csrf_token=new_token)

        try:
            Versement = float(Versement)
        except (ValueError, TypeError):
            return render_template("ModifyDentistVersement.html", error="Valeur du versement invalide",
                                   csrf_token=new_token)

            # if Versement < 0:
        #   return render_template("ModifyDentistVersement.html", error="Versement cannot be negative", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute(""" 
                            SELECT price, khalsa, versement, b9aw, MONTH(date), YEAR(date)  
                            FROM dentists  
                            WHERE user_id = %s AND dentist_name = %s AND patient_number = %s """
                           , (session['id'], DentistName, KhedmaId))
            result = cursor.fetchone()

            if not result:
                return render_template("ModifyDentistVersement.html", message="Tâche introuvable ",
                                       csrf_token=new_token)

            price = float(result[0])
            oldkhalsa = result[1]
            oldversement = float(result[2])
            month = result[4]
            year = result[5]

            if oldkhalsa.lower() == "yes" and Versement > 0:
                cursor.execute("SELECT * FROM dentists WHERE user_id = %s ", (session['id'],))
                result = cursor.fetchall()
                return render_template("DentistFile.html", message="Tâche déjà Khalsa", result=result,
                                       csrf_token=new_token)

            NewVersement = oldversement + Versement

            if NewVersement > price:
                return render_template("ModifyDentistVersement.html", error="Versement invalide", csrf_token=new_token)

            elif NewVersement == price:
                b9aw = 0

                cursor.execute(""" 
                                UPDATE dentists  
                                SET  
                                khalsa = "yes",   
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
                                UPDATE khedma  
                                SET khedma_khalsa = 'yes'  
                                WHERE user_id = %s AND khedma_patient = %s """, (session['id'], KhedmaId))

                cursor.execute(""" 
                                UPDATE dentist_stat  
                                SET  
                                khalsin = khalsin + %s , 
                                machi_khalsin = machi_khalsin - %s 
                                WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s """
                               , (Versement, Versement, session['id'], DentistName, month, year))

                cursor.execute(""" 
                                SELECT * FROM dentists 
                                WHERE user_id = %s """, (session['id'],))

                result = cursor.fetchall()
                conn.commit()

                return render_template("DentistFile.html", message="Informations mises à jour avec succès",
                                       result=result,
                                       csrf_token=new_token)

            else:
                b9aw = price - NewVersement

                if b9aw > price:
                    return render_template("ModifyDentistVersement.html", message="Versement invalide",
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
                                 WHERE user_id = %s """, (session['id'],))

                result = cursor.fetchall()

                return render_template("DentistFile.html", message="Informations mises à jour avec succès",
                                       result=result, csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            print(f"{str(e)}")
            return render_template("ModifyDentistVersement.html", error="Erreur : An internal error occurred", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@dentists.route("/DeleteDentistPatient", methods=["POST", "GET"])
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

        if not form_token or not session_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        Dentist_name = request.form.get("DentistName")
        PatientF_deleted = request.form.get("DeleteF")
        Confirm_PatientF = request.form.get("ConfirmDeletePatientF")
        PatientL_deleted = request.form.get("DeleteL")
        Confirm_PatientL = request.form.get("ConfirmDeletePatientL")
        Patient_unique = request.form.get("uniquepatient")
        Confirm_Unique = request.form.get("confirmunique")

        if not Patient_unique.isdigit() or len(Patient_unique) >= 10:
            return render_template("DeleteDentistPatient.html", error="Numéro unique invalide", csrf_token=new_token)

        if (PatientF_deleted != Confirm_PatientF or
                PatientL_deleted != Confirm_PatientL or
                Patient_unique != Confirm_Unique):
            return render_template("DeleteDentistPatient.html", error="Confirmation invalide", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)
        try:

            cursor.execute(""" 
                    SELECT price, khalsa, MONTH(date), YEAR(date), versement, b9aw   
                    FROM dentists  
                    WHERE dentist_name = %s AND patient_firstname = %s AND patient_lastname = %s  
                    AND patient_number = %s AND user_id = %s  
                    """, (Dentist_name, PatientF_deleted, PatientL_deleted, Patient_unique, session['id']))

            result = cursor.fetchone()

            if not result:
                return render_template("DeleteDentistPatient.html"
                                       , message="Patient introuvable", csrf_token=new_token)

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

            if found:
                if found[0] == PatientF_deleted and found[1] == PatientL_deleted:
                    return render_template("DeleteDentistPatient.html",
                                           message=f"Ce service est toujours attribué à {found[2]}, nous ne pouvons pas le supprimer",
                                           csrf_token=new_token)

            if khalsa.lower() == "yes":
                cursor.execute(""" 
                                UPDATE dentist_stat  
                                SET  
                                total_khedma = total_khedma - 1 , 
                                khalsin = khalsin - %s   
                                WHERE dentist_name = %s AND user_id = %s AND month = %s AND year = %s  
                                """, (price, Dentist_name, session['id'], month, year))
            else:
                cursor.execute(""" 
                                UPDATE dentist_stat  
                                SET  
                                total_khedma = total_khedma - 1 , 
                                khalsin = khalsin - %s , 
                                machi_khalsin = machi_khalsin - %s  
                                WHERE dentist_name = %s AND user_id = %s AND month = %s AND year = %s """,
                               (versement, b9aw, Dentist_name, session['id'], month, year))

            cursor.execute(""" 
                            UPDATE dentist_history  
                            SET status = 'deleted'  
                            WHERE  
                            user_id = %s AND dentistname = %s AND pFirstname = %s AND pLastname = %s AND pNumber = %s  """,
                           (session['id'], Dentist_name, PatientF_deleted, PatientL_deleted, Patient_unique))

            cursor.execute("DELETE FROM khedma WHERE user_id = %s AND khedma_patient = %s AND khedma_dentist = %s ",
                           (session['id'], Patient_unique, Dentist_name))

            cursor.execute(""" 
                DELETE FROM dentists 
                WHERE dentist_name = %s AND patient_firstname = %s AND patient_lastname = %s 
                  AND patient_number = %s AND user_id = %s 
            """, (Dentist_name, PatientF_deleted, PatientL_deleted, Patient_unique, session['id']))
            conn.commit()

            cursor.execute("SELECT * FROM dentists WHERE user_id = %s ",
                           (session["id"],))
            rows = cursor.fetchall()

            return render_template("DentistFile.html", message="Patient supprimé avec succès", result=rows,
                                   csrf_token=new_token)

        except Exception as e:
            conn.rollback()
            print(f"{str(e)}")
            return render_template("DeleteDentistPatient.html", error="Erreur : An internal error occurred", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@dentists.route("/DentistHistory", methods=["POST", "GET"])
def getDentistHistory():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session["csrf_token"] = token

        conn = get_connection()
        cursor = conn.cursor()

        try:
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
                    message="Tableau introuvable",
                    csrf_token=token,
                    my_test_token=token
                )

        except Exception as e:
            conn.rollback()
            print(f"{str(e)}")
            return "Erreur : An internal error occurred"

        finally:
            cursor.close()
            conn.close()

    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or not session_token or not secrets.compare_digest(form_token, session_token):
            return "Attaque CSRF détectée", 403

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
                    return render_template("DentistHistory.html", message="Patient introuvable", csrf_token=new_token)

            cursor.execute(""" 
                        SELECT * FROM dentist_history 
                        WHERE user_id = %s AND dentistname = %s 
                    """, (session['id'], dentist_name.lower()))
            result = cursor.fetchall()
            if result:
                return render_template("DentistHistory.html", HistoryDentist=result, csrf_token=new_token)
            else:
                return render_template("DentistHistory.html",
                                       message="Dentiste introuvable", csrf_token=new_token)
        finally:
            cursor.close()
            conn.close()


@dentists.route("/AllDentistHistory")
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
                            pDate <= DATE_SUB(CURDATE() , INTERVAL 25 MONTH) AND user_id = %s 
                            AND ( (b9aw = 0 AND status = 'finished') OR (status = 'deleted'))""",
                       (session['id'],))
        conn.commit()

        cursor.execute("SELECT * FROM dentist_history WHERE user_id = %s", (session['id'],))
        result = cursor.fetchall()
        if result:
            return render_template("DentistHistory.html", History=result, csrf_token=session['csrf_token'])
        else:
            return render_template("DentistHistory.html", message="Tableau introuvable",
                                   csrf_token=session['csrf_token'])
    finally:
        cursor.close()
        conn.close()


@dentists.route("/DentistMainTable")
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
            return render_template("DentistFile.html", message="Tableau principal", main=main,
                                   csrf_token=token)  # ✅ Pass token
        else:
            return render_template("DentistFile.html", message="Tableau vide", csrf_token=token)  # ✅ Pass token

    finally:
        cursor.close()
        conn.close()


@dentists.route("/DentistMostKhedma", methods=["GET"])
def FindMostDentistKhedma():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        dentist_dics = DentistsDics(cursor)
        if not dentist_dics:
            return render_template("DentistFile.html", error="Aucun tableau de dentistes trouvé.")
        name, count = max(dentist_dics.items(), key=lambda x: x[1], default=('none', 0))
        if count == 0:
            return render_template("DentistFile.html", message="Tous les tableaux sont vides.")
        cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                       (session['id'], name))
        result = cursor.fetchall()
        return render_template("DentistFile.html", most=result, most_name=name)
    finally:
        cursor.close()
        conn.close()


@dentists.route("/DentistLessKhedma", methods=["GET"])
def FindLessDentistKhedma():
    if not is_logged_in():
        return redirect(url_for('home'))
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        dentist_dics = DentistsDics(cursor)
        active_dentists = {n: c for n, c in dentist_dics.items() if c > 0}
        if not active_dentists:
            return render_template("DentistFile.html", message="Tous les dentistes ont actuellement 0 service.")
        name, count = min(active_dentists.items(), key=lambda x: x[1])
        cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                       (session['id'], name))
        result = cursor.fetchall()
        return render_template("DentistFile.html", less=result, less_name=name)
    finally:
        cursor.close()
        conn.close()


@dentists.route("/DentistDeadLine")
def ShowDeadLine():
    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute(""" 
                        SELECT * FROM dentists WHERE user_id = %s  
                        ORDER BY DeadLine ASC """, (session['id'],))
        dateDeadLine = cursor.fetchall()
        return render_template("DentistFile.html", dateDeadLine=dateDeadLine)

    finally:
        cursor.close()
        conn.close()


@dentists.route("/DentistTotal", methods=["GET"])
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
                result[dentist_name] = row[0] if row and row[0] is not None else 0
            except Exception as e:
                result[dentist_name] = 0
        if result:
            return render_template("DentistFile.html", total=result)
        return render_template("DentistFile.html", message="Aucune donnée sur les dentistes trouvée.")
    finally:
        cursor.close()
        conn.close()


@dentists.route("/DentistsStat")
def DentistsStat():
    if not is_logged_in():
        return redirect(url_for('home'))

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:

        # Delete empty statistics
        cursor.execute(""" 
            DELETE FROM dentist_stat 
            WHERE total_khedma = 0 
              AND khalsin = 0 
              AND machi_khalsin = 0 
              AND user_id = %s 
        """, (session['id'],))

        cursor.execute("""
                        SELECT ds.id, ds.total_khedma, COUNT(CASE WHEN dh.status = 'finished' AND dh.b9aw = 0 THEN 1 END) AS total_finished
                        FROM dentist_stat ds 
                        JOIN dentist_history dh ON dh.dentistname = ds.dentist_name AND 
                              MONTH(dh.pDate) = ds.month AND YEAR(dh.pDate) = ds.year AND 
                             dh.user_id = ds.user_id                         
                        WHERE 
                            ds.user_id = %s AND dh.pDate >= DATE_SUB(CURDATE() , INTERVAL 18 MONTH )
                        GROUP BY 
                        ds.id , ds.total_khedma 
                        """,(session['id'],))
        deleted = cursor.fetchall()

        conn.commit()

        hiders = [delete[0] for delete in deleted if delete[1] == delete[2]]

        # Get all dentists
        dentists_list = GetAllDentistTables(cursor)
        result = {}

        placeholders = ','.join(['%s']*len(hiders))

        for dentist in dentists_list:
            if hiders:
                cursor.execute(f""" 
                                SELECT * 
                                FROM dentist_stat 
                                WHERE 
                                 id NOT IN ({placeholders}) AND user_id = %s AND dentist_name = %s 
                                ORDER BY year DESC, month ASC 
                """, (*hiders, session['id'], dentist))

                rows = cursor.fetchall()
            else :
                cursor.execute(f""" 
                               SELECT * 
                               FROM dentist_stat 
                               WHERE 
                               user_id = %s AND dentist_name = %s 
                               ORDER BY year DESC, month ASC 
                  """, (session['id'], dentist))

                rows = cursor.fetchall()


            # Only add dentist if statistics exist
            if rows:
                result[dentist] = rows

                # Statistics found
        if result:
            return render_template(
                "DentistFile.html",
                message="Tableau des statistiques",
                result=result)

            # No statistics found
        return render_template(
            "DentistFile.html",
            message="Tableau introuvable (aucune statistique disponible)")

    except Exception as e:
        conn.rollback()
        print(f"{str(e)}")
        return render_template(
            "DentistFile.html",
            message="Erreur : An internal error occurred")

    finally:
        cursor.close()
        conn.close()

@dentists.route("/DentistsStatByPeriod")
def DentistsStatByPeriod():

    if not is_logged_in():
        return jsonify({
            "success": False,
            "message": "Authentication required"
        }), 401

    try:
        month = int(request.args.get("month", 0))
        year = int(request.args.get("year", 0))

        if not 1 <= month <= 12 or year < 2000:
            return jsonify({
                "success": False,
                "message": "Invalid month or year"
            }), 400

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            cursor.execute("""
                SELECT dentist_name, total_khedma, khalsin, machi_khalsin
                FROM dentist_stat
                WHERE 
                user_id = %s AND month = %s AND year = %s
                ORDER BY dentist_name
            """, (session['id'], month, year))

            rows = cursor.fetchall()

            dentists_data = []

            for row in rows:
                dentists_data.append({
                    "name": row[0],
                    "total_khedma": int(row[1] or 0),
                    "paid": float(row[2] or 0),
                    "unpaid": float(row[3] or 0)
                })

            return jsonify({
                "success": True,
                "month": month,
                "year": year,
                "dentists": dentists_data
            })

        finally:
            cursor.close()
            conn.close()

    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid parameters"
        }), 400

    except Exception:
        #app.logger.exception("DentistsStatByPeriod failed")
        return jsonify({
            "success": False,
            "message": "An internal error occurred"
        }), 500


@dentists.route("/UpdateDentistStatus", methods=['POST', 'GET'])
def UpdateDentistStatus():
    if not is_logged_in():
        return jsonify({
            'success': False,
            'message': 'Utilisateur non autorisé'
        }), 403

    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'message': 'Aucune donnée reçue'
        }), 403

    patientNumber = data.get('patient_number')
    status = data.get('status')
    dentistName = data.get('dentist_name')

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
                        SELECT 1 FROM dentists  
                        WHERE dentist_name = %s AND patient_number = %s AND user_id = %s """
                       , (dentistName, patientNumber, session['id']))
        found = cursor.fetchone()

        if not found:
            return jsonify({
                'success': False,
                'message': 'Patient introuvable'
            }), 400

        cursor.execute(""" 
                        UPDATE dentists  
                        SET status = %s  
                        WHERE dentist_name = %s AND patient_number = %s AND user_id = %s """
                       , (status, dentistName, patientNumber, session['id']))
        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"{str(e)}")
        return jsonify({
            'success': False,
            'message': 'Erreur : An internal error occurred'
        })

    finally:
        cursor.close()
        conn.close()

    return jsonify({
        'success': True,
        'message': 'Statut mis à jour avec succès'
    })

@dentists.route("/DentistFacture", methods=["GET"])
def DentistFacture():

    if not is_logged_in():
        return redirect(url_for("home"))

    dentistName = request.args.get("dentist")
    month = request.args.get("month")
    year = request.args.get("year")

    if not dentistName or not month or not year:
        return "Informations de facture manquantes", 400

    try:
        month = int(month)
        year = int(year)

        if not 1 <= month <= 12 or year < 2000:
            return "Mois ou année invalide", 400

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT dentistname, pNumber, pKhedma, versement, b9aw, pDate, STATUS
                FROM dentist_history
                WHERE 
                user_id = %s AND dentistname = %s AND MONTH(pDate) = %s AND YEAR(pDate) = %s
            """, (session['id'], dentistName, month, year))

            results = cursor.fetchall()

            if not results:
                return "Aucune prestation trouvée pour cette période.", 404

            total = sum(float(row[4] or 0) for row in results if row[6] != 'deleted')

            details = []

            for row in results:
                details.append({
                    "dentistName": row[0],
                    "patientNumber": row[1],
                    "service": row[2],
                    "versement": float(row[3] or 0),
                    "remaining": float(row[4] or 0),
                    "date": str(row[5]),
                    "status": row[6]
                })

            return render_template(
                "DentistFacture.html",
                invoice_number=f"DH-{session['id']}-{year}{month:02d}",
                dentistName=dentistName,
                month=month,
                year=year,
                emission_date=date.today().strftime("%d/%m/%Y"),
                details=details,
                total=total
            )

        finally:
            cursor.close()
            conn.close()

    except (ValueError, TypeError):
        return "Mois ou année invalide", 400

    except Exception as e:
        return "Erreur lors de la génération de la facture.", 500
