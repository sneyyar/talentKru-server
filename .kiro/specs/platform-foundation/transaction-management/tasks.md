# Tasks: Service-Layer Transaction Management

**Feature**: Transaction Management Refactoring  
**Approach**: Approach B - Declarative `@transactional()` from Phase 1  
**Total Effort**: 21-26 hours (3-4 working days)  
**Status**: Ready for Implementation  

---

## Overview

This task list breaks down the complete transaction management refactoring into 25 specific, actionable tasks across 5 phases. Each task has clear success criteria and verification steps.

**Key Decision**: Implement the `@transactional()` decorator in Phase 1 (Task 1.3) so all phases 2-5 use clean decorator syntax from the start. This saves 5-10 hours of refactoring work compared to starting with context managers.

---

## Phase 1: Foundation (2 hours)

### Task 1.1: Fix Database Layer Configuration
**File**: `app/database.py`  
**Requirement**: Req-5 (Transaction Control in Service Layer)  
**Effort**: 10 minutes  

**What**: Update database session factory configuration to support service-layer transaction control.

**Changes**:
```python
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=True,      # ← Add this (was False)
    autoflush=True,              # ← Change to True
)
```

**Why**: 
- `expire_on_commit=True` forces fresh queries after commit (matches production behavior)
- `autoflush=True` ensures consistency between Python objects and database

**Verification**:
- [~] File modified and saved
- [~] Check: `grep -A 5 "async_sessionmaker" app/database.py` shows both settings

---

### Task 1.2: Create Service Base Helper
**File**: `app/service_base.py` (NEW)  
**Requirement**: Req-1 (Atomic Service Operations), Req-2 (Clear Transaction Boundaries)  
**Effort**: 5 minutes  

**What**: Create reusable context manager for service-layer transactions.

**Implementation**:
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
    
    Args:
        db: SQLAlchemy AsyncSession instance
        operation_name: Descriptive name for logging (e.g., "create_candidate")
    
    Yields:
        The same AsyncSession
    
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

**Verification**:
- [~] File created at `app/service_base.py`
- [~] Check: `python -c "from app.service_base import atomic_transaction"` works
- [~] Check: Context manager is properly async (has `__aenter__`, `__aexit__`)

---

### Task 1.3: Create Transaction Decorator (NEW - Approach B)
**File**: `app/decorators.py` (NEW)  
**Requirement**: Req-1 (Atomic Service Operations), Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**What**: Create reusable `@transactional()` and `@read_only` decorators for clean service method syntax.

**Implementation**:
```python
from functools import wraps
from typing import Callable, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.service_base import atomic_transaction

def transactional(name: Optional[str] = None) -> Callable:
    """
    Decorator for service methods that modify state.
    
    Wraps the method in atomic_transaction automatically.
    Use for all write operations.
    
    Usage:
        @transactional()
        async def create_candidate(self, ...):
            # Just do the work, decorator handles transaction
            candidate = Candidate(...)
            self.db.add(candidate)
            return candidate
        
        @transactional(name="custom_operation_name")
        async def multi_step_operation(self, ...):
            # Complex operation with custom name for logging
            ...
    
    Args:
        name: Optional custom name for logging (defaults to method name)
    
    Returns:
        Decorated async method
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs) -> Any:
            operation_name = name or func.__name__
            async with atomic_transaction(self.db, operation_name):
                return await func(self, *args, **kwargs)
        return wrapper
    return decorator


def read_only(func: Callable) -> Callable:
    """
    Decorator for service methods that only read data.
    
    Does NOT wrap in transaction. Use for queries only.
    
    Usage:
        @read_only
        async def get_candidate(self, candidate_id):
            result = await self.db.execute(select(Candidate).where(...))
            return result.scalar_one_or_none()
    
    Returns:
        Original method (no modification)
    """
    # Intentionally a no-op; provides explicit intent marker
    @wraps(func)
    async def wrapper(self, *args, **kwargs) -> Any:
        return await func(self, *args, **kwargs)
    return wrapper
```

**Verification**:
- [~] File created at `app/decorators.py`
- [~] Check: `python -c "from app.decorators import transactional, read_only"` works
- [~] Check: Decorators are callable and return wrapped functions
- [~] Check: `@transactional()` can be called with and without `name` parameter

---

### Task 1.4: Verify Audit Listener Implementation
**File**: `app/base_model.py`  
**Requirement**: Req-3 (Audit Trail Integration)  
**Effort**: 15 minutes  

**What**: Verify that SQLAlchemy `before_flush` listener automatically populates audit fields.

