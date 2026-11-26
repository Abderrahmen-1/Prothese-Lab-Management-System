import math
import re
from flask import session
from datetime import datetime, timedelta
from ManageMyLab.ConnectToSql import get_connection


# =============================================================================
# CONSTANTES
# =============================================================================

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ADMIN_IDS = (1, 2)   # TODO : remplacer par une colonne users.is_admin
TRIAL_DAYS = 30

HISTORY_TABLES = ("patient_history", "dentist_history", "other_prothesists_history")


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
# OUTILS INTERNES (prefixe _ : non exportes par `import *`)
# =============================================================================

def _uid():
    return session['id']


def _to_date(value):
    """Accepte une chaine 'YYYY-MM-DD' ou un objet date/datetime."""
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d")
    return value


# =============================================================================
# AUTH / VALIDATION
# =============================================================================

def SearcheTable(cursor, DentistName):
    cursor.execute("""
        SELECT 1 FROM dentist_registry
        WHERE user_id = %s AND dentist_name = %s
    """, (_uid(), DentistName))
    return cursor.fetchone()


def CheckData(email=None, username=None, password=None, phoneNumber=None):
    if username:
        if not username.strip() or len(username) < 4 or username.isdigit():
            raise InvalideNameException

    if email:
        if (
            email != email.strip()
            or len(email) > 254
            or not EMAIL_RE.match(email)
            or email.endswith(".")
        ):
            raise InvalideEmailException

    if password:
        if not password.strip() or len(password) < 8 or len(password) > 128:
            raise InvalidePasswordException

    if phoneNumber:
        if not phoneNumber.isdigit() or not (5 <= len(phoneNumber) <= 15):
            raise InvalidePhoneNumberException


def ConfirmLogIn(email, username):
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT id, user_password, email_confirmed
            FROM users
            WHERE user_email = %s AND user_name = %s
        """, (email, username))
        return cursor.fetchone()
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
    """, (_uid(),))
    return [row[0] for row in cursor.fetchall()]


def AddDentistTable(cursor, dentistName):
    dentistName = (dentistName or "").strip()
    if len(dentistName) < 3:
        raise InvalideNameException

    cursor.execute("""
        INSERT INTO dentist_registry (user_id, dentist_name)
        VALUES (%s, %s)
    """, (_uid(), dentistName.lower()))


def DentistsDics(cursor):
    findMostKhedma = {}
    for dentist in GetAllDentistTables(cursor):
        cursor.execute("""
            SELECT COUNT(*) FROM dentists
            WHERE user_id = %s AND dentist_name = %s
        """, (_uid(), dentist))
        row = cursor.fetchone()
        findMostKhedma[dentist] = row[0] if row else 0
    return findMostKhedma


def getdentist(cursor, dentist_name):
    cursor.execute("""
        SELECT dentist_name, patient_firstname, patient_lastname, patient_number,
               date, Dkhedma, user_id, price, versement, b9aw, status
        FROM dentists
        WHERE dentist_name = %s AND user_id = %s
    """, (dentist_name, _uid()))
    return cursor.fetchall()


def getDentists(cursor, dentist_name=None):
    """Tous les dentistes du client, ou un seul si dentist_name est donne."""
    if dentist_name:
        cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                       (_uid(), dentist_name))
    else:
        cursor.execute("SELECT * FROM dentists WHERE user_id = %s", (_uid(),))
    return cursor.fetchall()


