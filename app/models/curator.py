from sqlalchemy import BigInteger, String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class Curator(Base):
    __tablename__ = "curator"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    login: Mapped[str] = mapped_column(String, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    patronymic: Mapped[str] = mapped_column(String, nullable=False)

    groups: Mapped[list["Group"]] = relationship(
        "Group",
        back_populates="curator",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    exams: Mapped[list["Exam"]] = relationship(
        "Exam",
        back_populates="curator",
        cascade="all, delete-orphan",
        passive_deletes=True
    )