**Implementation** (if not already present):
```python
from contextvars import ContextVar
from sqlalchemy import event
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime

# Context var set by middleware
current_user_id_var: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)

@event.listens_for(Session, "before_flush")
def receive_before_flush(session: Session, flush_context, instances):
    """Automatically populate audit fields on flush."""
    user_id = current_user_id_var.get()
    timestamp = datetime.utcnow()
    
    for instance in session.new:
        if hasattr(instance, "created_by") and instance.created_by is None:
            instance.created_by = user_id
        if hasattr(instance, "created_at") and instance.created_at is None:
            instance.created_at = timestamp
    
    for instance in session.dirty:
        if hasattr(instance, "updated_by"):
            instance.updated_by = user_id
        if hasattr(instance, "updated_at"):
            instance.updated_at = timestamp
    
    for instance in session.deleted:
        if hasattr(instance, "deleted_by") and instance.deleted_by is None:
            instance.deleted_by = user_id
        if hasattr(instance, "deleted_at") and instance.deleted_at is None:
            instance.deleted_at = timestamp
```

**Verification**:
- [~] Listener is registered in `app/base_model.py`
- [~] Check: `grep -n "before_flush" app/base_model.py` shows listener
- [~] Check: Listener handles new, dirty, and deleted instances

---

### Task 1.5: Update Test Fixtures for Transaction Isolation
**File**: `tests/conftest.py`  
**Requirement**: Req-4 (Test Fixture Alignment)  
**Effort**: 10 minutes  

**What**: Update test fixtures to use production-like session configuration and rollback cleanup.

**Changes**:
```python
@pytest.fixture
async def db_session(async_session_factory):
    """
    Provides a database session for each test with rollback cleanup.
    
    Session config matches production:
    - expire_on_commit=True
    - autoflush=True
    
    Lifecycle:
    1. Test begins with fresh session
    2. Test calls service.create_x() → service uses @transactional()
    3. @transactional() commits within the session
    4. Test sees committed data
    5. Test ends → fixture rolls back for next test
    """
    async with async_session_factory() as session:
        yield session
        # Rollback cleans up test data
        await session.rollback()
```

**Verify existing fixture matches production config**:
- [~] `async_session_factory` has `expire_on_commit=True`
- [~] `async_session_factory` has `autoflush=True`
- [~] Fixture rolls back after yield

**Verification**:
- [~] Check: `grep -A 10 "def db_session" tests/conftest.py` shows rollback

---

### Task 1.6: Add Audit Context Setup in Middleware
**File**: `app/middleware/auth_extraction.py`  
**Requirement**: Req-3 (Audit Trail Integration)  
**Effort**: 5 minutes  

**What**: Set current user ID in context variable after JWT validation.

**Changes** (in auth extraction middleware):
```python
from app.base_model import current_user_id_var

async def auth_extraction_middleware(request: Request, call_next):
    # ... existing JWT extraction code ...
    
    principal = await extract_jwt_principal(request)
    if principal:
        # Set context var for audit listener
        current_user_id_var.set(principal.user_id)
        request.state.principal = principal
    
    response = await call_next(request)
    return response
```

**Verification**:
- [~] Middleware imports `current_user_id_var`
- [~] Middleware sets context var after auth

---

### Task 1.7: Run Phase 1 Validation Tests
**Command**: `uv run invoke test`  
**Requirement**: Req-6 (Test Validation), Req-7 (Success Criteria)  
**Effort**: 10 minutes  

**What**: Run full test suite to verify Phase 1 infrastructure works.

**Validation Checklist**:
- [~] All existing tests still pass: `uv run invoke test` → All green ✅
- [~] No import errors from new modules (service_base, decorators)
- [~] No errors in conftest fixtures
- [~] Coverage maintained: >80%

**Success**: Phase 1 foundation is solid and ready for module refactoring.

---

## Phase 2: Core Services (4 hours)

### Module Pattern for All Tasks
Each module (auth, users, organizations, rbac, invitations, password_reset) follows this pattern:

**In `service.py`**:
```python
from app.decorators import transactional, read_only

class XyzService:
    @transactional()
    async def create_xyz(self, ...):
        xyz = Xyz(...)
        self.db.add(xyz)
        await self.db.flush()
        return xyz
    
    @transactional(name="complex_operation")
    async def complex_xyz_operation(self, ...):
        # Multiple steps, all atomic
        ...
    
    @read_only
    async def get_xyz(self, ...):
        result = await self.db.execute(select(Xyz).where(...))
        return result.scalar_one_or_none()
```

