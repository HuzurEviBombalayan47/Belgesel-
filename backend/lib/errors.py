"""Shared API error types."""


class FeatureDisabled(Exception):
    """A capability that exists as an architectural seam but is intentionally not
    implemented yet (a later build stage). Rendered as an honest 501 by the global
    handler in server.py — never a fake success."""

    def __init__(self, feature: str, stage: int = 2, reason: str | None = None):
        self.feature = feature
        self.stage = stage
        self.reason = reason
        message = f"{feature} is not enabled yet — it ships in stage {stage} of the build plan."
        if reason:
            message += f" ({reason})"
        super().__init__(message)


class StorageNotConfigured(RuntimeError):
    """Cloudflare R2 credentials/bucket are missing from the environment."""


class ScenePlanningError(RuntimeError):
    """The AI scene planner failed or returned unusable output. Surfaced to the client
    as an explicit error — never swapped for placeholder scenes."""
