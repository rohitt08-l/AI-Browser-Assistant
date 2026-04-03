from groq import Groq
from openai import AzureOpenAI
from backend.core.config import Config


def call_llm(prompt: str):
    provider = Config.LLM_PROVIDER.lower()

    if provider == "groq":
        client = Groq(api_key=Config.GROQ_API_KEY)

        response = client.chat.completions.create(
            model=Config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful browser assistant"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        return response.choices[0].message.content

    elif provider == "azure":
        client = AzureOpenAI(
            api_key=Config.AZURE_OPENAI_API_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        )

        response = client.chat.completions.create(
            model=Config.AZURE_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful browser assistant"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        return response.choices[0].message.content

    else:
        raise ValueError(f"Unsupported provider: {provider}")