import secrets
from flask import Blueprint, request, render_template, redirect, url_for, session, jsonify
from ManageMyLab.FunctionFile import *
from ManageMyLab.ConnectToSql import get_connection

services = Blueprint("services", __name__, url_prefix="/services")


def is_logged_in():
    return "id" in session


@services.route("/OtherServices" , methods=["POST", "GET"])
def OtherServices():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":

        token = secrets.token_hex(16)
        session['csrf_token'] = token

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(""" 
                            DELETE FROM others_services  
                            WHERE  
                            date <= DATE_SUB(CURDATE() , INTERVAL 6 MONTH) AND user_id = %s 
                             AND khalsa = 'yes' """
                           , (session['id'],))
            conn.commit()

            cursor.execute(""" 
                            SELECT * FROM others_services 
                            WHERE user_id = %s """, (session['id'],))
            result = cursor.fetchall()

            return render_template("OtherServices.html", result=result, csrf_token=token)

        finally:
            cursor.close()
            conn.close()
    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("csrf_token")

        if not form_token or form_token != session_token:
            return "Attaque CSRF détectée", 403

        new_token = secrets.token_hex(16)
        session["csrf_token"] = new_token

        SearchBar = request.form.get("SearchBar")

        conn = get_connection()
        cursor = conn.cursor(buffered=True)

        try:
            if SearchBar.isdigit():
                cursor.execute(""" 
                                SELECT * FROM others_services  
                                WHERE user_id = %s AND number = %s """,
                               (session['id'], SearchBar))
                result = cursor.fetchall()

            else:
                cursor.execute(""" 
                                SELECT * FROM others_services  
                                WHERE user_id = %s AND name = %s """,
                               (session['id'], SearchBar))

                result = cursor.fetchall()

            if not result:
                return render_template("OtherServices.html", error="Service introuvable",
                                       csrf_token=session['csrf_token'])

            return render_template("OtherServices.html", result=result, message=f"Tableau de {SearchBar}",
                                   csrf_token=session['csrf_token'])

        finally:
            cursor.close()
            conn.close()


# -------------------------------
# DISPLAY TABLE
# -------------------------------
@services.route("/OtherServicesTable")
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
            return render_template("OtherServices.html", result=result, message="Tableau des autres services",
                                   csrf_token=token)
        else:
            return render_template("OtherServices.html", error="Tableau vide", csrf_token=token)

    finally:
        cursor.close()
        conn.close()

# -------------------------------
# ADD SERVICE
# -------------------------------
@services.route("/AddService", methods=["GET", "POST"])
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
            return "Attaque CSRF détectée", 403

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
            return render_template("AddService.html", error="Nom invalide", csrf_token=new_token)

        if not number.isdigit() or len(number) != 10:
            return render_template("AddService.html", error="Numéro invalide", csrf_token=new_token)

        if not function:
            return render_template("AddService.html", error="Fonction invalide", csrf_token=new_token)

        if khalsa not in ['yes', 'no']:
            return render_template("AddService.html", error="Khalsa doit être yes ou no", csrf_token=new_token)

        if price < 0:
            return render_template("AddService.html", error="Prix invalide", csrf_token=new_token)

        if khalsa == 'no':
            versa = request.form.get('ServiceVersa', 'no').lower()

            if versa not in ['yes', 'no']:
                return render_template("AddService.html", error="Le versement doit être yes ou no",
                                       csrf_token=new_token)

            if versa == 'yes':
                Vprice = float(request.form.get('VersaService', '0'))

                if Vprice < 0:
                    return render_template("AddService.html", error="Prix invalide", csrf_token=new_token)

                if Vprice > price:
                    return render_template("AddService.html", error="Le versement ne peut pas être supérieur au prix",
                                           csrf_token=new_token)

                if Vprice == price:
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
                            WHERE user_id = %s """, (session['id'],))
            result = cursor.fetchall()

            return render_template("OtherServices.html", result=result, message="Service ajouté avec succès",
                                   csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()

        # -------------------------------


# MARK AS PAID
# -------------------------------

@services.route("/ServicePaid/<int:service_id>", methods=["POST"])
def ServicePaid(service_id):
    if not is_logged_in():
        return jsonify({
            'success': False,
            'error': 'Vous devez vous connecter'
        }), 401

    data = request.get_json()
    name = data.get('name')
    number = data.get('number')

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:

        cursor.execute(""" 
                        SELECT price, versement, b9aw, khalsa, MONTH(date) AS month, YEAR(date) AS year 
                        FROM others_services  
                        WHERE user_id = %s AND id = %s """, (session['id'], service_id))

        result = cursor.fetchone()

        if result[3] == 'yes':
            return jsonify({
                'success': False,
                'message': 'Service déjà payé'
            })

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

        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Informations mises à jour'
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': f'Erreur : {str(e)}'
        }), 500

    finally:
        cursor.close()
        conn.close()


@services.route("/ModifyServiceVersement/<int:service_id>", methods=["POST"])
def ModifyServiceVersement(service_id):
    if not is_logged_in():
        return jsonify({
            'success': False,
            'error': 'Vous devez vous connecter'
        }), 401

    data = request.get_json()
    name = data.get('name')
    number = data.get('number')
    newVersement = data.get('newVersement')

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(""" 
                        SELECT price, versement, b9aw, khalsa, MONTH(date) AS month, YEAR(date) AS year 
                        FROM others_services 
                        WHERE user_id = %s AND id = %s 
                        """, (session['id'], service_id))
        result = cursor.fetchone()

        if result[3] == 'yes':
            return jsonify({
                'success': False,
                'message': 'Service déjà payé'
            }), 401

        final = float(newVersement) + float(result[1])

        if final == float(result[0]):
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

        elif final < float(result[0]):
            b9aw = float(result[0]) - final
            if b9aw > float(result[0]):
                return jsonify({
                    'success': False,
                    'message': 'Versement invalide'
                }), 402

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

        else:
            return jsonify({
                'success': False,
                'message': "Valeur du versement invalide"
            }), 401

        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Informations mises à jour'
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': f'Erreur : {str(e)}'
        }), 500

    finally:
        cursor.close()
        conn.close()


@services.route("/DeleteService/<int:service_id>", methods=["POST"])
def DeleteService(service_id):
    if not is_logged_in():
        return jsonify({
            'success': False,
            'error': 'Vous devez vous connecter'
        }), 401

    data = request.get_json()
    name = data.get('name')
    number = data.get('number')

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(""" 
                        SELECT price, versement, b9aw, khalsa, MONTH(date) AS month, YEAR(date) AS year 
                        FROM others_services 
                        WHERE user_id = %s AND id = %s 
                        """, (session['id'], service_id))
        result = cursor.fetchone()

        cursor.execute(""" 
                        DELETE FROM others_services 
                        WHERE user_id = %s AND id = %s """, (session['id'], service_id))

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
            'message': 'Informations mises à jour'
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': f'Erreur : {str(e)}'
        }), 500

    finally:
        cursor.close()
        conn.close()

    # -------------------------------


# STATS
# -------------------------------
@services.route("/ServicesStats")
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
                        """, (session['id'],))
        conn.commit()

        cursor.execute(""" 
            SELECT * FROM other_services_stats 
            WHERE user_id = %s 
        """, (session['id'],))

        result = cursor.fetchall()

        if result:
            return render_template("OtherServices.html", stats=result, message="Statistiques des services")
        else:
            return render_template("OtherServices.html", error="Tableau vide")

    finally:
        cursor.close()
        conn.close()
