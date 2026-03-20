from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import random, string

def generate_referral_code(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

class UserModel(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    photo_url: Optional[str] = None
    language_code: Optional[str] = "en"
    points: int = 0
    total_points_earned: int = 0
    sfg_tokens_estimated: float = 0.0
    xp: int = 0
    level: int = 1
    level_title: str = "SHILL ROOKIE"
    referral_code: str = Field(default_factory=generate_referral_code)
    referred_by: Optional[int] = None
    referral_count: int = 0
    referral_points_earned: int = 0
    tap_energy: int = 500
    tap_energy_last_update: datetime = Field(default_factory=datetime.utcnow)
    taps_today: int = 0
    taps_total: int = 0
    best_combo: int = 1
    tap_pts_base: int = 1
    tap_upgrades: Dict[str, int] = Field(default_factory=lambda: {"u1": 0, "u2": 0, "u3": 0, "u4": 0})
    active_theme: str = "default"
    owned_themes: List[str] = Field(default_factory=lambda: ["default"])
    checkin_streak: int = 0
    checkin_last_date: Optional[str] = None
    squad_id: Optional[str] = None
    wallet_address: Optional[str] = None
    wallet_type: Optional[str] = None
    active_boosts: List[Dict] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    completed_tasks: List[str] = Field(default_factory=list)
    last_spin_date: Optional[str] = None
    is_banned: bool = False
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}
