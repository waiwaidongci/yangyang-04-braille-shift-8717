import json
from collections import Counter

from sqlalchemy import func, select

from src.domain.analysis import seed, seed_assignments
from src.models.base import Session, ensure_schema
from src.models.workflow import AnalysisRun, Assignment, Observation, Review, Schedule
from src.services.assignments import add_assignments, effective_assignments
from src.services.observations import clean_observation, content_key


def seed_data():
    ensure_schema()
    rows = [clean_observation(row) for row in seed()]
    counts = Counter(content_key(row) for row in rows)
    seen = Counter()
    with Session.begin() as db:
        keys = set(db.scalars(select(Observation.source_key)))
        for row in rows:
            key = content_key(row)
            seen[key] += 1
            if counts[key] > 1 and seen[key] > 1:
                key = f'{key}:{seen[key]}'
            if key not in keys:
                db.add(Observation(source_key=key, payload=row))
        known = {item.payload['team'] for item in effective_assignments(db)}
        fresh = [row for row in seed_assignments() if row['team'] not in known]
        if fresh:
            add_assignments(db, fresh, 'seed', 'assignment.seeded')
        db.flush()
        return {model.__tablename__: db.scalar(select(func.count(model.id)))
                for model in (Observation, Assignment, AnalysisRun, Review, Schedule)}


if __name__ == '__main__':
    print(json.dumps(seed_data(), sort_keys=True))
