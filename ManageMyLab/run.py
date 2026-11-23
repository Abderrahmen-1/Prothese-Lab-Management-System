from ManageMyLab.manageMyLab import app
from waitress import serve

if __name__ == "__main__":
    print("Starting Flask with Waitress...")

    serve(
        app,
        host="127.0.0.1",
        port=5000,
        threads=8
    )