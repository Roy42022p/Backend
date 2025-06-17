from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class Telegram(Base):
    __tablename__ = "telegram"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    student: Mapped["Student"] = relationship("Student", back_populates="telegram", uselist=False, passive_deletes=True)