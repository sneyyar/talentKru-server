# Implementation Plan: Identity and Access

## Overview

Implement the foundational security layer for TalentKru.ai using FastAPI, async SQLAlchemy, and Python. The module covers user lifecycle management, JWT authentication, token refresh/revocation, RBAC, fine-grained privileges, SuperAdmin impersonation, user invitations, password reset, AES-256-GCM field encryption, audit logging, and in-memory sliding-window rate limiting. All 25 correctness properties are verified using Hypothesis property-based tests.

## Tasks

- [ ] 1. Set up module structure, base configuration, and shared crypto utilities
  - Create directory tree: `app/modules/{auth,users,rbac,invitations,password_reset}/` with `__init__.py` files
  - Create `app/crypto.py` with `encrypt_field` / `decrypt_field` using AES-256-GCM (96-bit nonce, base64 output)
  - Create `app/config.py` `Settings` model (Pydantic) with `JWT_SIGNING_KEY` and `ENCRYPTION_KEY`; raise `ValidationError` on startup if either is missing or empty
  - Add `pytest`, `pytest-asyncio`, `hypothesis`, `httpx`, `pytest-mock` to `pyproject.toml` test dependencies
  - _Requirements: 3.3, 3.10, 7.1, 7.2_

  - [ ] 1.1 Implement `encrypt_field` and `decrypt_field` in `app/crypto.py`
    - AES-256-GCM with fresh 96-bit nonce per call; base64-encode `nonce + ciphertext`
    - Derive 32-byte key from `ENCRYPTION_KEY` via SHA-256
    - _Requirements: 7.1, 7.2_

  - [ ]* 1.2 Write property test for PII encryption round-trip (Property 13)
    - **Property 13: PII encryption round-trip**
    - **Validates: Requirements 7.1, 7.2**
    - Use `@given(plaintext=st.text(min_size=1, max_size=254))` with `max_examples=200`
    - Assert `encrypt_field(p) != p` and `decrypt_field(encrypt_field(p)) == p`


- [ ] 2. Implement SQLAlchemy data models
  - [ ] 2.1 Create `User` and `PasswordHistory` models in `app/modules/users/models.py`
    - `User`: `user_id`, `organization_id`, `email` (VARCHAR 512, encrypted), `email_hash` (VARCHAR 64, SHA-256), `given_name`, `last_name`, `status` (enum: Active/Inactive/Locked/PendingInvitation), `manager_user_id`, `hashed_password` (nullable), `failed_login_attempts`, `last_failed_login_at`, `locale`, plus `AuditMixin` and `VersionMixin`
    - `UniqueConstraint("organization_id", "email_hash", name="uq_users_org_email")`
    - `PasswordHistory`: `password_history_id`, `user_id` (FK), `hashed_password`, `created_at`; index on `(user_id, created_at DESC)`
    - _Requirements: 1.1, 1.8, 7.1_

  - [ ] 2.2 Create `RefreshToken` and `RevokedToken` models in `app/modules/auth/models.py`
    - `RefreshToken`: `refresh_token_id`, `user_id` (FK), `token_hash` (UNIQUE), `expires_at`, `is_revoked`, `issued_at`, `replaced_by_token_id` (nullable self-FK)
    - `RevokedToken`: `revoked_token_id`, `jti` (UNIQUE, indexed), `revoked_at`, `expires_at`, `user_id`, `reason`; index on `expires_at` for cleanup
    - _Requirements: 4.1, 4.4, 4.7_

  - [ ] 2.3 Create RBAC models in `app/modules/rbac/models.py`
    - `Role`: `role_name` (PK), `description`
    - `UserRole`: `user_role_id`, `user_id` (FK), `role_name` (FK); `UniqueConstraint("user_id", "role_name")`; `AuditMixin`
    - `Privilege`: `privilege_id`, `name` (UNIQUE), `description`, `resource_category`
    - `RolePrivilege`: `role_privilege_id`, `role_name` (FK), `privilege_id` (FK); `UniqueConstraint("role_name", "privilege_id")`; `AuditMixin`
    - _Requirements: 5.1, 5.2, 6.1, 6.2_

  - [ ] 2.4 Create `InvitationToken` and `PasswordResetToken` models
    - `InvitationToken` in `app/modules/invitations/models.py`: `invitation_token_id`, `user_id` (FK), `token_hash` (UNIQUE), `expires_at` (72 h), `is_used`, `created_at`
    - `PasswordResetToken` in `app/modules/password_reset/models.py`: `password_reset_token_id`, `user_id` (FK), `token_hash` (UNIQUE), `expires_at` (15 min), `is_used`, `created_at`
    - _Requirements: 9.1, 10.1_


