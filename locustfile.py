import os
from locust import HttpUser, task, between, events
from bs4 import BeautifulSoup

# Test account: must exist, email_confirmed=TRUE, is_paid=TRUE, status not 'block'/'out of limits'
EMAIL = os.getenv('LOCUST_EMAIL')
USERNAME = os.getenv('LOCUST_USERNAME')
PASSWORD = os.getenv('LOCUST_PASSWORD')

def extract_csrf(html):
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("input", {"name": "csrf_token"})
    return tag.get("value") if tag and tag.get("value") else None


class AppUser(HttpUser):
    """Logged-in user browsing the app (read-only requests)."""
    weight = 9
    wait_time = between(1, 3)

    def on_start(self):
        self.authenticated = False

        # 1. GET login page (this also sets the session + csrf token)
        with self.client.get("/", name="GET Login Page", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"Login page HTTP {r.status_code}")
                self.stop()
                return
            csrf = extract_csrf(r.text)
            if not csrf:
                r.failure("CSRF token missing in login page")
                self.stop()
                return
            r.success()

        # 2. POST login (needs email + username + password)
        data = {
            "csrf_token": csrf,
            "email": EMAIL,
            "username": USERNAME,
            "password": PASSWORD,
        }
        with self.client.post("/", data=data, allow_redirects=False,
                              name="POST Login", catch_response=True) as r:
            if r.status_code in (302, 303):
                location = r.headers.get("Location", "")
                if "HomePage" in location:
                    r.success()
                else:
                    r.failure(f"Redirected to {location} (payment/limit?)")
                    self.stop()
                    return
            elif r.status_code == 403:
                r.failure("CSRF rejected (403)")
                self.stop()
                return
            else:
                errs = [e.get_text(strip=True) for e in
                        BeautifulSoup(r.text, "html.parser").select(".error, .alert, .flash, .message")]
                r.failure(f"Login failed: HTTP {r.status_code} {errs}")
                self.stop()
                return

        self.authenticated = True

    def _get(self, path, name):
        """GET a protected page; a redirect means the session was lost."""
        with self.client.get(path, allow_redirects=False, name=name,
                             catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            elif r.status_code in (301, 302, 303):
                r.failure(f"Redirected to {r.headers.get('Location')} (not authenticated)")
            else:
                r.failure(f"HTTP {r.status_code}")
            return r

    @task(5)
    def dashboard(self):
        if self.authenticated:
            self._get("/AllTotalAccount", "GET /AllTotalAccount")

    @task(3)
    def home(self):
        if self.authenticated:
            self._get("/HomePage", "GET /HomePage")

    @task(3)
    def all_khedma(self):
        if self.authenticated:
            self._get("/Allkhedma", "GET /Allkhedma")

    @task(2)
    def khedma_page(self):
        if self.authenticated:
            self._get("/Khedma", "GET /Khedma")

    @task(1)
    def khedma_search(self):
        """Read-only search: GET the form for a fresh token, then POST it."""
        if not self.authenticated:
            return
        r = self._get("/Khedma", "GET /Khedma (before search)")
        if r.status_code != 200:
            return
        csrf = extract_csrf(r.text)
        if not csrf:
            return
        with self.client.post("/Khedma",
                              data={"csrf_token": csrf, "SearchBar": "dentist"},
                              allow_redirects=False, name="POST /Khedma search",
                              catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 403:
                resp.failure("CSRF 403 on /Khedma")
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(1)
    def static_pages(self):
        if self.authenticated:
            self._get("/Khalsa", "GET /Khalsa")


class LoginStormUser(HttpUser):
    """Repeated fresh logins: stresses password hashing (scrypt) and the
    UPDATE/DELETE statements that run on every login."""
    weight = 1
    wait_time = between(2, 5)

    @task
    def full_login(self):
        self.client.cookies.clear()
        with self.client.get("/", name="STORM GET Login", catch_response=True) as r:
            csrf = extract_csrf(r.text) if r.status_code == 200 else None
            if not csrf:
                r.failure(f"No page/CSRF (HTTP {r.status_code})")
                return
            r.success()

        with self.client.post("/", allow_redirects=False, name="STORM POST Login",
                              data={"csrf_token": csrf, "email": EMAIL,
                                    "username": USERNAME, "password": PASSWORD},
                              catch_response=True) as r:
            if r.status_code in (302, 303):
                r.success()
            else:
                r.failure(f"Login HTTP {r.status_code}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"Testing with account: {EMAIL} / {USERNAME}")