**In `router.py`**:
```python
@router.post("/xyz")
async def create_xyz(
    request: CreateXyzRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: JWTPrincipal = Depends(require_auth),
):
    service = XyzService(db)
    xyz = await service.create_xyz(...)
    # No await db.commit() — service committed internally
    return XyzResponse.from_orm(xyz)
```

---

### Task 2.1: Refactor Auth Service
**File**: `app/modules/auth/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 20 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def login(self, email: str, password: str) -> Token:
    # Existing code

@transactional()
async def register(self, email: str, password: str) -> User:
    # Existing code

@transactional(name="revoke_token")
async def revoke_token(self, token_id: UUID) -> None:
    # Existing code

@read_only
async def verify_token(self, token: str) -> JWTPrincipal:
    # Existing code (no decorator wrapping needed)
```

**Remove**: Any `async with atomic_transaction(...)` context managers (if present)

**Verification**:
- [~] All write methods have `@transactional()` decorator
- [~] Read methods have `@read_only` decorator
- [~] Check: `grep -n "@transactional" app/modules/auth/service.py` shows decorators
- [~] Tests pass: `uv run pytest tests/test_auth_service.py -v`

---

### Task 2.2: Update Auth Router (Remove Commits)
**File**: `app/modules/auth/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 10 minutes  

**What**: Remove all `await db.commit()` calls from routes.

**Changes**:
```python
@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    service = AuthService(db)
    token = await service.login(request.email, request.password)
    # Remove: await db.commit()
    return {"access_token": token}
```

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/auth/router.py` returns nothing
- [~] Routes still work: `uv run invoke dev` and test login endpoint
- [~] Tests pass: `uv run pytest tests/test_auth_router.py -v`

---

### Task 2.3: Refactor Users Service
**File**: `app/modules/users/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 20 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def create_user(self, ...) -> User:
    # Create user with all fields

@transactional()
async def update_user(self, user_id: UUID, **updates) -> User:
    # Update user fields

@transactional()
async def deactivate_user(self, user_id: UUID) -> None:
    # Soft delete

@read_only
async def get_user(self, user_id: UUID) -> User | None:
    # Query user
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_user_service.py -v`

---

### Task 2.4: Update Users Router (Remove Commits)
**File**: `app/modules/users/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 10 minutes  

**What**: Remove all `await db.commit()` calls from routes.

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/users/router.py` returns nothing
- [~] Tests pass: `uv run pytest tests/test_user_service.py tests/test_user_router.py -v`

---

### Task 2.5: Refactor Organizations Service
**File**: `app/modules/organizations/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 20 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_organizations.py -v`

---

### Task 2.6: Update Organizations Router (Remove Commits)
**File**: `app/modules/organizations/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 10 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/organizations/router.py` returns nothing

---

### Task 2.7: Refactor RBAC Service
**File**: `app/modules/rbac/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 20 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def assign_role(self, ...) -> UserRole:
    # Assign role to user

@transactional()
async def revoke_role(self, ...) -> None:
    # Remove role from user

@read_only
async def get_user_roles(self, user_id: UUID) -> list[Role]:
    # Query roles
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_rbac_service.py -v`

---

### Task 2.8: Update RBAC Router (Remove Commits)
**File**: `app/modules/rbac/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 10 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/rbac/router.py` returns nothing

---

### Task 2.9: Refactor Invitations Service
**File**: `app/modules/invitations/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 20 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def create_invitation(self, ...) -> Invitation:
    # Create invitation token

@transactional()
async def accept_invitation(self, token: str, ...) -> User:
    # Accept invitation and create user (multi-step atomic)

@transactional()
async def revoke_invitation(self, invitation_id: UUID) -> None:
    # Revoke invitation

@read_only
async def verify_invitation_token(self, token: str) -> Invitation | None:
    # Verify token
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_invitation_service.py -v`

---

### Task 2.10: Update Invitations Router (Remove Commits)
**File**: `app/modules/invitations/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 10 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/invitations/router.py` returns nothing

---

### Task 2.11: Refactor Password Reset Service
**File**: `app/modules/password_reset/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 20 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def request_reset(self, email: str) -> PasswordResetToken:
    # Create reset token

@transactional()
async def reset_password(self, token: str, new_password: str) -> User:
    # Verify token, update password, revoke token (multi-step)

@read_only
async def verify_reset_token(self, token: str) -> PasswordResetToken | None:
    # Verify token validity
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_password_reset_service.py -v`

---

### Task 2.12: Update Password Reset Router (Remove Commits)
**File**: `app/modules/password_reset/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 10 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/password_reset/router.py` returns nothing