- [ ] 3. Create Alembic migration and seed data
  - [ ] 3.1 Write Alembic migration for all Identity and Access tables
    - Generate DDL for `users`, `password_history`, `refresh_tokens`, `revoked_tokens`, `roles`, `user_roles`, `privileges`, `role_privileges`, `invitation_tokens`, `password_reset_tokens`
    - Include all indexes and unique constraints from the DDL summary in the design
    - _Requirements: 1.1, 4.1, 5.1, 6.1, 9.1, 10.1_

  - [ ] 3.2 Write seed data migration for roles and default privilege mappings
    - Insert all 7 roles: `SuperAdministrator`, `Administrator`, `Recruiter`, `HiringManager`, `CommitteeMember`, `HRManager`, `Interviewer`
    - Insert default privileges (`users:read`, `users:write`, `roles:assign`, `privileges:manage`, `candidates:write`, `requisitions:write`, `journeys:transition`, `interviews:feedback`, `reports:read`) and their default role assignments
    - _Requirements: 5.1, 6.1, 6.3_


- [ ] 4. Implement RevocationCache and RateLimiter infrastructure
  - [ ] 4.1 Implement `RevocationCache` in `app/modules/auth/service.py`
    - Thread-safe in-memory dict keyed by JTI; configurable TTL (default 300 s)
    - `revoke(jti)`, `is_revoked(jti)` with lazy eviction of expired entries
    - Startup warm-up: load all non-expired JTIs from `RevokedToken` table on app lifespan start
    - _Requirements: 4.4_

  - [ ] 4.2 Implement `SlidingWindowCounter` and `RateLimiter` in `app/middleware/rate_limit.py`
    - `SlidingWindowCounter`: thread-safe `deque` of monotonic timestamps; `is_allowed()` returns `(bool, retry_after_seconds)`
    - `RateLimiter`: dict keyed by `(endpoint_group, identifier)`; `check(key, window_seconds, max_requests)` returns `retry_after_seconds`
    - _Requirements: 8.7_

  - [ ] 4.3 Implement `RateLimitMiddleware` as a FastAPI middleware in `app/middleware/rate_limit.py`
    - Apply IP-based sliding window on `POST /token` and `POST /token/refresh` (5 failures / 5 min; 15-min lockout with `Retry-After` header)
    - Apply per-tenant rate limiting on all authenticated endpoints (configurable per org, default 1000 req/min; return `X-RateLimit-*` headers)
    - Apply per-agent rate limiting on `/internal/agents/` routes (default 100 req/min; keyed by `X-Agent-API-Key`)
    - Apply IP-based rate limiting on `POST /auth/invitation/accept` (10 attempts / 10 min) and password reset endpoints (3 req/10 min for request, 5 attempts/10 min for confirm)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.9, 10.8, 10.9_

  - [ ]* 4.4 Write property test for authentication endpoint rate limiting (Property 14)
    - **Property 14: Authentication endpoint rate limiting**
    - **Validates: Requirements 8.1, 8.2**
    - Use `@given(ip=st.ip_addresses(v=4).map(str))` with `max_examples=50`
    - After 5 failed attempts from same IP, assert 429 with `Retry-After` header on 6th request

  - [ ]* 4.5 Write property test for per-tenant API rate limiting (Property 15)
    - **Property 15: Per-tenant API rate limiting**
    - **Validates: Requirements 8.3, 8.4**
    - Generate org with configured limit N; send N+1 requests; assert last returns 429 with `X-RateLimit-*` headers


