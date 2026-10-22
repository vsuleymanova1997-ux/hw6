from pathlib import Path
import os

from dotenv import load_dotenv
from openai import AuthenticationError, OpenAI


HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
load_dotenv(HERE.parent / ".env")

api_key = os.getenv("PORTKEY_API_KEY")
if not api_key:
    raise SystemExit("PORTKEY_API_KEY was not found in .env")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.portkey.ai/v1",
    default_headers={"x-portkey-provider": "openai"},
)

try:
    response = client.chat.completions.create(
        model="gpt-5.6-luna",
        messages=[{"role": "user", "content": "Reply with exactly: Luna test passed."}],
        temperature=0.0,
    )
except AuthenticationError as error:
    raise SystemExit(
        "Portkey rejected PORTKEY_API_KEY. Replace or reactivate the key in your .env file."
    ) from error

print(response.choices[0].message.content)
