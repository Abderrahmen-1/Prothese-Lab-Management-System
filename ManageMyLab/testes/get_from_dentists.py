
import sys
from pathlib import Path

import pytest


# ============================================================
# IMPORT FLASK APPLICATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ManageMyLab.manageMyLab import app


# ============================================================
# FIND ROUTE
# ============================================================

ROUTE_PATH = "/dentists/GetFromDentist"

ROUTE_ENDPOINT = next(
    rule.endpoint
    for rule in app.url_map.iter_rules()
    if rule.rule == ROUTE_PATH
)

ROUTE_GLOBALS = app.view_functions[ROUTE_ENDPOINT].__globals__


# ============================================================
# FAKE DATABASE
# ============================================================

class FakeCursor:

    def __init__(self):
        self.executed_queries = []
        self.last_query = ""
        self.closed = False

        self.duplicate_patient = False
        self.prothesist_exists = True

        self.raise_on_insert_dentist = False
        self.raise_on_insert_prothesist = False

    def execute(self, query, params=None):

        normalized_query = " ".join(query.lower().split())

        self.last_query = normalized_query

        self.executed_queries.append({
            "query": normalized_query,
            "params": params
        })

        if (
            self.raise_on_insert_dentist
            and "insert into dentists" in normalized_query
        ):
            raise Exception("Simulated dentist database error")

        if (
            self.raise_on_insert_prothesist
            and "insert into other_prothesists_khedma" in normalized_query
        ):
            raise Exception("Simulated prothesist database error")

    def fetchone(self):

        if "from dentists" in self.last_query:
            if self.duplicate_patient:
                return (1,)

            return None

        if "from other_prothesists" in self.last_query:
            if self.prothesist_exists:
                return (1,)

            return None

        return None

    def fetchall(self):
        return []

    def close(self):
        self.closed = True


class FakeConnection:

    def __init__(self, cursor):
        self.fake_cursor = cursor

        self.committed = False
        self.rollback_called = False
        self.closed = False

    def cursor(self, buffered=True):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rollback_called = True

    def close(self):
        self.closed = True


# ============================================================
# FORM DATA HELPERS
# ============================================================

def valid_basic_data():

    return {
        "Dentistinput": "Dr Test",
        "PatientFirstName": "Ahmed",
        "PatientLastName": "Test",
        "PatientUnique": "12345",

        "KhedmaChoice": "Couronne",
        "KhedmaPrice": "5000",

        "Khalsa": "no",

        "date": "2026-11-15",
        "DeadLine": "2026-11-25",

        "OtherPro": "no",

        "csrf_token": "valid_token"
    }


def valid_other_pro_data():

    return {
        "OtherPro": "yes",

        "ProName": "Pro Test",
        "ProNumber": "12345",

        "ProPrice": "2000",

        "ProDate": "2026-11-16",
        "ProDeadLine": "2026-11-20",

        "ProKhalsa": "no",

        "Proversa": "yes",
        "ProVersaAmount": "500"
    }


def post_form(client, extra_data=None):

    data = valid_basic_data()

    if extra_data:
        data.update(extra_data)

    return client.post(
        ROUTE_PATH,
        data=data,
        follow_redirects=False
    )


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def database(monkeypatch):

    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    monkeypatch.setitem(
        ROUTE_GLOBALS,
        "get_connection",
        lambda: connection
    )

    monkeypatch.setitem(
        ROUTE_GLOBALS,
        "SearcheTable",
        lambda cursor, dentist: True
    )

    monkeypatch.setitem(
        ROUTE_GLOBALS,
        "checkValue",
        lambda value: (
            str(value).strip() != ""
            and float(value) >= 0
        )
    )

    monkeypatch.setitem(
        ROUTE_GLOBALS,
        "Dentist_History",
        lambda *args: None
    )

    monkeypatch.setitem(
        ROUTE_GLOBALS,
        "DentistStats",
        lambda *args: None
    )

    monkeypatch.setitem(
        ROUTE_GLOBALS,
        "Prothesist_History",
        lambda *args: None
    )

    monkeypatch.setitem(
        ROUTE_GLOBALS,
        "ProthesistsStat",
        lambda *args: None
    )

    return {
        "cursor": cursor,
        "connection": connection
    }


