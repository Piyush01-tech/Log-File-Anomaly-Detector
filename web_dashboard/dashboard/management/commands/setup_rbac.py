"""
dashboard/management/commands/setup_rbac.py — Phase 9B
=========================================================
Idempotent management command to configure Django Groups and Permissions.

USAGE:
  python manage.py setup_rbac

PURPOSE:
  - Creates the "Super Admin" and "Analyst" groups.
  - Creates all 14 custom permissions on the User content type.
  - Assigns appropriate permissions to each group.
  - Syncs all existing users to their correct group based on role.
  - Safe to run multiple times (fully idempotent via get_or_create).

WHY A MANAGEMENT COMMAND:
  - Permissions must exist in the database before they can be assigned.
  - Django's auto-created permissions (add/change/delete/view) are
    tied to models, but our custom permissions are domain-specific
    (e.g., "upload_evtx", "manage_users").
  - This command is run once after deployment (or migrations) and
    can be re-run safely to sync any drift.

DEPLOYMENT:
  Run after `python manage.py migrate`:
    python manage.py setup_rbac

DESIGN DECISIONS:
  - Uses `get_or_create` for all groups and permissions (idempotent).
  - Assigns permissions by clearing and re-setting to handle
    permission additions in future phases.
  - Syncs ALL existing users, not just newly created ones.
  - Outputs colored status messages for operator visibility.
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from dashboard.permissions import DashboardPermissions

logger = logging.getLogger(__name__)

User = get_user_model()


class Command(BaseCommand):
    """
    Management command to set up RBAC groups and permissions.

    Creates groups, permissions, assigns permissions to groups,
    and syncs existing users to their correct groups.
    """

    help = (
        "Set up RBAC groups and permissions for the SOC Dashboard. "
        "Safe to run multiple times (idempotent)."
    )

    def handle(self, *args, **options):
        """Execute the RBAC setup."""
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n=== Phase 9B: RBAC Setup ==="
        ))

        # Step 1: Create custom permissions
        self._create_permissions()

        # Step 2: Create groups
        admin_group = self._create_group(
            DashboardPermissions.GROUP_SUPER_ADMIN,
            DashboardPermissions.get_super_admin_permissions(),
        )
        analyst_group = self._create_group(
            DashboardPermissions.GROUP_ANALYST,
            DashboardPermissions.get_analyst_permissions(),
        )

        # Step 3: Sync existing users
        self._sync_users(admin_group, analyst_group)

        self.stdout.write(self.style.SUCCESS(
            "\n[SUCCESS] RBAC setup completed successfully.\n"
        ))

    def _create_permissions(self):
        """Create all custom permissions on the User content type."""
        self.stdout.write("\n* Creating custom permissions...")

        # Get the content type for our User model
        content_type = ContentType.objects.get_for_model(User)

        all_permissions = DashboardPermissions.get_all_custom_permissions()
        created_count = 0
        existing_count = 0

        for codename, description in all_permissions:
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={"name": description},
            )
            if created:
                created_count += 1
                self.stdout.write(
                    f"  + Created permission: {codename}"
                )
            else:
                existing_count += 1
                # Update description if it changed
                if perm.name != description:
                    perm.name = description
                    perm.save(update_fields=["name"])
                    self.stdout.write(
                        f"  ~ Updated description: {codename}"
                    )

        self.stdout.write(self.style.SUCCESS(
            f"  Permissions: {created_count} created, "
            f"{existing_count} already existed."
        ))

    def _create_group(
        self, group_name: str, permission_codenames: list[str]
    ) -> Group:
        """
        Create a group and assign permissions to it.

        Args:
            group_name:           Name of the Django Group.
            permission_codenames: List of permission codenames to assign.

        Returns:
            The created or existing Group instance.
        """
        self.stdout.write(f"\n* Setting up group: '{group_name}'...")

        group, created = Group.objects.get_or_create(name=group_name)
        if created:
            self.stdout.write(
                f"  + Created group: {group_name}"
            )
        else:
            self.stdout.write(
                f"  - Group already exists: {group_name}"
            )

        # Get the content type for our User model
        content_type = ContentType.objects.get_for_model(User)

        # Fetch all matching permissions
        permissions = Permission.objects.filter(
            codename__in=permission_codenames,
            content_type=content_type,
        )

        found_codenames = set(permissions.values_list("codename", flat=True))
        missing = set(permission_codenames) - found_codenames
        if missing:
            self.stdout.write(self.style.WARNING(
                f"  ! Missing permissions (run setup_rbac again): {missing}"
            ))

        # Clear and re-assign permissions (handles additions in future phases)
        group.permissions.set(permissions)

        self.stdout.write(self.style.SUCCESS(
            f"  Assigned {permissions.count()} permissions to '{group_name}'."
        ))

        # List assigned permissions
        for perm in permissions:
            self.stdout.write(f"    v {perm.codename}")

        return group

    def _sync_users(self, admin_group: Group, analyst_group: Group):
        """
        Sync all existing users to their correct groups.

        Users with role=ADMIN → Super Admin group.
        Users with role=ANALYST → Analyst group.

        Args:
            admin_group:   The Super Admin Group instance.
            analyst_group: The Analyst Group instance.
        """
        self.stdout.write("\n* Syncing existing users to groups...")

        admin_users = User.objects.filter(role="ADMIN")
        analyst_users = User.objects.filter(role="ANALYST")

        admin_synced = 0
        analyst_synced = 0

        for user in admin_users:
            user.groups.remove(analyst_group)
            if not user.groups.filter(pk=admin_group.pk).exists():
                user.groups.add(admin_group)
            admin_synced += 1
            self.stdout.write(
                f"  + {user.username} -> Super Admin"
            )

            # Ensure admin users have is_staff
            if not user.is_staff:
                User.objects.filter(pk=user.pk).update(is_staff=True)
                self.stdout.write(
                    f"    -> Set is_staff=True for {user.username}"
                )

        for user in analyst_users:
            user.groups.remove(admin_group)
            if not user.groups.filter(pk=analyst_group.pk).exists():
                user.groups.add(analyst_group)
            analyst_synced += 1
            self.stdout.write(
                f"  + {user.username} -> Analyst"
            )

        total = admin_synced + analyst_synced
        self.stdout.write(self.style.SUCCESS(
            f"  Synced {total} users: "
            f"{admin_synced} admins, {analyst_synced} analysts."
        ))
