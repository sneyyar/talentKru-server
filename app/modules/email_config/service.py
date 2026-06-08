"""
Email configuration service for managing organization-level and global email settings.

Provides:
- EmailConfigService: Credential encryption, provider validation, system-wide settings

Requirements: 6.1, 6.2, 6.5, 6.6, 6.7, 6.8
"""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.crypto import encrypt_field, decrypt_field
from app.decorators import transactional, read_only
from app.modules.email_config.models import (
    OrganizationEmailConfig,
    SystemSetting,
    ProviderType,
)
from app.observability.logging import get_logger

logger = get_logger(__name__)


class EmailConfigService:
    """Service for managing email configuration at organization and system level."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @transactional()
    async def create_or_update_config(
        self,
        org_id: UUID,
        provider_type: str,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        smtp_use_tls: bool | None = None,
        third_party_api_key: str | None = None,
        third_party_provider_region: str | None = None,
        from_address: str | None = None,
        from_name: str | None = None,
        email_notifications_enabled: bool = True,
    ) -> OrganizationEmailConfig:
        """
        Create or update organization email configuration with validation.
        
        Validates provider-specific required fields:
        - SMTP requires: smtp_host, smtp_port, smtp_username, smtp_password
        - SENDGRID/SES require: third_party_api_key
        
        Encrypts smtp_password and third_party_api_key before storing.
        
        Args:
            org_id: Organization ID
            provider_type: Email provider type (SMTP, SENDGRID, or SES)
            smtp_host: SMTP host (required for SMTP)
            smtp_port: SMTP port (required for SMTP)
            smtp_username: SMTP username (required for SMTP)
            smtp_password: SMTP password (required for SMTP, will be encrypted)
            smtp_use_tls: Whether to use TLS for SMTP
            third_party_api_key: API key for SendGrid/SES (required for those providers, encrypted)
            third_party_provider_region: Region for SES
            from_address: From email address
            from_name: From display name
            email_notifications_enabled: Whether notifications are enabled
            
        Returns:
            The created or updated OrganizationEmailConfig
            
        Raises:
            HTTPException: 422 if validation fails
        """
        # Validate provider type
        provider_type_upper = provider_type.upper()
        if provider_type_upper not in {e.value for e in ProviderType}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid provider_type: {provider_type}. Must be one of: SMTP, SENDGRID, SES",
            )

        # Validate provider-specific required fields
        missing_fields = []
        
        if provider_type_upper == ProviderType.SMTP.value:
            if not smtp_host:
                missing_fields.append("smtp_host")
            if smtp_port is None:
                missing_fields.append("smtp_port")
            if not smtp_username:
                missing_fields.append("smtp_username")
            if not smtp_password:
                missing_fields.append("smtp_password")
        elif provider_type_upper in {ProviderType.SENDGRID.value, ProviderType.SES.value}:
            if not third_party_api_key:
                missing_fields.append("third_party_api_key")

        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing required fields for provider {provider_type_upper}: {', '.join(missing_fields)}",
            )

        # Encrypt sensitive fields
        encrypted_password = None
        if smtp_password:
            encrypted_password = encrypt_field(smtp_password)

        encrypted_api_key = None
        if third_party_api_key:
            encrypted_api_key = encrypt_field(third_party_api_key)

        # Check if config already exists
        result = await self.db.execute(
            select(OrganizationEmailConfig).where(
                OrganizationEmailConfig.organization_id == org_id,
                OrganizationEmailConfig.deleted_at.is_(None),
            )
        )
        existing_config = result.scalar_one_or_none()

        if existing_config:
            # Update existing config
            existing_config.provider_type = provider_type_upper
            existing_config.email_notifications_enabled = email_notifications_enabled
            existing_config.smtp_host = smtp_host
            existing_config.smtp_port = smtp_port
            existing_config.smtp_username = smtp_username
            existing_config.smtp_password = encrypted_password
            existing_config.smtp_use_tls = smtp_use_tls
            existing_config.third_party_api_key = encrypted_api_key
            existing_config.third_party_provider_region = third_party_provider_region
            existing_config.from_address = from_address or existing_config.from_address
            existing_config.from_name = from_name or existing_config.from_name
            config = existing_config
            logger.info(
                "email_config_updated",
                org_id=str(org_id),
                provider_type=provider_type_upper,
            )
        else:
            # Create new config
            from uuid import uuid4
            config = OrganizationEmailConfig(
                organization_email_config_id=uuid4(),
                organization_id=org_id,
                email_notifications_enabled=email_notifications_enabled,
                provider_type=provider_type_upper,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_username=smtp_username,
                smtp_password=encrypted_password,
                smtp_use_tls=smtp_use_tls,
                third_party_api_key=encrypted_api_key,
                third_party_provider_region=third_party_provider_region,
                from_address=from_address,
                from_name=from_name,
            )
            self.db.add(config)
            logger.info(
                "email_config_created",
                org_id=str(org_id),
                provider_type=provider_type_upper,
            )

        await self.db.flush()
        return config

    @read_only
    async def get_config(self, org_id: UUID) -> OrganizationEmailConfig | None:
        """
        Retrieve organization email configuration (org-scoped).
        
        Returns config with encrypted fields masked in the response schema
        (handled by router/schema layer).
        
        Args:
            org_id: Organization ID
            
        Returns:
            The OrganizationEmailConfig or None if not found
        """
        result = await self.db.execute(
            select(OrganizationEmailConfig).where(
                OrganizationEmailConfig.organization_id == org_id,
                OrganizationEmailConfig.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @read_only
    async def get_global_setting(self, setting_key: str) -> SystemSetting | None:
        """
        Retrieve a global system setting by key.
        
        Args:
            setting_key: The setting key (e.g., 'email_notifications_enabled')
            
        Returns:
            The SystemSetting or None if not found
        """
        result = await self.db.execute(
            select(SystemSetting).where(
                SystemSetting.setting_key == setting_key,
                SystemSetting.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @transactional()
    async def update_global_setting(
        self,
        setting_key: str,
        setting_value: str,
    ) -> SystemSetting:
        """
        Update a global system setting.
        
        Validates that setting_value is "true" or "false" for boolean settings.
        
        Args:
            setting_key: The setting key
            setting_value: The new value (must be "true" or "false" for email_notifications_enabled)
            
        Returns:
            The updated SystemSetting
            
        Raises:
            HTTPException: 422 if validation fails
        """
        # Validate value for email_notifications_enabled
        if setting_key == "email_notifications_enabled":
            if setting_value.lower() not in {"true", "false"}:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid value for {setting_key}. Must be 'true' or 'false', got '{setting_value}'",
                )

        # Fetch existing setting
        result = await self.db.execute(
            select(SystemSetting).where(
                SystemSetting.setting_key == setting_key,
                SystemSetting.deleted_at.is_(None),
            )
        )
        setting = result.scalar_one_or_none()

        if not setting:
            # Create if doesn't exist
            from uuid import uuid4
            setting = SystemSetting(
                setting_key=setting_key,
                setting_value=setting_value,
            )
            self.db.add(setting)
            logger.info(
                "system_setting_created",
                setting_key=setting_key,
                setting_value=setting_value,
            )
        else:
            # Update existing
            setting.setting_value = setting_value
            logger.info(
                "system_setting_updated",
                setting_key=setting_key,
                setting_value=setting_value,
            )

        await self.db.flush()
        return setting
