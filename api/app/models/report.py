"""Report model — metadata for generated PDF reports."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    nas_filter: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
