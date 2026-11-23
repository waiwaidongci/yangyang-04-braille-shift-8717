import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.config.project import SPEC
from src.domain import analysis
from src.models.workflow import Assignment, AuditEvent
from src.services.errors import BusinessError
from src.services.validation import validated

MAX_ASSIGNMENT_RECORDS = 2000


def clean_assignment(raw):
    row = validated(SPEC['assignment_fields'], raw)
    try:
        analysis.validate_assignment(row)
    except ValueError as exc:
        raise BusinessError(str(exc)) from exc
    return row


def effective_assignments(db):
    """Latest record per team: the assignment sheet as currently in force."""
    rows = list(db.scalars(select(Assignment).order_by(Assignment.id)))
    latest = {}
    for row in rows:
        latest[row.payload['team']] = row
    return sorted(latest.values(), key=lambda item: item.id)


def _record_key(row, supersedes):
    basis = json.dumps({'row': row, 'supersedes': supersedes}, sort_keys=True, ensure_ascii=False)
    return 'assign:' + hashlib.sha256(basis.encode()).hexdigest()


def add_assignments(db, rows, actor, action):
    current = {item.payload['team']: item for item in effective_assignments(db)}
    added = []
    try:
        for row in rows:
            team = row['team']
            existing = current.get(team)
            if existing is not None and all(existing.payload.get(key) == row.get(key)
                                            for key in ('machine', 'arm', 'note')):
                continue
            record = Assignment(source_key=_record_key(row, existing.id if existing else 0), payload=row)
            db.add(record)
            db.flush()
            current[team] = record
            added.append(record)
    except IntegrityError as exc:
        raise BusinessError('有相同分派记录刚刚写入，请刷新后重试', 409) from exc
    if db.scalar(select(func.count(Assignment.id))) > MAX_ASSIGNMENT_RECORDS:
        raise BusinessError(f'当前项目最多保留 {MAX_ASSIGNMENT_RECORDS} 条分派记录', 409)
    if added:
        db.add(AuditEvent(actor=actor, action=action, detail=f'新增 {len(added)} 条分派记录'))
    return added
