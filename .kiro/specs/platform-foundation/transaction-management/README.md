# Transaction Management Specification

**Feature**: Service-Layer Transaction Boundaries  
**Status**: In Specification Phase  
**Start Date**: June 3, 2026

---

## Overview

This specification establishes **service-layer transaction management** for TalentKru.ai, replacing the current problematic pattern where routes implicitly commit and transaction control is scattered across layers.

**Goal**: Atomic, testable, production-ready transaction semantics using Python/SQLAlchemy async patterns.

---

## Problem Statement

### Current Issues

1. **Auto-commit in FastAPI dependency** — every route auto-commits (wrong layer!)
2. **Explicit commits in routes** — 35+ `await db.commit()` calls across 12 modules
3. **Inconsistent service layer** — services don't manage transactions
4. **Test fixture mismatch** — tests don't mirror production behavior
5. **Session config problems** — `expire_on_commit=False` causes stale reads

### Impact

- ❌ Partial commits possible (data inconsistency)
- ❌ Service methods can't guarantee atomicity
- ❌ Tests don't validate transaction behavior
- ❌ Unpredictable behavior between test and production
- ❌ Difficult to compose multi-operation workflows

---

## Solution Architecture

### Core Principle

**Services own transaction boundaries.** Each service method that modifies state wraps itself in an explicit transaction.

### Three-Layer Pattern

```
HTTP Request
    ↓
FastAPI Route Handler (HTTP concerns only)
    ├─ No commits/rollbacks
    ├─ No transaction logic
    └─ Call service method
    ↓
Service Layer (Transaction boundary)
    ├─ Wrap write operation in atomic_transaction
    ├─ Commit on success
    ├─ Rollback on error
    └─ Return result
    ↓
Database Layer (No auto-commit)
    ├─ Provide session
    ├─ No commit/rollback
    └─ Let caller manage lifecycle
    ↓
HTTP Response
```

---

## Implementation

### Phase 1: Foundation (Platform Foundation Spec)

**What**: Establish transaction infrastructure  
**Modules**: Core database/session management + test fixtures  
**Files**:
- [ ] Create `app/service_base.py` — transaction helper
- [ ] Update `app/database.py` — remove auto-commit, fix session config
- [ ] Update `tests/conftest.py` — match production config

**Effort**: 1.5 hours  
**Tests**: Verify infrastructure works

### Phase 2: Core Services (Identity & Access Spec)

**What**: Refactor foundational services  
**Modules**: `auth`, `users`, `organizations`, `rbac`, `invitations`, `password_reset`  
**Pattern**: Wrap all write methods in `atomic_transaction`

**Effort**: 4 hours  
**Tests**: Run service tests + verify no regressions

### Phase 3: Candidate & Job Management

**What**: Refactor domain services  
**Modules**: `candidates`, `resumes`, `skills`, `requisitions`, `job_posting`, `job_profile`  
**Pattern**: Wrap in `atomic_transaction`, ensure atomicity

**Effort**: 5-6 hours  
**Tests**: Integration tests for multi-operation workflows

### Phase 4: Interview & Support Services

**What**: Refactor remaining services  
**Modules**: `journeys`, `interviews`, `questionnaires`, `privacy`, `portal`, `matching`, `reporting`  
**Pattern**: Apply same transaction pattern

**Effort**: 8-10 hours  
**Tests**: Full test suite

### Phase 5: Verification & Enhancement

**What**: Verify correctness + optional declarative decorator  
**Tasks**:
- [ ] Full test suite: `uv run invoke test` ✅
- [ ] Coverage validation: >80%
- [ ] Regression testing
- [ ] Optional: Add `@transactional` decorator (Spring-like syntax)

**Effort**: 2-3 hours  
**Benefit**: Cleaner service code, Spring-like declarative syntax

---

## Documentation Structure

| Document | Purpose | Audience |
|----------|---------|----------|
| **requirements.md** | What needs to change | Product, leads |
| **design.md** | How to implement it | Architects, seniors |
| **tasks.md** | Specific tasks to execute | Developers |
| **DECLARATIVE_ENHANCEMENT.md** | Optional Phase 2 enhancement | Developers (future) |
| **README.md** (this) | Overview & navigation | Everyone |

---

## Key Documents

### For Understanding the Problem
- Read: `TRANSACTION_MANAGEMENT_ANALYSIS.md` (root)
- Explains current issues, SQLAlchemy behavior, and why fixes are needed

### For Specification
- Read: `requirements.md`
- Details what each requirement means and acceptance criteria
- Then read: `design.md`
- Explains how each requirement is implemented