---

### Task 2.13: Phase 2 Integration Tests
**Command**: `uv run invoke test`  
**Requirement**: Req-6 (Test Validation)  
**Effort**: 10 minutes  

**What**: Run complete test suite for Phase 2 modules.

**Verification**:
- [~] All tests pass: `uv run pytest tests/test_auth*.py tests/test_user*.py tests/test_org*.py tests/test_rbac*.py tests/test_invitation*.py tests/test_password*.py -v`
- [~] No transaction errors
- [~] No data inconsistencies
- [~] All existing tests still pass

**Success**: Phase 2 complete — 6 core services use clean decorator syntax.

---

## Phase 3: Candidate & Job Management (5-6 hours)

### Task 3.1: Refactor Candidates Service
**File**: `app/modules/candidates/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def create_candidate(self, ...) -> Candidate:
    # Create candidate

@transactional()
async def update_candidate(self, candidate_id: UUID, **updates) -> Candidate:
    # Update candidate fields

@transactional()
async def archive_candidate(self, candidate_id: UUID) -> None:
    # Archive candidate

@transactional(name="bulk_update_candidates")
async def bulk_update_candidates(self, candidate_ids: list[UUID], **updates) -> int:
    # Update multiple candidates atomically

@read_only
async def get_candidate(self, candidate_id: UUID) -> Candidate | None:
    # Query candidate

@read_only
async def list_candidates(self, org_id: UUID, ...) -> list[Candidate]:
    # Query candidates with filters
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_candidate_service.py -v`

---

### Task 3.2: Update Candidates Router (Remove Commits)
**File**: `app/modules/candidates/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/candidates/router.py` returns nothing

---

### Task 3.3: Refactor Resumes Service
**File**: `app/modules/resumes/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def upload_resume(self, candidate_id: UUID, file: UploadFile) -> Resume:
    # Upload and parse resume

@transactional(name="parse_and_extract_resume")
async def parse_and_extract_resume(self, resume_id: UUID) -> Resume:
    # Parse and extract skills (multi-step atomic)

@transactional()
async def delete_resume(self, resume_id: UUID) -> None:
    # Delete resume

@read_only
async def get_resume(self, resume_id: UUID) -> Resume | None:
    # Query resume
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_resume_ingestion_service.py -v`

---

### Task 3.4: Update Resumes Router (Remove Commits)
**File**: `app/modules/resumes/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/resumes/router.py` returns nothing

---

### Task 3.5: Refactor Skills Service
**File**: `app/modules/skills/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def create_skill(self, ...) -> Skill:
    # Create skill

@transactional(name="assign_candidate_skills")
async def assign_candidate_skills(
    self, 
    candidate_id: UUID, 
    skills: list[SkillInput]
) -> list[CandidateSkill]:
    # Assign multiple skills atomically

@transactional()
async def update_skill_proficiency(self, ...) -> CandidateSkill:
    # Update proficiency level

@read_only
async def get_candidate_skills(self, candidate_id: UUID) -> list[CandidateSkill]:
    # Query candidate skills
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_skills_service.py -v`

---

### Task 3.6: Update Skills Router (Remove Commits)
**File**: `app/modules/skills/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/skills/router.py` returns nothing

---

### Task 3.7: Refactor Requisitions Service
**File**: `app/modules/requisitions/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def create_requisition(self, ...) -> Requisition:
    # Create job requisition

@transactional()
async def update_requisition(self, requisition_id: UUID, **updates) -> Requisition:
    # Update requisition

@transactional()
async def close_requisition(self, requisition_id: UUID) -> None:
    # Close requisition

@read_only
async def get_requisition(self, requisition_id: UUID) -> Requisition | None:
    # Query requisition
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_requisition_integration.py -v`

---

### Task 3.8: Update Requisitions Router (Remove Commits)
**File**: `app/modules/requisitions/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/requisitions/router.py` returns nothing

---

### Task 3.9: Refactor Job Posting Service
**File**: `app/modules/job_posting/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_job_posting_service.py -v`

---

### Task 3.10: Update Job Posting Router (Remove Commits)
**File**: `app/modules/job_posting/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/job_posting/router.py` returns nothing

---

### Task 3.11: Refactor Job Profile Service
**File**: `app/modules/job_profile/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_job_profile*.py -v`

---

### Task 3.12: Update Job Profile Router (Remove Commits)
**File**: `app/modules/job_profile/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/job_profile/router.py` returns nothing

---

