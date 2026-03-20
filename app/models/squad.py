from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
import random, string

def gen_invite_code(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

class SquadModel(BaseModel):
    squad_id: str
    name: str
    emoji: str = "⚔️"
    invite_code: str = Field(default_factory=gen_invite_code)
    owner_telegram_id: int
    members: List[int] = Field(default_factory=list)
    max_members: int = 50
    total_points: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
