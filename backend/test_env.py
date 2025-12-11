import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(BASE_DIR, ".env")

print("Loading .env from:", env_path)
load_dotenv(env_path)

print("OPENAI_API_KEY =", os.getenv("OPENAI_API_KEY"))