- [ ] 5. Implement UserService and user management endpoints
  - [ ] 5.1 Implement `UserService` in `app/modules/users/service.py`
    - `create_user`: validate email format and required fields (422); compute `email_hash = SHA-256(lower(email))`; encrypt email via `encrypt_field`; check `(org_id, email_hash)` uniqueness (409 on conflict); set `status=PendingInvitation`; `hashed_password=None`
    - `update_user`: validate fields; handle status transitions; enforce org-scoping
    - `list_users`: paginated query (default page size 20, max 100); exclude soft-deleted records
    - `lock_user`: set `status=Locked`; use `VersionMixin` optimistic locking with retry on `StaleDataError` (max 3 retries)
    - `get_password_history`: return last 5 `PasswordHistory` entries for a user
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 1.7, 1.8, 1.9_

  - [ ]* 5.2 Write property test for email uniqueness within organization (Property 1)
    - **Property 1: Email uniqueness within organization**
    - **Validates: Requirements 1.2, 1.3**
    - Use `@given(email=st.emails(), given_name=st.text(min_size=1, max_size=100), last_name=st.text(min_size=1, max_size=100))` with `max_examples=100`
    - Same email + same org → second call raises 409; same email + different orgs → both succeed

  - [ ] 5.3 Implement user management router in `app/modules/users/router.py`
    - `GET /users` (paginated), `POST /users`, `PATCH /users/{user_id}` — all restricted to `Administrator` or `SuperAdministrator` via `require_role`
    - `DELETE /admin/users/{user_id}/sessions` — restricted to `Administrator` or `SuperAdministrator`
    - _Requirements: 1.6, 4.6_

  - [ ]* 5.4 Write unit tests for UserService
    - Test required field validation (422 on missing email/given_name/last_name)
    - Test email format validation (422 on malformed email)
    - Test password history rejection (last 5 hashes rejected, 6th-oldest accepted)
    - Test lockout: exactly 5 consecutive failures trigger `status=Locked`; successful login resets counter
    - _Requirements: 1.2, 1.7, 1.8, 1.9_


- [ ] 6. Implement AuthService, JWT issuance, and authentication endpoint
  - [ ] 6.1 Implement `AuthService.authenticate` and JWT issuance in `app/modules/auth/service.py`
    - Look up user by `email_hash` within `org_id`; verify bcrypt hash; handle Locked/Inactive (401)
    - `_issue_access_token`: HS256 JWT with `sub`, `org_id`, `roles`, `exp` (+60 min), `iat`, `jti` (UUID4)
    - `_issue_refresh_token`: `secrets.token_bytes(32).hex()`; store SHA-256 hash in `RefreshToken` table
    - `_handle_failed_attempt`: increment `failed_login_attempts`; set `status=Locked` at 5 (with `VersionMixin` retry)
    - `validate_password_policy`: return list of violated rules (empty = valid)
    - `check_password_history`: bcrypt-check new password against last 5 stored hashes
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7, 3.8, 4.1, 4.7_

  - [ ]* 6.2 Write property test for JWT claims completeness (Property 3)
    - **Property 3: JWT claims completeness**
    - **Validates: Requirements 3.4, 4.7, 5.7**
    - Use `@given(email=st.emails(), roles=st.lists(st.sampled_from(SUPPORTED_ROLES), min_size=1, max_size=3, unique=True))` with `max_examples=100`
    - Decode issued token; assert `sub==email`, `org_id` matches, `roles` set matches, `jti` present, `exp - iat` ≈ 3600 s

  - [ ]* 6.3 Write property test for authentication token issuance (Property 4)
    - **Property 4: Authentication token issuance**
    - **Validates: Requirements 4.1, 3.1**
    - For any Active user with valid credentials, assert both access token (JWT, 60-min TTL) and refresh token returned; refresh token hash stored in DB

  - [ ]* 6.4 Write property test for JWT signature verification (Property 5)
    - **Property 5: JWT signature verification**
    - **Validates: Requirements 3.3**
    - Use `@given(wrong_key=st.text(min_size=1))` with `max_examples=100`
    - Assert `jwt.decode(token, JWT_SIGNING_KEY)` succeeds; `jwt.decode(token, wrong_key)` raises `InvalidTokenError`

  - [ ]* 6.5 Write property test for locked user authentication rejection (Property 2)
    - **Property 2: Locked user authentication rejection**
    - **Validates: Requirements 1.4, 3.8**
    - For any user with `status in (Locked, Inactive)`, any POST /token attempt returns 401

  - [ ] 6.6 Implement `POST /token` router in `app/modules/auth/router.py`
    - Accept `application/x-www-form-urlencoded` (`OAuth2PasswordRequestForm`); return `TokenResponse`
    - Return 422 if `email` or `password` missing; return 401 on invalid credentials (no field disclosure)
    - _Requirements: 3.1, 3.2, 3.9_


