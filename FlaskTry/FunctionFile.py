from flask import session
from datetime import datetime , timedelta
from FlaskTry.ConnectToSql import get_connection

# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class InvalideNameException(Exception):
    pass

class InvalideEmailException(Exception):
    pass

class InvalidePasswordException(Exception):
    pass

class InvalideDateException(Exception):
    pass

class InvalidePriceException(Exception):
    pass

class InvalideIdException(Exception):
    pass

class InvalidePhoneNumberException(Exception):
    pass


# =============================================================================
# AUTH
# =============================================================================

def CheckData(email=None, username=None, password=None, phoneNumber=None):
    if username :
        if not username.strip() or len(username) < 4 or username.isdigit():
            raise InvalideNameException
    if email :
        if not email.strip() or email.isdigit() or "@" not in email or ".com" not in email:
            raise InvalideEmailException
    if password :
        if not password.strip() or len(password) < 8:
            raise InvalidePasswordException
    if phoneNumber :
        if not phoneNumber.isdigit() or len(phoneNumber) < 5 :
            raise InvalidePhoneNumberException


def ConfirmLogIn(email, username):
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT id, user_password 
            FROM users
            WHERE user_email = %s AND user_name = %s
        """, (email, username))
        row = cursor.fetchone()
        return row
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# DENTISTS
# =============================================================================

def GetAllDentistTables(cursor):
    cursor.execute("""
        SELECT dentist_name FROM dentist_registry
        WHERE user_id = %s
    """, (session['id'],))
    return [row[0] for row in cursor.fetchall()]


def AddDentistTable(cursor, conn, dentistName):
    if len(dentistName) < 3 or not dentistName.strip():
        raise InvalideNameException

    dentistName = dentistName.lower()
    cursor.execute("""
        INSERT INTO dentist_registry (user_id, dentist_name)
        VALUES (%s, %s)
    """, (session['id'], dentistName))
    conn.commit()


def DentistsDics(cursor):
    findMostKhedma = {}
    dentists = GetAllDentistTables(cursor)
    for dentist in dentists:
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM dentists
                WHERE user_id = %s AND dentist_name = %s
            """, (session['id'], dentist))
            row = cursor.fetchone()

            findMostKhedma[dentist] = row[0] if row else 0
        except Exception as e:
            findMostKhedma[dentist] = 0
    return findMostKhedma


def getdentist(cursor, dentist_name):
    cursor.execute("""
        SELECT dentist_name, patient_firstname, patient_lastname, patient_number,
               date, Dkhedma, user_id, price, versement, b9aw
        FROM dentists
        WHERE dentist_name = %s AND user_id = %s
    """, (dentist_name, session['id']))
    history = cursor.fetchall()
    return history