### Task 3.13: Phase 3 Integration Tests
**Command**: `uv run invoke test`  
**Requirement**: Req-6 (Test Validation)  
**Effort**: 15 minutes  

**What**: Run complete test suite for Phase 3 modules.

**Verification**:
- [~] All tests pass: `uv run pytest tests/test_candidate*.py tests/test_resume*.py tests/test_skills*.py tests/test_job*.py tests/test_requisition*.py -v`
- [ ] All existing tests still pass
- [ ] Coverage maintained: >80%

**Success**: Phase 3 complete — 6 domain services use clean decorator syntax.

---

## Phase 4: Interview & Support Services (8-10 hours)

### Task 4.1: Refactor Journeys Service
**File**: `app/modules/journeys/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def create_journey(self, ...) -> InterviewJourney:
    # Create interview journey

@transactional(name="transition_journey_stage")
async def transition_journey_stage(self, journey_id: UUID, next_stage: str) -> InterviewJourney:
    # Transition to next stage

@transactional()
async def cancel_journey(self, journey_id: UUID) -> None:
    # Cancel journey

@read_only
async def get_journey(self, journey_id: UUID) -> InterviewJourney | None:
    # Query journey
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_journeys*.py -v`

---

### Task 4.2: Update Journeys Router (Remove Commits)
**File**: `app/modules/journeys/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/journeys/router.py` returns nothing

---

### Task 4.3: Refactor Interviews Service
**File**: `app/modules/interviews/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_interviews*.py -v`

---

### Task 4.4: Update Interviews Router (Remove Commits)
**File**: `app/modules/interviews/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/interviews/router.py` returns nothing

---

### Task 4.5: Refactor Questionnaires Service
**File**: `app/modules/questionnaires/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_questionnaire*.py -v`

---

### Task 4.6: Update Questionnaires Router (Remove Commits)
**File**: `app/modules/questionnaires/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/questionnaires/router.py` returns nothing

---

### Task 4.7: Refactor Privacy Service
**File**: `app/modules/privacy/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional()
async def create_dsar_request(self, ...) -> DSARRequest:
    # Create data subject access request

@transactional(name="process_dsar_request")
async def process_dsar_request(self, dsar_id: UUID) -> DSARRequest:
    # Process request (fetch data, create archive) — multi-step atomic

@transactional()
async def deny_dsar_request(self, dsar_id: UUID, reason: str) -> None:
    # Deny request

@read_only
async def get_dsar_request(self, dsar_id: UUID) -> DSARRequest | None:
    # Query request
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_privacy_service.py tests/test_dsar*.py -v`

---

### Task 4.8: Update Privacy Router (Remove Commits)
**File**: `app/modules/privacy/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/privacy/router.py` returns nothing

---

### Task 4.9: Refactor Portal Service
**File**: `app/modules/portal/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_portal*.py -v`

---

### Task 4.10: Update Portal Router (Remove Commits)
**File**: `app/modules/portal/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/portal/router.py` returns nothing

---

### Task 4.11: Refactor Matching Service
**File**: `app/modules/matching/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator.

**Methods to decorate**:
```python
@transactional(name="generate_candidate_matches")
async def generate_candidate_matches(self, requisition_id: UUID) -> list[Match]:
    # Query candidates, score matches, store results — multi-step atomic

@transactional()
async def mark_match_viewed(self, match_id: UUID) -> Match:
    # Mark match as viewed

@read_only
async def get_matches_for_requisition(self, requisition_id: UUID) -> list[Match]:
    # Query matches
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_matching*.py -v`

---

### Task 4.12: Update Matching Router (Remove Commits)
**File**: `app/modules/matching/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/matching/router.py` returns nothing

---

### Task 4.13: Refactor Reporting Service
**File**: `app/modules/reporting/service.py`  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 30 minutes  

**What**: Wrap all write methods in `@transactional()` decorator (mostly read-only).

**Methods to decorate**:
```python
@transactional()
async def cache_leaderboard_data(self, org_id: UUID) -> ReportCache:
    # Generate and cache leaderboard

@read_only
async def get_interview_leaderboard(self, org_id: UUID) -> Leaderboard:
    # Query cached leaderboard

@read_only
async def get_recruitment_metrics(self, org_id: UUID) -> Metrics:
    # Query metrics
```

**Verification**:
- [ ] All write methods have `@transactional()` decorator
- [~] Tests pass: `uv run pytest tests/test_reporting*.py -v`

---

### Task 4.14: Update Reporting Router (Remove Commits)
**File**: `app/modules/reporting/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 15 minutes  

**Verification**:
- [~] Check: `grep "await db.commit" app/modules/reporting/router.py` returns nothing

