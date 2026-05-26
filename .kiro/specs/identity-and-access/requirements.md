# Requirements Document

## Introduction

This is the Identity and Access module of TalentKru.ai Server. It covers user management, user invitation and account setup, authentication, password reset, token lifecycle, role-based access control, fine-grained privileges, security and encryption, and rate limiting. These capabilities form the foundational security layer upon which all other modules depend.

Key architectural decisions relevant to this module:
- JWT-based local authentication as the primary auth mechanism (SSO/OAuth2 deferred).
- bcrypt password hashing for credential storage.
- HMAC-SHA256 signing for JWT tokens using the JWT_SIGNING_KEY environment variable.
- Stateless authentication with a token revocation list for immediate session termination.
- Field-level encryption of PII data at rest using the ENCRYPTION_KEY environment variable.
- In-memory sliding window rate limiting with no external dependency.

## Glossary

- **Server**: The TalentKru.ai FastAPI backend application.
- **Organization**: A client tenant in the system; all data is scoped to an organization.
- **User**: An internal user (recruiter, hiring manager, administrator, interviewer) belonging to an organization.
- **RBAC**: Role-Based Access Control governing endpoint authorization.
- **JWT_SIGNING_KEY**: The secret key used exclusively for HMAC-SHA256 signing and verification of JSON Web Tokens.
- **ENCRYPTION_KEY**: The secret key used exclusively for field-level encryption of PII data at rest.
- **AuditFields**: Standard fields on all entities: CreatedAt, UpdatedAt, DeletedAt, CreatedBy, UpdatedBy, DeletedBy.
- **Username**: A user's email address, which serves as their unique login identifier within the system. No separate username field exists.
- **Invitation Token**: A cryptographically random, single-use token sent to a newly added user's email address to allow them to set their initial password and activate their account.
- **Password Reset Token**: A cryptographically random, single-use token sent to a user's email address to allow them to reset a forgotten password.

## Requirements

### Requirement 1: User Management

**User Story:** As an administrator, I want to manage users within my organization, so that the right people have access to the recruiting system.

#### Acceptance Criteria

1. THE Server SHALL store User entities with fields: UserID (UUID), OrganizationID (FK), Email (unique within organization, maximum 254 characters), GivenName (maximum 100 characters), LastName (maximum 100 characters), Status (Active, Inactive, Locked, PendingInvitation), ManagerUserID (FK to User), hashed_password (nullable until the user completes account setup via invitation), FailedLoginAttempts (integer, default 0), LastFailedLoginAt (nullable timestamp), Locale (language and region code, e.g., en-US, default to organization locale), and AuditFields.
2. WHEN an administrator creates a user, THE Server SHALL validate that the email is unique within the organization and that required fields (Email, GivenName, LastName) are present; THE Server SHALL NOT require the administrator to supply a password, as the user will set their own password via the invitation flow.
3. IF an administrator attempts to create a user with an email that already exists within the organization, THEN THE Server SHALL reject the request with a 409 Conflict response indicating the email is already in use.
4. WHEN an administrator updates a user status to Locked, THE Server SHALL prevent that user from authenticating on subsequent authentication attempts.
5. THE Server SHALL enforce that all users except SuperAdministrator are linked to exactly one organization.
6. THE Server SHALL support listing, creating, and updating users via REST endpoints restricted to Administrator and SuperAdministrator roles, with listing supporting pagination with a default page size of 20 and a maximum page size of 100.
7. IF a user creation or update request contains an invalid email format or is missing required fields (Email, GivenName, LastName on creation), THEN THE Server SHALL reject the request with a 422 response indicating which fields failed validation.
8. THE Server SHALL store a password history of the last 5 hashed passwords per user and reject password changes that reuse any of the stored historical passwords with a 400 Bad Request response indicating the password has been used recently.
9. WHEN a user accumulates 5 consecutive failed login attempts, THE Server SHALL automatically set the user Status to Locked and record the lockout timestamp; IF the status update fails due to a database error or concurrent modification, THE Server SHALL retry the lock operation until it succeeds before returning a response to the caller.

### Requirement 2: SuperAdmin On-Behalf-Of Impersonation

**User Story:** As a SuperAdministrator, I want to temporarily assume the identity of an Administrator within an organization, so that I can perform configuration changes on behalf of that organization without requiring the Administrator's credentials.

#### Acceptance Criteria