def Dentist_History(cursor, conn, dentist_name):
    result = getdentist(cursor, dentist_name)
    if result :
        for data in result:
            cursor.execute("""
                SELECT pNumber, pFirstname, dentistname FROM dentist_history
                WHERE dentistname = %s AND pNumber = %s AND pFirstname = %s AND user_id = %s
            """, (dentist_name, data[3], data[1], session['id']))
            exist = cursor.fetchall()

            if not exist:
                cursor.execute("""
                    INSERT INTO dentist_history
                        (dentistname, pNumber, pFirstname, pLastname, pKhedma, pPrice, versement, b9aw, pDate, user_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (data[0], data[3], data[1], data[2], data[5], data[7], data[8], data[9], data[4], data[6], 'active'))
                conn.commit()

            cursor.execute("""
                DELETE FROM dentist_history
                WHERE pDate < DATE_SUB(NOW(), INTERVAL 6 MONTH)
            """)
            conn.commit()


def DentistStats(cursor, conn, dentistName, price, khalsa, date):
    if isinstance(date, str):
        parsed = datetime.strptime(date, "%Y-%m-%d")
    else:
        parsed = date

    month = parsed.month
    year  = parsed.year

    if khalsa.lower() == 'yes':
        khalsin       = price
        machi_khalsin = 0
    else:
        khalsin       = 0
        machi_khalsin = price

    cursor.execute("""
        SELECT id FROM dentist_stat
        WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s
    """, (session['id'], dentistName, month, year))
    existing = cursor.fetchone()
    cursor.fetchall()

    if existing:
        cursor.execute("""
            UPDATE dentist_stat
            SET total_khedma  = total_khedma + 1,
                khalsin       = khalsin + %s,
                machi_khalsin = machi_khalsin + %s
            WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s
        """, (khalsin, machi_khalsin, session['id'], dentistName, month, year))
    else:
        cursor.execute("""
            INSERT INTO dentist_stat
                (dentist_name, total_khedma, khalsin, machi_khalsin, month, year, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (dentistName, 1, khalsin, machi_khalsin, month, year, session['id']))

    conn.commit()


# =============================================================================
# PATIENTS
# =============================================================================

def getpatient(cursor, unique):
    cursor.execute("""
        SELECT patient_firstname, patient_lastname, patient_number,
               la_date, T_ype, user_id, COALESCE(versa,0) + COALESCE(b9aw,0) AS price,
               versa, b9aw
        FROM patient
        WHERE patient_number = %s AND user_id = %s
    """, (unique, session['id']))
    history = cursor.fetchall()
    return history


def Patient_History(cursor, conn, unique):
    result = getpatient(cursor, unique)
    if result :
        data = result[0]
        cursor.execute("""
            SELECT pNumber FROM patient_history
            WHERE pNumber = %s AND user_id = %s
        """, (data[2], session['id']))
        exist = cursor.fetchall()

        if not exist:
            cursor.execute("""
                INSERT INTO patient_history
                    (user_id, firstname, lastname, pNumber, pDate, pKhedma, pPrice, versement, b9aw, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (data[5], data[0], data[1], data[2], data[3], data[4], data[6], data[7], data[8], 'active'))

        cursor.execute("""
            DELETE FROM patient_history
            WHERE pDate < DATE_SUB(NOW(), INTERVAL 6 MONTH)
        """)
        conn.commit()


def PatientStats(cursor, conn, price, khalsa, date, versa):
    if isinstance(date, str):
        parsed = datetime.strptime(date, "%Y-%m-%d")
    else:
        parsed = date

    month = parsed.month
    year  = parsed.year

    if khalsa.lower() == 'yes':
        khalsin       = price
        machi_khalsin = 0
    else:
        khalsin       = versa
        machi_khalsin = price - versa

    cursor.execute("""
        SELECT id FROM patient_stat
        WHERE user_id = %s AND month = %s AND year = %s
    """, (session['id'], month, year))
    existing = cursor.fetchone()
    cursor.fetchall()

    if existing:
        cursor.execute("""
            UPDATE patient_stat
            SET patients_number = patients_number + 1,
                khalsin         = khalsin + %s,
                machi_khalsin   = machi_khalsin + %s
            WHERE user_id = %s AND month = %s AND year = %s
        """, (khalsin, machi_khalsin, session['id'], month, year))
    else:
        cursor.execute("""
            INSERT INTO patient_stat
                (patients_number, khalsin, machi_khalsin, month, year, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (1, khalsin, machi_khalsin, month, year, session['id']))

    conn.commit()


def checkExistPatient(cursor, firstName, unique, khedma):
    cursor.execute("""
        SELECT * FROM patient
        WHERE user_id = %s AND patient_number = %s
        AND patient_firstname = %s AND T_ype = %s
    """, (session['id'], unique, firstName, khedma))
    result = cursor.fetchone()
    cursor.fetchall()
    return result


def checkExistDentistPatient(cursor, dentist, unique, firstName):
    cursor.execute("""
        SELECT * FROM dentists
        WHERE user_id = %s AND dentist_name = %s
        AND patient_number = %s AND patient_firstname = %s
    """, (session['id'], dentist, unique, firstName))
    result = cursor.fetchone()
    cursor.fetchall()
    return result


# =============================================================================
# KHALSA STATS
# =============================================================================

def UpdateKhalsaStat(cursor, conn, table, dentistName=None, b9aw=0, date=None):
    if isinstance(date, str):
        parsed = datetime.strptime(date, "%Y-%m-%d")
    else:
        parsed = date

    month = parsed.month
    year  = parsed.year

    if table == "dentist":
        cursor.execute("""
            SELECT id FROM dentist_stat
            WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s
        """, (session['id'], dentistName, month, year))
    else:
        cursor.execute("""
            SELECT id FROM patient_stat
            WHERE user_id = %s AND month = %s AND year = %s
        """, (session['id'], month, year))

    existing = cursor.fetchone()

    if not existing:
        return

    if table == "dentist":
        cursor.execute("""
            UPDATE dentist_stat
            SET khalsin       = khalsin + %s,
                machi_khalsin = machi_khalsin - %s
            WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s
        """, (b9aw, b9aw, session['id'], dentistName, month, year))
    else:
        cursor.execute("""
            UPDATE patient_stat
            SET khalsin       = khalsin + %s,
                machi_khalsin = machi_khalsin - %s
            WHERE user_id = %s AND month = %s AND year = %s
        """, (b9aw, b9aw, session['id'], month, year))

    conn.commit()


# =============================================================================
# PROTHESISTS
# =============================================================================

def GetAllProthesists(cursor):
    cursor.execute("""
        SELECT pNumber, pName
        FROM other_prothesists
        WHERE user_id = %s
    """, (session['id'],))
    rows = cursor.fetchall()
    return [ row for row in rows]


def ProthesistDics(cursor):
    AllProthesists = GetAllProthesists(cursor)
    result = {}
    for Pro in AllProthesists:
        pNumber , pName = Pro
        try:
            cursor.execute("""
                SELECT COUNT(*)
                FROM other_prothesists_khedma
                WHERE user_id = %s AND pName = %s AND pNumber = %s
            """, (session['id'], pName, pNumber))
            row = cursor.fetchone()
            result[pName] = row[0] if row else 0
        except Exception as e:
            result[Pro] = 0
    return result

def getprothesist(cursor,prothesist_name, prothesist_number, unique):
    cursor.execute("""
        SELECT pFirstname, pLastname, patient_number,
               pDate, pKhedma, user_id, pPrice, versement, b9aw, status, dentist_name
        FROM other_prothesists_khedma
        WHERE patient_number = %s AND pName = %s AND pNumber = %s AND user_id = %s
    """, (unique, prothesist_name, prothesist_number, session['id']))
    history = cursor.fetchall()
    return history


def Prothesist_History(cursor, conn, prothesistname, prothesist_number, unique):
    result = getprothesist(cursor, prothesistname, prothesist_number, unique)
    if result :
        data = result[0]
        cursor.execute("""
            SELECT 1 
            FROM other_prothesists_history
            WHERE pNumber = %s AND pName = %s AND patient_number = %s AND pFirstname = %s AND 
             pLastname = %s AND user_id = %s
        """, (prothesist_number, prothesistname, data[0], data[1], session['id']))
        exist = cursor.fetchall()

        if not exist:
            cursor.execute("""
                INSERT INTO other_prothesists_history
                    (dentistname, prothesist, pNumber, pFirstname, pLastname, patient_number, pKhedma, pPrice, versement, b9aw, pDate, user_id, Status) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (data[10], prothesistname, prothesist_number, data[0], data[1], data[2], data[4], data[6], data[7], data[8], data[3], session['id'], data[9]))

        cursor.execute("""
            DELETE FROM other_prothesists_history
            WHERE pDate < DATE_SUB(NOW(), INTERVAL 6 MONTH)
        """)
        conn.commit()



def ProthesistsStat(cursor, conn, price, pNumber, pName, khalsa, date, versa):
    if isinstance(date, str):
        parsed = datetime.strptime(date, "%Y-%m-%d")
    else:
        parsed = date

    month = parsed.month
    year  = parsed.year

    if khalsa.lower() == 'yes':
        khalsin       = price
        machi_khalsin = 0
    else:
        khalsin       = versa
        machi_khalsin = price - versa

    cursor.execute("""
        SELECT id FROM prothesist_stat
        WHERE user_id = %s AND month = %s AND year = %s
        AND prothesist_name = %s AND prothesist_number = %s
    """, (session['id'], month, year, pName, pNumber))
    existing = cursor.fetchone()
    cursor.fetchall()

    if existing:
        cursor.execute("""
            UPDATE prothesist_stat
            SET total_khedma  = total_khedma + 1,
                khalsin       = khalsin + %s,
                machi_khalsin = machi_khalsin + %s
            WHERE user_id = %s AND month = %s AND year = %s
            AND prothesist_name = %s AND prothesist_number = %s
        """, (khalsin, machi_khalsin, session['id'], month, year, pName, pNumber))
    else:
        cursor.execute("""
            INSERT INTO prothesist_stat
                (prothesist_name, prothesist_number, total_khedma, khalsin, machi_khalsin, month, year, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (pName, pNumber, 1, khalsin, machi_khalsin, month, year, session['id']))

    conn.commit()


def UpdateProKhalsaStat(cursor, conn, ProName=None, ProNumber=0, b9aw=0, date=None):
    if isinstance(date, str):
        parsed = datetime.strptime(date, "%Y-%m-%d")
    else:
        parsed = date

    month = parsed.month
    year  = parsed.year

    cursor.execute("""
        SELECT id FROM prothesist_stat
        WHERE user_id = %s AND month = %s AND year = %s AND prothesist_name = %s AND prothesist_number = %s
    """, (session['id'], month, year, ProName, ProNumber))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE prothesist_stat
            SET 
                khalsin       = khalsin + %s,
                machi_khalsin = machi_khalsin - %s
            WHERE user_id = %s AND prothesist_name = %s AND prothesist_number = %s AND month = %s AND year = %s
        """, (b9aw, b9aw, session['id'], ProName, ProNumber, month, year))

        conn.commit()

    else :
        return

# =============================================================================
# NET PROFIT
# =============================================================================

def NetProfit():
    from ConnectToSql import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    try:
        result = {}

        cursor.execute("""
            SELECT COALESCE(SUM(khalsin), 0), COALESCE(SUM(machi_khalsin), 0)
            FROM patient_stat
            WHERE user_id = %s
        """, (session['id'],))
        row = cursor.fetchone()
        total_khalsin       = float(row[0] or 0)
        total_machi_khalsin = float(row[1] or 0)
        gross_income        = round(total_khalsin + total_machi_khalsin, 2)
        result['total']     = gross_income

        cursor.execute("""
            SELECT COALESCE(SUM(pVersa), 0)
            FROM other_prothesists_khedma
            WHERE user_id = %s
        """, (session['id'],))
        pro_paid = float(cursor.fetchone()[0] or 0)

        cursor.execute("""
            SELECT COALESCE(SUM(pB9aw), 0)
            FROM other_prothesists_khedma
            WHERE user_id = %s
        """, (session['id'],))
        pro_owed = float(cursor.fetchone()[0] or 0)

        total_pro_cost              = round(pro_paid + pro_owed, 2)
        result['total-prothesists'] = total_pro_cost

        cursor.execute("""
            SELECT COALESCE(SUM(sel3a_price), 0)
            FROM sel3a
            WHERE user_id = %s
        """, (session['id'],))
        total_sel3a           = float(cursor.fetchone()[0] or 0)
        result['total-sel3a'] = total_sel3a

        result['total-profits'] = round(gross_income - total_pro_cost - total_sel3a, 2)

        return result
    finally:
        cursor.close()
        conn.close()


def a_acces(cursor):
    cursor.execute("""
                   SELECT id, date_inscription FROM users 
                   WHERE id = %s""",(session['id'],))

    row = cursor.fetchone()
    if not row :
        return False

    date_inscription = row[1]
    user_id = row[0]

    maintenant = datetime.now()
    fin_essaie = date_inscription + timedelta(days=30)

    if maintenant <= fin_essaie or user_id == 2 or user_id == 1 :
        return True
    else :
        return False



def getDentists(cursor):
    cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                   (session["id"],))
    rows = cursor.fetchall()

    return rows


def checkValue(value=None):
    if value :
        try:
            value = float(value)
        except (ValueError, TypeError):
            return False

        if value < 0:
            return False

        return True
    else :
        return True

def checkVersement(value=None):
    if value :
        try:
            value = float(value)
        except (ValueError, TypeError):
            return False
    else :
        return True

def checkIntValue(value=None):
    if value :
        try:
            value = int(value)
        except (ValueError, TypeError):
            return False

        if value < 0:
            return False

        return True
    else:
        return True

