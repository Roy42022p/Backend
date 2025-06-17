from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class Admin(Base):
    __tablename__ = "admin"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    login: Mapped[str] = mapped_column(String, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
