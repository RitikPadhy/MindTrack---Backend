# reading.py
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from firebase_admin import firestore
from app.core.firebase import db  # your initialized Firestore client

router = APIRouter()

# ---------- Pydantic Models ----------
class SectionMaterial(BaseModel):
    section_id: int
    title: str
    material: str  # single string now

# ---------- Add/Update Reading Material ----------
@router.post("/reading-material")
def add_reading_material(section: SectionMaterial):
    try:
        doc_ref = db.collection("reading_material").document(str(section.section_id))
        doc_ref.set({
            "title": section.title,
            "material": section.material
        })
        return {"message": f"Section {section.section_id} saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------- Get Reading Material ----------
@router.get("/reading-material/{section_id}")
def get_reading_material(section_id: int):
    try:
        doc_ref = db.collection("reading_material").document(str(section_id))
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Section not found")
        return {"section_id": section_id, **doc.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------- Optional: Get All Sections ----------
@router.get("/reading-material")
def get_all_reading_material():
    try:
        sections = db.collection("reading_material").stream()
        data = []
        for doc in sections:
            item = doc.to_dict()
            item["section_id"] = int(doc.id)
            data.append(item)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))