### For Implementation
- Read: `tasks.md`
- 24 specific tasks broken down by phase
- Follow in order, run tests after each phase

### For Enhancement (Optional)
- Read: `DECLARATIVE_ENHANCEMENT.md`
- Shows how to add Spring-like `@transactional` decorator
- Do this as Phase 2 enhancement (after Phase 1 verification)

### For Comparison
- Read: `DECLARATIVE_TRANSACTIONS_COMPARISON.md` (root)
- Compares Java Spring vs Python/SQLAlchemy
- Explains why Python needs custom decorator
- Recommends hybrid approach

---

## Timeline

| Phase | Modules | Duration | Status |
|-------|---------|----------|--------|
| 1: Foundation | Core infra | 1.5 hrs | Pending |
| 2: Core Services | 6 modules | 4 hrs | Pending |
| 3: Candidate/Job | 6 modules | 5-6 hrs | Pending |
| 4: Interview/Support | 7 modules | 8-10 hrs | Pending |
| 5: Verification | Tests + optional decorator | 2-3 hrs | Pending |
| **TOTAL** | **15 modules** | **~20-25 hrs** | **Pending** |

**Schedule**: 3-4 working days (5-6 hours/day)

---

## Success Criteria

### Code Quality
- ✅ Zero `await db.commit()` in routes (all removed)
- ✅ All service write methods wrapped in `atomic_transaction`
- ✅ Session config: `expire_on_commit=True`, `autoflush=True`
- ✅ Test fixtures match production config
- ✅ No explicit commits in tests

### Testing
- ✅ All tests pass: `uv run invoke test`
- ✅ Coverage maintained: >80%
- ✅ No transaction-related errors
- ✅ Audit fields populated correctly
- ✅ Domain events persisted atomically

### Behavior
- ✅ Atomic operations (all-or-nothing)
- ✅ Clear transaction boundaries
- ✅ Consistent test/production behavior
- ✅ No data inconsistencies

---

## Recommended Reading Order

### For Project Leads/Architects
1. This README
2. `requirements.md` — understand the scope
3. `design.md` — understand the approach

### For Developers Implementing
1. `tasks.md` — follow tasks in order
2. `design.md` — reference as needed
3. Corresponding service code for examples

### For Code Reviewers
1. `requirements.md` — verify implementation meets requirements
2. `design.md` — verify design is followed
3. Code — verify patterns are correct

### For Future Developers
1. This README
2. `DECLARATIVE_TRANSACTIONS_COMPARISON.md` — understand philosophy
3. Service code examples (see `design.md`)

---

## Key Concepts

### Atomic Transaction
**Definition**: All-or-nothing operation. Either all changes commit, or all rollback.

**Example**:
```python
async def create_candidate_with_skills(org_id, first_name, skills):
    async with atomic_transaction(db, "create_candidate_with_skills"):
        # Create candidate
        candidate = Candidate(...)
        db.add(candidate)
        
        # Assign skills
        for skill in skills:
            candidate_skill = CandidateSkill(...)
            db.add(candidate_skill)
        
        # If ANY operation fails → ROLLBACK everything
        # If ALL succeed → COMMIT everything
        return candidate
```

### Transaction Boundaries
**Definition**: Clear points where transactions begin and end.

**Good** (clear boundaries):
```python
async def create_candidate():  # ← Boundary starts
    async with atomic_transaction(db):
        # ... work ...
    # ← Boundary ends
```

**Bad** (unclear boundaries):
```python
@router.post("/candidates")
async def create_candidate(db):
    service = CandidateService(db)
    result = await service.create_candidate()  # When does txn start?
    await db.commit()  # When does txn end? (Route commits!)
```

### Propagation
**Definition**: What happens when one transaction calls another.

**Python async** (simplified):
- **REQUIRED** (default): Use existing transaction (same session)
- **REQUIRES_NEW**: Create new transaction (new session)
- **READ_ONLY**: No transaction needed (query only)

**Not needed**: Java Spring has 7 propagation types; async Python is simpler.

---

## Testing Strategy

### Unit Tests (Per Service)
Test that individual service methods are atomic:

```python
@pytest.mark.asyncio
async def test_create_candidate_is_atomic(db_session):
    service = CandidateService(db_session)
    candidate = await service.create_candidate(...)
    # Service committed; data visible
    # Fixture rolls back at end
```

### Integration Tests
Test multi-service workflows:

```python
@pytest.mark.asyncio
async def test_create_candidate_with_skills_atomic(db_session):
    service = CandidateService(db_session)
    candidate = await service.create_candidate_with_skills(...)
    # Both candidate and skills committed atomically
```