@pytest.fixture
def authenticated_client(monkeypatch):

    monkeypatch.setitem(
        ROUTE_GLOBALS,
        "is_logged_in",
        lambda: True
    )

    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"

    client = app.test_client()

    with client.session_transaction() as session:
        session["id"] = 1
        session["username"] = "test"
        session["csrf_token"] = "valid_token"

    return client


@pytest.fixture
def unauthenticated_client(monkeypatch):

    monkeypatch.setitem(
        ROUTE_GLOBALS,
        "is_logged_in",
        lambda: False
    )

    return app.test_client()


# ============================================================
# DATABASE ASSERTION HELPERS
# ============================================================

def inserted_tables(database):

    return [
        item["query"]
        for item in database["cursor"].executed_queries
        if item["query"].startswith("insert into")
    ]


def assert_no_insertions(database):

    assert inserted_tables(database) == []


def assert_connection_closed(database):

    assert database["cursor"].closed is True
    assert database["connection"].closed is True


# ============================================================
# AUTHENTICATION TESTS
# ============================================================

class TestAuthentication:

    def test_unauthenticated_get_redirects(
        self, unauthenticated_client
    ):

        response = unauthenticated_client.get(ROUTE_PATH)

        assert response.status_code == 302

    def test_unauthenticated_post_redirects(
        self, unauthenticated_client
    ):

        response = unauthenticated_client.post(
            ROUTE_PATH,
            data=valid_basic_data()
        )

        assert response.status_code == 302

    def test_authenticated_user_can_access_page(
        self, authenticated_client
    ):

        response = authenticated_client.get(ROUTE_PATH)

        assert response.status_code == 200

    def test_get_generates_csrf_token(
        self, authenticated_client
    ):

        response = authenticated_client.get(ROUTE_PATH)

        assert response.status_code == 200

        with authenticated_client.session_transaction() as session:
            assert session.get("csrf_token")

    def test_get_generates_new_csrf_token(
        self, authenticated_client
    ):

        with authenticated_client.session_transaction() as session:
            old_token = session["csrf_token"]

        authenticated_client.get(ROUTE_PATH)

        with authenticated_client.session_transaction() as session:
            new_token = session["csrf_token"]

        assert new_token != old_token


# ============================================================
# CSRF TESTS
# ============================================================

class TestCSRF:

    def test_missing_csrf_token(
        self, authenticated_client, database
    ):

        data = valid_basic_data()
        data.pop("csrf_token")

        response = authenticated_client.post(
            ROUTE_PATH,
            data=data
        )

        assert response.status_code == 403
        assert_no_insertions(database)

    def test_invalid_csrf_token(
        self, authenticated_client, database
    ):

        data = valid_basic_data()
        data["csrf_token"] = "wrong_token"

        response = authenticated_client.post(
            ROUTE_PATH,
            data=data
        )

        assert response.status_code == 403
        assert_no_insertions(database)

    def test_valid_csrf_token(
        self, authenticated_client, database
    ):

        response = post_form(authenticated_client)

        assert response.status_code == 200

    def test_csrf_token_rotates_after_valid_post(
        self, authenticated_client, database
    ):

        with authenticated_client.session_transaction() as session:
            old_token = session["csrf_token"]

        post_form(authenticated_client)

        with authenticated_client.session_transaction() as session:
            new_token = session["csrf_token"]

        assert new_token != old_token


# ============================================================
# BASIC FORM VALIDATION
# ============================================================