- [ ] 7. Implement token refresh, revocation, and JWT dependency
  - [ ] 7.1 Implement `AuthService.refresh` and token family revocation in `app/modules/auth/service.py`
    - Hash submitted token; look up `RefreshToken` by hash; check `is_revoked` and `expires_at`
    - On valid token: mark old token `is_revoked=True`, set `replaced_by_token_id`; issue new access + refresh tokens
    - On revoked token (theft): walk `replaced_by_token_id` chain; revoke all family members; add all JTIs to `RevocationCache` and `RevokedToken` table; return 401
    - `revoke_all_user_tokens(user_id)`: revoke all active refresh tokens and add active JTIs to revocation list (used by status change and session delete)
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 7.2 Write property test for refresh token rotation (Property 6)
    - **Property 6: Refresh token rotation**
    - **Validates: Requirements 4.2**
    - For any valid non-expired non-revoked refresh token, assert: new access + refresh tokens returned; old token `is_revoked=True`; `replaced_by_token_id` set to new token ID

  - [ ]* 7.3 Write property test for token family revocation on reuse (Property 7)
    - **Property 7: Token family revocation on reuse**
    - **Validates: Requirements 4.3**
    - Use `@given(chain_length=st.integers(min_value=1, max_value=5))` with `max_examples=50`
    - Build rotation chain of `chain_length`; reuse first token; assert 401 and all tokens in chain `is_revoked=True`

  - [ ]* 7.4 Write property test for revoked JTI rejection (Property 8)
    - **Property 8: Revoked JTI rejection**
    - **Validates: Requirements 4.4**
    - Add a JTI to `RevocationCache`; assert any protected endpoint request with that JWT returns 401

  - [ ]* 7.5 Write property test for status change triggering token revocation (Property 9)
    - **Property 9: Status change triggers token revocation**
    - **Validates: Requirements 4.5**
    - Change user status to Locked or Inactive; assert all `RefreshToken.is_revoked=True` and active JTIs in revocation list

  - [ ] 7.6 Implement `get_current_principal`, `require_role`, `require_privilege` in `app/modules/auth/dependencies.py`
    - `get_current_principal`: decode JWT with `JWT_SIGNING_KEY`; check `exp`; check `jti` in `RevocationCache`; return `Principal`
    - `require_role(*roles)`: dependency factory; 403 if principal holds none of the required roles
    - `require_privilege(privilege_name)`: dependency factory; DB lookup of role→privilege mapping; 403 if not found
    - _Requirements: 3.5, 3.6, 4.4, 5.3, 5.6, 6.4_

  - [ ] 7.7 Implement `POST /token/refresh` router in `app/modules/auth/router.py`
    - Accept `RefreshRequest`; delegate to `AuthService.refresh`; return `TokenResponse` or 401
    - _Requirements: 4.2, 4.3_


