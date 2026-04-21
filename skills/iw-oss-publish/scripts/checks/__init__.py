"""Check modules. Importing this package triggers registration of every check.

Add new check modules here so they get imported (and their decorators fire).
"""

from . import (  # noqa: F401  — side effect: registers checks
    ci_cd,
    community,
    contributor,
    dependencies,
    environment,
    export_control,
    github,
    governance,
    history,
    hygiene,
    internal_refs,
    license_check,
    privacy,
    release,
    secrets,
    trademark,
)
