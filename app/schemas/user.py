from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    interests: list[str] = Field(default_factory=list, max_length=10)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    interests: list[str]

    @field_validator("interests", mode="before")
    @classmethod
    def serialize_interests(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return [getattr(interest, "name", interest) for interest in value]
        return value