- [ ] 8. Checkpoint — core auth working
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement RBAC service and role management endpoints
  - [ ] 9.1 Implement `RBACService` in `app/modules/rbac/service.py`
    - `assign_role(user_id, role_name, actor)`: validate role name in supported list (400 on unknown); check duplicate (400 if already held); insert `UserRole`; write audit log entry
    - `remove_role(user_id, role_name, actor)`: soft-delete `UserRole`; write audit log entry
    - `list_roles()`, `get_user_roles(user_id)`: read-only queries
    - _Requirements: 5.1, 5.2, 5.8, 5.9_

  - [ ]* 9.2 Write property test for non-admin role management rejection (Property 10)
    - **Property 10: Non-admin role management rejection**
    - **Validates: Requirements 5.3, 1.6**
    - For any user without Administrator or SuperAdministrator role, assert user/role management endpoints return 403

  - [ ]* 9.3 Write property test for role assignment audit log (Property 11)
    - **Property 11: Role assignment audit log**
    - **Validates: Requirements 5.8**
    - For any role assignment or removal, assert audit log entry created with actor UserID, affected user, role name, operation, timestamp; assert no audit entry on read-only access

  - [ ] 9.4 Implement RBAC router in `app/modules/rbac/router.py`
    - `GET /roles`, `POST /roles/{role_name}/users/{user_id}` (assign), `DELETE /roles/{role_name}/users/{user_id}` (remove) — restricted to `Administrator` or `SuperAdministrator`
    - `GET /roles/{role_name}/privileges`, `GET /privileges` — restricted to `Administrator` or `SuperAdministrator`
    - `POST /roles/{role_name}/privileges`, `DELETE /roles/{role_name}/privileges/{privilege_id}` — restricted to `SuperAdministrator`
    - _Requirements: 5.1, 5.6, 6.5, 6.6_


- [ ] 10. Implement privilege management service
  - [ ] 10.1 Implement privilege management in `app/modules/rbac/service.py`
    - `assign_privilege(role_name, privilege_id, actor)`: verify `privilege_id` exists in system set (400 if not); insert `RolePrivilege`; write audit log
    - `remove_privilege(role_name, privilege_id, actor)`: check remaining privilege count; reject with 400 if removal would leave role with 0 privileges; soft-delete `RolePrivilege`; write audit log
    - `list_privileges()`, `get_role_privileges(role_name)`: read-only queries
    - _Requirements: 6.1, 6.2, 6.5, 6.6, 6.7, 6.8, 6.9_

  - [ ]* 10.2 Write property test for role minimum privilege invariant (Property 12)
    - **Property 12: Role minimum privilege invariant**
    - **Validates: Requirements 6.8**
    - For any role with exactly one privilege, assert removing that privilege returns 400; role still has 1 privilege after rejection

  - [ ]* 10.3 Write unit tests for privilege management
    - Non-existent `PrivilegeID` returns 400
    - Duplicate privilege assignment returns 400
    - Audit log entry created on assign and remove
    - _Requirements: 6.7, 6.9_


