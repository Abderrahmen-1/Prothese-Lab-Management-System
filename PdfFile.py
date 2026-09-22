
import io
from flask import Flask, request, render_template, session, redirect, url_for, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from FunctionFile import *
from ConnectToSql import *

app = Flask(__name__)
app.secret_key = "mysecret123"


# ═══════════════════════════ HELPERS ═════════════════════════════════════════

def SearcheTable(DentistName):
    cursor.execute("""
        SELECT * FROM Dentist_registry
        WHERE user_id = %s AND dentist_name = %s
    """, (getSession(), DentistName))
    exist = cursor.fetchone()
    cursor.fetchall()
    return exist


def SearcheProTable(ProName):
    cursor.execute("""
        SELECT * FROM Other_Prothesists
        WHERE user_id = %s AND pName = %s
    """, (getSession(), ProName))
    exist = cursor.fetchone()
    cursor.fetchall()
    return exist


def is_logged_in():
    return "id" in session


# ═══════════════════════════ PDF HELPERS ══════════════════════════════════════

HEADER_BG    = colors.HexColor('#2c3e50')
ROW_ALT      = colors.HexColor('#f2f2f2')


def _base_table_style():
    return TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0),  HEADER_BG),
        ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',       (0, 0), (-1, 0),  9),
        ('FONTNAME',       (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',       (0, 1), (-1, -1), 8),
        ('ALIGN',          (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ('GRID',           (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('TOPPADDING',     (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 4),
    ])


def _make_pdf(title, build_fn):
    """Build PDF in memory and return a Flask response."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm,    bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('T', parent=styles['Title'],
                                 fontSize=20, textColor=HEADER_BG, spaceAfter=12)
    h2_style    = ParagraphStyle('H2', parent=styles['Heading2'],
                                 fontSize=12, textColor=HEADER_BG,
                                 spaceBefore=14, spaceAfter=6)

    story = [Paragraph(title, title_style), Spacer(1, 0.4*cm)]
    build_fn(story, styles, h2_style)
    doc.build(story)

    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type']        = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={title.replace(" ", "_")}.pdf'
    return response


# ════════════════════════════ HOME ════════════════════════════════════════════

@app.route("/log_in", methods=["POST", "GET"])
def home():
    if request.method == "POST":
        email    = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        try:
            CheckData(email, username, password)
        except InvalideNameException:
            return render_template("Log-in.html", error="Invalide Name")
        except InvalidePasswordException:
            return render_template("Log-in.html", error="Invalide Password")
        except InvalideEmailException:
            return render_template("Log-in.html", error="Invalide Email")
        row = ConfirmLogIn(email, username)
        if row and check_password_hash(row[2], password):
            session['id']       = row[0]
            session['username'] = username
            return render_template("HomePage.html", message=f"Welcome {session['username']}")
        else:
            return render_template("Log-in.html", error="Invalid Information")
    return render_template("Log-in.html")


@app.route("/HomePage")
def getHome():
    if 'username' in session:
        return render_template("HomePage.html", message=f"WELCOME {session['username']}")
    return redirect(url_for('home'))


# ════════════════════════════ PATIENTS ════════════════════════════════════════

@app.route("/Patient", methods=["POST", "GET"])
def PatientPage():
    if not is_logged_in():
        return render_template("HomePage.html")
    cursor.execute("SELECT * FROM Patient WHERE user_id = %s", (session['id'],))
    rows = cursor.fetchall()
    return render_template("PatientsFile.html", data=rows)


@app.route("/AddPatient", methods=["POST", "GET"])
def AddPatient():
    if request.method == "POST":
        firstName = request.form['PatientFirstName']
        lastName  = request.form['PatientLastName']
        unique    = request.form['PatientUnique']
        choice    = request.form['KhedmaChoice']
        date      = request.form['date']
        price     = request.form['KhedmaPrice']
        khalsa    = request.form['Khalsa']
        versa     = request.form['versa']
        Versa     = request.form["Versa"]
        ProCheck  = request.form['OtherPro']

        if not firstName.strip() or not lastName.strip():
            return render_template("AddPatient.html", message="Invalide Name")
        if len(unique) != 10 or not unique.isdigit() or int(unique) < 0:
            return render_template("AddPatient.html", message="Invalide Unique number")
        if not choice.strip():
            return render_template("AddPatient.html", message="Invalide Choice")
        if khalsa.lower() not in ["no", "yes"]:
            return render_template("AddPatient.html", message="You must put 'yes' or 'no' in Khalsa")
        if versa.lower() not in ['yes', 'no']:
            return render_template("AddPatient.html", message="In versa insert 'yes' or 'no'")
        if versa.lower() == 'no':
            Versa = 0
        try:
            Versa = float(Versa)
            price = float(price)
            if price < 0:
                return render_template("AddPatient.html", message="Price must be positive")
            if khalsa.lower() == 'yes':
                Versa = price
            if not Versa:
                Versa = 0
            if Versa > price:
                return render_template("AddPatient.html", message="Versa must not be bigger than price")
            b9aw = round(price - Versa, 2) if khalsa.lower() == 'no' else 0
            if b9aw == 0:
                patient_infos = (firstName, lastName, unique, choice, date, 'no', 'yes', Versa, b9aw, session['id'])
            else:
                patient_infos = (firstName, lastName, unique, choice, date, 'no', 'no', Versa, b9aw, session['id'])
        except ValueError:
            return render_template("AddPatient.html", message="Invalide prices")

        if ProCheck.lower() not in ['yes', 'no']:
            return render_template("AddPatient.html", message="You must enter 'yes' or 'no' in the Prothesists check part")
        if ProCheck.lower() == "yes":
            ProName   = request.form['ProName']
            ProNumber = request.form['ProNumber']
            ProPrice  = request.form['ProPrice']
            ProDate   = request.form['ProDate']
            ProKhalsa = request.form['ProKhalsa']
            Proversa  = request.form['Proversa']
            ProVersa  = request.form['ProVersa']
            if not ProName.strip():
                return render_template("AddPatient.html", message="Prothesist Name must not be empty")
            if not ProNumber.isdigit() or int(ProNumber) < 0:
                return render_template("AddPatient.html", message="Prothesist Number must be a positive number")
            if ProKhalsa.lower() not in ['yes', 'no']:
                return render_template("AddPatient.html", message="You must put 'yes' or 'no' in Prothesist Khalsa")
            if Proversa.lower() not in ['yes', 'no']:
                return render_template("AddPatient.html", message="In Prothesist versa insert 'yes' or 'no'")
            if ProDate < date:
                return render_template("AddPatient.html", message="Invalide Prothesist Date")
            if Proversa.lower() == 'no':
                ProVersa = 0
            try:
                ProVersa = float(ProVersa)
                ProPrice = float(ProPrice)
                if ProPrice < 0:
                    return render_template("AddPatient.html", message="Prothesist price must be positive")
                if ProKhalsa.lower() == 'yes':
                    ProVersa = ProPrice
                if not ProVersa:
                    ProVersa = 0
                if ProVersa > ProPrice:
                    return render_template("AddPatient.html", message="Prothesist Versa must not be bigger than his price")
                Prob9aw = round(ProPrice - ProVersa, 2) if ProKhalsa.lower() == 'no' else 0
            except ValueError:
                return render_template("AddPatient.html", message="Invalide Prothesist prices")
            cursor.execute("""
                SELECT id FROM Other_Prothesists WHERE pName = %s AND pNumber = %s AND user_id = %s
            """, (ProName, ProNumber, session['id']))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO Other_Prothesists (pName, pNumber, user_id) VALUES (%s, %s, %s)
                """, (ProName, ProNumber, session['id']))
            cursor.execute("""
                INSERT INTO Other_Prothesists_Khedma
                    (patient_number, dentist_name, pName, pNumber, pDate, pKhedma, pPrice, pVersa, pB9aw, pKhalsa, pFinished, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (unique, None, ProName, ProNumber, ProDate, choice, ProPrice, ProVersa, Prob9aw, ProKhalsa, 'no', session['id']))
            connection.commit()
            ProthesistsStat(ProPrice, ProNumber, ProName, ProKhalsa, ProDate, ProVersa)

        exist = checkExistPatient(firstName, unique, choice)
        if not exist:
            cursor.execute("""
                INSERT IGNORE INTO Patient(
                    patient_firstname, patient_lastname, patient_number,
                    T_ype, la_date, finished, khalsa, versa, b9aw, user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, patient_infos)
            connection.commit()
            cursor.execute("""
                INSERT INTO Khedma(khedman, khedma_price, khedma_date, khedma_dentist,
                                   khedma_patient, khedma_wajda, khedma_khalsa, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (choice, price, date, 'NO', unique, 'no', khalsa, session['id']))
            connection.commit()
            Patient_History(unique)
            PatientStats(price, khalsa, date, Versa)
            return render_template("PatientsFile.html", message="Patient Added Successfully")
        else:
            return render_template("PatientsFile.html", message="Patient already exists")
    return render_template("AddPatient.html")


@app.route("/DeletePatient", methods=["POST", "GET"])
def DeletePatient():
    if request.method == "POST":
        PatientF_deleted = request.form["DeleteF"]
        Confirm_PatientF = request.form["ConfirmDeletePatientF"]
        PatientL_deleted = request.form["DeleteL"]
        Confirm_PatientL = request.form["ConfirmDeletePatientL"]
        Patient_unique   = request.form["uniquepatient"]
        Confirm_Unique   = request.form["confirmunique"]
        if not Patient_unique.isdigit() or len(Patient_unique) != 10:
            return render_template("DeletePatient.html", message="Invalid Unique number")
        if (PatientF_deleted != Confirm_PatientF or
                PatientL_deleted != Confirm_PatientL or
                Patient_unique != Confirm_Unique):
            return render_template("DeletePatient.html", message="Invalid Confirmation")
        cursor.execute("DELETE FROM Khedma WHERE user_id = %s AND khedma_patient = %s",
                       (session['id'], Patient_unique))
        cursor.execute("""
            DELETE FROM Patient
            WHERE patient_firstname = %s AND patient_lastname = %s
              AND patient_number = %s AND user_id = %s
        """, (PatientF_deleted, PatientL_deleted, Patient_unique, session['id']))
        connection.commit()
        return render_template("PatientsFile.html", message="Patient Deleted Successfully")
    return render_template("DeletePatient.html")


@app.route("/PatientStat")
def PatietStat():
    cursor.execute("""
        SELECT * FROM Patient_Stat WHERE user_id = %s ORDER BY year DESC, month DESC
    """, (session['id'],))
    row = cursor.fetchall()
    return render_template("PatientsFile.html", stat=row)


# ── Patient Statistics PDF ───────────────────────────────────────────────────
@app.route("/PatientStatPDF")
def PatientStatPDF():
    if not is_logged_in():
        return redirect('/log_in')
    cursor.execute("""
        SELECT * FROM Patient_Stat WHERE user_id = %s ORDER BY year DESC, month DESC
    """, (session['id'],))
    rows = cursor.fetchall()

    def build(story, styles, h2):
        story.append(Paragraph("Monthly Breakdown", h2))
        headers = ['ID', 'Patients', 'Khalsin (Paid)', 'Machi Khalsin (Owed)', 'Month', 'Year', 'User ID']
        col_w   = [1.2*cm, 2*cm, 3.5*cm, 4*cm, 2*cm, 2*cm, 2*cm]
        data    = [headers] + ([str(c) if c is not None else '-' for c in r] for r in rows) \
                  if rows else [headers, ['No data'] + ['-']*6]
        # rebuild properly (generator won't work in list concat)
        data = [headers]
        if rows:
            for r in rows:
                data.append([str(c) if c is not None else '-' for c in r])
        else:
            data.append(['No data available', '-', '-', '-', '-', '-', '-'])
        t = Table(data, colWidths=col_w, repeatRows=1)
        t.setStyle(_base_table_style())
        story.append(t)

        if rows:
            story.append(Spacer(1, 0.5*cm))
            story.append(Paragraph("Totals", h2))
            total_p    = sum(r[1] or 0 for r in rows)
            total_paid = sum(float(r[2] or 0) for r in rows)
            total_owed = sum(float(r[3] or 0) for r in rows)
            s = Table(
                [['Total Patients', 'Total Paid', 'Total Owed'],
                 [str(total_p), f"{total_paid:.2f}", f"{total_owed:.2f}"]],
                colWidths=[5*cm, 5*cm, 5*cm]
            )
            s.setStyle(_base_table_style())
            story.append(s)

    return _make_pdf("Patient Statistics Report", build)


@app.route("/PatientHistory", methods=["POST", "GET"])
def getHistory():
    if request.method == "POST":
        patientName = request.form["SearchName"]
        cursor.execute("""
            SELECT * FROM Patient_history WHERE user_id = %s AND firstname = %s
        """, (session['id'], patientName))
        result = cursor.fetchall()
        if result:
            return render_template("PatientHistory.html", HistoryPatient=result)
        else:
            return render_template("PatientHistory.html", message="Patient Not Found")
    return render_template("PatientHistory.html")


@app.route("/AllPatientsHistory")
def getAllHistory():
    cursor.execute("SELECT * FROM Patient_history WHERE user_id = %s", (session['id'],))
    resultAll = cursor.fetchall()
    if resultAll:
        return render_template("PatientHistory.html", History=resultAll)
    else:
        return render_template("PatientHistory.html", message="Table not found")


@app.route("/PatientByDateASC")
def ShowByDateASC():
    cursor.execute("SELECT * FROM Patient WHERE user_id = %s ORDER BY la_date ASC", (session['id'],))
    return render_template("PatientsFile.html", dataASC=cursor.fetchall())


@app.route("/PatientByDateDESC")
def ShowByDateDESC():
    cursor.execute("SELECT * FROM Patient WHERE user_id = %s ORDER BY la_date DESC", (session['id'],))
    return render_template("PatientsFile.html", dataDESC=cursor.fetchall())


@app.route("/PatientByB9aw")
def ShowByB9aw():
    cursor.execute("SELECT * FROM Patient WHERE user_id = %s ORDER BY b9aw DESC", (session['id'],))
    return render_template("PatientsFile.html", dataPrice=cursor.fetchall())


# ════════════════════════════ DENTISTS ════════════════════════════════════════

@app.route("/Dentist", methods=["POST", "GET"])
def DentistPage():
    if not is_logged_in():
        return redirect("/log_in")
    if request.method == "POST":
        DentistName = request.form["SearchBar"]
        if SearcheTable(DentistName):
            cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                           (session["id"], DentistName))
            return render_template("DentistFile.html", result=cursor.fetchall())
        else:
            return render_template("DentistFile.html", error=f"Dentist {DentistName} Not Found")
    return render_template("DentistFile.html")


@app.route("/AddDentist", methods=["POST", "GET"])
def AddDentist():
    if request.method == "POST":
        dentist_name = request.form["AddDentists"]
        if not SearcheTable(dentist_name):
            AddDentistTable(dentist_name)
            return render_template("AddDentist.html", message=f"Dentist {dentist_name} Added Successfully")
        else:
            return render_template("AddDentist.html", message="Dentist Already exists")
    return render_template("AddDentist.html")


@app.route("/DeleteDentist", methods=["POST", "GET"])
def DeleteDentist():
    if request.method == "POST":
        Dentist_deleted = request.form["DeleteDentist"]
        Confirm_Dentist = request.form["ConfirmDeleteDentist"]
        if SearcheTable(Dentist_deleted):
            if Dentist_deleted != Confirm_Dentist:
                return render_template("DeleteDentist.html", message="Invalide Confirmation")
            cursor.execute("DELETE FROM dentists WHERE user_id = %s AND dentist_name = %s",
                           (session['id'], Dentist_deleted))
            connection.commit()
            cursor.execute("DELETE FROM Dentist_registry WHERE user_id = %s AND dentist_name = %s",
                           (session['id'], Dentist_deleted))
            connection.commit()
            cursor.execute("DELETE FROM Khedma WHERE user_id = %s AND khedma_dentist = %s",
                           (session['id'], f"Dr.{Dentist_deleted}"))
            connection.commit()
            return render_template("DeleteDentist.html", message="Dentist Deleted Successfully")
        else:
            return render_template("DeleteDentist.html", message="Dentist doesn't exist")
    return render_template("DeleteDentist.html")


@app.route("/GetFromDentist", methods=["POST", "GET"])
def Get_From_Dentist():
    if request.method == "POST":
        dentist   = request.form['Dentistinput']
        firstName = request.form['PatientFirstName']
        lastName  = request.form['PatientLastName']
        unique    = request.form['PatientUnique']
        choice    = request.form['KhedmaChoice']
        date      = request.form['date']
        price     = request.form['KhedmaPrice']
        khalsa    = request.form['Khalsa']
        ProCheck  = request.form['ProCheck']

        if not SearcheTable(dentist):
            return render_template("GetFromDentist.html", message="Dentist doesn't exist")
        if not firstName.strip() or not lastName.strip():
            return render_template("GetFromDentist.html", message="Invalide Name")
        if not unique.isdigit() or len(unique) < 4 or int(unique) < 0:
            return render_template("GetFromDentist.html", message="Invalide Unique number")
        if not choice.strip():
            return render_template("GetFromDentist.html", message="Invalide Choice")
        if khalsa.lower() not in ["no", "yes"]:
            return render_template("GetFromDentist.html", message="You must put 'yes' or 'no' in Khalsa")
        try:
            price = float(price)
            if price < 0:
                raise ValueError
        except ValueError:
            return render_template("GetFromDentist.html", message="Invalide Price Value")

        exist = checkExistDentistPatient(dentist, unique, firstName)
        if not exist:
            if khalsa.lower() == 'yes':
                infos = (dentist, session['id'], firstName, lastName, unique, choice, price, 'no', 'yes', date)
            else:
                infos = (dentist, session['id'], firstName, lastName, unique, choice, price, 'no', 'no', date)

            if ProCheck.lower() not in ['yes', 'no']:
                return render_template("GetFromDentist.html",
                                       message="You must enter 'yes' or 'no' in the Prothesists check part")
            if ProCheck.lower() == "yes":
                ProName   = request.form['ProName']
                ProNumber = request.form['ProNumber']
                ProPrice  = request.form['ProPrice']
                ProDate   = request.form['ProDate']
                ProKhalsa = request.form['ProKhalsa']
                Proversa  = request.form['Proversa']
                ProVersa  = request.form['ProVersa']
                if not ProName.strip():
                    return render_template("GetFromDentist.html", message="Prothesist Name must not be empty")
                if not ProNumber.isdigit() or int(ProNumber) < 0:
                    return render_template("GetFromDentist.html", message="Prothesist Number must be a positive number")
                if ProKhalsa.lower() not in ['yes', 'no']:
                    return render_template("GetFromDentist.html", message="You must put 'yes' or 'no' in Prothesist Khalsa")
                if Proversa.lower() not in ['yes', 'no']:
                    return render_template("GetFromDentist.html", message="In Prothesist versa insert 'yes' or 'no'")
                if ProDate < date:
                    return render_template("GetFromDentist.html", message="Invalide Prothesist Date")
                if Proversa.lower() == 'no':
                    ProVersa = 0
                try:
                    ProVersa = float(ProVersa)
                    ProPrice = float(ProPrice)
                    if ProPrice < 0:
                        return render_template("GetFromDentist.html", message="Prothesist price must be positive")
                    if ProKhalsa.lower() == 'yes':
                        ProVersa = ProPrice
                    if not ProVersa:
                        ProVersa = 0
                    if ProVersa > ProPrice:
                        return render_template("GetFromDentist.html", message="Prothesist Versa must not be bigger than his price")
                    Prob9aw = round(ProPrice - ProVersa, 2) if ProKhalsa.lower() == 'no' else 0
                except ValueError:
                    return render_template("GetFromDentist.html", message="Invalide Prothesist prices")
                cursor.execute("""
                    SELECT id FROM Other_Prothesists WHERE pName = %s AND pNumber = %s AND user_id = %s
                """, (ProName, ProNumber, session['id']))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO Other_Prothesists (pName, pNumber, user_id) VALUES (%s, %s, %s)
                    """, (ProName, ProNumber, session['id']))
                cursor.execute("""
                    INSERT INTO Other_Prothesists_Khedma
                        (patient_number, dentist_name, pName, pNumber, pDate, pKhedma, pPrice, pVersa, pB9aw, pKhalsa, pFinished, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (unique, dentist, ProName, ProNumber, ProDate, choice, ProPrice, ProVersa, Prob9aw, ProKhalsa, 'no', session['id']))
                connection.commit()
                ProthesistsStat(ProPrice, ProNumber, ProName, ProKhalsa, ProDate, ProVersa)

            cursor.execute("""
                INSERT INTO dentists
                    (dentist_name, user_id, patient_firstname, patient_lastname,
                     patient_number, Dkhedma, price, finished, khalsa, date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, infos)
            connection.commit()
            cursor.execute("""
                INSERT INTO Khedma
                    (khedman, khedma_price, khedma_date, khedma_dentist,
                     khedma_patient, khedma_wajda, khedma_khalsa, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (choice, price, date, f"Dr.{dentist}", unique, 'no', khalsa, session['id']))
            connection.commit()
            Dentist_History(dentist)
            DentistStats(dentist, price, khalsa, date)
            return render_template("DentistFile.html", message="Khedma Added Successfully")
        else:
            return render_template("DentistFile.html", message="Patient already exists")
    return render_template("GetFromDentist.html")


@app.route("/DentistHistory", methods=["POST", "GET"])
def getDentistHistory():
    if request.method == "POST":
        dentist_name = request.form["SearchName"]
        cursor.execute("""
            SELECT * FROM Dentist_history WHERE user_id = %s AND dentistname = %s
        """, (session['id'], dentist_name))
        result = cursor.fetchall()
        if result:
            return render_template("DentistHistory.html", HistoryDentist=result)
        else:
            return render_template("DentistHistory.html", message="Dentist not found")
    return render_template("DentistHistory.html")


@app.route("/AllDentistHistory")
def getAllDentistHistory():
    cursor.execute("SELECT * FROM Dentist_history WHERE user_id = %s", (session['id'],))
    result = cursor.fetchall()
    if result:
        return render_template("DentistHistory.html", History=result)
    else:
        return render_template("DentistHistory.html", message="Table not found")


@app.route("/DentistMostKhedma", methods=["GET"])
def FindMostDentistKhedma():
    dentist_dics = DentistsDics()
    if not dentist_dics:
        return render_template("DentistFile.html", error="No dentist tables found.")
    name, count = max(dentist_dics.items(), key=lambda x: x[1], default=('none', 0))
    if count == 0:
        return render_template("DentistFile.html", message="All tables are empty.")
    cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                   (session['id'], name))
    return render_template("DentistFile.html", most=cursor.fetchall(), most_name=name)


@app.route("/DentistLessKhedma", methods=["GET"])
def FindLessDentistKhedma():
    dentist_dics    = DentistsDics()
    active_dentists = {n: c for n, c in dentist_dics.items() if c > 0}
    if not active_dentists:
        return render_template("DentistFile.html", message="All dentists currently have 0 khedma.")
    name, count = min(active_dentists.items(), key=lambda x: x[1])
    cursor.execute("SELECT * FROM dentists WHERE user_id = %s AND dentist_name = %s",
                   (session['id'], name))
    return render_template("DentistFile.html", less=cursor.fetchall(), less_name=name)


@app.route("/DentistTotal", methods=["GET"])
def ShowTotal():
    current_dentists = GetAllDentistTables()
    result = {}
    for dentist_name in current_dentists:
        try:
            cursor.execute("""
                SELECT SUM(price) FROM dentists
                WHERE user_id = %s AND khalsa = %s AND dentist_name = %s
            """, (session['id'], "no", dentist_name))
            row = cursor.fetchone()
            cursor.fetchall()
            result[dentist_name] = row[0] if row and row[0] is not None else 0
        except Exception as e:
            result[dentist_name] = 0
    if result:
        return render_template("DentistFile.html", total=result)
    return render_template("DentistFile.html", message="No dentist data found.")


@app.route("/DentistsStat")
def DentistsStat():
    dentists_list = GetAllDentistTables()
    result = {}
    for dentist in dentists_list:
        cursor.execute("""
            SELECT * FROM Dentist_Stat WHERE user_id = %s AND dentist_name = %s
            ORDER BY year DESC, month DESC
        """, (session['id'], dentist))
        result[dentist] = cursor.fetchall()
    if result:
        return render_template("DentistFile.html", message="The Stat Table", result=result)
    return render_template("DentistFile.html", message="Table Not Found (There is no Dentists)")


# ── Dentist Statistics PDF ───────────────────────────────────────────────────
@app.route("/DentistStatPDF")
def DentistStatPDF():
    if not is_logged_in():
        return redirect('/log_in')
    dentists_list = GetAllDentistTables()
    all_data = {}
    for dentist in dentists_list:
        cursor.execute("""
            SELECT * FROM Dentist_Stat WHERE user_id = %s AND dentist_name = %s
            ORDER BY year DESC, month DESC
        """, (session['id'], dentist))
        all_data[dentist] = cursor.fetchall()

    def build(story, styles, h2):
        if not all_data:
            story.append(Paragraph("No dentist data found.", styles['Normal']))
            return
        headers = ['ID', 'Dentist', 'Total Khedma', 'Khalsin (Paid)', 'Machi Khalsin (Owed)', 'Month', 'Year', 'User ID']
        col_w   = [1*cm, 3*cm, 2.5*cm, 3*cm, 3.5*cm, 1.8*cm, 1.8*cm, 1.8*cm]
        for dentist, rows in all_data.items():
            story.append(Paragraph(f"Dentist: {dentist}", h2))
            story.append(Spacer(1, 0.2*cm))
            data = [headers]
            if rows:
                for r in rows:
                    data.append([str(c) if c is not None else '-' for c in r])
            else:
                data.append(['-', dentist, '0', '0', '0', '-', '-', '-'])
            t = Table(data, colWidths=col_w, repeatRows=1)
            t.setStyle(_base_table_style())
            story.append(t)
            story.append(Spacer(1, 0.4*cm))

        story.append(Paragraph("Grand Summary — All Dentists", h2))
        s_data = [['Dentist', 'Total Khedma', 'Total Paid', 'Total Owed']]
        for dentist, rows in all_data.items():
            s_data.append([dentist,
                           str(sum(r[2] or 0 for r in rows)),
                           f"{sum(float(r[3] or 0) for r in rows):.2f}",
                           f"{sum(float(r[4] or 0) for r in rows):.2f}"])
        s = Table(s_data, colWidths=[4.5*cm, 3.5*cm, 3.5*cm, 3.5*cm])
        s.setStyle(_base_table_style())
        story.append(s)

    return _make_pdf("Dentist Statistics Report", build)


# ════════════════════════════ KHEDMA ══════════════════════════════════════════

@app.route("/Khedma", methods=["POST", "GET"])
def KhedmaPage():
    if not is_logged_in():
        return render_template("HomePage.html")
    cursor.execute("SELECT * FROM Khedma WHERE user_id = %s", (session['id'],))
    return render_template("KhedmaFile.html", result=cursor.fetchall())


@app.route("/Finished", methods=["POST", "GET"])
def khedmaMkemla():
    if request.method == "POST":
        choice = request.form['Choice']
        if choice.lower() == "patient":
            patientId = request.form['PatientID']
            cursor.execute("SELECT patient_number FROM Patient WHERE patient_number = %s AND user_id = %s",
                           (patientId, session['id']))
            if not cursor.fetchone():
                return render_template("FinishedKhedma.html", message="Patient Not Found")
            cursor.fetchall()
            cursor.execute("UPDATE Patient SET finished = %s WHERE patient_number = %s AND user_id = %s",
                           ('yes', patientId, session['id']))
            cursor.execute("DELETE FROM khedma WHERE khedma_patient = %s AND user_id = %s",
                           (patientId, session['id']))
            cursor.execute("DELETE FROM Patient WHERE finished = %s AND khalsa = %s AND user_id = %s",
                           ('yes', 'yes', session['id']))
        elif choice.lower() == "dentist":
            dentistName = request.form['Dentist']
            patientId   = request.form['DPatientID']
            if not SearcheTable(dentistName):
                return render_template("FinishedKhedma.html", message="Incorrect dentist name")
            cursor.execute("""
                SELECT patient_number FROM dentists
                WHERE patient_number = %s AND user_id = %s AND dentist_name = %s
            """, (patientId, session['id'], dentistName))
            if not cursor.fetchone():
                return render_template("FinishedKhedma.html", message="Patient Not Found")
            cursor.fetchall()
            cursor.execute("""
                UPDATE dentists SET finished = %s
                WHERE patient_number = %s AND user_id = %s AND dentist_name = %s
            """, ('yes', patientId, session['id'], dentistName))
            cursor.execute("DELETE FROM khedma WHERE khedma_patient = %s AND user_id = %s",
                           (patientId, session['id']))
            cursor.execute("""
                DELETE FROM dentists
                WHERE finished = %s AND khalsa = %s AND user_id = %s AND dentist_name = %s
            """, ('yes', 'yes', session['id'], dentistName))
        else:
            return render_template("FinishedKhedma.html", message="You have to enter 'patient' or 'dentist'")
        connection.commit()
        return render_template("FinishedKhedma.html", message="Information Updated Successfully")
    return render_template("FinishedKhedma.html")


@app.route("/Khalsa", methods=["POST", "GET"])
def KhedmaKhalsa():
    if request.method == "POST":
        choice = request.form['Choice']
        if choice.lower() == "patient":
            patientId = request.form['PatientID']
            cursor.execute("SELECT * FROM patient WHERE patient_number = %s AND user_id = %s",
                           (patientId, session['id']))
            result = cursor.fetchone()
            cursor.fetchall()
            if not result:
                return render_template("KhedmaKhalsa.html", message="Patient Not Found")
            patient_price = result[10]
            patient_date  = result[6]
            old_khalsa    = result[8]
            cursor.execute("UPDATE Patient SET khalsa = %s, b9aw = %s WHERE patient_number = %s AND user_id = %s",
                           ('yes', 0, patientId, session['id']))
            cursor.execute("UPDATE Khedma SET khedma_khalsa = %s WHERE khedma_patient = %s AND user_id = %s",
                           ('yes', patientId, session['id']))
            connection.commit()
            cursor.execute("DELETE FROM Patient WHERE user_id = %s AND finished = %s AND khalsa = %s",
                           (session['id'], 'yes', 'yes'))
            cursor.execute("DELETE FROM Khedma WHERE khedma_khalsa = %s AND khedma_wajda = %s AND user_id = %s",
                           ('yes', 'yes', session['id']))
            if old_khalsa.lower() == 'no':
                UpdateKhalsaStat(table="patient", price=patient_price, date=patient_date)
        elif choice.lower() == "dentist":
            name      = request.form['Dentist']
            patientId = request.form['DPatientID']
            if not SearcheTable(name):
                return render_template("KhedmaKhalsa.html", message="Incorrect dentist name")
            cursor.execute("SELECT * FROM dentists WHERE patient_number = %s AND user_id = %s AND dentist_name = %s",
                           (patientId, session['id'], name))
            result = cursor.fetchone()
            cursor.fetchall()
            if not result:
                return render_template("KhedmaKhalsa.html", message="Patient Not Found")
            dentist_price = result[7]
            dentist_date  = result[10]
            old_khalsa    = result[9]
            cursor.execute("UPDATE dentists SET khalsa = %s WHERE patient_number = %s AND user_id = %s AND dentist_name = %s",
                           ('yes', patientId, session['id'], name))
            connection.commit()
            cursor.execute("DELETE FROM dentists WHERE finished = %s AND khalsa = %s AND user_id = %s AND dentist_name = %s",
                           ('yes', 'yes', session['id'], name))
            cursor.execute("UPDATE Khedma SET khedma_khalsa = %s WHERE user_id = %s AND khedma_dentist = %s AND khedma_patient = %s",
                           ('yes', session['id'], f"Dr.{name}", patientId))
            connection.commit()
            cursor.execute("DELETE FROM Khedma WHERE user_id = %s AND khedma_dentist = %s AND khedma_wajda = %s AND khedma_khalsa = %s",
                           (session['id'], f"Dr.{name}", 'yes', 'yes'))
            if old_khalsa.lower() == 'no':
                UpdateKhalsaStat(table="dentist", dentistName=name, price=dentist_price, date=dentist_date)
        else:
            return render_template("KhedmaKhalsa.html", message="You have to enter (patient / dentist)")
        connection.commit()
        return render_template("KhedmaKhalsa.html", message="Payment Updated Successfully")
    return render_template("KhedmaKhalsa.html")


@app.route("/Allkhedma", methods=["POST", "GET"])
def allkhedma():
    cursor.execute("SELECT * FROM Khedma WHERE user_id = %s", (session['id'],))
    return render_template("ALLKhedma.html", result=cursor.fetchall())


@app.route("/KhedmaByDateASC")
def ShowKhedmaByDateASC():
    cursor.execute("SELECT * FROM khedma WHERE user_id = %s ORDER BY khedma_date ASC", (session['id'],))
    return render_template("ALLKhedma.html", asc=cursor.fetchall())


@app.route("/KhedmaByDateDESC")
def ShowKhedmaByDateDESC():
    cursor.execute("SELECT * FROM khedma WHERE user_id = %s ORDER BY khedma_date DESC", (session['id'],))
    return render_template("ALLKhedma.html", desc=cursor.fetchall())


# ════════════════════════════ SEL3A ═══════════════════════════════════════════

@app.route("/Sel3a", methods=["POST", "GET"])
def Sel3aPage():
    if not is_logged_in():
        return render_template("HomePage.html")
    cursor.execute("SELECT * FROM Sel3a WHERE user_id = %s", (session['id'],))
    rows = cursor.fetchall()
    if rows:
        return render_template("Sel3a.html", message="Main Sel3a Table", table=rows)
    return render_template("Sel3a.html", error="Table Not Found")


@app.route("/AddSel3a", methods=["POST", "GET"])
def addsel3a():
    if request.method == "POST":
        name  = request.form["SName"]
        price = float(request.form["SPrice"])
        date  = request.form["SDate"]
        if price < 0 or not name.strip():
            return render_template("AddSel3a.html", message="Invalide Informations")
        cursor.execute("INSERT INTO sel3a (user_id, sel3a_name, sel3a_price, buy_date) VALUES (%s, %s, %s, %s)",
                       (session['id'], name, price, date))
        connection.commit()
        return render_template("Sel3a.html", message="Sel3a added Successfully")
    return render_template("AddSel3a.html")


@app.route("/Sel3aStat")
def Sel3aStat():
    cursor.execute("""
        SELECT SUM(sel3a_price), MONTH(buy_date), YEAR(buy_date)
        FROM sel3a WHERE user_id = %s GROUP BY MONTH(buy_date), YEAR(buy_date)
    """, (session['id'],))
    rows = cursor.fetchall()
    if rows:
        return render_template("Sel3a.html", message="The Stat Table", stat_table=rows)
    return render_template("Sel3a.html", error="Table not found")


@app.route("/ShowByPrice")
def ShowSel3aByPrice():
    cursor.execute("SELECT * FROM sel3a WHERE user_id = %s ORDER BY sel3a_price ASC", (session['id'],))
    return render_template("Sel3a.html", message="Price Order", Pricetable=cursor.fetchall())


@app.route("/ShowByDateASC")
def ShowSel3aByDate():
    cursor.execute("SELECT * FROM sel3a WHERE user_id = %s ORDER BY buy_date ASC", (session['id'],))
    return render_template("Sel3a.html", message="Date Order", Datetable=cursor.fetchall())


# ════════════════════════════ CREATE ACCOUNT ══════════════════════════════════

@app.route("/CreateAnAccount", methods=["POST", "GET"])
def Create():
    if request.method == "POST":
        email       = request.form['email']
        phone       = request.form['phone']
        username    = request.form['username']
        password    = request.form['password']
        confirmpass = request.form['confirmation']
        if password != confirmpass:
            return render_template("CreateAccount.html", error="Invalide Confirmation")
        try:
            CheckData(email, username, password)
        except InvalideNameException:
            return render_template("Log-in.html", error="Invalide Name")
        except InvalidePasswordException:
            return render_template("Log-in.html", error="Invalide Password")
        except InvalideEmailException:
            return render_template("Log-in.html", error="Invalide Email")
        if not phone.strip() or len(phone) != 10 or not phone.isdigit():
            return render_template("CreateAccount.html", error="Invalide Phone Number")
        password = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO Users (user_name, user_password, user_email, user_phoneNumber)
            VALUES (%s, %s, %s, %s)
        """, (username, password, email, phone))
        connection.commit()
        return render_template("Log-in.html", message=f"Account Created Welcome {username}")
    return render_template("CreateAccount.html")


# ════════════════════════════ PROTHESISTS ═════════════════════════════════════

@app.route("/ProKhedma", methods=["POST", "GET"])
def ProKhedmaPage():
    if not is_logged_in():
        return render_template("HomePage.html")
    cursor.execute("SELECT * FROM Other_Prothesists_Khedma WHERE user_id = %s", (session['id'],))
    return render_template("KhedmaProFile.html", result=cursor.fetchall())


@app.route("/ProFinished", methods=["POST", "GET"])
def khedmaProMkemla():
    if request.method == "POST":
        choice = request.form['Choice']
        if choice.lower() == "patient":
            patientId = request.form['PatientID']
            cursor.execute("SELECT patient_number FROM Patient WHERE patient_number = %s AND user_id = %s",
                           (patientId, session['id']))
            if not cursor.fetchone():
                return render_template("FinishedProKhedma.html", message="Patient Not Found")
            cursor.fetchall()
            cursor.execute("UPDATE Patient SET finished = %s WHERE patient_number = %s AND user_id = %s",
                           ('yes', patientId, session['id']))
            cursor.execute("DELETE FROM khedma WHERE khedma_patient = %s AND user_id = %s",
                           (patientId, session['id']))
            cursor.execute("DELETE FROM Patient WHERE finished = %s AND khalsa = %s AND user_id = %s",
                           ('yes', 'yes', session['id']))
            cursor.execute("UPDATE Other_Prothesists_Khedma SET pFinished = %s WHERE user_id = %s AND patient_number = %s",
                           ('yes', session['id'], patientId))
        elif choice.lower() == "dentist":
            dentistName = request.form['Dentist']
            patientId   = request.form['DPatientID']
            if not SearcheTable(dentistName):
                return render_template("FinishedProKhedma.html", message="Incorrect dentist name")
            cursor.execute("""
                SELECT patient_number FROM dentists
                WHERE patient_number = %s AND user_id = %s AND dentist_name = %s
            """, (patientId, session['id'], dentistName))
            if not cursor.fetchone():
                return render_template("FinishedProKhedma.html", message="Patient Not Found")
            cursor.fetchall()
            cursor.execute("UPDATE dentists SET finished = %s WHERE patient_number = %s AND user_id = %s AND dentist_name = %s",
                           ('yes', patientId, session['id'], dentistName))
            cursor.execute("DELETE FROM khedma WHERE khedma_patient = %s AND user_id = %s",
                           (patientId, session['id']))
            cursor.execute("DELETE FROM dentists WHERE finished = %s AND khalsa = %s AND user_id = %s AND dentist_name = %s",
                           ('yes', 'yes', session['id'], dentistName))
            cursor.execute("UPDATE Other_Prothesists_Khedma SET pFinished = %s WHERE user_id = %s AND dentist_name = %s AND patient_number = %s",
                           ('yes', session['id'], dentistName, patientId))
        else:
            return render_template("FinishedProKhedma.html", message="You have to enter 'patient' or 'dentist'")
        connection.commit()
        return render_template("FinishedProKhedma.html", message="Information Updated Successfully")
    return render_template("FinishedProKhedma.html")


@app.route("/ProKhalsa", methods=["POST", "GET"])
def KhedmaProKhalsa():
    if request.method == "POST":
        Prochoice = request.form['ProthesistChoice']
        choice    = request.form['Choice']
        cursor.execute("SELECT id FROM Other_Prothesists WHERE user_id = %s AND pName = %s",
                       (session['id'], Prochoice))
        row = cursor.fetchone()
        cursor.fetchall()
        if not row:
            return render_template("KhedmaProKhalsa.html", message=f"Prothesist {Prochoice} not found")

        if choice.lower() == "patient":
            patientId = request.form['PatientID']
            cursor.execute("SELECT * FROM Other_Prothesists_Khedma WHERE pName = %s AND user_id = %s AND patient_number = %s",
                           (Prochoice, session['id'], patientId))
            result = cursor.fetchone()
            cursor.fetchall()
            if not result:
                return render_template("KhedmaProKhalsa.html", message="Patient Not Found")
            prothesist_price = result[9]
            prothesist_date  = result[5]
            old_khalsa       = result[10]
            cursor.execute("UPDATE Other_Prothesists_Khedma SET pKhalsa = %s, pB9aw = %s WHERE user_id = %s AND patient_number = %s AND pName = %s",
                           ('yes', 0, session['id'], patientId, Prochoice))
            cursor.execute("UPDATE Khedma SET khedma_khalsa = %s WHERE khedma_patient = %s AND user_id = %s",
                           ('yes', patientId, session['id']))
            connection.commit()
            cursor.execute("DELETE FROM Patient WHERE user_id = %s AND finished = %s AND khalsa = %s",
                           (session['id'], 'yes', 'yes'))
            cursor.execute("DELETE FROM Khedma WHERE khedma_khalsa = %s AND khedma_wajda = %s AND user_id = %s",
                           ('yes', 'yes', session['id']))
            if old_khalsa.lower() == 'no':
                UpdateProKhalsaStat(ProName=Prochoice, price=prothesist_price, date=prothesist_date)

        elif choice.lower() == "dentist":
            name      = request.form['Dentist']
            patientId = request.form['DPatientID']
            if not SearcheTable(name):
                return render_template("KhedmaProKhalsa.html", message="Incorrect dentist name")
            cursor.execute("SELECT * FROM Other_Prothesists_Khedma WHERE pName = %s AND user_id = %s AND patient_number = %s AND dentist_name = %s",
                           (Prochoice, session['id'], patientId, name))
            result = cursor.fetchone()
            cursor.fetchall()
            if not result:
                return render_template("KhedmaProKhalsa.html", message="Patient Not Found")
            prothesist_price = result[9]
            prothesist_date  = result[5]
            old_khalsa       = result[10]
            cursor.execute("UPDATE Other_Prothesists_Khedma SET pKhalsa = %s, pB9aw = %s WHERE user_id = %s AND patient_number = %s AND dentist_name = %s AND pName = %s",
                           ('yes', 0, session['id'], patientId, name, Prochoice))
            cursor.execute("UPDATE dentists SET khalsa = %s WHERE patient_number = %s AND user_id = %s AND dentist_name = %s",
                           ('yes', patientId, session['id'], name))
            connection.commit()
            cursor.execute("DELETE FROM dentists WHERE finished = %s AND khalsa = %s AND user_id = %s AND dentist_name = %s",
                           ('yes', 'yes', session['id'], name))
            cursor.execute("UPDATE Khedma SET khedma_khalsa = %s WHERE user_id = %s AND khedma_dentist = %s AND khedma_patient = %s",
                           ('yes', session['id'], f"Dr.{name}", patientId))
            connection.commit()
            cursor.execute("DELETE FROM Khedma WHERE user_id = %s AND khedma_dentist = %s AND khedma_wajda = %s AND khedma_khalsa = %s",
                           (session['id'], f"Dr.{name}", 'yes', 'yes'))
            if old_khalsa.lower() == 'no':
                UpdateProKhalsaStat(ProName=Prochoice, price=prothesist_price, date=prothesist_date)
        else:
            return render_template("KhedmaProKhalsa.html", message="You have to enter (patient / dentist)")
        connection.commit()
        return render_template("KhedmaProKhalsa.html", message="Payment Updated Successfully")
    return render_template("KhedmaProKhalsa.html")


@app.route("/ProAllkhedma")
def Proallkhedma():
    if not is_logged_in():
        return redirect("/log_in")
    cursor.execute("SELECT * FROM Other_Prothesists_Khedma WHERE user_id = %s", (session['id'],))
    return render_template("ALLProKhedma.html", result=cursor.fetchall())


@app.route("/ProKhedmaByDateASC")
def ProKhedmaByDateASC():
    if not is_logged_in():
        return redirect("/log_in")
    cursor.execute("SELECT * FROM Other_Prothesists_Khedma WHERE user_id = %s ORDER BY pDate ASC", (session['id'],))
    return render_template("ALLProKhedma.html", asc=cursor.fetchall())


@app.route("/ProKhedmaByDateDESC")
def ProKhedmaByDateDESC():
    if not is_logged_in():
        return redirect("/log_in")
    cursor.execute("SELECT * FROM Other_Prothesists_Khedma WHERE user_id = %s ORDER BY pDate DESC", (session['id'],))
    return render_template("ALLProKhedma.html", desc=cursor.fetchall())


@app.route("/ProMostKhedma", methods=["GET"])
def FindMostProKhedma():
    Pro_dics = ProthesistDics()
    if not Pro_dics:
        return render_template("ProStats.html", error="No Prothesist tables found.")
    name, count = max(Pro_dics.items(), key=lambda x: x[1], default=('none', 0))
    if count == 0:
        return render_template("ProStats.html", message="All tables are empty.")
    cursor.execute("SELECT * FROM Other_Prothesists_Khedma WHERE user_id = %s AND pName = %s",
                   (session['id'], name))
    return render_template("ProStats.html", most=cursor.fetchall(), most_name=name)


@app.route("/ProLessKhedma", methods=["GET"])
def FindLessProKhedma():
    Pro_dics    = ProthesistDics()
    active_Pros = {n: c for n, c in Pro_dics.items() if c > 0}
    if not active_Pros:
        return render_template("ProStats.html", message="All prothesists currently have 0 khedma.")
    name, count = min(active_Pros.items(), key=lambda x: x[1])
    cursor.execute("SELECT * FROM Other_Prothesists_Khedma WHERE user_id = %s AND pName = %s",
                   (session['id'], name))
    return render_template("ProStats.html", less=cursor.fetchall(), less_name=name)


@app.route("/ProTotal", methods=["GET"])
def ShowProTotal():
    current_Pros = GetAllProthesists()
    result = {}
    for Pro_name in current_Pros:
        try:
            cursor.execute("""
                SELECT pName, pNumber, COALESCE(SUM(pVersa), 0), COALESCE(SUM(pB9aw), 0)
                FROM Other_Prothesists_Khedma WHERE user_id = %s AND pName = %s
            """, (session['id'], Pro_name))
            row = cursor.fetchone()
            cursor.fetchall()
            result[Pro_name] = row if row and row[0] is not None else (Pro_name, '-', 0, 0)
        except Exception as e:
            result[Pro_name] = (Pro_name, '-', 0, 0)
    if result:
        return render_template("ProStats.html", total=result)
    return render_template("ProStats.html", message="No Prothesist data found.")


@app.route("/Prostat")
def ProStat():
    Pro_list = GetAllProthesists()
    stat = {}
    for Pro in Pro_list:
        cursor.execute("""
            SELECT * FROM Prothesist_Stat WHERE user_id = %s AND prothesist_name = %s
            ORDER BY year DESC, month DESC
        """, (session['id'], Pro))
        stat[Pro] = cursor.fetchall()
    if stat:
        return render_template("ProStats.html", message="The Stat Table", stat=stat)
    return render_template("ProStats.html", message="Table Not Found (There is no Prothesists)")


# ── Prothesist Statistics PDF ────────────────────────────────────────────────
@app.route("/ProStatPDF")
def ProStatPDF():
    if not is_logged_in():
        return redirect('/log_in')
    Pro_list = GetAllProthesists()
    all_data = {}
    for Pro in Pro_list:
        cursor.execute("""
            SELECT * FROM Prothesist_Stat WHERE user_id = %s AND prothesist_name = %s
            ORDER BY year DESC, month DESC
        """, (session['id'], Pro))
        all_data[Pro] = cursor.fetchall()

    def build(story, styles, h2):
        if not all_data:
            story.append(Paragraph("No prothesist data found.", styles['Normal']))
            return
        headers = ['ID', 'Name', 'Number', 'Total Khedma', 'Khalsin (Paid)', 'Machi Khalsin (Owed)', 'Month', 'Year', 'User ID']
        col_w   = [1*cm, 2.5*cm, 2*cm, 2.5*cm, 2.8*cm, 3.2*cm, 1.5*cm, 1.5*cm, 1.5*cm]
        for pro, rows in all_data.items():
            story.append(Paragraph(f"Prothesist: {pro}", h2))
            story.append(Spacer(1, 0.2*cm))
            data = [headers]
            if rows:
                for r in rows:
                    data.append([str(c) if c is not None else '-' for c in r])
            else:
                data.append(['-', pro, '-', '0', '0', '0', '-', '-', '-'])
            t = Table(data, colWidths=col_w, repeatRows=1)
            t.setStyle(_base_table_style())
            story.append(t)
            story.append(Spacer(1, 0.4*cm))

        story.append(Paragraph("Grand Summary — All Prothesists", h2))
        s_data = [['Prothesist', 'Total Khedma', 'Total Paid', 'Total Owed']]
        for pro, rows in all_data.items():
            s_data.append([pro,
                           str(sum(r[3] or 0 for r in rows)),
                           f"{sum(float(r[4] or 0) for r in rows):.2f}",
                           f"{sum(float(r[5] or 0) for r in rows):.2f}"])
        s = Table(s_data, colWidths=[4.5*cm, 3.5*cm, 3.5*cm, 3.5*cm])
        s.setStyle(_base_table_style())
        story.append(s)

    return _make_pdf("Prothesist Statistics Report", build)


@app.route("/ProSearch", methods=["POST", "GET"])
def ProSearchPage():
    if not is_logged_in():
        return redirect("/log_in")
    if request.method == "POST":
        ProName = request.form["SearchBar"]
        if SearcheProTable(ProName):
            cursor.execute("SELECT * FROM Other_Prothesists_Khedma WHERE user_id = %s AND pName = %s",
                           (session["id"], ProName))
            return render_template("ProStats.html", result=cursor.fetchall())
        else:
            return render_template("ProStats.html", error=f"Prothesist {ProName} Not Found")
    return render_template("ProStats.html")


# =============================================================================

if __name__ == "__main__":
    app.run(debug=True)