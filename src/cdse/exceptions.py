"""Custom exceptions for CDSE Client."""


class CDSEError(Exception):
    """Base exception for CDSE Client errors."""

    pass


class AuthenticationError(CDSEError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(self.message)


class CatalogError(CDSEError):
    """Raised when catalog search fails."""

    def __init__(self, message: str = "Catalog search failed"):
        self.message = message
        super().__init__(self.message)


class DownloadError(CDSEError):
    """Raised when download fails."""

    def __init__(self, message: str = "Download failed", product_id: str = None):
        self.message = message
        self.product_id = product_id
        super().__init__(self.message)


class ValidationError(CDSEError):
    """Raised when input validation fails."""

    def __init__(self, message: str = "Validation failed", field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)
