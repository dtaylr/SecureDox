"""ORM models.

Importing this package registers every mapper on `Base.metadata`, which is
what Alembic's autogenerate and the test fixtures both rely on. Import the
package, never the individual modules, or autogenerate will propose dropping
the tables it did not see.
"""

from __future__ import annotations

from .audit import AuditEvent
from .document import Document
from .extraction import ExtractedField
from .tenant import Tenant
from .validation import ValidationResult

__all__ = [
    "AuditEvent",
    "Document",
    "ExtractedField",
    "Tenant",
    "ValidationResult",
]
