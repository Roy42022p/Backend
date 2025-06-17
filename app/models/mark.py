from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class Mark(Base):
    __tablename__ = "marks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mark: Mapped[int] = mapped_column(Integer, nullable=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exam.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("student.id", ondelete="CASCADE"), nullable=False)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="marks", passive_deletes=True)
    student: Mapped["Student"] = relationship("Student", back_populates="marks", passive_deletes=True)
