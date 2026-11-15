import mysql.connector.pooling
import os
from dotenv import load_dotenv

load_dotenv()

pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="labo_pool",
    pool_size=15,
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

def get_connection():
    return pool.get_connection()
