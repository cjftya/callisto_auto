class CLIError(RuntimeError):
    """Sanitized CLI failure; never contains prompts, screenshots or stderr."""


class CLIAuthenticationError(CLIError):
    status_code = 401


class CLIProtocolError(CLIError):
    status_code = 422


class UnsupportedCapability(CLIError):
    status_code = 400
