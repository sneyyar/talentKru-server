"""
Thin shard routing placeholder for multi-tenant database access.

Currently always resolves to shard 0 (single-shard deployment).
The interface is defined now so future sharding logic can be dropped in
without changing call sites.
"""

from uuid import UUID

from app.database import engine


def get_shard_id(organization_id: UUID) -> int:
    """
    Resolve the database shard for the given organization.
    Currently always returns 0 (single-shard deployment).
    Future: look up Organization.shard_id and return the appropriate
    connection pool / engine for that shard.
    """
    return 0


def get_engine_for_org(organization_id: UUID):
    """Return the SQLAlchemy engine for the shard that owns this org."""
    shard = get_shard_id(organization_id)
    # shard 0 is the only shard; extend this dict for horizontal scaling
    shard_engines = {0: engine}
    return shard_engines[shard]
