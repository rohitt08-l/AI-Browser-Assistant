from groq import Groq
from backend.core.config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

def groq_llm(prompt):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content