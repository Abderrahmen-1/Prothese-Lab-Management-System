from datetime import date, timedelta, datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from FlaskTry.scheduler.email_service import send_deadline_emails, send_quantity_email, send_prothesists_email, send_abonnement_email
from FlaskTry.flasktry import app, mail
from FlaskTry.FunctionFile import get_connection

load_dotenv()

def check_deadlines():
    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try :
        today = date.today()
        limit_date = today + timedelta(days=2)

        cursor.execute("""
                        SELECT p.patient_firstname, p.patient_lastname, p.patient_number, p.DeadLine, u.user_email
                        FROM patient p 
                        JOIN users u ON p.user_id = u.id 
                        WHERE 
                         p.finished = %s AND p.DeadLine IS NOT NULL 
                         AND p.DeadLine >= %s AND p.DeadLine <= %s """,('no', today, limit_date))
        patients = cursor.fetchall()

        cursor.execute("""
                        SELECT d.id, d.patient_firstname, d.patient_lastname, d.patient_number, 
                                d.DeadLine, u.user_email, d.dentist_name
                        FROM dentists d 
                        JOIN users u ON d.user_id = u.id
                        WHERE 
                          d.finished = %s AND d.DeadLine IS NOT NULL 
                          AND d.DeadLine >= %s AND d.DeadLine <= %s """, ('no', today, limit_date))
        dentists = cursor.fetchall()

        for patient in patients:
            print(
                f"Deadline found: "
                f"{patient[3]} "
                f"{patient[4]}" )
            deadline = datetime.strptime(patient[3], "%Y-%m-%d").date()
            remaine = (deadline - today).days

            cursor.execute("""
                            SELECT pr.pName, pr.pFinished 
                            FROM other_prothesists_khedma pr
                            JOIN users u ON u.id = pr.user_id  
                            WHERE 
                            patient_number = %s AND dentist_name IS NULL
                            """,(patient[2],))
            found = cursor.fetchone()

            with app.app_context():
                if found :
                    send_deadline_emails(patient[4], remaine, patient[3], mail, patient[2], patient[0], patient[1], 'patient', None, found[0], found[1])
                    print(f"Email sent to {patient[5]}")
                else :
                    send_deadline_emails(patient[4], remaine, patient[3], mail, patient[2], patient[0], patient[1],'patient', None)
                    print(f"Email sent to {patient[5]}")



        for dentist in dentists :
            print(
                f"Deadline found: "
                f"{dentist[3]} "
                f"{dentist[4]}")
            deadline = datetime.strptime(dentist[3], "%Y-%m-%d").date()
            remain = (deadline - today).days

            cursor.execute("""
                            SELECT pr.pName, pr.pFinished 
                            FROM other_prothesists_khedma pr
                            JOIN users u ON u.id = pr.user_id  
                            WHERE 
                            patient_number = %s AND dentist_name IS NOT NULL 
                            """, (dentist[2],))
            found = cursor.fetchone()

            with app.app_context():
                if found :
                    send_deadline_emails(dentist[4], remain, dentist[3], mail, dentist[2], dentist[0], dentist[1], 'dentist', dentist[5], found[0], found[1])
                    print(f"Email sent to {dentist[5]}")
                else :
                    send_deadline_emails(dentist[4], remain, dentist[3], mail, dentist[2], dentist[0], dentist[1],'dentist', dentist[5])
                    print(f"Email sent to {dentist[5]}")

    except Exception as e :
        conn.rollback()
        return f"error {str(e)}"

    finally:
        cursor.close()
        conn.close()


def check_quantity():
    conn = get_connection()
    cursor = conn.cursor()

    try :
        cursor.execute("""
                        SELECT s.sel3a_name, s.quantity, s.max_quantity, s.unit, u.user_email,
                                s.low_stock_notified, s.out_of_stock_notified, s.id 
                        FROM sel3a s
                        JOIN users u ON u.id = s.user_id
                         """)
        result = cursor.fetchall()

        for r in result :
            with app.app_context():
                stock = send_quantity_email(r[4], mail, r[0], r[1], r[2], r[3], r[5], r[6])
                print(f"Email sent to {r[4]}")
                cursor.execute("""
                                UPDATE sel3a 
                                SET 
                                low_stock_notified = %s, out_of_stock_notified = %s
                                WHERE 
                                id = %s 
                                """,(stock[0], stock[1], r[7]))
                conn.commit()

    except Exception as e :
        conn.rollback()
        return f"error {str(e)}"

    finally :
        cursor.close()
        conn.close()


def check_prothesist_deadline():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        today = date.today()
        limit_date = today + timedelta(days=2)

        cursor.execute("""
                        SELECT p.patient_number, p.pName, p.DeadLine, u.user_email, u.user_name, p.pKhedma
                        FROM other_prothesists_khedma p 
                        JOIN users u ON u.id = p.user_id 
                        WHERE 
                        p.pFinished = 'no' AND p.DeadLine >= %s AND p.DeadLine <= %s
                        """,(today, limit_date))
        results = cursor.fetchall()

        for result in results :
            DeadLine = datetime.strptime(result[2], "%Y-%m-%d").date()
            remain = (DeadLine - today).days

            with app.app_context():
                send_prothesists_email(result[3], mail, result[4], result[5], result[1], result[0], remain, result[2])
                print(f"Email sent to : {result[3]}")

    except Exception as e :
        conn.rollback()
        return f"error {str(e)}"

    finally:
        cursor.close()
        conn.close()

def check_abonnement_deadline():
    conn = get_connection()
    cursor = conn.cursor()

    try :
        cursor.execute("""
                        SELECT user_name, user_email
                        FROM users 
                        WHERE 
                        (CASE 
                         WHEN paid_at IS NOT NULL THEN DATE_ADD(paid_at, INTERVAL 30 DAYS) = DATE_ADD(CURDATE() , INTERVAL 4 DAYS) 
                         ELSE DATE_ADD(date_inscription, INTERVAL 30 DAYS) = DATE_ADD(CURDATE() , INTERVAL 4 DAYS) END) """)
        results = cursor.fetchall()

        for result in results :
            with app.app_context():
                send_abonnement_email(mail, result[1], result[0])
                print(f"Email sent for the user {result[1]}")

    except Exception as e :
        conn.rollback()
        return f"error {str(e)}"

    finally :
        cursor.close()
        conn.close()





scheduler = BlockingScheduler()

scheduler.add_job(
    check_abonnement_deadline,
    trigger='cron',
    hour=8,
    minute=0
)

scheduler.add_job(
    check_deadlines,
    trigger="cron",
    hour=9,
    minute=0
)

scheduler.add_job(
    check_prothesist_deadline,
    trigger="cron",
    hour=10,
    minute=0
)

scheduler.add_job(
    check_quantity,
    trigger="cron",
    hour=11,
    minute=0
)


print("Scheduler started.")
print("Abonnements DeadLine check schuled every day at 8:00.")
print("Deadline check scheduled every day at 09:00.")
print("Quantities check scheduled every day at 11:00.")
print("Prothesists DeadLine check schuled every day at 10:00.")

scheduler.start()


