from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.association import user_interests

if TYPE_CHECKING:
    from app.models.user import User


class Interest(Base):
    __tablename__ = "interests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    users: Mapped[list["User"]] = relationship(
        secondary=user_interests,
        back_populates="interests",
        lazy="selectin",
    )