def Dentist_History(cursor, dentist_name):
    for data in getdentist(cursor, dentist_name):
        cursor.execute("""
            SELECT 1
            FROM dentist_history
            WHERE dentistname = %s AND pNumber = %s AND pFirstname = %s AND user_id = %s
        """, (dentist_name, data[3], data[1], _uid()))
        exist = cursor.fetchall()

        if not exist:
            cursor.execute("""
                INSERT INTO dentist_history
                    (dentistname, pNumber, pFirstname, pLastname, pKhedma, pPrice,
                     versement, b9aw, pDate, user_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (data[0], data[3], data[1], data[2], data[5], data[7],
                  data[8], data[9], data[4], data[6], data[10]))


def DentistStats(cursor, dentistName, price, khalsa, date):
    parsed = _to_date(date)
    month, year = parsed.month, parsed.year

    if khalsa.lower() == 'yes':
        khalsin, machi_khalsin = price, 0
    else:
        khalsin, machi_khalsin = 0, price

    cursor.execute("""
        SELECT id FROM dentist_stat
        WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s
    """, (_uid(), dentistName, month, year))
    existing = cursor.fetchone()
    cursor.fetchall()

    if existing:
        cursor.execute("""
            UPDATE dentist_stat
            SET total_khedma  = total_khedma + 1,
                khalsin       = khalsin + %s,
                machi_khalsin = machi_khalsin + %s
            WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s
        """, (khalsin, machi_khalsin, _uid(), dentistName, month, year))
    else:
        cursor.execute("""
            INSERT INTO dentist_stat
                (dentist_name, total_khedma, khalsin, machi_khalsin, month, year, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (dentistName, 1, khalsin, machi_khalsin, month, year, _uid()))


# =============================================================================
# PATIENTS
# =============================================================================

def getpatient(cursor, unique):
    cursor.execute("""
        SELECT patient_firstname, patient_lastname, patient_number,
               la_date, T_ype, user_id, COALESCE(versa,0) + COALESCE(b9aw,0) AS price,
               versa, b9aw, status
        FROM patient
        WHERE patient_number = %s AND user_id = %s
    """, (unique, _uid()))
    return cursor.fetchall()


def Patient_History(cursor, unique):
    result = getpatient(cursor, unique)
    if not result:
        return

    data = result[0]
    cursor.execute("""
        SELECT 1 FROM patient_history
        WHERE pNumber = %s AND user_id = %s
    """, (data[2], _uid()))
    exist = cursor.fetchall()

    if not exist:
        cursor.execute("""
            INSERT INTO patient_history
                (user_id, firstname, lastname, pNumber, pDate, pKhedma, pPrice, versement, b9aw, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (data[5], data[0], data[1], data[2], data[3], data[4],
              data[6], data[7], data[8], data[9]))


def PatientStats(cursor, price, khalsa, date, versa):
    parsed = _to_date(date)
    month, year = parsed.month, parsed.year

    if khalsa.lower() == 'yes':
        khalsin, machi_khalsin = price, 0
    else:
        khalsin = versa
        machi_khalsin = round(price - versa, 2)

    cursor.execute("""
        SELECT id FROM patient_stat
        WHERE user_id = %s AND month = %s AND year = %s
    """, (_uid(), month, year))
    existing = cursor.fetchone()
    cursor.fetchall()

    if existing:
        cursor.execute("""
            UPDATE patient_stat
            SET patients_number = patients_number + 1,
                khalsin         = khalsin + %s,
                machi_khalsin   = machi_khalsin + %s
            WHERE user_id = %s AND month = %s AND year = %s
        """, (khalsin, machi_khalsin, _uid(), month, year))
    else:
        cursor.execute("""
            INSERT INTO patient_stat
                (patients_number, khalsin, machi_khalsin, month, year, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (1, khalsin, machi_khalsin, month, year, _uid()))


def checkExistPatient(cursor, firstName, unique, khedma):
    cursor.execute("""
        SELECT * FROM patient
        WHERE user_id = %s AND patient_number = %s
        AND patient_firstname = %s AND T_ype = %s
    """, (_uid(), unique, firstName, khedma))
    result = cursor.fetchone()
    cursor.fetchall()
    return result


def checkExistDentistPatient(cursor, dentist, unique, firstName):
    cursor.execute("""
        SELECT * FROM dentists
        WHERE user_id = %s AND dentist_name = %s
        AND patient_number = %s AND patient_firstname = %s
    """, (_uid(), dentist, unique, firstName))
    result = cursor.fetchone()
    cursor.fetchall()
    return result


# =============================================================================
# KHALSA STATS
# =============================================================================

def UpdateKhalsaStat(cursor, table, dentistName=None, b9aw=0, date=None):
    parsed = _to_date(date)
    month, year = parsed.month, parsed.year

    if table == "dentist":
        cursor.execute("""
            SELECT id FROM dentist_stat
            WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s
        """, (_uid(), dentistName, month, year))
    else:
        cursor.execute("""
            SELECT id FROM patient_stat
            WHERE user_id = %s AND month = %s AND year = %s
        """, (_uid(), month, year))

    existing = cursor.fetchone()
    cursor.fetchall()

    if not existing:
        return

    if table == "dentist":
        cursor.execute("""
            UPDATE dentist_stat
            SET khalsin       = khalsin + %s,
                machi_khalsin = machi_khalsin - %s
            WHERE user_id = %s AND dentist_name = %s AND month = %s AND year = %s
        """, (b9aw, b9aw, _uid(), dentistName, month, year))
    else:
        cursor.execute("""
            UPDATE patient_stat
            SET khalsin       = khalsin + %s,
                machi_khalsin = machi_khalsin - %s
            WHERE user_id = %s AND month = %s AND year = %s
        """, (b9aw, b9aw, _uid(), month, year))


# =============================================================================
# PROTHESISTS
# =============================================================================

def GetAllProthesists(cursor):
    cursor.execute("""
        SELECT pNumber, pName
        FROM other_prothesists
        WHERE user_id = %s
    """, (_uid(),))
    return list(cursor.fetchall())


def ProthesistDics(cursor):
    result = {}
    for pNumber, pName in GetAllProthesists(cursor):
        cursor.execute("""
            SELECT COUNT(*)
            FROM other_prothesists_khedma
            WHERE user_id = %s AND pName = %s AND pNumber = %s
        """, (_uid(), pName, pNumber))
        row = cursor.fetchone()
        result[pName] = row[0] if row else 0
    return result


def getprothesist(cursor, prothesist_name, prothesist_number, unique):
    cursor.execute("""
        SELECT patient_number, pDate, pKhedma, user_id, pPrice,
               pVersa, pB9aw, dentist_name
        FROM other_prothesists_khedma
        WHERE patient_number = %s AND pName = %s AND pNumber = %s AND user_id = %s
    """, (unique, prothesist_name, prothesist_number, _uid()))
    return cursor.fetchall()


def Prothesist_History(cursor, prothesistname, prothesist_number, unique,
                       patient_firstname, patient_lastname):
    result = getprothesist(cursor, prothesistname, prothesist_number, unique)
    if not result:
        return

    data = result[0]
    cursor.execute("""
        SELECT 1
        FROM other_prothesists_history
        WHERE pNumber = %s AND prothesist = %s AND patient_number = %s
          AND pFirstname = %s AND pLastname = %s AND user_id = %s
    """, (prothesist_number, prothesistname, data[0],
          patient_firstname, patient_lastname, _uid()))
    exist = cursor.fetchall()

    if not exist:
        cursor.execute("""
            INSERT INTO other_prothesists_history
                (dentistname, prothesist, pNumber, pFirstname, pLastname, patient_number,
                 pKhedma, pPrice, versement, b9aw, pDate, user_id, Status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (data[7], prothesistname, prothesist_number, patient_firstname,
              patient_lastname, data[0], data[2], data[4], data[5], data[6],
              data[1], _uid(), 'active'))


def ProthesistsStat(cursor, price, pNumber, pName, khalsa, date, versa):
    parsed = _to_date(date)
    month, year = parsed.month, parsed.year

    if khalsa.lower() == 'yes':
        khalsin, machi_khalsin = price, 0
    else:
        khalsin = versa
        machi_khalsin = round(price - versa, 2)

    cursor.execute("""
        SELECT id FROM prothesist_stat
        WHERE user_id = %s AND month = %s AND year = %s
          AND prothesist_name = %s AND prothesist_number = %s
    """, (_uid(), month, year, pName, pNumber))
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
        """, (khalsin, machi_khalsin, _uid(), month, year, pName, pNumber))
    else:
        cursor.execute("""
            INSERT INTO prothesist_stat
                (prothesist_name, prothesist_number, total_khedma, khalsin,
                 machi_khalsin, month, year, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (pName, pNumber, 1, khalsin, machi_khalsin, month, year, _uid()))


def UpdateProKhalsaStat(cursor, ProName=None, ProNumber=0, b9aw=0, date=None):
    parsed = _to_date(date)
    month, year = parsed.month, parsed.year

    cursor.execute("""
        SELECT id FROM prothesist_stat
        WHERE user_id = %s AND month = %s AND year = %s
          AND prothesist_name = %s AND prothesist_number = %s
    """, (_uid(), month, year, ProName, ProNumber))
    existing = cursor.fetchone()
    cursor.fetchall()

    if not existing:
        return

    cursor.execute("""
        UPDATE prothesist_stat
        SET khalsin       = khalsin + %s,
            machi_khalsin = machi_khalsin - %s
        WHERE user_id = %s AND prothesist_name = %s AND prothesist_number = %s
          AND month = %s AND year = %s
    """, (b9aw, b9aw, _uid(), ProName, ProNumber, month, year))


# =============================================================================
# PURGE DE L'HISTORIQUE (a appeler explicitement, jamais depuis un helper)
# =============================================================================

def purge_old_history(cursor, months=25):
    for table in HISTORY_TABLES:   # noms de tables constants : pas d'injection possible
        cursor.execute(f"""
            DELETE FROM {table}
            WHERE user_id = %s
              AND pDate < DATE_SUB(NOW(), INTERVAL %s MONTH)
              AND ((status = 'finished' AND b9aw = 0) OR status = 'deleted')
        """, (_uid(), int(months)))


# =============================================================================
# NET PROFIT
# =============================================================================

def NetProfit():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        uid = _uid()
        result = {}

        cursor.execute("""
            SELECT COALESCE(SUM(khalsin), 0), COALESCE(SUM(machi_khalsin), 0)
            FROM patient_stat
            WHERE user_id = %s
        """, (uid,))
        row = cursor.fetchone()
        gross_income = round(float(row[0] or 0) + float(row[1] or 0), 2)
        result['total'] = gross_income

        cursor.execute("""
            SELECT COALESCE(SUM(pVersa), 0), COALESCE(SUM(pB9aw), 0)
            FROM other_prothesists_khedma
            WHERE user_id = %s
        """, (uid,))
        row = cursor.fetchone()
        total_pro_cost = round(float(row[0] or 0) + float(row[1] or 0), 2)
        result['total-prothesists'] = total_pro_cost

        cursor.execute("""
            SELECT COALESCE(SUM(sel3a_price), 0)
            FROM sel3a
            WHERE user_id = %s
        """, (uid,))
        total_sel3a = float(cursor.fetchone()[0] or 0)
        result['total-sel3a'] = total_sel3a

        result['total-profits'] = round(gross_income - total_pro_cost - total_sel3a, 2)
        return result
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# ACCES / ESSAI GRATUIT
# =============================================================================

def a_acces(cursor):
    cursor.execute("""
        SELECT id, date_inscription FROM users
        WHERE id = %s
    """, (_uid(),))
    row = cursor.fetchone()
    if not row:
        return False

    user_id, date_inscription = row

    if user_id in ADMIN_IDS:
        return True
    if date_inscription is None:
        return False

    # date_inscription peut etre un DATE (pas de heure) ou un DATETIME
    if not isinstance(date_inscription, datetime):
        date_inscription = datetime.combine(date_inscription, datetime.min.time())

    return datetime.now() <= date_inscription + timedelta(days=TRIAL_DAYS)


# =============================================================================
# VALIDATION DE VALEURS
# =============================================================================

def checkValue(value=None):
    """True si vide ou nombre fini >= 0."""
    if not value:
        return True
    try:
        value = float(value)
    except (ValueError, TypeError):
        return False
    return math.isfinite(value) and value >= 0


def checkVersement(value=None):
    """True si vide ou nombre fini (negatif autorise : correction de versement)."""
    if not value:
        return True
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError):
        return False


def checkIntValue(value=None):
    """True si vide ou entier >= 0."""
    if not value:
        return True
    try:
        value = int(value)
    except (ValueError, TypeError):
        return False
    return value >= 0