### Regression Tests
Existing tests still pass:

```bash
uv run invoke test  # All tests
uv run invoke test-cov  # Coverage
```

---

## Quick Reference

### Before (Current - Wrong)
```python
# Route commits (WRONG!)
@router.post("/candidates")
async def create_candidate(db: AsyncSession = Depends(get_db_session)):
    service = CandidateService(db)
    candidate = await service.create_candidate(...)
    await db.commit()  # ← Route shouldn't commit!
    return candidate

# Service doesn't manage transaction
class CandidateService:
    async def create_candidate(self, ...):
        candidate = Candidate(...)
        self.db.add(candidate)
        # No transaction management (relies on route to commit)
```

### After (Proposed - Right)
```python
# Route delegates to service (RIGHT!)
@router.post("/candidates")
async def create_candidate(db: AsyncSession = Depends(get_db_session)):
    service = CandidateService(db)
    candidate = await service.create_candidate(...)
    # Service already committed; no route commit
    return candidate

# Service manages transaction
class CandidateService:
    async def create_candidate(self, ...):
        async with atomic_transaction(self.db, "create_candidate"):
            candidate = Candidate(...)
            self.db.add(candidate)
            await self.db.flush()
            return candidate  # Commit on exit
```

---

## FAQ

### Q: Does this match Spring @Transactional?
**A**: Similar but not identical. Python async patterns are different. See `DECLARATIVE_TRANSACTIONS_COMPARISON.md` for details.

### Q: Can I still use context managers directly?
**A**: Yes! Phase 1 uses context managers. Phase 2 optionally adds decorators on top (backward compatible).

### Q: What about nested transactions?
**A**: Python async doesn't support "suspend current transaction" like Java. Create a new session with `REQUIRES_NEW`. Handled via separate session, not savepoints.

### Q: Will this be slower?
**A**: Slightly faster. Explicit transactions reduce overhead vs. implicit auto-commit. No noticeable difference for typical workloads.

### Q: What if I need a transaction that spans multiple service calls?
**A**: Create a higher-level service or use orchestration layer. Example:
```python
async def workflow(db):
    async with atomic_transaction(db, "workflow"):
        await service1.create(...)  # Within same txn
        await service2.update(...)  # Within same txn
        # All-or-nothing
```

### Q: How does this work with FastAPI background tasks?
**A**: Background tasks run after route returns. They can create their own transactions:
```python
async def background_task():
    async with AsyncSessionFactory() as db:
        async with atomic_transaction(db, "background_work"):
            # Do work
```

---

## Getting Help

### For Implementation Questions
1. Check `design.md` — detailed explanations with examples
2. Check `tasks.md` — specific task requirements
3. Look at example code in `design.md` — copy patterns

### For Specification Questions
1. Check `requirements.md` — what needs to be done
2. Check acceptance criteria — verify implementation

### For Understanding Philosophy
1. Check `TRANSACTION_MANAGEMENT_ANALYSIS.md` — current problems
2. Check `DECLARATIVE_TRANSACTIONS_COMPARISON.md` — Spring comparison

### For Testing Help
1. Check `design.md` "Testing Strategy" section
2. Check `tasks.md` "Testing" sections
3. Run tests: `uv run invoke test -v`

---

## Status & Next Steps

### Current Status
- ✅ Problem identified and analyzed
- ✅ Specification written (requirements, design, tasks)
- ✅ Comparison with Java Spring documented
- ✅ Optional enhancement designed (decorators)
- ⏳ Implementation ready to begin

### Next Steps (For Approval)
1. Review specification documents (requirements.md, design.md)
2. Verify timeline (3-4 working days)
3. Approve and assign developer
4. Start Phase 1

### Approval Checklist
- [ ] Requirements make sense
- [ ] Design is sound
- [ ] Tasks are clear
- [ ] Timeline is acceptable
- [ ] Success criteria are achievable

---

## Contact & Questions

For questions about this specification, refer to the appropriate document:

- **Problem analysis**: TRANSACTION_MANAGEMENT_ANALYSIS.md
- **Spring comparison**: DECLARATIVE_TRANSACTIONS_COMPARISON.md
- **Requirements detail**: requirements.md
- **Design detail**: design.md
- **Implementation tasks**: tasks.md
- **Declarative enhancement**: DECLARATIVE_ENHANCEMENT.md

---

## Version History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-06-03 | 1.0 | Initial specification | Kiro |
| — | 1.1 (planned) | Phase 1 implementation | TBD |
| — | 2.0 (planned) | Phase 2+ implementations | TBD |