1. THE Server SHALL expose a POST /admin/impersonate endpoint restricted to the SuperAdministrator role that accepts a target OrganizationID and a target UserID and returns a scoped on-behalf-of JWT.
2. THE Server SHALL only permit impersonation of users who hold the Administrator role within the specified organization; IF the target user does not hold the Administrator role, THEN THE Server SHALL reject the request with a 403 Forbidden response.
3. WHEN a SuperAdministrator initiates an on-behalf-of session, THE Server SHALL issue a JWT with the same TTL as a normal JWT (60 minutes), containing the impersonated user's org_id and roles claims, plus an additional obo_by claim set to the SuperAdministrator's UserID to identify the originating actor.
4. THE Server SHALL record an audit log entry at the start of every on-behalf-of session containing the SuperAdministrator's UserID as the actor, the target OrganizationID, the target UserID, and the session start timestamp.
5. THE Server SHALL record an audit log entry for every action performed during an on-behalf-of session, with the SuperAdministrator's UserID as the actor and the obo_by claim present, so that all changes are traceable to the SuperAdministrator rather than the impersonated user.
6. IF a request bearing an on-behalf-of JWT attempts to access data outside the impersonated user's organization, THEN THE Server SHALL reject the request with a 403 Forbidden response.
7. THE Server SHALL NOT allow nested impersonation; IF a request bearing an on-behalf-of JWT attempts to call the POST /admin/impersonate endpoint, THEN THE Server SHALL reject the request with a 403 Forbidden response.

### Requirement 3: JWT Local Authentication

**User Story:** As a user, I want to authenticate with my email address and password, so that I can access the system without external SSO dependencies and without needing to remember a separate username.

#### Acceptance Criteria

