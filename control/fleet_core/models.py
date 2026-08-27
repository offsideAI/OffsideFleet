import uuid

from django.db import models


class Workspace(models.Model):
    """Tenancy root. Every tenant-owned row carries a workspace FK from day one
    (ADR-006), even though auth/membership arrives in M7."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.slug


DEFAULT_WORKSPACE_SLUG = "default"


def default_workspace() -> Workspace:
    """Dev/M1 convenience until real workspaces land in M7."""
    ws, _ = Workspace.objects.get_or_create(
        slug=DEFAULT_WORKSPACE_SLUG, defaults={"name": "Default Workspace"}
    )
    return ws
