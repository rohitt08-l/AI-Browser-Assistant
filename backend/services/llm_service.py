from openai import AzureOpenAI
from backend.core.config import Config

client = AzureOpenAI(
    api_key=Config.AZURE_OPENAI_API_KEY,
    api_version=Config.AZURE_OPENAI_API_VERSION,
    azure_endpoint=Config.AZURE_OPENAI_ENDPOINT
)

def azure_llm(prompt):
    response = client.chat.completions.create(
        model=Config.OPENAI_MODEL_DEPLOYMENT_NAME,
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content