# Requirements: Transaction Management Refactoring

**Feature**: Implement service-layer transaction boundaries with explicit commit/rollback semantics  
**Status**: In Progress  
**Last Updated**: June 3, 2026

---

## Overview

Currently, transaction management is scattered across the FastAPI dependency layer and individual route handlers, causing unclear ownership, test pollution, and potential data inconsistencies. This spec establishes service-layer transaction boundaries that provide:

1. **Clear ownership**: Services control transaction lifecycle
2. **Atomicity**: All-or-nothing semantics per service call
3. **Testability**: Tests can validate transaction behavior independently
4. **Consistency**: Production and test behavior match

---

## Current State Problems

### Problem 1: Auto-Commit in FastAPI Dependency
- **Location**: `app/database.py:get_db_session()`
- **Issue**: Every route auto-commits after yielding, hiding transaction control
- **Impact**: Routes can't coordinate multiple service calls in one transaction

### Problem 2: Explicit Commits in Routes
- **Location**: All `app/modules/*/router.py` files
- **Count**: 35+ `await db.commit()` calls across 12 modules
- **Issue**: Transaction control is split between route and service layers
- **Impact**: Violates separation of concerns; hard to test service atomicity

### Problem 3: Inconsistent Service Layer
- **Location**: `app/modules/*/service.py` files
- **Count**: 15 service modules, 0-1 commits each
- **Issue**: Services don't manage transactions; routes assume responsibility
- **Impact**: Service methods can't be composed atomically

### Problem 4: Test Fixtures Don't Mirror Production
- **Location**: `tests/conftest.py:db_session` fixture
- **Issue**: Tests call `commit()` mid-execution then `rollback()` at end
- **Impact**: Tests don't validate actual transaction behavior

### Problem 5: Session Configuration Mismatches
- **Location**: `app/database.py` and `tests/conftest.py`
- **Issue**: `expire_on_commit=False` causes stale object reads
- **Impact**: Tests pass but production code fails due to expired objects

---

## Requirements

### Req 1: Service-Layer Transaction Boundaries

**Description**: Each service method that modifies state must explicitly manage its own transaction.

**Acceptance Criteria**:

- [ ] Service methods wrap write operations in explicit `async with transaction:` blocks
- [ ] Transaction commits only on successful completion
- [ ] Transaction rolls back on any exception
- [ ] Read-only methods may operate without transaction scope
- [ ] Service methods can call other service methods; transactions don't nest (use savepoints if needed)

**Scope**: All 15 service modules

**Validation**: 
```python
@pytest.mark.asyncio
async def test_service_transaction_atomicity(db_session):
    service = CandidateService(db_session)
    candidate = await service.create_candidate(...)
    # Rollback session — should lose the candidate
    await db_session.rollback()
    # Verify candidate is not persisted
```

---

### Req 2: Remove Route-Layer Commits

**Description**: No `await db.commit()` calls in route handlers.

**Acceptance Criteria**:

- [ ] All route handlers delegate DB operations to services
- [ ] Services handle all commits/rollbacks
- [ ] Routes focus only on HTTP concerns (validation, response formatting)
- [ ] Zero `await db.commit()` calls in any `app/modules/*/router.py`

**Scope**: 12 modules with explicit commits

**Validation**: 
```bash
grep -r "await db.commit\|await session.commit" app/modules/*/router.py
# Result: (empty)
```

---

### Req 3: FastAPI Dependency Doesn't Auto-Commit

**Description**: The `get_db_session()` dependency provides a session without implicit transaction management.

**Acceptance Criteria**:

- [ ] `get_db_session()` yields session as-is
- [ ] No `await session.commit()` on success
- [ ] No `await session.rollback()` on error (error handling is service concern)
- [ ] Session lifecycle is managed by `async with AsyncSessionFactory()`

**Scope**: `app/database.py`

**Validation**:
```python
# In a route, after service call:
service = CandidateService(db)
candidate = await service.create_candidate(...)
# Session is not committed; caller (test/scheduler) handles lifetime
```

---

### Req 4: Consistent Test Fixtures

**Description**: Test fixtures should mirror production transaction behavior.

**Acceptance Criteria**:

- [ ] Test fixture yields session without calling `commit()`
- [ ] Test cleanup always calls `rollback()` to ensure clean state
- [ ] Tests cannot pass if service doesn't manage transactions
- [ ] Session config matches production (`expire_on_commit=True`, `autoflush=True`)

**Scope**: `tests/conftest.py`, all test files

**Validation**:
```bash
grep -r "await.*\.commit()" tests/
# Result: (empty, except in service method tests)
```

---

### Req 5: Session Configuration Consistency

**Description**: Database and test sessions use identical configuration for consistent behavior.

**Acceptance Criteria**:

- [ ] Both use `expire_on_commit=True` (objects expire after commit, forcing fresh queries)
- [ ] Both use `autoflush=True` (flush before queries for consistency)
- [ ] Both use `AsyncSession` class
- [ ] No difference between `app/database.py` and `tests/conftest.py` factory config

**Scope**: `app/database.py`, `tests/conftest.py`

**Validation**:
```python
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=True,    # ✅ Consistent
    autoflush=True,           # ✅ Consistent
)
```

---

### Req 6: Audit Field Population

**Description**: Audit fields (`created_by`, `updated_by`, `deleted_by`) are automatically populated.

**Acceptance Criteria**:

