from enum import StrEnum


class Role(StrEnum):
    VIEWER = 'viewer'
    ANALYST = 'analyst'
    SUPERVISOR = 'supervisor'


class RunStatus(StrEnum):
    QUEUED = 'queued'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'


class Method(StrEnum):
    LEGACY = 'v1'
    STRATIFIED = 'v2'


class Decision(StrEnum):
    APPROVED = 'approved'
    RETURNED = 'returned'
