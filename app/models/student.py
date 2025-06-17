from sqlalchemy import BigInteger, String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class Student(Base):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    login: Mapped[str] = mapped_column(String, nullable=True)
    password: Mapped[str] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    patronymic: Mapped[str] = mapped_column(String, nullable=False)
    date_of_birth: Mapped[str] = mapped_column(String, nullable=True)
    telephone: Mapped[str] = mapped_column(String, nullable=True)
    mail: Mapped[str] = mapped_column(String, nullable=True)
    snils: Mapped[str] = mapped_column(String, nullable=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("group.id", ondelete="CASCADE"), nullable=False)
    telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("telegram.id", ondelete="SET NULL"), nullable=True)
    verif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    group: Mapped["Group"] = relationship("Group", back_populates="students", passive_deletes=True)
    telegram: Mapped["Telegram"] = relationship("Telegram", back_populates="student", uselist=False)
    marks: Mapped[list["Mark"]] = relationship(
        "Mark",
        back_populates="student",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