- [ ] `created_by` is set from request context on object creation
- [ ] `updated_by` is set from request context on object update
- [ ] `deleted_by` is set from request context on soft delete
- [ ] Works within service transaction boundaries
- [ ] No manual audit field setting required in services

**Scope**: `app/base_model.py`, all service methods

**Validation**:
```python
@pytest.mark.asyncio
async def test_audit_fields_populated(db_session, org_id):
    service = CandidateService(db_session)
    candidate = await service.create_candidate(
        organization_id=org_id,
        first_name="John",
        # created_by NOT passed
    )
    assert candidate.created_by is not None  # Populated by mixin
```

---

### Req 7: Domain Events Transactional

**Description**: Domain events are published within service transactions and persisted atomically.

**Acceptance Criteria**:

- [ ] Events are persisted before service commit
- [ ] If service rolls back, event persists (already flushed)
- [ ] Event dispatch happens after service commit (asynchronously)
- [ ] Failed event dispatch doesn't affect service transaction

**Scope**: `app/domain_events/publisher.py`, all service methods using events

**Validation**:
```python
@pytest.mark.asyncio
async def test_domain_event_persisted_on_service_commit(db_session):
    service = CandidateService(db_session)
    candidate = await service.create_candidate(...)
    # Service committed; event should be persisted
    
    events = await db_session.execute(
        select(DomainEvent).where(DomainEvent.event_type == "CandidateCreated")
    )
    assert events.scalar_one_or_none() is not None
```

---

### Req 8: Error Handling Semantics

**Description**: Errors within service transactions result in full rollback without retries.

**Acceptance Criteria**:

- [ ] Any exception triggers rollback
- [ ] Validation errors (ValueError, HTTPException) are caught and re-raised
- [ ] Database errors (constraint violations) trigger rollback
- [ ] No automatic retries (retry logic lives in caller, not service)
- [ ] Correlation ID is preserved across rollback

**Scope**: All service methods, error handling

**Validation**:
```python
@pytest.mark.asyncio
async def test_service_rollback_on_validation_error(db_session, org_id):
    service = CandidateService(db_session)
    
    with pytest.raises(ValueError):
        await service.create_candidate(
            organization_id=org_id,
            first_name="",  # Invalid
        )
    
    # Verify nothing was persisted
    result = await db_session.execute(select(Candidate))
    assert result.scalars().all() == []
```

---

## Implementation Phases

### Phase 1: Foundation (Platform Foundation Spec)
- [ ] Create `app/service_base.py` with transaction helpers
- [ ] Update `app/database.py` session configuration
- [ ] Update `tests/conftest.py` fixtures
- [ ] Update `app/base_model.py` audit field handling

### Phase 2: Core Services (Identity & Access Spec)
- [ ] Refactor `auth`, `users`, `organizations` services
- [ ] Refactor `rbac`, `invitations`, `password_reset` services
- [ ] Remove all route commits in these modules

### Phase 3: Candidate Management (Candidate Lifecycle Spec)
- [ ] Refactor `candidates`, `resumes`, `skills` services
- [ ] Remove all route commits in these modules

### Phase 4: Job Management (Candidate Lifecycle Spec - Jobs section)
- [ ] Refactor `requisitions`, `job_posting`, `job_profile` services
- [ ] Remove all route commits in these modules

### Phase 5: Interview Management (Interview Workflow Spec)
- [ ] Refactor `journeys`, `interviews`, `questionnaires` services
- [ ] Refactor `portal`, `matching` services
- [ ] Remove all route commits in these modules

### Phase 6: Support Services & Verification
- [ ] Refactor `privacy`, `reporting` services
- [ ] Remove all route commits in these modules
- [ ] Run full test suite
- [ ] Verify no regressions

---

## Testing Strategy

### Unit Tests (Per Service)
- Test atomic operations
- Test rollback behavior on error
- Test audit field population
- Test domain event emission

### Integration Tests
- Test multi-service workflows
- Test cross-module data consistency
- Test concurrent operations with different transactions

### Regression Tests
- Run existing test suite
- Verify all previously passing tests still pass
- Check coverage remains >80%

---

## Success Metrics

| Metric | Target | Validation |
|--------|--------|-----------|
| Route commits removed | 100% (0 remaining) | `grep -r "await db.commit" app/modules/*/router.py` |
| Service transactions added | 100% of write operations | Code review + test coverage |
| Test suite pass rate | 100% | `uv run invoke test` |
| Coverage | >80% | `uv run invoke test-cov` |
| No transaction-related errors | 0 | Full test suite execution |
| Audit fields populated | 100% of mutable entities | `test_audit_fields_populated` pass |
| Domain events persisted | 100% | `test_domain_event_persisted_on_service_commit` pass |

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Circular imports in transaction helper | Medium | Blocks refactoring | Place helper in module with no imports |
| Nested transaction errors | Medium | Test failures | Use savepoints for nested txns |
| Test interference/pollution | High | Test unreliability | Explicit rollback in fixture |
| Performance degradation | Low | Increased latency | Profile before/after |
| Incomplete refactoring | Medium | Inconsistent behavior | Spec-driven + checklist |

---

## References

- [SQLAlchemy Async Sessions](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Transaction Semantics](https://docs.sqlalchemy.org/en/20/orm/session_state_management.html)
- [Previous Analysis](../../../TRANSACTION_MANAGEMENT_ANALYSIS.md)

