import secrets
from flask import Blueprint, request, render_template, redirect, url_for, session
from FlaskTry.FunctionFile import *
from FlaskTry.ConnectToSql import get_connection
import os

users = Blueprint('users', __name__, url_prefix='/users')

def is_logged_in():
    return "id" in session

@users.route("/ModifyStatus", methods=["POST", "GET"])
def ModifyStatus():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session['csrf_token'] = token
        return render_template("ModifyUsersStatus.html", csrf_token=token)

    if request.method == "POST" :
        token_form = request.form.get('csrf_token')
        session_token = session.get('csrf_token')

        if not token_form or token_form != session_token :
            return "error CSRF attack",403

        new_token = secrets.token_hex(16)
        session['csrf_token'] = new_token

        user_name = request.form.get('userName')
        email = request.form.get('email')
        phoneNumber = request.form.get('phoneNumber')
        status = request.form.get('NewStatus')

        if not user_name or user_name.isdigit() or len(user_name) < 5 :
            return render_template("ModifyUsersStatus.html", error="Invalid UserName", csrf_token=new_token)

        if not email or email.isdigit() or '@' not in email or len(email) < 5 :
            return render_template("ModifyUsersStatus.html", error="Invalid Email", csrf_token=new_token)

        if not phoneNumber or not phoneNumber.isdigit() or len(phoneNumber) != 10 :
            return render_template("ModifyUsersStatus.html", error="Invalid PhoneNumber", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor()

        try :
            cursor.execute("""
                            SELECT id 
                            FROM users 
                            WHERE 
                            user_name = %s AND user_email = %s AND user_phoneNumber = %s
                            """,(user_name, email, phoneNumber))
            found = cursor.fetchone()

            if not found :
                return render_template("ModifyUsersStatus.html", error="User not found", csrf_token=new_token)

            cursor.execute("""
                            UPDATE users 
                            SET status = %s 
                            WHERE id = %s """,(status, found[0]))
            conn.commit()

            return render_template("ModifyUsersStatus.html", message="Information Updated", csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("ModifyUsersStatus.html", error=f"error {str(e)}", csrf_token=new_token)

        finally :
            cursor.close()
            conn.close()



@users.route("/DeleteUser", methods=["POST", "GET"])
def DeleteUser():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session['csrf_token'] = token
        return render_template("DeleteUser.html", csrf_token=token)

    if request.method == "POST" :
        token_form = request.form.get('csrf_token')
        session_token = session.get('csrf_token')

        if not token_form or token_form != session_token :
            return "error CSRF attack",403

        new_token = secrets.token_hex(16)
        session['csrf_token'] = new_token

        user_name = request.form.get('userName')
        confirm_UserName = request.form.get('confirmUserName')
        email = request.form.get('email')
        confirm_email = request.form.get('confirmEmail')
        phoneNumber = request.form.get('phoneNumber')
        confirm_phone = request.form.get('confirmPhoneNumber')

        if not user_name or user_name.isdigit() or len(user_name) < 5 :
            return render_template("DeleteUser.html", error="Invalid UserName", csrf_token=new_token)

        if not email or email.isdigit() or '@' not in email or len(email) < 5 :
            return render_template("DeleteUser.html", error="Invalid Email", csrf_token=new_token)

        if not phoneNumber or not phoneNumber.isdigit() or len(phoneNumber) != 10 :
            return render_template("DeleteUser.html", error="Invalid PhoneNumber", csrf_token=new_token)

        if user_name != confirm_UserName or email != confirm_email or phoneNumber != confirm_phone:
            return render_template("DeleteUser.html", error="Invalid confirmation", csrf_token=new_token)

        conn = get_connection()
        cursor = conn.cursor()

        try :
            cursor.execute("""
                            SELECT id 
                            FROM users 
                            WHERE 
                            user_name = %s AND user_email = %s AND user_phoneNumber = %s
                            """,(user_name, email, phoneNumber))
            found = cursor.fetchone()

            if not found :
                return render_template("DeleteUser.html", error="User not found", csrf_token=new_token)

            cursor.execute("""
                            DELETE FROM patient WHERE user_id = %s """,(found[0],))
            cursor.execute("""
                            DELETE FROM patient_history WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM patient_stat WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM dentists WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM dentist_registry WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM dentist_history WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM dentist_stat WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM other_prothesists WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM other_prothesists_khedma WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM other_prothesists_history WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM prothesist_stat WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM khedma WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM sel3a WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM others_services WHERE user_id = %s """, (found[0],))
            cursor.execute("""
                            DELETE FROM other_services_stats WHERE user_id = %s """, (found[0],))

            cursor.execute("""UPDATE users SET status = 'deleted' WHERE id = %s """,(found[0],))

            conn.commit()

            return render_template("DeleteUser.html", message="User Deleted", csrf_token=new_token)

        except Exception as e :
            conn.rollback()
            return render_template("DeleteUser.html", error=f"error {str(e)}", csrf_token=new_token)

        finally :
            cursor.close()
            conn.close()


@users.route("/ConfirmOwnerData", methods=["POST" , "GET"])
def ConfirmOwnerData():
    if not is_logged_in():
        return redirect(url_for('home'))

    if request.method == "GET":
        token = secrets.token_hex(16)
        session['csrf_token'] = token
        return render_template("ConfirmOwnerData.html", csrf_token=token)

    if request.method == "POST" :
        token_form = request.form.get('csrf_token')
        session_token = session.get('csrf_token')

        if not token_form or token_form != session_token :
            return "error CSRF attack",403

        new_token = secrets.token_hex(16)
        session['csrf_token'] = new_token

        user_name = request.form.get('userName')
        email = request.form.get('email')
        phoneNumber = request.form.get('phoneNumber')
        password = request.form.get('password')
        function = request.form.get('function')

        if user_name == os.getenv('owner_name') and email == os.getenv('owner_email') and phoneNumber == os.getenv('owner_phoneNumber') and password == os.getenv('owner_password'):
            if function == 'add':
                return redirect(url_for('Create'))
            elif function == 'block':
                return redirect(url_for('users.ModifyStatus'))
            elif function == 'delete':
                return redirect(url_for('users.DeleteUser'))

        else :
            return render_template('ConfirmOwnerData.html', message='Do not have the access', csrf_token=new_token)

