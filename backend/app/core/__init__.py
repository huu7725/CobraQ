# Core module exports
from .config import get_settings, Settings
from .security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    get_current_user,
    get_current_user_optional,
    require_role,
    Role,
)
from .audit import audit_log, AuditLogger, EventType
