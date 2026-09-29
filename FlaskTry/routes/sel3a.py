import secrets
from flask import Blueprint, request, render_template, redirect, url_for, session, jsonify
from FlaskTry.FunctionFile import *
from FlaskTry.ConnectToSql import get_connection

products = Blueprint("products", __name__, url_prefix="/products")

def is_logged_in():
    return 'id' in session 


@products.route("/Sel3a", methods=["GET"])
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


@products.route("/AddSel3a", methods=["POST", "GET"])
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
        quantity = request.form.get("SQuantity")
        unit = request.form.get("SUnit")
        date  = request.form.get("SDate")
        khalsa = request.form.get("SKhalsa")
        versa = request.form.get("Versement")

        if not name :
            return render_template("AddSel3a.html", error="Invalid Name Value", csrf_token=new_token)

        try:
            price = float(price) * int(quantity)
        except (ValueError, TypeError):
            return render_template("AddSel3a.html", error="Invalid Price Value", csrf_token=new_token)

        if price < 0 or not name.strip():
            return render_template("AddSel3a.html", error="Invalide Informations", csrf_token=new_token)

        if not quantity or not unit :
            return render_template("AddSel3a.html", error="Unit and Quantity are required ", csrf_token=new_token)

        if khalsa.lower() not in ['yes' , 'no']:
            return render_template("AddSel3a.html" , error="In khalsa case enter 'yes' or 'no' ", csrf_token=new_token)

        if khalsa == 'no' :
            try:
                versa = float(versa)
            except (ValueError, TypeError):
                return render_template("AddSel3a.html" , error="Invalide Versement Value", csrf_token=new_token)

            if versa < 0 or price < versa:
                return render_template("AddSel3a.html" , error="Invalide Versement Value", csrf_token=new_token)

            if versa == price :
                khalsa = 'yes'

        if khalsa.lower() == 'yes' :
            versa = price
            b9aw = 0
        else :
            b9aw = float(price) - float(versa)

        conn = get_connection()
        cursor = conn.cursor(buffered=True)
        try:
            cursor.execute("""
                INSERT INTO sel3a (user_id, sel3a_name, quantity, max_quantity, unit, sel3a_price, buy_date, khalsa, versement, b9aw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (session['id'], name, quantity, quantity, unit, price, date, khalsa, versa, b9aw))
            conn.commit()

            return redirect(url_for("Sel3aPage"))

        except Exception as e :
            conn.rollback()
            return render_template("AddSel3a.html",
                                   error=f"error {str(e)}", csrf_token=new_token)

        finally:
            cursor.close()
            conn.close()


@products.route("/ModifySel3aQuantity/<int:sel3a_id>", methods=["POST" , "GET"])
def ModifySel3aQuantity(sel3a_id):
    if not is_logged_in():
        return {'success': False, 'error': "Unauthorized"}, 401

    conn = get_connection()
    cursor = conn.cursor()

    data = request.get_json()

    try :
        used = int(data.get('used'))
    except (TypeError , ValueError):
        return jsonify({
            'success': False,
            'message': 'Enter a valid quantity value'
        }),400

    try :
        cursor.execute("""
                        SELECT quantity 
                        FROM sel3a 
                        WHERE id = %s AND user_id = %s """,(sel3a_id, session['id']))
        result = cursor.fetchone()

        new_quantity = int(result[0]) - used

        if new_quantity < 0 :
            return jsonify({
                'success': False,
                'message': 'The stock is not egnoth for this usage'
            }),400

        cursor.execute("""
                        UPDATE sel3a 
                        SET quantity = %s 
                        WHERE user_id = %s AND id = %s """,(new_quantity, session['id'], sel3a_id))
        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Information Updated Successfully'
        }),200


    except Exception as e :
        conn.rollback()
        return jsonify({
            'success': False,
            'message': f"error {str(e)}"
        }),500

    finally:
        cursor.close()
        conn.close()


@products.route("/DeleteSel3a/<int:sel3a_id>", methods=["POST"])
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


@products.route("/Sel3aStat")
def Sel3aStat():
    if not is_logged_in():
        return redirect(url_for('home'))
    return redirect(url_for('Sel3aPage'))


@products.route("/ShowByPrice")
def ShowSel3aByPrice():
    if not is_logged_in():
        return redirect(url_for('home'))
    return redirect(url_for('Sel3aPage'))


@products.route("/ShowByDateASC")
def ShowSel3aByDate():
    if not is_logged_in():
        return redirect(url_for('home'))
    return redirect(url_for('Sel3aPage'))


@products.route("/Sel3aPaid/<int:sel3a_id>", methods=["POST"] )
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


@products.route("/ModifySel3aVersement/<int:sel3a_id>", methods=["POST"])
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