---

### Task 4.15: Phase 4 Integration Tests
**Command**: `uv run invoke test`  
**Requirement**: Req-6 (Test Validation)  
**Effort**: 20 minutes  

**What**: Run complete test suite for Phase 4 modules.

**Verification**:
- [~] All tests pass: `uv run pytest tests/test_journeys*.py tests/test_interviews*.py tests/test_questionnaire*.py tests/test_privacy*.py tests/test_portal*.py tests/test_matching*.py tests/test_reporting*.py -v`
- [ ] All existing tests still pass
- [ ] Coverage maintained: >80%

**Success**: Phase 4 complete — 7+ support services use clean decorator syntax.

---

## Phase 5: Verification & Finalization (2-3 hours)

### Task 5.1: Full Test Suite Validation
**Command**: `uv run invoke test`  
**Requirement**: Req-6 (Test Validation), Req-7 (Success Criteria)  
**Effort**: 15 minutes  

**What**: Run complete test suite to verify all refactoring.

**Verification**:
- [~] All tests pass: `uv run invoke test` → All green ✅
- [~] No transaction-related errors
- [~] No data inconsistency errors
- [~] No timeout issues

**Success**: All 25 tasks implemented correctly.

---

### Task 5.2: Verify Zero Route Commits
**Command**: `grep -r "await db.commit" app/modules/*/router.py`  
**Requirement**: Req-2 (Clear Transaction Boundaries)  
**Effort**: 5 minutes  

**What**: Verify no commits remain in route handlers.

**Verification**:
- [~] Command returns empty (no route commits)
- [~] If found: Remove any remaining `await db.commit()` calls

**Success**: Transaction control is entirely in service layer.

---

### Task 5.3: Verify All Services Use Decorators
**Command**: Check each service file  
**Requirement**: Req-1 (Atomic Service Operations)  
**Effort**: 10 minutes  

**What**: Verify all service write methods have decorators.

**Quick Check**:
```bash
# Check each service has decorators
for module in auth users organizations rbac invitations password_reset candidates resumes skills requisitions job_posting job_profile journeys interviews questionnaires privacy portal matching reporting; do
  grep "@transactional\|@read_only" app/modules/$module/service.py | head -2
done
```

**Verification**:
- [~] Each service shows decorator usage
- [~] No `atomic_transaction` context managers in service code (all converted to decorators)

**Success**: Clean decorator syntax used everywhere.

---

### Task 5.4: Verify Audit Fields Population
**File**: Tests  
**Requirement**: Req-3 (Audit Trail Integration)  
**Effort**: 10 minutes  

**What**: Run tests that verify audit fields are automatically populated.

**Test Command**:
```bash
uv run pytest -k "audit" -v
```

**Verification**:
- [~] Audit field tests pass
- [~] `created_by`, `updated_by`, `deleted_by` are set automatically
- [~] Context variable integration works

**Success**: Audit trail is automatic and complete.

---

### Task 5.5: Verify Domain Events Atomicity
**File**: Tests  
**Requirement**: Req-5 (Domain Events Integration)  
**Effort**: 10 minutes  

**What**: Run tests that verify domain events are committed atomically with main operation.

**Test Command**:
```bash
uv run pytest tests/test_domain_events* -v
```

**Verification**:
- [~] Domain event tests pass
- [~] Events are persisted atomically with main operation
- [~] No orphaned events on rollback

**Success**: Event system is transactional.

---

### Task 5.6: Performance Validation (Optional)
**Command**: Benchmark test  
**Requirement**: Req-7 (Success Criteria - No Performance Regression)  
**Effort**: 15 minutes  

**What**: Compare performance before/after transaction refactoring.

**Option A - Quick Benchmark**:
```bash
# Run test suite with timing
time uv run invoke test
```

**Option B - Load Test**:
```bash
# Create test script that measures throughput
uv run python scripts/benchmark_transactions.py
```

**Verification**:
- [~] No significant performance regression
- [~] Response times acceptable
- [~] Throughput acceptable

**Success**: Transaction management has no negative performance impact.

---

### Task 5.7: Update Documentation
**Files**: 
- `README.md` (transaction management section)
- `.kiro/steering/tech.md` (add transaction patterns)  
- Architecture docs  
**Requirement**: Req-8 (Documentation Updates)  
**Effort**: 15 minutes  

**What**: Update project documentation with transaction patterns.

**Changes**:
1. Add transaction management section to `.kiro/steering/tech.md`
2. Document `@transactional()` decorator usage
3. Document pattern applied to all services
4. Link to this spec for reference