class TestBasicValidation:

    @pytest.mark.parametrize(
        "field,value",
        [
            ("Dentistinput", ""),
            ("Dentistinput", "   "),
            ("PatientFirstName", ""),
            ("PatientFirstName", "   "),
            ("PatientLastName", ""),
            ("PatientLastName", "   "),
            ("PatientUnique", ""),
            ("PatientUnique", "abc"),
            ("PatientUnique", "1234567890"),
            ("KhedmaChoice", ""),
            ("KhedmaChoice", "   "),
        ]
    )
    def test_invalid_basic_fields(
        self,
        authenticated_client,
        database,
        field,
        value
    ):

        response = post_form(
            authenticated_client,
            {field: value}
        )

        assert response.status_code == 200
        assert_no_insertions(database)

    @pytest.mark.parametrize(
        "price",
        ["", "invalid", "-100"]
    )
    def test_invalid_dentist_price(
        self,
        authenticated_client,
        database,
        price
    ):

        response = post_form(
            authenticated_client,
            {"KhedmaPrice": price}
        )

        assert response.status_code == 200
        assert_no_insertions(database)

    @pytest.mark.parametrize(
        "khalsa",
        ["", "maybe", "paid", "yesno"]
    )
    def test_invalid_dentist_payment_status(
        self,
        authenticated_client,
        database,
        khalsa
    ):

        response = post_form(
            authenticated_client,
            {"Khalsa": khalsa}
        )

        assert response.status_code == 200
        assert_no_insertions(database)

    @pytest.mark.parametrize(
        "field",
        ["date", "DeadLine"]
    )
    def test_missing_dentist_dates(
        self,
        authenticated_client,
        database,
        field
    ):

        response = post_form(
            authenticated_client,
            {field: ""}
        )

        assert response.status_code == 200
        assert_no_insertions(database)

    def test_deadline_before_start_date(
        self,
        authenticated_client,
        database
    ):

        response = post_form(
            authenticated_client,
            {"DeadLine": "2026-11-10"}
        )

        assert response.status_code == 200
        assert_no_insertions(database)

    def test_dentist_not_found(
        self,
        authenticated_client,
        database,
        monkeypatch
    ):

        search_called = []

        def dentist_not_found(cursor, dentist):
            search_called.append(dentist)
            return False

        monkeypatch.setitem(
            ROUTE_GLOBALS,
            "SearcheTable",
            dentist_not_found
        )

        response = post_form(authenticated_client)

        assert response.status_code == 200
        assert search_called == ["Dr Test"]
        assert_no_insertions(database)

    def test_duplicate_patient_number(
        self,
        authenticated_client,
        database
    ):

        database["cursor"].duplicate_patient = True

        response = post_form(authenticated_client)

        assert response.status_code == 200
        assert_no_insertions(database)

    @pytest.mark.parametrize(
        "other_pro",
        ["", "maybe", "invalid"]
    )
    def test_invalid_other_pro_choice(
        self,
        authenticated_client,
        database,
        other_pro
    ):

        response = post_form(
            authenticated_client,
            {"OtherPro": other_pro}
        )

        assert response.status_code == 200
        assert_no_insertions(database)


# ============================================================
# OTHER PROTHESIST VALIDATION
# ============================================================

