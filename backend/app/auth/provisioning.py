"""Reconcile the stored RBAC grants with the policy in code.

Role -> permission grants live in the database (roles, permissions, role_permissions) but the policy
itself is code: ROLE_PERMISSIONS in app.auth.rbac. Without reconciliation an existing database keeps
whatever it was seeded with, so tightening or extending the policy would silently not take effect -
tests would pass (they seed fresh) while a running deployment kept the old grants.

This runs at startup, guarded by an advisory lock so concurrent workers cannot race each other.
"""
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.rbac import PERMISSION_DESCRIPTIONS, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS, RoleName
from app.models import Permission, Role

logger = logging.getLogger("careflow.rbac")
LOCK_ID = 606061  # distinct from the MRN allocation lock


def sync_role_permissions(db: Session) -> dict[str, list[str]]:
    """Make the stored grants match ROLE_PERMISSIONS. Returns what changed, for logging."""
    db.execute(select(func.pg_advisory_xact_lock(LOCK_ID)))
    known = {p.code: p for p in db.scalars(select(Permission))}
    for perm, description in PERMISSION_DESCRIPTIONS.items():
        row = known.get(perm.value)
        if row is None:
            row = Permission(code=perm.value, description=description)
            db.add(row)
            known[perm.value] = row
        else:
            row.description = description
    db.flush()

    changes: dict[str, list[str]] = {"granted": [], "revoked": []}
    for role in db.scalars(select(Role)):
        try:
            wanted = {p.value for p in ROLE_PERMISSIONS[RoleName(role.name)]}
        except (KeyError, ValueError):
            logger.warning("stored role has no policy in code", extra={"fields": {"role": role.name}})
            continue
        held = {p.code for p in role.permissions}
        for code in sorted(wanted - held):
            role.permissions.append(known[code])
            changes["granted"].append(f"{role.name}:{code}")
        for permission in [p for p in role.permissions if p.code not in wanted]:
            role.permissions.remove(permission)
            changes["revoked"].append(f"{role.name}:{permission.code}")
        role.description = ROLE_DESCRIPTIONS[RoleName(role.name)]
    db.flush()
    if changes["granted"] or changes["revoked"]:
        logger.info("role permissions reconciled", extra={"fields": changes})
    return changes
