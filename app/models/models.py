from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import relationship
from app.repo.db import Base
import uuid

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(Text)
    credits = Column(Integer, nullable=False, default=0)
    is_admin = Column(Integer, default=0)
    friends_invited = Column(Integer)
    email = Column(Text)
    receipt_opt_out = Column(Integer, default=0)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    locale = Column(String(8), nullable=True)

    payments = relationship("Payment", back_populates="user", primaryjoin="User.user_id==foreign(Payment.user_id)")
    tasks = relationship("VideoRequest", back_populates="user", primaryjoin="User.user_id==foreign(VideoRequest.user_id)")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    provider_payment_id = Column(String(128), unique=True, nullable=False)
    qty_credits = Column(Integer, nullable=False)
    amount_rub = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="payments", primaryjoin="User.user_id==foreign(Payment.user_id)")

class VideoRequest(Base):
    __tablename__ = "video_requests"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    chat_id = Column(BigInteger)

    prompt = Column(Text)
    format = Column(Text)        # "16:9" | "9:16" (для I2V влияет входная картинка)
    model = Column(Text)        
    cost = Column(Integer)
    duration = Column(Integer)   # 5 | 10 (сек)
    resolution = Column(Text)    # "480P"|"720P"|"1080P"

    video_url = Column(Text, nullable=True)
    task_id = Column(Text, nullable=True)     
    status = Column(Text, nullable=True)      # pending|processing|success|error

    submit_time = Column(Text)    # опционально: из ответа /tasks
    scheduled_time = Column(Text)
    end_time = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    user = relationship("User", back_populates="tasks", primaryjoin="User.user_id==foreign(VideoRequest.user_id)")

class BroadcastJob(Base):
    __tablename__ = "broadcast_jobs"
    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_by = Column(BigInteger, nullable=False)
    text = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    total = Column(Integer, default=0)
    sent = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    note = Column(Text)
