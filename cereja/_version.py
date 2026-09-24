"""Release metadata, readable by build tools without importing feature modules.

Update both representations together; the import contract tests verify that the
public version formatter produces the same PEP 440 value. Release metadata must
not depend on a runtime Git subprocess or on an installed distribution.
"""

VERSION = "2.3.0.final.0"
__version__ = "2.3.0"