- [ ] 11. Implement SuperAdmin impersonation
  - [ ] 11.1 Implement `impersonate` in `app/modules/auth/service.py`
    - Reject if `principal.obo_by is not None` (nested impersonation → 403)
    - Look up target user by `(target_user_id, target_org_id)`; 404 if not found
    - Verify target holds `Administrator` role; 403 if not
    - Issue JWT with target's `sub`, `org_id`, `roles`, standard `exp`/`iat`/`jti`, plus `obo_by = super_admin.sub`
    - Write audit log entry: actor=SuperAdmin, action=`ImpersonationStarted`, target org + user, timestamp
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7_

  - [ ]* 11.2 Write property test for nested impersonation rejection (Property 24)
    - **Property 24: Nested impersonation rejection**
    - **Validates: Requirements 2.7**
    - For any JWT containing `obo_by` claim, assert `POST /admin/impersonate` returns 403

  - [ ]* 11.3 Write property test for OBO JWT org isolation (Property 23)
    - **Property 23: OBO JWT org isolation**
    - **Validates: Requirements 2.6**
    - For any OBO JWT, assert requests to resources in a different org return 403

  - [ ] 11.4 Implement `POST /admin/impersonate` router in `app/modules/auth/router.py`
    - Restricted to `SuperAdministrator` via `require_role`; accept `ImpersonateRequest`; return `TokenResponse`
    - _Requirements: 2.1, 2.5_

  - [ ]* 11.5 Write unit tests for impersonation
    - Non-Administrator target returns 403
    - OBO JWT contains correct `obo_by` claim
    - Audit log entry created on impersonation start
    - _Requirements: 2.2, 2.3, 2.4_


- [ ] 12. Implement invitation service and endpoints
  - [ ] 12.1 Implement `InvitationService` in `app/modules/invitations/service.py`
    - `generate_invitation(user_id, db)`: `secrets.token_bytes(32).hex()`; store SHA-256 hash in `InvitationToken` with `expires_at = now + 72h`, `is_used=False`
    - `send_invitation_email(user, token, org_name)`: dispatch email with invitation link embedding plain-text token, user's `GivenName`, org name, and expiry time
    - `accept_invitation(token, password, db)`: hash token; look up `InvitationToken`; reject (400) if not found, `is_used`, or `expires_at < now`; validate password policy (422 on violation, token stays unused); bcrypt-hash password; set `hashed_password`; set `status=Active`; mark `is_used=True`; append to `PasswordHistory`; write audit log (`AccountActivated`)
    - `resend_invitation(user_id, actor, db)`: verify `status=PendingInvitation` (400 if not); invalidate existing unused tokens; generate and send new token
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [ ]* 12.2 Write property test for invitation token generation on user creation (Property 16)
    - **Property 16: Invitation token generation on user creation**
    - **Validates: Requirements 9.1**
    - For any user creation, assert `status=PendingInvitation`; `InvitationToken` exists with SHA-256 hash, `expires_at ≈ now+72h`, `is_used=False`

  - [ ]* 12.3 Write property test for invalid invitation token rejection (Property 17)
    - **Property 17: Invalid invitation token rejection**
    - **Validates: Requirements 9.4, 9.7**
    - For expired, used, or non-existent tokens, assert `POST /auth/invitation/accept` returns 400; user `status` remains `PendingInvitation`

  - [ ]* 12.4 Write property test for successful invitation acceptance (Property 18)
    - **Property 18: Successful invitation acceptance activates account**
    - **Validates: Requirements 9.3, 9.8**
    - For valid token + policy-compliant password, assert `status=Active`, bcrypt hash stored, `is_used=True`, `PasswordHistory` entry added, audit log entry with `AccountActivated`

  - [ ] 12.5 Implement invitation router in `app/modules/invitations/router.py`
    - `POST /auth/invitation/accept` — public (no JWT required); rate-limited (10/10 min per IP)
    - `POST /auth/invitation/resend` — restricted to `Administrator` or `SuperAdministrator`
    - _Requirements: 9.3, 9.6, 9.9_


