from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentMethod(enum.Enum):
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    CRYPTO = "crypto"

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    currency = Column(String, default="USD")
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    method = Column(Enum(PaymentMethod))
    transaction_id = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    payment_metadata = Column(String, nullable=True)  # JSON formatında ek bilgiler
    is_recurring = Column(Boolean, default=False)
    next_payment_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="payments")
    
    def __repr__(self):
        return f"<Payment {self.transaction_id} - {self.status.value}>" 