1. WHEN a user submits valid credentials to the POST /token endpoint using application/x-www-form-urlencoded format, THE Server SHALL verify the password against the stored bcrypt hash and return a signed JWT containing the user's identity and organization.
2. WHEN a user submits invalid credentials to the POST /token endpoint, THE Server SHALL return a 401 Unauthorized response without revealing whether the username or password was incorrect.
3. THE Server SHALL sign JWTs using HMAC-SHA256 with a secret key loaded from the JWT_SIGNING_KEY environment variable.
4. THE Server SHALL include the following claims in issued JWTs: sub (the user's email address, which serves as the unique login identifier), org_id (OrganizationID), roles (list of role names), and exp (expiration timestamp set to 60 minutes from the time of issuance).
5. WHEN a request includes an expired JWT, THE Server SHALL return a 401 Unauthorized response.
6. WHEN a request to a protected endpoint lacks a valid Authorization Bearer token, THE Server SHALL return a 401 Unauthorized response.
7. THE Server SHALL implement authentication as a stateless mechanism with no server-side session storage.
8. IF the user account has a Status of Locked or Inactive, THEN THE Server SHALL reject the authentication attempt with a 401 Unauthorized response regardless of whether the credentials are valid; IF the user account has a Status of Active but the credentials are invalid, THE Server SHALL also reject the authentication attempt with a 401 Unauthorized response.
9. IF the POST /token request body is missing required fields (email or password), THEN THE Server SHALL return a 422 Unprocessable Entity response indicating which fields are missing.
10. IF the JWT_SIGNING_KEY environment variable is not set or is empty at application startup, THEN THE Server SHALL fail to start and log an error message indicating the missing configuration.

### Requirement 4: Token Refresh and Revocation

**User Story:** As a security officer, I want tokens to be refreshable and revocable, so that compromised sessions can be terminated immediately and users experience seamless session continuity.

#### Acceptance Criteria

1. WHEN a user successfully authenticates via the POST /token endpoint, THE Server SHALL issue both an access token (JWT, 60-minute TTL) and a refresh token (opaque, cryptographically random string of at least 32 bytes, 7-day TTL) stored in the RefreshToken table with fields: RefreshTokenID (UUID), UserID (FK), TokenHash (SHA-256 hash of the token value), ExpiresAt (timestamp), IsRevoked (boolean, default false), IssuedAt (timestamp), and ReplacedByTokenID (nullable FK to RefreshToken).
2. WHEN a user submits a valid, non-expired, non-revoked refresh token to the POST /token/refresh endpoint, THE Server SHALL issue a new access token and a new refresh token, revoke the submitted refresh token by setting IsRevoked to true and linking ReplacedByTokenID to the new token, and return both new tokens in the response.
3. IF a user submits a refresh token that has already been revoked, THEN THE Server SHALL revoke all refresh tokens in the same token family (linked via ReplacedByTokenID chain) and return a 401 Unauthorized response, treating this as a potential token theft.
4. THE Server SHALL maintain a token revocation list backed by an in-memory cache (with a configurable TTL of 5 minutes) and a persistent RevokedToken table, and SHALL check the revocation list on every protected endpoint request before granting access.
5. WHEN a user account Status is changed to Locked or Inactive, THE Server SHALL immediately revoke all active refresh tokens for that user and add the user's active access token JTI claims to the revocation list.
6. WHEN an administrator explicitly revokes a user session via the DELETE /admin/users/{user_id}/sessions endpoint, THE Server SHALL revoke all refresh tokens for that user and add active JTI claims to the revocation list.
7. THE Server SHALL include a jti (JWT ID) claim in all issued access tokens to support individual token revocation.

### Requirement 5: Role-Based Access Control

**User Story:** As an administrator, I want to assign roles to users, so that access to system features is governed by organizational responsibilities.

#### Acceptance Criteria

1. THE Server SHALL support the following roles: Administrator, Recruiter, HiringManager, CommitteeMember, HRManager, Interviewer, and SuperAdministrator.
2. THE Server SHALL implement a UserRole many-to-many relationship allowing users to hold multiple roles simultaneously.
3. IF a user without Administrator or SuperAdministrator role attempts to manage users or roles, THEN THE Server SHALL return a 403 Forbidden response.
4. IF a user without Recruiter role attempts to create candidates or job requisitions, THEN THE Server SHALL return a 403 Forbidden response; this restriction applies to all roles including SuperAdministrator, which must also hold the Recruiter role to create candidates or job requisitions.
5. IF a user without Recruiter or HiringManager role attempts to transition an InterviewJourney between stages, THEN THE Server SHALL return a 403 Forbidden response.
6. THE Server SHALL enforce role checks via FastAPI dependency injection on all route handlers except the health check endpoint, the POST /token authentication endpoint, the POST /token/refresh endpoint, and public portal token-validation endpoints.
7. THE Server SHALL include role information in the JWT claims so that authorization decisions do not require additional database lookups for each request.
8. WHEN an Administrator or SuperAdministrator assigns or removes a role for a user, THE Server SHALL persist the change in the UserRole relationship and record the operation in the audit log; THE Server SHALL only record audit log entries when an actual role assignment or removal occurs, and SHALL NOT log access to the role management interface without a change.
9. IF a role assignment request specifies a role not in the supported roles list or assigns a role the user already holds, THEN THE Server SHALL return a 400 Bad Request response indicating the validation failure.
10. WHEN a user's roles are modified, THE Server SHALL require the user to re-authenticate to obtain a new JWT reflecting the updated roles, and THE Server SHALL continue to honor the previously issued JWT until its expiration.

### Requirement 6: Role and Privilege Management

**User Story:** As an administrator, I want to assign fine-grained privileges to roles, so that API authorization is governed by specific capabilities rather than broad role names alone.

#### Acceptance Criteria

1. THE Server SHALL define a fixed, system-managed set of Privilege entities with fields: PrivilegeID (UUID), Name (unique, snake_case identifier, max 100 characters), Description (max 500 characters), and ResourceCategory (the module or domain the privilege governs, e.g., candidates, requisitions, interviews).
2. THE Server SHALL store RolePrivilege entities representing the many-to-many assignment of Privileges to Roles, with fields: RolePrivilegeID (UUID), RoleName (FK to the supported roles list), PrivilegeID (FK), and AuditFields.
3. THE Server SHALL ship with a default RolePrivilege mapping that preserves all existing role-based access rules defined in Requirement 5, so that the system behaves identically before and after the privilege layer is introduced.
4. WHEN a request reaches a protected endpoint, THE Server SHALL evaluate authorization by checking whether the authenticated user holds at least one role that has been assigned the privilege required by that endpoint, in addition to any coarse-grained role checks already defined.
5. THE Server SHALL expose read-only endpoints for listing all system-defined privileges and retrieving the privilege assignments for a given role, restricted to Administrator and SuperAdministrator roles.
6. THE Server SHALL expose endpoints for assigning and removing privileges from roles, restricted to the SuperAdministrator role only.
7. IF a SuperAdministrator attempts to assign a PrivilegeID that does not exist in the system-defined privilege set, THEN THE Server SHALL reject the request with a 400 Bad Request response.
8. IF a SuperAdministrator attempts to remove a privilege assignment that would leave a role with no privileges, THEN THE Server SHALL reject the request with a 400 Bad Request response indicating that a role must retain at least one privilege.
9. WHEN a role's privilege assignments are modified, THE Server SHALL record an audit log entry containing the actor's UserID, the affected RoleName, the PrivilegeID added or removed, and the timestamp.
10. THE privilege layer augments coarse-grained role checks; existing role-based checks defined in Requirement 5 remain as a first-pass filter, and THE Server SHALL apply the privilege layer to provide fine-grained control within those role boundaries.

### Requirement 7: Security and Data Protection

**User Story:** As a security officer, I want sensitive data encrypted and access audited, so that candidate privacy is protected and compliance requirements are met.

#### Acceptance Criteria

1. THE Server SHALL encrypt the following PII fields at rest using the ENCRYPTION_KEY from environment configuration: Candidate Email, Candidate Phone, Candidate Name, and User Email.
2. THE Server SHALL encrypt the CandidateID and InterviewJourneyID columns in the CandidateInterviewJourney join table using the ENCRYPTION_KEY from environment configuration.
3. THE Server SHALL record an audit log entry for each stage transition, candidate change, user change, role assignment, InterviewSlot change, and AI agent call, where each entry includes the actor identity, timestamp, action type, affected entity identifier, and a summary of changed values.
4. THE Server SHALL use soft deletion for all entities, retaining records with a DeletedAt timestamp for audit purposes.
5. WHEN a candidate's InterviewJourney stage transitions to OfferAccepted, THE Server SHALL automatically set OverallStatus to Completed and encrypt the CandidateID and InterviewJourneyID in the CandidateInterviewJourney join table so that the hired candidate's interview data cannot be retrieved by lookup.
6. THE Server SHALL validate all input data on external-facing endpoints by enforcing type constraints, maximum field lengths, and allowed value ranges defined in the corresponding Pydantic request models, rejecting invalid input with a 422 response.
7. IF a request attempts to read interview artifacts for a candidate whose CandidateInterviewJourney join table keys are encrypted, THEN THE Server SHALL return a 403 Forbidden response indicating the data is no longer accessible.

### Requirement 8: Rate Limiting

**User Story:** As a platform operator, I want API rate limiting enforced at multiple levels, so that the system is protected from abuse, brute-force attacks, and noisy tenants.

#### Acceptance Criteria

1. THE Server SHALL enforce rate limiting on the POST /token and POST /token/refresh authentication endpoints, allowing a maximum of 5 failed attempts per source IP address within a 5-minute sliding window.
2. IF a source IP address exceeds 5 failed authentication attempts within a 5-minute window, THEN THE Server SHALL reject all subsequent authentication requests from that IP — regardless of whether the credentials would succeed or fail — with a 429 Too Many Requests response for a lockout period of 15 minutes, including a Retry-After header indicating the remaining lockout duration in seconds.
3. THE Server SHALL enforce per-tenant general API rate limiting with a configurable limit stored in the Organization entity (default 1000 requests per minute), applied across all authenticated endpoints for a given OrganizationID.
4. IF a tenant exceeds the configured request rate, THEN THE Server SHALL reject excess requests with a 429 Too Many Requests response including X-RateLimit-Limit, X-RateLimit-Remaining, and X-RateLimit-Reset headers.
5. THE Server SHALL enforce per-agent rate limiting on internal agent callback endpoints (routes under /internal/agents/), with configurable limits per agent identity derived from the X-Agent-API-Key header, defaulting to 100 requests per minute per agent.
6. IF an agent exceeds its configured rate limit, THEN THE Server SHALL reject excess requests with a 429 Too Many Requests response.
7. THE Server SHALL implement rate limiting using an in-memory sliding window counter with no external dependency, suitable for single-instance deployment.

### Requirement 9: User Invitation and Account Setup

**User Story:** As a new user, I want to receive an invitation email when an administrator adds me to the system, so that I can set my own password and activate my account without the administrator knowing my credentials.

#### Acceptance Criteria

1. WHEN an administrator creates a new user, THE Server SHALL set the user's Status to PendingInvitation and generate a cryptographically random Invitation Token of at least 32 bytes, store a SHA-256 hash of the token in the InvitationToken table with fields: InvitationTokenID (UUID), UserID (FK), TokenHash, ExpiresAt (timestamp, 72 hours from issuance), IsUsed (boolean, default false), and CreatedAt (timestamp).
2. WHEN an invitation token is generated, THE Server SHALL send an invitation email to the user's registered email address containing a unique invitation link that embeds the plain-text token as a query parameter; the email SHALL include the user's GivenName, the organization name, and the token expiry time.
3. WHEN a user submits a valid, non-expired, unused invitation token and a new password to the POST /auth/invitation/accept endpoint, THE Server SHALL validate the password against the password policy (minimum 12 characters, at least one uppercase letter, at least one lowercase letter, at least one digit, at least one special character), store the password using bcrypt hashing, mark the InvitationToken as used (IsUsed = true), and set the user's Status to Active.
4. IF the invitation token submitted to POST /auth/invitation/accept is expired, already used, or does not exist, THEN THE Server SHALL return a 400 Bad Request response indicating the token is invalid or expired, without revealing which condition applies.
5. IF the password submitted during invitation acceptance does not meet the password policy, THEN THE Server SHALL return a 422 Unprocessable Entity response indicating which policy rules were violated, and THE Server SHALL NOT mark the invitation token as used.
6. THE Server SHALL expose a POST /auth/invitation/resend endpoint restricted to Administrator and SuperAdministrator roles that accepts a UserID, invalidates any existing unused invitation tokens for that user, and issues a new invitation token and email; IF the user's Status is not PendingInvitation, THEN THE Server SHALL reject the request with a 400 Bad Request response.
7. IF an invitation token has not been used within 72 hours of issuance, THE Server SHALL treat it as expired and reject any acceptance attempt; the user's Status SHALL remain PendingInvitation until a valid token is accepted or the administrator resends the invitation.
8. WHEN a user successfully completes account setup via the invitation flow, THE Server SHALL record an audit log entry containing the UserID, the action type (AccountActivated), and the timestamp.
9. THE Server SHALL enforce rate limiting on the POST /auth/invitation/accept endpoint, allowing a maximum of 10 attempts per source IP address within a 10-minute sliding window, rejecting excess attempts with a 429 Too Many Requests response.

### Requirement 10: Password Reset

**User Story:** As a user, I want to reset my forgotten password by receiving a unique code on my registered email address, so that I can regain access to the system without administrator intervention.

#### Acceptance Criteria

1. THE Server SHALL expose a POST /auth/password-reset/request endpoint that accepts an email address and, IF a user with that email exists within any organization, generates a cryptographically random Password Reset Token of at least 32 bytes and stores a SHA-256 hash of the token in the PasswordResetToken table with fields: PasswordResetTokenID (UUID), UserID (FK), TokenHash, ExpiresAt (timestamp, 15 minutes from issuance), IsUsed (boolean, default false), and CreatedAt (timestamp).
2. WHEN a password reset token is generated, THE Server SHALL send an email to the user's registered address containing the plain-text token as a numeric or alphanumeric code; IF no user exists with the submitted email, THE Server SHALL return a 200 OK response without sending an email, so that the endpoint does not reveal whether an account exists for a given email address.
3. WHEN a user submits a valid, non-expired, unused password reset token and a new password to the POST /auth/password-reset/confirm endpoint, THE Server SHALL validate the new password against the password policy (minimum 12 characters, at least one uppercase letter, at least one lowercase letter, at least one digit, at least one special character, and not matching any of the user's last 5 passwords), store the new password using bcrypt hashing, mark the PasswordResetToken as used (IsUsed = true), and return a 200 OK response.
4. IF the password reset token submitted to POST /auth/password-reset/confirm is expired, already used, or does not exist, THEN THE Server SHALL return a 400 Bad Request response indicating the token is invalid or expired, without revealing which condition applies.
5. IF the new password submitted to POST /auth/password-reset/confirm does not meet the password policy or matches one of the user's last 5 passwords, THEN THE Server SHALL return a 422 Unprocessable Entity response indicating which policy rules were violated, and THE Server SHALL NOT mark the reset token as used.
6. WHEN a password reset is successfully completed, THE Server SHALL immediately revoke all active refresh tokens for that user and add the user's active access token JTI claims to the revocation list, forcing re-authentication on all active sessions.
7. IF the user's account Status is Locked or Inactive at the time of the POST /auth/password-reset/request submission, THE Server SHALL still return a 200 OK response without sending an email, so that the endpoint does not reveal account status to unauthenticated callers.
8. THE Server SHALL enforce rate limiting on the POST /auth/password-reset/request endpoint, allowing a maximum of 3 requests per source IP address within a 10-minute sliding window, rejecting excess requests with a 429 Too Many Requests response including a Retry-After header.
9. THE Server SHALL enforce rate limiting on the POST /auth/password-reset/confirm endpoint, allowing a maximum of 5 attempts per source IP address within a 10-minute sliding window, rejecting excess attempts with a 429 Too Many Requests response.
10. WHEN a password reset is successfully completed, THE Server SHALL record an audit log entry containing the UserID, the action type (PasswordReset), and the timestamp.
11. THE POST /auth/password-reset/request and POST /auth/password-reset/confirm endpoints SHALL be exempt from JWT authentication requirements and SHALL be accessible without a valid Bearer token.
