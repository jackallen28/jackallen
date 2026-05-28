from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routes.chat import router as chat_router
from routes.compiler import router as compiler_router
from routes.files import router as files_router

load_dotenv()

app = FastAPI(title="Allentronics VibeDuino API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(compiler_router)
app.include_router(files_router)