- [ ] 13. Implement password reset service and endpoints
  - [ ] 13.1 Implement `PasswordResetService` in `app/modules/password_reset/service.py`
    - `request_reset(email, db)`: look up user by `email_hash`; if not found, Locked, or Inactive → return 200 silently (no email); otherwise generate `secrets.token_bytes(32).hex()`; store SHA-256 hash in `PasswordResetToken` with `expires_at = now + 15 min`, `is_used=False`; dispatch email with plain-text token
    - `confirm_reset(token, new_password, db)`: hash token; look up `PasswordResetToken`; reject (400) if not found, `is_used`, or expired; validate password policy (422 on violation, token stays unused); check password history (422 if matches last 5); bcrypt-hash; update `hashed_password`; mark `is_used=True`; append to `PasswordHistory`; call `revoke_all_user_tokens(user_id)`; write audit log (`PasswordReset`)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.10_

  - [ ]* 13.2 Write property test for password policy enforcement (Property 19)
    - **Property 19: Password policy enforcement**
    - **Validates: Requirements 9.5, 10.5**
    - Use `@given(password=st.text(max_size=11))` (too short) with `max_examples=100`
    - Assert 422 returned; invitation/reset token `is_used` remains `False`

  - [ ]* 13.3 Write property test for invalid password reset token rejection (Property 20)
    - **Property 20: Invalid password reset token rejection**
    - **Validates: Requirements 10.4**
    - For expired, used, or non-existent reset tokens, assert `POST /auth/password-reset/confirm` returns 400

  - [ ]* 13.4 Write property test for password reset triggering session revocation (Property 21)
    - **Property 21: Password reset triggers session revocation**
    - **Validates: Requirements 10.6**
    - After successful reset, assert all `RefreshToken.is_revoked=True` for user; active JTIs in revocation list

  - [ ]* 13.5 Write property test for password reset endpoint non-disclosure (Property 22)
    - **Property 22: Password reset endpoint non-disclosure**
    - **Validates: Requirements 10.2, 10.7**
    - Use `@given(email=st.emails())` with `max_examples=100`
    - Assert `POST /auth/password-reset/request` always returns 200 regardless of whether email exists

  - [ ] 13.6 Implement password reset router in `app/modules/password_reset/router.py`
    - `POST /auth/password-reset/request` — public (no JWT); rate-limited (3/10 min per IP); always 200
    - `POST /auth/password-reset/confirm` — public (no JWT); rate-limited (5/10 min per IP)
    - _Requirements: 10.1, 10.8, 10.9, 10.11_


- [ ] 14. Implement audit logging and soft delete
  - [ ] 14.1 Implement `write_audit_log` helper in `app/audit.py`
    - Accept `actor_id`, `action`, `target_entity`, `target_id`, `org_id`, `changed_values` (dict), `obo_by` (optional), `timestamp`
    - Persist to `audit_log` table (or structured JSON log via structlog if table not yet defined)
    - _Requirements: 7.3, 2.4, 2.5, 5.8, 6.9, 9.8, 10.10_

  - [ ] 14.2 Wire audit log calls into all service methods that require it
    - User create/update, role assign/remove, privilege assign/remove, impersonation start, invitation accept (`AccountActivated`), password reset (`PasswordReset`), session revocation
    - Ensure OBO sessions pass `obo_by` from `Principal` to every audit entry
    - _Requirements: 2.5, 5.8, 6.9, 7.3_

  - [ ]* 14.3 Write property test for soft delete preserving records (Property 25)
    - **Property 25: Soft delete preserves records**
    - **Validates: Requirements 7.4**
    - For any entity deletion, assert `deleted_at` is set to a UTC timestamp; assert entity absent from default (non-deleted) query results; assert entity present in query with `include_deleted=True`

  - [ ]* 14.4 Write unit tests for audit logging
    - Audit entry created for stage transitions, user changes, role assignments, AI agent calls
    - OBO audit entries contain `obo_by` claim
    - Read-only access does NOT create audit entries
    - _Requirements: 7.3, 2.5, 5.8_


