"""
Password reset service for password recovery.

Provides:
- PasswordResetService: Token generation, email dispatch, password update

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.10
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit_log
from app.decorators import transactional, read_only
from app.email_service import get_email_service
from app.modules.password_reset.models import PasswordResetToken
from app.modules.users.models import PasswordHistory, User, UserStatus
from app.modules.auth.service import (
    validate_password_policy,
    check_password_history,
    AuthService,
    RevocationCache,
)


PASSWORD_RESET_TOKEN_BYTES = 32
PASSWORD_RESET_TOKEN_TTL_MINUTES = 15


class PasswordResetService:
    """
    Password reset service for password recovery.
    
    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.10
    """

    def __init__(self, db: AsyncSession, revocation_cache: Optional[RevocationCache] = None):
        """
        Initialize the password reset service.
        
        Args:
            db: AsyncSession for database access
            revocation_cache: Optional RevocationCache for token revocation
        """
        self.db = db
        self.revocation_cache = revocation_cache or RevocationCache()

    @transactional(name="request_password_reset")
    async def request_reset(self, email: str, org_id: UUID | None = None) -> None:
        """
        Request a password reset for a user.
        
        Always returns 200 silently (no email disclosure).
        
        Args:
            email: User email address
            org_id: Organization ID for scoping (optional; if None, searches all orgs)
            
        Requirements: 10.1, 10.2, 10.7
        """
        # Look up user by email
        email_hash = hashlib.sha256(email.lower().encode()).hexdigest()
        
        if org_id:
            stmt = select(User).where(
                User.organization_id == org_id,
                User.email_hash == email_hash,
            )
        else:
            # Search across all organizations
            stmt = select(User).where(User.email_hash == email_hash)
        
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        # If user not found, locked, or inactive, return silently
        if not user or user.status in (UserStatus.LOCKED, UserStatus.INACTIVE):
            return
        
        # Generate reset token
        raw_token = secrets.token_bytes(PASSWORD_RESET_TOKEN_BYTES).hex()
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        now = datetime.now(timezone.utc)
        reset_token = PasswordResetToken(
            user_id=user.user_id,
            token_hash=token_hash,
            expires_at=now + timedelta(minutes=PASSWORD_RESET_TOKEN_TTL_MINUTES),
            is_used=False,
        )
        self.db.add(reset_token)
        await self.db.flush()
        
        # Send email with reset token
        await self._send_password_reset_email(user, raw_token)

    @read_only
    async def _send_password_reset_email(self, user: User, token: str) -> bool:
        """
        Send a password reset email to the user.
        
        Args:
            user: User entity
            token: Raw password reset token (plain text)
            
        Returns:
            True if email was sent successfully, False otherwise
            
        Requirements: 10.2
        """
        email_service = get_email_service()
        
        # Calculate expiry time
        now = datetime.now(timezone.utc)
        expiry_time = now + timedelta(minutes=PASSWORD_RESET_TOKEN_TTL_MINUTES)
        expiry_str = expiry_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Build password reset link (in production, this would be a full URL)
        reset_link = f"https://app.talentKru.ai/auth/password-reset/confirm?token={token}"
        
        # Build email body
        subject = "Password Reset Request - TalentKru.ai"
        
        body = f"""
Hello {user.given_name},

We received a request to reset your password for your TalentKru.ai account.

To reset your password, please click the link below:

{reset_link}

This password reset link will expire on {expiry_str}.

If you did not request a password reset, please ignore this email. Your password will not be changed.

Best regards,
The TalentKru.ai Team
"""
        
        html_body = f"""
<html>
<body>
<p>Hello {user.given_name},</p>

<p>We received a request to reset your password for your TalentKru.ai account.</p>

<p>To reset your password, please click the link below:</p>

<p><a href="{reset_link}">Reset Password</a></p>

<p>This password reset link will expire on {expiry_str}.</p>

<p>If you did not request a password reset, please ignore this email. Your password will not be changed.</p>

<p>Best regards,<br/>The TalentKru.ai Team</p>
</body>
</html>
"""
        
        return await email_service.send_email(
            to_email=user.email,
            subject=subject,
            body=body,
            html_body=html_body,
        )

    @transactional(name="confirm_password_reset")
    async def confirm_reset(
        self, token: str, new_password: str
    ) -> User:
        """
        Confirm a password reset and update the password.
        
        Args:
            token: Raw password reset token
            new_password: New password (plaintext)
            
        Returns:
            Updated User entity
            
        Raises:
            ValueError: If token is invalid, expired, used, or password policy violated
            
        Requirements: 10.3, 10.4, 10.5, 10.6
        """
        # Hash the token
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Look up the reset token
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
        result = await self.db.execute(stmt)
        reset_token = result.scalar_one_or_none()  # type: ignore[assignment]
        
        if not reset_token:
            raise ValueError("Invalid or expired password reset token")
        
        # Check if already used
        if reset_token.is_used:
            raise ValueError("Invalid or expired password reset token")
        
        # Check if expired
        now = datetime.now(timezone.utc)
        if reset_token.expires_at < now:
            raise ValueError("Invalid or expired password reset token")
        
        # Get the user
        user = await self.db.get(User, reset_token.user_id)  # type: ignore[arg-type]  # type: ignore[assignment]
        if not user:
            raise ValueError("Invalid or expired password reset token")
        
        # Validate password policy
        violations = validate_password_policy(new_password)
        if violations:
            raise ValueError(f"Password does not meet policy requirements: {', '.join(violations)}")
        
        # Check password history
        if await check_password_history(user.user_id, new_password, self.db):
            raise ValueError("Password has been used recently")
        
        # Hash password
        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        
        # Update user
        user.hashed_password = hashed_password
        await self.db.flush()
        
        # Add to password history
        history = PasswordHistory(
            user_id=user.user_id,
            hashed_password=hashed_password,
        )
        self.db.add(history)
        await self.db.flush()
        
        # Mark reset token as used
        reset_token.is_used = True  # type: ignore[assignment]
        await self.db.flush()
        
        # Revoke all user tokens
        auth_service = AuthService(self.db, self.revocation_cache)
        await auth_service.revoke_all_user_tokens(user.user_id, reason="password_reset")
        
        # Write audit log entry (PasswordReset)
        await write_audit_log(
            actor_id=user.user_id,
            action="PasswordReset",
            target_entity="User",
            target_id=user.user_id,
            org_id=user.organization_id,
            timestamp=now,
            db=self.db,
        )
        
        return user
