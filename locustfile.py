
from locust import HttpUser, task, between
from bs4 import BeautifulSoup
import os


class MyUser(HttpUser):

    wait_time = between(1, 3)

    def on_start(self):

        self.authenticated = False

        # 1. Get login page
        response = self.client.get("/")

        if response.status_code != 200:
            print("LOGIN PAGE ERROR:", response.status_code)
            self.stop(True)
            return

        # 2. Extract CSRF token
        soup = BeautifulSoup(response.text, "html.parser")

        csrf_input = soup.find("input", {"name": "csrf_token"})

        if csrf_input is None:
            print("CSRF TOKEN NOT FOUND")
            self.stop(True)
            return

        csrf_token = csrf_input.get("value")

        # 3. Login
        data = {
            "csrf_token": csrf_token,
            "email": '',
            "username": '',
            "password": ''
        }

        # Don't follow redirect: inspect login response
        login_response = self.client.post(
            "/",
            data=data,
            allow_redirects=False
        )

        if login_response.status_code not in (302, 303):
            print("LOGIN FAILED:", login_response.status_code)
            print(login_response.text[:500])
            self.stop(True)
            return

        # 4. Verify protected route
        test_response = self.client.get(
            "/AllTotalAccount",
            allow_redirects=False
        )

        if test_response.status_code == 200:
            self.authenticated = True
            print("LOGIN SUCCESS")

        else:
            print("AUTHENTICATION CHECK FAILED:",
                  test_response.status_code)
            self.stop(True)

    @task
    def home(self):

        if not self.authenticated:
            return

        with self.client.get(
            "/AllTotalAccount",
            allow_redirects=False,
            catch_response=True
        ) as response:

            if response.status_code == 200:
                response.success()

            elif response.status_code == 302:
                response.failure("Session expired / Not authenticated")

            else:
                response.failure(
                    f"Server error: HTTP {response.status_code}"
                )
