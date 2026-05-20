import sys
from pathlib import Path

from sqlalchemy import Integer, String, UniqueConstraint, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hlpp_l0_contracts.idempotency import idempotent_insert, sha256_url


class Base(DeclarativeBase):
    pass


class SeenUrl(Base):
    __tablename__ = "seen_urls"
    __table_args__ = (UniqueConstraint("url_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    url_hash: Mapped[str] = mapped_column(String, nullable=False)


def test_sha256_url_is_deterministic():
    url = "https://example.com/articles/1"

    assert sha256_url(url) == sha256_url(url)
    assert len(sha256_url(url)) == 64


def test_idempotent_insert_duplicate_is_noop_for_sqlite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    record = {
        "url": "https://example.com/articles/1",
        "url_hash": sha256_url("https://example.com/articles/1"),
    }

    with Session(engine) as session:
        first = idempotent_insert(session, SeenUrl, record)
        second = idempotent_insert(session, SeenUrl, record)
        session.commit()

        count = session.scalar(select(func.count()).select_from(SeenUrl))

    assert first.rowcount == 1
    assert second.rowcount == 0
    assert count == 1
