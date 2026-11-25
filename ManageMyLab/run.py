# run_server.py
from waitress import serve
from ManageMyLab.manageMyLab import app

serve(app, host="127.0.0.1", port=5000,
      threads=16, connection_limit=1000, backlog=2048,
      channel_timeout=120)