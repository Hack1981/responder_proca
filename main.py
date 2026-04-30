from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
from google.genai import types

app = FastAPI()

API_KEY = "AIzaSyDxKpqdh5jAM8xbhD1bAWU1HVSUgepITxU"

client = genai.Client(api_key=API_KEY)

class Prompt(BaseModel):
    prompt: str


@app.post("/gerar")
def gerar(dados: Prompt):
    resposta = ""

    try:
        for chunk in client.models.generate_content_stream(
            model="gemini-2.5-flash-lite",
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=dados.prompt)],
                )
            ],
        ):
            if chunk.text:
                resposta += chunk.text

        return {"resposta": resposta}

    except Exception as e:
        return {"erro": str(e)}
