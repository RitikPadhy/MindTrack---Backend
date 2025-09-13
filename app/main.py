from fastapi import FastAPI
from app.api import auth

app = FastAPI()

app.include_router(auth.router, prefix="/auth")  # all auth routes under /auth

@app.get("/")
def home():
    return {"message": "Backend is running"}