- [ ] 15. Wire all modules into the FastAPI application
  - [ ] 15.1 Register all routers and middleware in `app/main.py`
    - Include `auth`, `users`, `rbac`, `invitations`, `password_reset` routers under `/api/v1` prefix
    - Add `RateLimitMiddleware` to the middleware stack
    - Register lifespan handler: warm `RevocationCache` from `RevokedToken` table on startup
    - Exempt `POST /token`, `POST /token/refresh`, `POST /auth/invitation/accept`, `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm`, and health check from JWT auth requirement
    - _Requirements: 3.6, 4.4, 5.6, 10.11_

  - [ ] 15.2 Add Pydantic schemas for all request/response models
    - `app/modules/auth/schemas.py`: `LoginRequest`, `RefreshRequest`, `ImpersonateRequest`, `TokenResponse`
    - `app/modules/users/schemas.py`: `UserCreate`, `UserUpdate`, `UserResponse` (with pagination wrapper)
    - `app/modules/rbac/schemas.py`: `RoleAssignRequest`, `PrivilegeResponse`, `RolePrivilegeResponse`
    - `app/modules/invitations/schemas.py`: `InvitationAcceptRequest`, `InvitationResendRequest`
    - `app/modules/password_reset/schemas.py`: `PasswordResetRequest`, `PasswordResetConfirm`
    - Enforce max field lengths and allowed values per requirements
    - _Requirements: 1.1, 1.7, 3.9, 7.6_

  - [ ]* 15.3 Write integration tests for full authentication flow
    - Login → access protected endpoint → refresh → revoke session
    - Verify 401 after session revocation
    - _Requirements: 3.1, 4.2, 4.6_

  - [ ]* 15.4 Write integration tests for invitation and password reset flows
    - Create user → accept invitation → login
    - Request password reset → confirm → verify old sessions revoked → login with new password
    - _Requirements: 9.3, 10.3, 10.6_

  - [ ]* 15.5 Write integration tests for impersonation flow
    - SuperAdmin impersonates Administrator → performs action → verify audit log contains `obo_by`
    - _Requirements: 2.3, 2.4, 2.5_

  - [ ]* 15.6 Write smoke tests for startup validation
    - App starts successfully with all required env vars set
    - App fails to start when `JWT_SIGNING_KEY` is missing or empty
    - App fails to start when `ENCRYPTION_KEY` is missing or empty
    - All 7 roles exist in DB after migration; default privilege mappings present
    - _Requirements: 3.10, 5.1, 6.3_

- [ ] 16. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints at tasks 8 and 16 ensure incremental validation
- Property tests use Hypothesis with `max_examples=100` (minimum); tag each test with `# Feature: identity-and-access, Property N: <title>`
- Unit tests complement property tests by covering specific examples, edge cases, and error conditions
- All code uses async SQLAlchemy sessions throughout; no synchronous DB calls
- Email dispatch is injected as a dependency to allow mocking in tests
- `VersionMixin` optimistic locking retry (max 3 attempts) is required for the user lockout operation (Requirement 1.9)
- The `RevocationCache` TTL defaults to 300 s (5 min) and must be warmed from `RevokedToken` on startup
- Public endpoints (password reset, invitation accept) must be explicitly excluded from JWT auth middleware

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "2.2", "2.3", "2.4"] },
    { "id": 1, "tasks": ["1.2", "3.1", "4.1", "4.2"] },
    { "id": 2, "tasks": ["3.2", "4.3", "5.1", "6.1"] },
    { "id": 3, "tasks": ["4.4", "4.5", "5.2", "5.3", "6.2", "6.3", "6.4", "6.5", "7.1"] },
    { "id": 4, "tasks": ["5.4", "6.6", "7.2", "7.3", "7.4", "7.5", "7.6"] },
    { "id": 5, "tasks": ["7.7", "9.1", "10.1"] },
    { "id": 6, "tasks": ["9.2", "9.3", "9.4", "10.2", "10.3", "11.1", "12.1", "13.1"] },
    { "id": 7, "tasks": ["11.2", "11.3", "11.4", "11.5", "12.2", "12.3", "12.4", "12.5", "13.2", "13.3", "13.4", "13.5", "13.6"] },
    { "id": 8, "tasks": ["14.1"] },
    { "id": 9, "tasks": ["14.2", "14.3", "14.4"] },
    { "id": 10, "tasks": ["15.1", "15.2"] },
    { "id": 11, "tasks": ["15.3", "15.4", "15.5", "15.6"] }
  ]
}
```
