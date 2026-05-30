"""
Invitation service for user account setup and activation.

Provides:
- InvitationService: Token generation, email dispatch, account activation

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
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
from app.email_service import get_email_service
from app.modules.invitations.models import InvitationToken
from app.modules.users.models import PasswordHistory, User, UserStatus
from app.modules.auth.service import validate_password_policy


INVITATION_TOKEN_BYTES = 32
INVITATION_TOKEN_TTL_HOURS = 72


class InvitationService:
    """
    Invitation service for user account setup.
    
    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the invitation service.
        
        Args:
            db: AsyncSession for database access
        """
        self.db = db

    async def generate_invitation(self, user_id: UUID) -> str:
        """
        Generate an invitation token for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Raw invitation token (hex string)
            
        Requirements: 9.1
        """
        raw_token = secrets.token_bytes(INVITATION_TOKEN_BYTES).hex()
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        now = datetime.now(timezone.utc)
        invitation = InvitationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=now + timedelta(hours=INVITATION_TOKEN_TTL_HOURS),
            is_used=False,
        )
        self.db.add(invitation)
        await self.db.flush()
        
        return raw_token

    async def send_invitation_email(
        self, user: User, token: str, org_name: str
    ) -> bool:
        """
        Send an invitation email to the user.
        
        Args:
            user: User entity
            token: Raw invitation token (plain text)
            org_name: Organization name
            
        Returns:
            True if email was sent successfully, False otherwise
            
        Requirements: 9.2
        """
        email_service = get_email_service()
        
        # Calculate expiry time
        now = datetime.now(timezone.utc)
        expiry_time = now + timedelta(hours=INVITATION_TOKEN_TTL_HOURS)
        expiry_str = expiry_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Build invitation link (in production, this would be a full URL)
        invitation_link = f"https://app.talentKru.ai/auth/invitation/accept?token={token}"
        
        # Build email body
        subject = f"Welcome to {org_name} - Complete Your Account Setup"
        
        body = f"""
Hello {user.given_name},

Welcome to {org_name}! An administrator has invited you to join our recruiting platform.

To complete your account setup and activate your account, please click the link below:

{invitation_link}

This invitation link will expire on {expiry_str}.

If you did not expect this invitation, please contact your administrator.

Best regards,
The TalentKru.ai Team
"""
        
        html_body = f"""
<html>
<body>
<p>Hello {user.given_name},</p>

<p>Welcome to {org_name}! An administrator has invited you to join our recruiting platform.</p>

<p>To complete your account setup and activate your account, please click the link below:</p>

<p><a href="{invitation_link}">Accept Invitation</a></p>

<p>This invitation link will expire on {expiry_str}.</p>

<p>If you did not expect this invitation, please contact your administrator.</p>

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

    async def accept_invitation(
        self, token: str, password: str
    ) -> User:
        """
        Accept an invitation and activate the user account.
        
        Args:
            token: Raw invitation token
            password: New password (plaintext)
            
        Returns:
            Activated User entity
            
        Raises:
            ValueError: If token is invalid, expired, used, or password policy violated
            
        Requirements: 9.3, 9.4, 9.5, 9.7, 9.8
        """
        # Hash the token
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Look up the invitation token
        stmt = select(InvitationToken).where(
            InvitationToken.token_hash == token_hash
        )
        result = await self.db.execute(stmt)
        invitation = result.scalar_one_or_none()
        
        if not invitation:
            raise ValueError("Invalid invitation token")
        
        # Check if already used
        if invitation.is_used:
            raise ValueError("Invitation token has already been used")
        
        # Check if expired
        now = datetime.now(timezone.utc)
        if invitation.expires_at < now:
            raise ValueError("Invitation token has expired")
        
        # Get the user
        user = await self.db.get(User, invitation.user_id)
        if not user:
            raise ValueError("User not found")
        
        # Validate password policy
        violations = validate_password_policy(password)
        if violations:
            raise ValueError(f"Password policy violations: {', '.join(violations)}")
        
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        
        # Update user
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        await self.db.flush()
        
        # Add to password history
        history = PasswordHistory(
            user_id=user.user_id,
            hashed_password=hashed_password,
        )
        self.db.add(history)
        await self.db.flush()
        
        # Mark invitation as used
        invitation.is_used = True
        await self.db.flush()
        
        # Write audit log entry (AccountActivated)
        await write_audit_log(
            actor_id=user.user_id,
            action="AccountActivated",
            target_entity="User",
            target_id=user.user_id,
            org_id=user.organization_id,
            timestamp=now,
            db=self.db,
        )
        
        return user

    async def resend_invitation(
        self, user_id: UUID, org_id: UUID, actor_id: UUID
    ) -> str:
        """
        Resend an invitation to a user.
        
        Args:
            user_id: User ID
            org_id: Organization ID for scoping
            actor_id: User ID of the actor performing the resend
            
        Returns:
            New raw invitation token
            
        Raises:
            ValueError: If user is not in PendingInvitation status
            
        Requirements: 9.6
        """
        # Get the user
        stmt = select(User).where(
            User.user_id == user_id,
            User.organization_id == org_id,
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")
        
        if user.status != UserStatus.PENDING_INVITATION:
            raise ValueError("User is not in PendingInvitation status")
        
        # Invalidate existing unused tokens
        now = datetime.now(timezone.utc)
        stmt = select(InvitationToken).where(
            InvitationToken.user_id == user_id,
            InvitationToken.is_used == False,
            InvitationToken.expires_at > now,
        )
        result = await self.db.execute(stmt)
        existing_tokens = result.scalars().all()
        
        for token in existing_tokens:
            token.is_used = True
        
        await self.db.flush()
        
        # Generate new token
        new_token = await self.generate_invitation(user_id)
        
        # Send invitation email
        # TODO: Get organization name from org_id
        org_name = "TalentKru.ai"
        await self.send_invitation_email(user, new_token, org_name)
        
        # Write audit log entry
        await write_audit_log(
            actor_id=actor_id,
            action="InvitationResent",
            target_entity="User",
            target_id=user_id,
            org_id=org_id,
            timestamp=now,
            db=self.db,
        )
        
        return new_token
