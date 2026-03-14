from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Date, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
import enum

from database import Base

class ContentType(str, enum.Enum):
    question = "question"
    passage = "passage"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    line_user_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime)
    current_combo = Column(Integer, default=0)
    max_combo = Column(Integer, default=0)
    
    answers = relationship("Answer", back_populates="user")
    deliveries = relationship("Delivery", back_populates="user")

class Passage(Base):
    __tablename__ = "passages"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    content = Column(String)
    
    questions = relationship("Question", back_populates="passage")

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    passage_id = Column(Integer, ForeignKey("passages.id"), nullable=True)
    question = Column(String)
    choice_a = Column(String)
    choice_b = Column(String)
    choice_c = Column(String)
    choice_d = Column(String)
    answer = Column(String)
    explanation = Column(String)
    notion_page_id = Column(String, unique=True, nullable=True, index=True)
    
    passage = relationship("Passage", back_populates="questions")
    answers = relationship("Answer", back_populates="question")

class Delivery(Base):
    __tablename__ = "deliveries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    content_type = Column(Enum(ContentType))
    content_id = Column(Integer)
    delivered_at = Column(DateTime)
    delivered_date = Column(Date) # UNIQUE制約と集計用
    
    __table_args__ = (
        UniqueConstraint('user_id', 'content_type', 'content_id', 'delivered_date', name='uq_user_content_date'),
    )
    
    user = relationship("User", back_populates="deliveries")
    answers = relationship("Answer", back_populates="delivery")

class Answer(Base):
    __tablename__ = "answers"
    
    id = Column(Integer, primary_key=True, index=True)
    delivery_id = Column(Integer, ForeignKey("deliveries.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    is_correct = Column(Boolean)
    answered_at = Column(DateTime)
    
    delivery = relationship("Delivery", back_populates="answers")
    user = relationship("User", back_populates="answers")
    question = relationship("Question", back_populates="answers")

class AIGenerationLog(Base):
    __tablename__ = "ai_generation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    prompt = Column(String)
    generated_question = Column(String) # JSON or text
    review_result = Column(String)
    created_at = Column(DateTime)

class SyncLog(Base):
    __tablename__ = "sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    notion_page_id = Column(String)
    result = Column(String) # Success / Skip / Error
    error_message = Column(String, nullable=True)
    synced_at = Column(DateTime)
