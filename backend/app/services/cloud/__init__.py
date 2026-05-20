"""Cloud-execution adapter package.

Intentionally empty. Re-exporting modal_adapter symbols here would force
`import modal` at base/local install time just for `from app.services.cloud
import mlx_serving_registry` to work. Each consumer imports the submodule it
needs directly so the optional cloud extra stays optional.
"""

from __future__ import annotations
