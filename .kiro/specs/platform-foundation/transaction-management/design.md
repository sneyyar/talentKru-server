# Design: Service-Layer Transaction Management

**Feature**: Transaction Management Refactoring  
**Subsystem**: Platform Foundation  
**Status**: Design Phase  
**Last Updated**: June 3, 2026

---

## Overview

This design establishes **service-layer transaction boundaries** where each service method that modifies state explicitly manages its own transaction lifecycle. This replaces the current pattern where routes implicitly commit and ensures atomic, testable operations.

---

## Architecture

### Current (Problematic) Flow

```
HTTP Request
    ↓
FastAPI Route Handler
    ├─ Create service instance
    ├─ Call service.create_x()  ← No transaction control
    ├─ await db.commit()         ← Route commits (wrong layer!)
    └─ Return response
    ↓
HTTP Response

Problems:
- Transaction control split across layers
- Services can't guarantee atomicity
- Tests can't validate transaction behavior
- Routes have DB responsibilities
```

### Target (Correct) Flow

```
HTTP Request
    ↓
FastAPI Route Handler
    ├─ Create service instance
    ├─ Call service.create_x()
    │   ├─ Begin transaction (async with)
    │   ├─ Perform work
    │   ├─ Commit on success
    │   └─ Rollback on error
    └─ Return response
    ↓
HTTP Response

Benefits:
- Transaction control centralized in service layer
- Services guarantee atomicity
- Tests validate transaction behavior
- Routes focus on HTTP concerns
```

---

## Components

### 1. Transaction Helper (`app/service_base.py`)

**Purpose**: Provide a reusable context manager for service-layer transactions.

**Design**:

```python
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from app.observability.logging import get_logger

logger = get_logger(__name__)

@asynccontextmanager
async def atomic_transaction(
    db: AsyncSession,
    operation_name: str,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for service-layer transactions.
    
    Wraps an operation in an explicit transaction with commit/rollback semantics:
    - On successful completion: commits transaction
    - On exception: rolls back transaction and re-raises
    
    Usage:
        async def create_candidate(self, org_id: UUID, first_name: str) -> Candidate:
            async with atomic_transaction(self.db, "create_candidate"):
                candidate = Candidate(organization_id=org_id, first_name=first_name)
                self.db.add(candidate)
                return candidate  # Commit on exit
    
    Args:
        db: SQLAlchemy AsyncSession instance
        operation_name: Descriptive name for logging (e.g., "create_candidate")
    
    Yields:
        The same AsyncSession (for consistency)
    
    Raises:
        Any exception raised within the context (after rollback)
    """
    try:
        yield db
        await db.commit()
        logger.info(
            "transaction_committed",
            operation=operation_name,
        )
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "transaction_rolled_back",
            operation=operation_name,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise
```

**Key Design Decisions**:

1. **Generic context manager**: Works for any service method without modification
2. **Logging at transaction boundaries**: Useful for debugging and observability
3. **Re-raises exceptions**: Caller (route) decides error handling
4. **Simple yield semantics**: Yields the same `db` session for ergonomics

**Alternative Patterns Considered**:

- **Decorator approach**: `@atomic_transaction("create_candidate")` — rejected because it requires passing `db` implicitly via context var (too magical)
- **Nested context managers**: `async with db.begin():` — rejected because SQLAlchemy's begin() doesn't play well with async sessions
- **Savepoint for nested txns**: Can be added later if services need to call other services

---

### 2. Database Layer Updates (`app/database.py`)

**Current Issues**:
- Auto-commits after yield
- `expire_on_commit=False` causes stale reads
- `autoflush=False` can cause consistency issues

