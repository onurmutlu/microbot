from sqlalchemy import Column, Integer, String, DateTime, JSON, Float
from app.db.base_class import Base
from datetime import datetime

class ResponseTemplate(Base):
    __tablename__ = "response_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    content = Column(String, nullable=False)
    category = Column(String, nullable=False)  # question, support, feedback, information
    sentiment = Column(String, nullable=False)  # positive, negative, neutral
    variables = Column(JSON, default=list)  # Kullanılabilir değişkenler listesi
    response_metadata = Column(JSON, default=dict)  # Şablon metadata'sı
    usage_count = Column(Integer, default=0)  # Kullanım sayısı
    success_rate = Column(Float, default=0.0)  # Başarı oranı
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Modeli dictionary'e çevir"""
        return {
            "id": self.id,
            "name": self.name,
            "content": self.content,
            "category": self.category,
            "sentiment": self.sentiment,
            "variables": self.variables,
            "metadata": self.response_metadata,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        } 