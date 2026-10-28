from sqlalchemy import ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ProductPhoto(Base, TimestampMixin):
    """The re-encoded bytes of an uploaded product photo.

    Photos live in Postgres rather than on disk so they survive hosts whose
    filesystem is wiped on restart (the free cloud tier), and so replacing a
    photo commits in the same transaction as the product's `photo_url`.
    """

    __tablename__ = "product_photos"

    # UUID hex we generate; also the file name in the served URL.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
