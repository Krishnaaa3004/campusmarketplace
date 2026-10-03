from datetime import datetime

from pydantic import BaseModel, Field, field_validator

MAX_LEN = 70


class ProductRequestCreate(BaseModel):
    product: str = Field(max_length=MAX_LEN)
    description: str | None = Field(default=None, max_length=MAX_LEN)

    @field_validator("product")
    @classmethod
    def product_required(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Tell sellers what you're looking for")
        return value

    @field_validator("description")
    @classmethod
    def one_line(cls, value: str | None) -> str | None:
        # Collapse newlines/extra spaces so it stays a single line.
        value = " ".join((value or "").split())
        return value or None


class RequesterOut(BaseModel):
    id: str
    name: str
    avatar_url: str | None = None
    email: str
    phone: str | None = None


class ProductRequestOut(BaseModel):
    id: int
    product: str
    description: str | None = None
    created_at: datetime
    requester: RequesterOut

    @classmethod
    def from_model(cls, r) -> "ProductRequestOut":
        return cls(
            id=r.id,
            product=r.product,
            description=r.description,
            created_at=r.created_at,
            requester=RequesterOut(
                id=str(r.user.id),
                name=r.user.name or r.user.email.split("@")[0],
                avatar_url=r.user.avatar_url,
                email=r.user.email,
                phone=r.user.phone,
            ),
        )