**Verification**:
- [~] Documentation is clear and complete
- [~] Developers can understand pattern from docs alone
- [~] Future developers will follow same pattern

**Success**: Documentation is up-to-date and helpful.

---

### Task 5.8: Audit Cross-Service Workflows (Optional)
**File**: Review all route files  
**Requirement**: Req-1 (Service-Layer Boundaries)  
**Effort**: 15 minutes  

**What**: Identify any routes that call multiple services and ensure they handle transactions correctly.

**Why**: If a route calls service1, then service2, and service2 fails after service1 commits, you have partial failure.

**Search Commands**:
```bash
# Find routes that might call multiple services
for file in app/modules/*/router.py; do
  count=$(grep -c "Service(db)" "$file")
  if [ "$count" -gt 1 ]; then
    echo "⚠️  $file has $count service instantiations"
    grep -n "Service(db)" "$file"
  fi
done

# Find routes with explicit commits (should be zero after phases 1-4)
grep -n "await db.commit" app/modules/*/router.py
```

**Expected Result**:
- Most routes should call **only ONE service** (safe)
- Multi-step operations should be **within the service** (safe)
- Zero route-level commits (removed in earlier phases)

**If found - Cross-Service Routes**:
If a route calls multiple services that must succeed together, create an **Orchestration Service**:

```python
# app/modules/workflows/orchestration_service.py
from app.decorators import transactional

class WorkflowOrchestration:
    @transactional(name="multi_service_workflow")
    async def execute(self, ...):
        # Call multiple services within single transaction
        result1 = await self.service1._raw_method(...)  # No commit
        result2 = await self.service2._raw_method(...)  # No commit
        # Both committed together or both rolled back
        return (result1, result2)
```

**Verification**:
- [~] Checked all route files for multi-service calls
- [~] Either: No cross-service routes found (most likely) ✅
- [~] Or: Created Orchestration Services for any found ✅
- [~] All routes delegate to services (no route commits) ✅

**Reference**: See CROSS_SERVICE_TRANSACTIONS.md for detailed pattern

---

### Task 5.9: Final Validation & Handoff
**Requirement**: Req-7 (Success Criteria - All Criteria Met)  
**Effort**: 5 minutes  

**What**: Verify all success criteria are met and mark complete.

**Final Checklist**:
- [~] All 25 tasks completed (or 26 with Task 5.8)
- [~] All tests pass: `uv run invoke test` ✅
- [~] Coverage >80%: `uv run invoke test-cov` ✅
- [~] Zero route commits: `grep "await db.commit" app/modules/*/router.py` ↓ (empty)
- [~] All services use decorators: Manual verification ✅
- [~] Audit fields work: Tests pass ✅
- [~] Domain events atomic: Tests pass ✅
- [~] Cross-service workflows audited: Task 5.8 ✅
- [~] Performance acceptable: Benchmark OK ✅
- [~] Documentation updated: ✅

**Success**: Transaction management refactoring is COMPLETE and PRODUCTION-READY! 🚀

---

## Task Dependency Graph

```
Phase 1 (Foundation)
  ├─ 1.1: Fix database layer
  ├─ 1.2: Create service base
  ├─ 1.3: Create decorators ← NEW (Approach B)
  ├─ 1.4: Verify audit listener
  ├─ 1.5: Update test fixtures
  ├─ 1.6: Add audit middleware
  └─ 1.7: Run tests
        ↓
Phase 2 (Core Services - 6 modules)
  ├─ 2.1-2.2: Auth service + router
  ├─ 2.3-2.4: Users service + router
  ├─ 2.5-2.6: Organizations service + router
  ├─ 2.7-2.8: RBAC service + router
  ├─ 2.9-2.10: Invitations service + router
  ├─ 2.11-2.12: Password reset service + router
  └─ 2.13: Integration tests
        ↓
Phase 3 (Domain Services - 6 modules)
  ├─ 3.1-3.2: Candidates service + router
  ├─ 3.3-3.4: Resumes service + router
  ├─ 3.5-3.6: Skills service + router
  ├─ 3.7-3.8: Requisitions service + router
  ├─ 3.9-3.10: Job posting service + router
  ├─ 3.11-3.12: Job profile service + router
  └─ 3.13: Integration tests
        ↓
Phase 4 (Support Services - 7+ modules)
  ├─ 4.1-4.2: Journeys service + router
  ├─ 4.3-4.4: Interviews service + router
  ├─ 4.5-4.6: Questionnaires service + router
  ├─ 4.7-4.8: Privacy service + router
  ├─ 4.9-4.10: Portal service + router
  ├─ 4.11-4.12: Matching service + router
  ├─ 4.13-4.14: Reporting service + router
  └─ 4.15: Integration tests
        ↓
Phase 5 (Verification)
  ├─ 5.1: Full test suite
  ├─ 5.2: Verify zero route commits
  ├─ 5.3: Verify decorator usage
  ├─ 5.4: Verify audit fields
  ├─ 5.5: Verify domain events
  ├─ 5.6: Performance validation
  ├─ 5.7: Update documentation
  └─ 5.8: Final validation
        ↓
COMPLETE ✅ Production-ready transaction management
```

