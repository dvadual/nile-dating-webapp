from sqlalchemy import Column, ForeignKey, Integer, Table

from app.core.database import Base


user_interests = Table(
    "user_interests",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "interest_id",
        Integer,
        ForeignKey("interests.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
