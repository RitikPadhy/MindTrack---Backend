from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth

app = FastAPI()

origins = [
    "http://localhost:3000",  # local dev
    "https://mind-track-web-interface.vercel.app",  # your Vercel frontend
    "https://mind-track-web-interface-3mjtxskme-ritikpadhys-projects.vercel.app",  # preview link
    "https://mindtracker.dedyn.io",  # your backend domain
]

# ✅ CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])

@app.get("/")
def home():
    return {"message": "Backend is running"}