from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth
from app.routes import routines  # Import the routines router
from app.routes import feedback
from app.routes import track_progress
from app.routes import reading
from app.routes import achievements
from app.routes import question
from app.routes import user_categories

app = FastAPI()

# ---------- CORS setup ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your front-end URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Include routers ----------
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(routines.router, prefix="/routines", tags=["routines"])
app.include_router(feedback.router, prefix="/weekly-feedback", tags=["feedback"])
app.include_router(reading.router, prefix="/reading", tags=["reading"])
app.include_router(track_progress.router, prefix="/track_progress", tags=["track_progress"])
app.include_router(achievements.router, prefix="/achievements", tags=["achievements"])
app.include_router(question.router, prefix="/question", tags=["question"])
app.include_router(user_categories.router, prefix="/analytics", tags=["analytics"])

# ---------- Root endpoint ----------
@app.get("/")
def home():
    return {"message": "Backend is running"}