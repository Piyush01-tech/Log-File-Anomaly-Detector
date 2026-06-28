"""
dashboard/managers.py
======================
Custom model managers for the dashboard application.

WHY THIS EXISTS:
  - Django's default UserManager creates users with just username/password.
  - Our custom User model adds a 'role' field that must be set during
    user creation for data integrity.
  - This manager ensures createsuperuser and programmatic user creation
    always produce properly-roled users.

USAGE:
  User.objects.create_user(
      username="analyst1",
      email="analyst1@corp.com",
      password="securepass",
      role=User.Role.ANALYST
  )
"""

import logging
from typing import Any, Optional

from django.contrib.auth.models import BaseUserManager

logger = logging.getLogger(__name__)


class UserManager(BaseUserManager):
    """
    Custom manager for the User model.

    Extends BaseUserManager to enforce role assignment during user
    creation and to normalize email addresses consistently.

    This manager is required because our User model adds a 'role'
    field that must be populated on every create path (interactive
    createsuperuser, programmatic creation, fixtures).
    """

    def create_user(
        self,
        username: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        **extra_fields: Any,
    ) -> "User":  # noqa: F821 — forward reference resolved at runtime
        """
        Create and return a regular user with the given credentials.

        Args:
            username: Unique username for authentication.
            email:    Email address (normalized to lowercase domain).
            password: Raw password (hashed before storage).
            **extra_fields: Additional model fields (e.g., role).

        Returns:
            The newly created User instance.

        Raises:
            ValueError: If username is not provided.
        """
        if not username:
            raise ValueError("Users must have a username.")

        if email:
            email = self.normalize_email(email)

        # Default role to ANALYST if not explicitly provided
        from .models import User  # Local import to avoid circular dependency
        extra_fields.setdefault("role", User.Role.ANALYST)

        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        logger.info(
            "Created user '%s' with role '%s'.",
            username,
            extra_fields.get("role", User.Role.ANALYST),
        )

        return user

    def create_superuser(
        self,
        username: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        **extra_fields: Any,
    ) -> "User":  # noqa: F821
        """
        Create and return a superuser with admin privileges.

        Superusers always get the ADMIN role and Django's built-in
        is_staff and is_superuser flags set to True.

        Args:
            username: Unique username for authentication.
            email:    Email address (normalized to lowercase domain).
            password: Raw password (hashed before storage).
            **extra_fields: Additional model fields.

        Returns:
            The newly created superuser instance.

        Raises:
            ValueError: If is_staff or is_superuser is explicitly
                        set to False.
        """
        from .models import User  # Local import to avoid circular dependency

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        logger.info("Creating superuser '%s'.", username)

        return self.create_user(
            username=username,
            email=email,
            password=password,
            **extra_fields,
        )
