from dotenv import load_dotenv
import os

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT")
DATABASE_URL = os.getenv("DATABASE_URL")
API_HOST = os.getenv("API_HOST")
API_PORT = os.getenv("API_PORT")
