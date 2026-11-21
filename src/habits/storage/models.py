from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class HabitRow(Base):
    __tablename__ = "habits"
    __table_args__ = (sa.CheckConstraint("frequency IN ('daily','weekly')", name="ck_habits_frequency"),)

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    frequency: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    target_per_week: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    archived: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=False)
