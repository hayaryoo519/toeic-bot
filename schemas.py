from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import enum

class ContentType(str, enum.Enum):
    question = "question"
    passage = "passage"

# --- Passages ---
class PassageBase(BaseModel):
    title: Optional[str] = None
    content: str

class PassageCreate(PassageBase):
    pass

class Passage(PassageBase):
    id: int

    class Config:
        from_attributes = True

# --- Questions ---
class QuestionBase(BaseModel):
    question: str
    choice_a: str
    choice_b: str
    choice_c: str
    choice_d: str
    answer: str
    explanation: str

class QuestionCreate(QuestionBase):
    passage_id: Optional[int] = None

class Question(QuestionBase):
    id: int
    passage_id: Optional[int] = None

    class Config:
        from_attributes = True

class PassageWithQuestions(Passage):
    questions: List[Question] = []
    
    class Config:
        from_attributes = True

# --- Users ---
class UserBase(BaseModel):
    line_user_id: str

class UserCreate(UserBase):
    created_at: datetime

class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- Deliveries ---
class DeliveryBase(BaseModel):
    user_id: int
    content_type: ContentType
    content_id: int
    delivered_at: datetime
    delivered_date: date

class DeliveryCreate(DeliveryBase):
    pass

class Delivery(DeliveryBase):
    id: int

    class Config:
        from_attributes = True

# --- Answers ---
class AnswerBase(BaseModel):
    delivery_id: int
    user_id: int
    question_id: int
    is_correct: bool
    answered_at: datetime

class AnswerCreate(AnswerBase):
    pass

class Answer(AnswerBase):
    id: int

    class Config:
        from_attributes = True
