from locust import HttpUser, task, between
from bs4 import BeautifulSoup


class MyUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        response = self.client.get("/log_in")

        soup = BeautifulSoup(response.text, "html.parser")

        csrf_input = soup.find("input", {"name": "csrf_token"})

        if csrf_input is None:
            print("❌ CSRF TOKEN NOT FOUND")
            print("STATUS:", response.status_code)
            print("HTML:", response.text[:500])
            return

        csrf_token = csrf_input["value"]

        data = {
            "csrf_token": csrf_token,
            "email": "your_actual_email",
            "username": "your_actual_username",
            "password": "your_actual_password"
        }

    @task
    def home(self):
        self.client.get("/HomePage")