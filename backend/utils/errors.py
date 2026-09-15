"""Custom exception hierarchy used across agents and integrations."""


class WorkflowOSError(Exception):
    """Base class for all application errors."""


class AgentExecutionError(WorkflowOSError):
    """Raised when an agent fails to complete its task after all fallbacks."""

    def __init__(self, agent_name: str, message: str, cause: Exception | None = None):
        self.agent_name = agent_name
        self.cause = cause
        super().__init__(f"[{agent_name}] {message}")


class NegotiationFailedError(WorkflowOSError):
    """Raised when two agents cannot reach agreement within max iterations."""

    def __init__(self, agent_a: str, agent_b: str, reason: str):
        self.agent_a = agent_a
        self.agent_b = agent_b
        self.reason = reason
        super().__init__(f"Negotiation between {agent_a} and {agent_b} failed: {reason}")


class IntegrationError(WorkflowOSError):
    """Raised by an integration client wrapper on unrecoverable API errors."""

    def __init__(self, service: str, message: str, status_code: int | None = None):
        self.service = service
        self.status_code = status_code
        super().__init__(f"[{service}] {message}" + (f" (status={status_code})" if status_code else ""))


class RateLimitError(IntegrationError):
    """Raised when an external API rate limit is hit."""


class AuthenticationError(IntegrationError):
    """Raised when an external API rejects credentials."""
