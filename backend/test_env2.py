import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(BASE_DIR, ".env")

print("ENV PATH:", env_path)
print("File exists:", os.path.exists(env_path))

load_dotenv(env_path)

print("OPENAI_API_KEY =", os.getenv("OPENAI_API_KEY"))
