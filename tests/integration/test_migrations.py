from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text


def test_alembic_upgrade_on_clean_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url))
    command.upgrade(cfg, "head")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "tenants" in tables
    assert "usage_events" in tables
    assert "stripe_events" in tables
    assert "alembic_version" in tables
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    from app.db.base import Base

    Base.metadata.create_all(engine)
