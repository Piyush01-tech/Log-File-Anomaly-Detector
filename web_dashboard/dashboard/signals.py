"""
dashboard/signals.py — Phase 9B
===================================
Django signals for keeping User.role and Django Groups in sync.

PURPOSE:
  - Automatically assigns users to the correct Django Group when
    their `role` field changes.
  - Ensures consistency between the `role` CharField and the
    Django Group-based permission system.

WHY THIS EXISTS:
  - Users can be created via multiple paths: registration form,
    `createsuperuser`, Django admin, programmatic creation.
  - Each path sets the `role` field, but may not assign the
    corresponding Django Group.
  - This signal catches ALL save paths and ensures the user is
    in the correct group.

SIGNAL:
  user_post_save — Fires after User.save(). Assigns the user to
                   the correct group based on their `role` field.

DESIGN DECISIONS:
  - Uses `post_save` (not `pre_save`) because the user must exist
    in the database before group membership can be set (M2M relation).
  - Silently handles missing groups (e.g., before `setup_rbac` runs)
    to prevent app startup failures.
  - Removes user from ALL dashboard groups before adding to the
    correct one — prevents stale group membership.
  - Connected in `DashboardConfig.ready()` to ensure it runs at
    app startup.
"""

import logging

from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# Map of role values to group names
# Matches the constants in permissions.py
_ROLE_GROUP_MAP = {
    "ADMIN": "Super Admin",
    "ANALYST": "Analyst",
}

# All managed group names (used for cleanup)
_ALL_MANAGED_GROUPS = set(_ROLE_GROUP_MAP.values())


@receiver(post_save, sender="dashboard.User")
def sync_user_group_on_save(sender, instance, created, **kwargs):
    """
    Sync user's Django Group membership when their role changes.

    Triggered after every User.save(). Ensures the user is in
    exactly one role-based group:
      - role=ADMIN  → "Super Admin" group
      - role=ANALYST → "Analyst" group

    For ADMIN users, also sets `is_staff=True` so they can access
    the Django admin panel.

    Args:
        sender:   The User model class.
        instance: The User instance being saved.
        created:  Boolean indicating if this is a new user.
        **kwargs: Additional signal kwargs.
    """
    try:
        target_group_name = _ROLE_GROUP_MAP.get(instance.role)
        if not target_group_name:
            logger.warning(
                "User '%s' has unknown role '%s' — skipping group sync.",
                instance.username,
                instance.role,
            )
            return

        # Get the target group (may not exist before setup_rbac runs)
        try:
            target_group = Group.objects.get(name=target_group_name)
        except Group.DoesNotExist:
            logger.debug(
                "Group '%s' does not exist yet — skipping sync for '%s'. "
                "Run 'python manage.py setup_rbac' to create groups.",
                target_group_name,
                instance.username,
            )
            return

        # Remove from all managed groups first
        managed_groups = Group.objects.filter(name__in=_ALL_MANAGED_GROUPS)
        for group in managed_groups:
            if group.name != target_group_name:
                instance.groups.remove(group)

        # Add to the correct group (idempotent — no duplicate entries)
        if not instance.groups.filter(pk=target_group.pk).exists():
            instance.groups.add(target_group)
            logger.info(
                "User '%s' added to group '%s' (role=%s).",
                instance.username,
                target_group_name,
                instance.role,
            )

        # Ensure ADMIN users have is_staff for Django admin access
        if instance.role == "ADMIN" and not instance.is_staff:
            # Use update() to avoid triggering post_save recursion
            sender.objects.filter(pk=instance.pk).update(is_staff=True)
            logger.info(
                "Set is_staff=True for admin user '%s'.",
                instance.username,
            )

    except Exception:
        # Signals should never crash the application
        logger.exception(
            "Error syncing group for user '%s'.", instance.username
        )
