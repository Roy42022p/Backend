from sqlalchemy import BigInteger, String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class Group(Base):
    __tablename__ = "group"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    curator_id: Mapped[int] = mapped_column(Integer, ForeignKey("curator.id", ondelete="CASCADE"), nullable=False)

    curator: Mapped["Curator"] = relationship("Curator", back_populates="groups", passive_deletes=True)
    students: Mapped[list["Student"]] = relationship(
        "Student",
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    exams: Mapped[list["Exam"]] = relationship(
        "Exam",
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True
    )