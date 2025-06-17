from sqlalchemy import BigInteger, String, SMALLINT, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class Exam(Base):
    __tablename__ = "exam"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    semester: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    course: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    discipline: Mapped[str] = mapped_column(String, nullable=False)
    holding_date: Mapped[str] = mapped_column(String, nullable=False)
    link: Mapped[str] = mapped_column(String, nullable=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("group.id", ondelete="CASCADE"), nullable=False)
    curator_id: Mapped[int] = mapped_column(Integer, ForeignKey("curator.id", ondelete="CASCADE"), nullable=False)

    group: Mapped["Group"] = relationship("Group", back_populates="exams", passive_deletes=True)
    curator: Mapped["Curator"] = relationship("Curator", back_populates="exams", passive_deletes=True)
    marks: Mapped[list["Mark"]] = relationship(
        "Mark",
        back_populates="exam",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
