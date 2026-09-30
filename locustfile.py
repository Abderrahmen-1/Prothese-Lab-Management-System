from locust import HttpUser, task, between
from bs4 import BeautifulSoup
import os


class MyUser(HttpUser):

    wait_time = between(1, 3)

    def on_start(self):

        # 1. Get login page
        response = self.client.get("/log_in")

        if response.status_code != 200:
            print("❌ Could not load login page")
            print("Status:", response.status_code)
            return

        # 2. Extract CSRF token
        soup = BeautifulSoup(response.text, "html.parser")

        csrf_input = soup.find(
            "input",
            {"name": "csrf_token"}
        )

        if csrf_input is None:
            print("❌ CSRF TOKEN NOT FOUND")
            return

        csrf_token = csrf_input.get("value")

        # 3. Login
        data = {
            "csrf_token": csrf_token,
            "email": "my_email",
            "username": "my_username",
            "password": "my_password"
        }

        login_response = self.client.post(
            "/log_in",
            data=data,
            allow_redirects=True
        )

        # 4. Check login result
        if login_response.status_code != 200:
            print(
                "❌ Login failed:",
                login_response.status_code
            )
            return

        # Check whether we actually reached HomePage
        if "WELCOME" not in login_response.text:
            print("⚠️ Login may have failed")

    @task
    def home(self):

        response = self.client.get("/AllTotalAccount")

        if response.status_code == 302:
            print("✅ LOGIN SUCCESS")
        else:
            print("❌ LOGIN FAILED:", response.status_code)