"""Public error codes never include provider responses or arbitrary exceptions."""

class ResearchError(RuntimeError):
    def __init__(self, code):
        if not isinstance(code, str) or not code.replace('_', '').isalnum() or code.upper() != code:
            code = 'RESEARCH_FAILED'
        self.code = code
        super().__init__(code)


def safe_error_code(exc):
    if isinstance(exc, ResearchError):
        return exc.code
    if isinstance(exc, FileNotFoundError):
        return 'INPUT_NOT_FOUND'
    if isinstance(exc, PermissionError):
        return 'FILE_PERMISSION_DENIED'
    if isinstance(exc, OSError):
        return 'IO_FAILED'
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return 'INVALID_DATA'
    return 'RESEARCH_FAILED'
