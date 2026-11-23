from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config.runtime import DSN


class Base(DeclarativeBase):
    pass


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


engine = create_engine(DSN, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)


def ensure_schema():
    """Create missing tables and backfill columns added after the first deploy."""
    from src.models import workflow  # noqa: F401
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        columns = {column['name'] for column in inspect(connection).get_columns('analysis_runs')}
        additions = {
            'method': 'ALTER TABLE analysis_runs ADD COLUMN method VARCHAR(16) NULL',
            'assignment_ids': 'ALTER TABLE analysis_runs ADD COLUMN assignment_ids JSON NULL',
            'last_assignment_id': 'ALTER TABLE analysis_runs ADD COLUMN last_assignment_id INTEGER NULL',
        }
        for name, statement in additions.items():
            if name not in columns:
                connection.execute(text(statement))
        connection.execute(text("UPDATE analysis_runs SET method = 'v1' WHERE method IS NULL"))