---

## Success Criteria Summary

| Criterion | How to Verify | Status |
|-----------|--------------|--------|
| No route commits | `grep "await db.commit" app/modules/*/router.py` returns empty | Pending |
| All services use `@transactional()` | Code review + grep all services | Pending |
| Session config: `expire_on_commit=True`, `autoflush=True` | `app/database.py` inspection | Pending |
| Test fixtures match production | `tests/conftest.py` inspection | Pending |
| All tests pass | `uv run invoke test` ✅ | Pending |
| Coverage maintained | >80% (`uv run invoke test-cov`) | Pending |
| Audit fields work | `test_audit_fields_populated` passes | Pending |
| Domain events atomic | `test_domain_event_persisted` passes | Pending |
| No performance regression | Benchmark before/after acceptable | Pending |
| Documentation updated | `.kiro/steering/tech.md` includes patterns | Pending |

---

## Implementation Notes

### Code Examples

**Using `@transactional()` decorator**:
```python
from app.decorators import transactional, read_only

class CandidateService:
    @transactional()
    async def create_candidate(self, org_id: UUID, first_name: str) -> Candidate:
        """Create candidate with automatic transaction management."""
        candidate = Candidate(organization_id=org_id, first_name=first_name)
        self.db.add(candidate)
        await self.db.flush()
        return candidate
    
    @transactional(name="bulk_import_candidates")
    async def bulk_import_candidates(self, org_id: UUID, rows: list[dict]) -> list[Candidate]:
        """Import multiple candidates atomically."""
        candidates = []
        for row in rows:
            candidate = Candidate(organization_id=org_id, **row)
            self.db.add(candidate)
            candidates.append(candidate)
        await self.db.flush()
        return candidates
    
    @read_only
    async def get_candidate(self, candidate_id: UUID) -> Candidate | None:
        """Get candidate (read-only, no transaction)."""
        result = await self.db.execute(
            select(Candidate).where(Candidate.candidate_id == candidate_id)
        )
        return result.scalar_one_or_none()
```

**Router with no commits**:
```python
@router.post("/candidates")
async def create_candidate(
    request: CreateCandidateRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: JWTPrincipal = Depends(require_auth),
):
    """Create candidate (service handles transaction)."""
    service = CandidateService(db)
    candidate = await service.create_candidate(
        org_id=principal.organization_id,
        first_name=request.first_name,
    )
    # Service already committed via @transactional() decorator
    return CandidateResponse.from_orm(candidate)
```

### Running Tasks

**Per-task**: 
```bash
# After completing each task, verify with tests
uv run pytest tests/test_module_name.py -v
```

**Per-phase**:
```bash
# After completing each phase, run related tests
uv run pytest tests/test_phase2*.py -v
```

**Full validation**:
```bash
# After all phases complete
uv run invoke test
uv run invoke test-cov
```

---

## References

- **Specification**: `requirements.md`, `design.md`
- **Comparison**: `DECLARATIVE_TRANSACTIONS_COMPARISON.md`
- **Problem Analysis**: `TRANSACTION_MANAGEMENT_ANALYSIS.md`
- **Enhancement**: `DECLARATIVE_ENHANCEMENT.md`
- **Tech Stack**: `.kiro/steering/tech.md`

---

## Notes

- **Approach B**: Decorator created in Phase 1 (Task 1.3), used by all phases 2-5
- **Context Manager**: Still exists in `app/service_base.py` as foundation; decorator wraps it
- **Backward Compatibility**: If a service absolutely needs raw context manager, can still use `atomic_transaction` directly
- **Testing**: All tests updated to use production-like session config
- **Performance**: No regressions expected; explicit transactions slightly more efficient

---

**Status**: ✅ Ready for Implementation

Begin with Phase 1 to establish transaction infrastructure, then proceed systematically through phases 2-5. After each phase, run tests to verify progress.

Total estimated time: **21-26 hours** (3-4 working days)