class TestOtherProthesistValidation:

    def test_missing_prothesist_name(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()
        data["ProName"] = ""

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    @pytest.mark.parametrize(
        "number",
        ["", "abc", "12abc", "-123"]
    )
    def test_invalid_prothesist_number(
        self,
        authenticated_client,
        database,
        number
    ):

        data = valid_other_pro_data()
        data["ProNumber"] = number

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    @pytest.mark.parametrize(
        "price",
        ["", "invalid", "-100"]
    )
    def test_invalid_prothesist_price(
        self,
        authenticated_client,
        database,
        price
    ):

        data = valid_other_pro_data()
        data["ProPrice"] = price

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    @pytest.mark.parametrize(
        "field",
        ["ProDate", "ProDeadLine"]
    )
    def test_missing_prothesist_dates(
        self,
        authenticated_client,
        database,
        field
    ):

        data = valid_other_pro_data()
        data[field] = ""

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    def test_pro_date_before_dentist_date(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()
        data["ProDate"] = "2026-11-14"

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    def test_pro_deadline_before_pro_start(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()
        data["ProDeadLine"] = "2026-11-15"

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    def test_pro_deadline_after_dentist_deadline(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()
        data["ProDeadLine"] = "2026-11-26"

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    @pytest.mark.parametrize(
        "status",
        ["", "maybe", "paid"]
    )
    def test_invalid_prothesist_payment_status(
        self,
        authenticated_client,
        database,
        status
    ):

        data = valid_other_pro_data()
        data["ProKhalsa"] = status

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    def test_prothesist_not_found(
        self,
        authenticated_client,
        database
    ):

        database["cursor"].prothesist_exists = False

        response = post_form(
            authenticated_client,
            valid_other_pro_data()
        )

        assert response.status_code == 200
        assert_no_insertions(database)


# ============================================================
# PROTHESIST PAYMENT VALIDATION
# ============================================================

class TestProthesistPayment:

    def test_fully_paid_prothesist(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()

        data["ProKhalsa"] = "yes"
        data["Proversa"] = ""
        data["ProVersaAmount"] = ""

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert database["connection"].committed is True

    def test_unpaid_prothesist_without_versement(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()

        data["ProKhalsa"] = "no"
        data["Proversa"] = "no"
        data["ProVersaAmount"] = ""

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert database["connection"].committed is True

    def test_unpaid_prothesist_with_versement(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()

        data["ProKhalsa"] = "no"
        data["Proversa"] = "yes"
        data["ProVersaAmount"] = "500"

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert database["connection"].committed is True

    def test_missing_versement_choice(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()
        data["Proversa"] = ""

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    def test_missing_versement_amount(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()
        data["ProVersaAmount"] = ""

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    @pytest.mark.parametrize(
        "amount",
        ["invalid", "-100"]
    )
    def test_invalid_versement_amount(
        self,
        authenticated_client,
        database,
        amount
    ):

        data = valid_other_pro_data()
        data["ProVersaAmount"] = amount

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)

    def test_versement_greater_than_price(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()

        data["ProPrice"] = "1000"
        data["ProVersaAmount"] = "1500"

        response = post_form(authenticated_client, data)

        assert response.status_code == 200
        assert_no_insertions(database)


# ============================================================
# SUCCESSFUL SUBMISSION TESTS
# ============================================================

class TestSuccessfulSubmission:

    def test_submit_without_other_prothesist(
        self,
        authenticated_client,
        database
    ):

        response = post_form(authenticated_client)

        assert response.status_code == 200
        assert database["connection"].committed is True

        queries = inserted_tables(database)

        assert any(
            "insert into dentists" in query
            for query in queries
        )

        assert any(
            "insert into khedma" in query
            for query in queries
        )

    def test_submit_with_other_prothesist(
        self,
        authenticated_client,
        database
    ):

        response = post_form(
            authenticated_client,
            valid_other_pro_data()
        )

        assert response.status_code == 200
        assert database["connection"].committed is True

        queries = inserted_tables(database)

        assert any(
            "insert into other_prothesists_khedma" in query
            for query in queries
        )

        assert any(
            "insert into dentists" in query
            for query in queries
        )

        assert any(
            "insert into khedma" in query
            for query in queries
        )

    def test_dentist_fully_paid(
        self,
        authenticated_client,
        database
    ):

        response = post_form(
            authenticated_client,
            {"Khalsa": "yes"}
        )

        assert response.status_code == 200
        assert database["connection"].committed is True

    def test_dentist_not_fully_paid(
        self,
        authenticated_client,
        database
    ):

        response = post_form(
            authenticated_client,
            {"Khalsa": "no"}
        )

        assert response.status_code == 200
        assert database["connection"].committed is True

    def test_other_prothesist_case_insensitive(
        self,
        authenticated_client,
        database
    ):

        data = valid_other_pro_data()
        data["OtherPro"] = "YES"

        response = post_form(authenticated_client, data)

        assert response.status_code == 200

        queries = inserted_tables(database)

        assert any(
            "insert into other_prothesists_khedma" in query
            for query in queries
        )


# ============================================================
# DATABASE ERROR HANDLING
# ============================================================

class TestDatabaseHandling:

    def test_dentist_insert_error_rolls_back(
        self,
        authenticated_client,
        database
    ):

        database["cursor"].raise_on_insert_dentist = True

        response = post_form(authenticated_client)

        assert response.status_code == 200

        assert database["connection"].rollback_called is True
        assert database["connection"].committed is False

        assert_connection_closed(database)

    def test_prothesist_insert_error_rolls_back(
        self,
        authenticated_client,
        database
    ):

        database["cursor"].raise_on_insert_prothesist = True

        response = post_form(
            authenticated_client,
            valid_other_pro_data()
        )

        assert response.status_code == 200

        assert database["connection"].rollback_called is True
        assert database["connection"].committed is False

        assert_connection_closed(database)

    def test_connection_and_cursor_are_closed(
        self,
        authenticated_client,
        database
    ):

        post_form(authenticated_client)

        assert_connection_closed(database)

    def test_invalid_dentist_does_not_leave_connection_open(
        self,
        authenticated_client,
        database
    ):

        post_form(
            authenticated_client,
            {"KhedmaPrice": ""}
        )

        assert_connection_closed(database)

    def test_dentist_not_found_closes_connection(
        self,
        authenticated_client,
        database,
        monkeypatch
    ):

        monkeypatch.setitem(
            ROUTE_GLOBALS,
            "SearcheTable",
            lambda cursor, dentist: False
        )

        post_form(authenticated_client)

        assert_connection_closed(database)
