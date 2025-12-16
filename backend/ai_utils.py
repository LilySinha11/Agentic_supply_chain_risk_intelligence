import os
import json
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)


# Create Groq key.
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyze_text(text):
    prompt = f"""
    You MUST respond ONLY in valid JSON. No extra text. No explanation.

    Extract the following from the news text:
    - summary (string)
    - sentiment (positive, neutral, negative)
    - sentiment_score (0 to 1)
    - entities (list of company or supplier names)
    - severity (0 to 1)

    Text:
    {text}
    """

    try:
        response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
        )

        raw = response.choices[0].message.content.strip()

        # 🔍 Debug print (optional)
        print("Raw LLM Output:", raw)

        # If model returned empty → avoid json error
        if not raw:
            raise ValueError("Empty response from model")

        # Try to parse JSON
        return json.loads(raw)

    except Exception as e:
        print("LLM error:", e)
        return {
            "summary": text[:100],
            "sentiment": "neutral",
            "sentiment_score": 0.5,
            "entities": [],
            "severity": 0.3
        }
