import uuid
from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.listing import CATEGORY_ART


class SignupRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    otp: str


class ProfileRequest(BaseModel):
    name: str
    college: str
    course: str
    year: str


class InterestsRequest(BaseModel):
    interests: list[str]

    @field_validator("interests")
    @classmethod
    def only_known_categories(cls, value: list[str]) -> list[str]:
        unknown = [c for c in value if c not in CATEGORY_ART]
        if unknown:
            raise ValueError(f"Unknown categories: {', '.join(unknown)}")
        return list(dict.fromkeys(value))  # drop duplicates, keep order


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None = None
    college: str | None = None
    course: str | None = None
    year: str | None = None
    role: str
    verified: bool
    profile_completed: bool
    interests: list[str] = []

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    token: str
    user: UserOut
