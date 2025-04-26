from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from app.services.template_generator import TemplateGenerator
from app.models.response_template import ResponseTemplate
from app.db.session import SessionLocal
from sqlalchemy.orm import Session

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/generate", response_model=List[Dict[str, Any]])
async def generate_templates():
    """Tüm kategoriler için şablonlar oluştur"""
    generator = TemplateGenerator()
    templates = await generator.generate_templates()
    return templates

@router.post("/generate/{category}", response_model=List[Dict[str, Any]])
async def generate_category_templates(category: str):
    """Belirli bir kategori için şablonlar oluştur"""
    generator = TemplateGenerator()
    templates = await generator.generate_category_templates(category)
    return templates

@router.post("/update", response_model=List[Dict[str, Any]])
async def update_templates():
    """Mevcut şablonları güncelle"""
    generator = TemplateGenerator()
    templates = await generator.update_existing_templates()
    return templates

@router.get("/", response_model=List[Dict[str, Any]])
async def list_templates(db: Session = Depends(get_db)):
    """Tüm şablonları listele"""
    templates = db.query(ResponseTemplate).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "content": t.content,
            "category": t.category,
            "sentiment": t.sentiment,
            "variables": t.variables,
            "created_at": t.created_at,
            "updated_at": t.updated_at
        }
        for t in templates
    ] 