**Target Configuration**:

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=True,    # Expire objects after commit (forces fresh queries)
    autoflush=True,           # Flush before queries (ensures consistency)
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.
    
    Transaction lifecycle:
    - Session begins on creation (implicit in asyncpg)
    - Caller (service layer) performs queries/mutations
    - Caller (service layer) commits via atomic_transaction context manager
    - If exception: caller rolls back via atomic_transaction context manager
    
    This dependency does NOT manage transaction lifecycle — that responsibility
    is entirely with the service layer. Routes should not call commit/rollback.
    
    Usage:
        @router.post("/candidates")
        async def create_candidate(
            request: CreateCandidateRequest,
            db: AsyncSession = Depends(get_db_session),
            principal: JWTPrincipal = Depends(require_auth),
        ):
            service = CandidateService(db)
            candidate = await service.create_candidate(
                organization_id=principal.organization_id,
                first_name=request.first_name,
            )
            return CandidateResponse.from_orm(candidate)
            # Service committed internally; no route-level commit
    """
    async with AsyncSessionFactory() as session:
        yield session
        # No commit/rollback here — service layer handles it
```

**Why These Changes**:

1. **`expire_on_commit=True`**: 
   - Objects are expired (detached) after commit
   - Forces fresh queries instead of using stale in-memory state
   - Matches production behavior (tests should mirror this)

2. **`autoflush=True`**: 
   - Flushes pending changes before any query
   - Ensures consistency between Python objects and database
   - Prevents surprises where updates aren't visible in same transaction

3. **No auto-commit**: 
   - Transaction lifecycle is explicit (service layer responsibility)
   - Routes can't accidentally commit partial state

---

### 3. Test Fixtures (`tests/conftest.py`)

**Current Issues**:
- Tests call `commit()` mid-execution
- Rollback at end doesn't undo mid-test commits
- Session config differs from production

**Target Configuration**:

```python
@pytest.fixture
async def db_session(async_session_factory):
    """
    Provides a database session for each test with rollback cleanup.
    
    Key points:
    - Session config matches production (expire_on_commit=True, autoflush=True)
    - Tests should NOT call commit() — services handle transactions
    - Rollback at end ensures clean state for next test
    - Services that call atomic_transaction internally commit/rollback as needed
    
    Sequence:
    1. Test begins with fresh session
    2. Test calls service.create_x() → service uses atomic_transaction
    3. atomic_transaction commits within the session
    4. Test sees committed data (session now has fresh objects after expire)
    5. Test ends → fixture calls rollback() to clean up
    
    The key insight: atomic_transaction commits within the session,
    but we rollback the whole session afterward for test cleanup.
    This validates that services properly commit, while tests stay clean.
    """
    async with async_session_factory() as session:
        yield session
        # Rollback to clean up test data (for next test)
        await session.rollback()
```

**Important Pattern for Service Tests**:

```python
@pytest.mark.asyncio
async def test_create_candidate_persists_data(db_session: AsyncSession, org_id):
    """
    Test that service.create_candidate() is atomic and persists data.
    
    This test validates:
    1. Service wraps operation in atomic_transaction
    2. Data is committed (visible via fresh session query)
    3. Rollback at fixture end cleans up test data
    """
    # Create candidate via service (which uses atomic_transaction)
    service = CandidateService(db_session)
    candidate = await service.create_candidate(
        organization_id=org_id,
        first_name="John",
        last_name="Doe",
    )
    
    # At this point:
    # - Service called atomic_transaction(db, "create_candidate")
    # - atomic_transaction committed the transaction
    # - Data is persisted in database
    # - Object in session is valid
    
    # Verify data is actually in database (not just in memory)
    # by querying fresh
    result = await db_session.execute(
        select(Candidate).where(Candidate.candidate_id == candidate.candidate_id)
    )
    fresh_candidate = result.scalar_one()
    assert fresh_candidate.first_name == "John"
    
    # When test ends, conftest rollback cleans up this test data
```

---

### 4. Service Layer Updates (All Modules)

**Current Pattern** (❌ No transaction control):
```python
class CandidateService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_candidate(self, org_id: UUID, first_name: str) -> Candidate:
        candidate = Candidate(organization_id=org_id, first_name=first_name)
        self.db.add(candidate)
        await self.db.flush()
        return candidate
        # No commit — route will commit (wrong!)
```

**Target Pattern** (✅ Service controls transaction):
```python
from app.service_base import atomic_transaction

class CandidateService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_candidate(self, org_id: UUID, first_name: str) -> Candidate:
        async with atomic_transaction(self.db, "create_candidate"):
            candidate = Candidate(organization_id=org_id, first_name=first_name)
            self.db.add(candidate)
            await self.db.flush()
            return candidate
            # atomic_transaction commits on exit (no exception)
            # If exception: atomic_transaction rolls back
```

**Pattern for Complex Operations**:

```python
async def create_candidate_with_skills(
    self,
    org_id: UUID,
    first_name: str,
    skills: list[SkillInput],
) -> Candidate:
    """Create candidate and assign skills atomically."""
    async with atomic_transaction(self.db, "create_candidate_with_skills"):
        # Create candidate
        candidate = Candidate(organization_id=org_id, first_name=first_name)
        self.db.add(candidate)
        await self.db.flush()
        
        # Assign skills (all within same transaction)
        for skill_input in skills:
            candidate_skill = CandidateSkill(
                candidate_id=candidate.candidate_id,
                skill_id=skill_input.skill_id,
            )
            self.db.add(candidate_skill)
        
        await self.db.flush()
        return candidate
        # atomic_transaction commits both candidate AND skills together
```

**Pattern for Read-Only Operations**:

```python
async def get_candidate(self, candidate_id: UUID, org_id: UUID) -> Candidate:
    """Get candidate — no transaction needed for read-only."""
    # No atomic_transaction wrapper needed
    result = await self.db.execute(
        select(Candidate).where(
            Candidate.candidate_id == candidate_id,
            Candidate.organization_id == org_id,
        )
    )
    return result.scalar_one_or_none()
```

---

### 5. Route Layer Updates (All Modules)

**Current Pattern** (❌ Routes commit):
```python
@router.post("/candidates")
async def create_candidate(
    request: CreateCandidateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    service = CandidateService(db)
    candidate = await service.create_candidate(...)
    await db.commit()  # ← WRONG: Route shouldn't commit
    return CandidateResponse.from_orm(candidate)
```

**Target Pattern** (✅ Service commits):
```python
@router.post("/candidates")
async def create_candidate(
    request: CreateCandidateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    service = CandidateService(db)
    candidate = await service.create_candidate(...)
    # Service already committed via atomic_transaction
    return CandidateResponse.from_orm(candidate)
```

---

### 6. Audit Field Population

**Current Implementation**:
- Audit fields are manually set in services (error-prone)
- No automatic population

**Target Implementation**:
- Use SQLAlchemy `SessionEvents.before_flush()` listener
- Automatically populate `created_by`, `updated_by`, `deleted_by`
- Works within service transactions

**Implementation** (`app/base_model.py`):

```python
from contextvars import ContextVar
from sqlalchemy import event
from sqlalchemy.orm import Session
from uuid import UUID

# Context var for current user (set by middleware)
current_user_id_var: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)

@event.listens_for(Session, "before_flush")
def receive_before_flush(session: Session, flush_context, instances):
    """Automatically populate audit fields on flush."""
    user_id = current_user_id_var.get()
    
    for instance in session.new:
        if hasattr(instance, "created_by"):
            instance.created_by = user_id
    
    for instance in session.dirty:
        if hasattr(instance, "updated_by"):
            instance.updated_by = user_id
    
    for instance in session.deleted:
        if hasattr(instance, "deleted_by"):
            instance.deleted_by = user_id
```

**Usage in Middleware**:

```python
# In auth middleware, after JWT validation:
from app.base_model import current_user_id_var

principal = await extract_jwt_principal(request)
current_user_id_var.set(principal.user_id)
```

**Benefits**:
- Services don't need to manually set audit fields
- Automatic for all entities with `AuditMixin`
- Testable in isolation

---

## Transaction Boundaries by Module

### Phase 1: Foundation (Platform Foundation)

#### `auth/service.py`
```python
async def login(...) -> Token:
    async with atomic_transaction(self.db, "auth_login"):
        # Query user, validate password, generate token
        ...

async def revoke_token(...):
    async with atomic_transaction(self.db, "auth_revoke"):
        # Create RevokedToken entry
        ...
```

#### `users/service.py`
```python
async def create_user(...) -> User:
    async with atomic_transaction(self.db, "create_user"):
        user = User(...)
        self.db.add(user)
        await self.db.flush()
        return user

async def update_user(...) -> User:
    async with atomic_transaction(self.db, "update_user"):
        user = await self._get_user(user_id)
        # Update fields
        await self.db.flush()
        return user
```

#### `organizations/service.py`
```python
async def create_organization(...) -> Organization:
    async with atomic_transaction(self.db, "create_organization"):
        org = Organization(...)
        self.db.add(org)
        await self.db.flush()
        return org
```

### Phase 2: Integration (Identity & Access)

#### `rbac/service.py`
```python
async def assign_role(...):
    async with atomic_transaction(self.db, "assign_role"):
        # Query user, add role
        ...

async def revoke_role(...):
    async with atomic_transaction(self.db, "revoke_role"):
        # Query role, soft delete
        ...
```

#### `invitations/service.py`
```python
async def accept_invitation(...) -> User:
    async with atomic_transaction(self.db, "accept_invitation"):
        invitation = await self._verify_token(token)
        user = await self._create_user_from_invitation(invitation, password)
        invitation.accepted_at = utcnow()
        return user
```

### Phase 3-6: Domain Services

Similar patterns for candidate, job, interview, and support services.

---

## Error Handling

### Design Principles

1. **No retries in service layer**: Retry logic lives in caller
2. **Full rollback on error**: Partial state is never persisted
3. **Error propagation**: Services raise exceptions; routes handle
4. **Consistent error context**: Correlation ID preserved across rollback

### Pattern

```python
async def create_candidate(...):
    async with atomic_transaction(self.db, "create_candidate"):
        # Validation errors
        if not first_name or not first_name.strip():
            raise ValueError("first_name is required")
        
        # Business logic errors
        if await self._first_name_exists(first_name):
            raise DuplicateError("Candidate already exists")
        
        # Database errors (constraints, etc.) propagate naturally
        candidate = Candidate(first_name=first_name)
        self.db.add(candidate)
        
        # All errors trigger rollback via atomic_transaction
        return candidate
```

---

## Testing Strategy

### Per-Service Test Pattern

```python
@pytest.mark.asyncio
async def test_create_candidate_commits_transaction(db_session, org_id):
    """Verify service commits data within transaction."""
    service = CandidateService(db_session)
    candidate = await service.create_candidate(org_id=org_id, first_name="John")
    
    # Service committed; data should be visible
    result = await db_session.execute(select(Candidate).where(...))
    assert result.scalar_one() is not None

@pytest.mark.asyncio
async def test_create_candidate_rollback_on_error(db_session, org_id):
    """Verify service rolls back on error."""
    service = CandidateService(db_session)
    
    with pytest.raises(ValueError):
        await service.create_candidate(org_id=org_id, first_name="")
    
    # Service rolled back; no data should exist
    result = await db_session.execute(select(Candidate))
    assert len(result.scalars().all()) == 0
```

### Integration Test Pattern

```python
@pytest.mark.asyncio
async def test_create_candidate_with_skills_is_atomic(db_session, org_id):
    """Verify multi-operation service is atomic."""
    service = CandidateService(db_session)
    
    # Success case
    candidate = await service.create_candidate_with_skills(
        org_id=org_id,
        first_name="John",
        skills=[...],
    )
    
    # Both candidate and skills should be persisted
    result = await db_session.execute(
        select(func.count(CandidateSkill.candidate_skill_id)).where(
            CandidateSkill.candidate_id == candidate.candidate_id
        )
    )
    assert result.scalar() == len(skills)
```

---

## Rollout Strategy

1. **Phase 1**: Implement `atomic_transaction`, update database layer, fixtures
2. **Phase 2**: Refactor core services, remove route commits
3. **Phase 3**: Refactor domain services, remove route commits
4. **Phase 4**: Refactor interview/support services, remove route commits
5. **Phase 5**: Run full test suite, verify regressions
6. **Phase 6**: Update documentation, declare complete

Each phase:
- Create branch
- Implement changes
- Run tests: `uv run invoke test`
- Code review
- Merge to main

---

## Success Criteria

| Criterion | Validation |
|-----------|-----------|
| No route commits | `grep -r "await db.commit" app/modules/*/router.py` returns empty |
| All services use atomic_transaction | Code review + grep |
| Session config consistent | `app/database.py` == `tests/conftest.py` |
| Test suite passes | `uv run invoke test` ✅ |
| Coverage maintained | >80% |
| Audit fields work | `test_audit_fields_populated` passes |
| Domain events atomic | `test_domain_event_persisted` passes |
| No performance regression | Benchmark before/after |

---

## References

- [ACID Properties](https://en.wikipedia.org/wiki/ACID)
- [SQLAlchemy Async Sessions](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Context Variables](https://docs.python.org/3/library/contextvars.html)
- [TransactionManagementAnalysis](../../../TRANSACTION_MANAGEMENT_ANALYSIS.md)

