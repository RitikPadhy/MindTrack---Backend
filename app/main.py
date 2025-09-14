from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth

app = FastAPI()

# ✅ CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://mind-track-web-interface.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],  # allow POST, GET, OPTIONS etc.
    allow_headers=["*"],  # allow Content-Type, Authorization, etc.
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])

@app.get("/")
def home():
    return {"message": "Backend is running"}