"""DEPRECATED: ht_l1_core renamed to hlpp_l0_contracts (HLPP v1.0 rebrand 2026-05-20).

Backward-compat shim — re-routes all submodule imports to hlpp_l0_contracts via sys.modules.
Removes after Phase 8b cleanup (1 week observation window).
"""
import sys
import warnings
import hlpp_l0_contracts as _new

warnings.warn(
    "ht_l1_core is deprecated → use hlpp_l0_contracts (HLPP v1.0 rebrand). Shim removes after Phase 8b.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-route all submodule access to hlpp_l0_contracts equivalents
_aliases = ["schema", "collector", "llm", "protocols", "browser_fetch",
            "http", "idempotency", "stamping", "sources_config",
            "backfillable", "source_status"]
for _name in _aliases:
    try:
        _sub = __import__(f"hlpp_l0_contracts.{_name}", fromlist=[_name])
        sys.modules[f"ht_l1_core.{_name}"] = _sub
    except ImportError:
        pass

# Schema submodules (nested)
for _sub_name in ["crawler_base", "lineage", "provenance", "vintage"]:
    try:
        _sub = __import__(f"hlpp_l0_contracts.schema.{_sub_name}", fromlist=[_sub_name])
        sys.modules[f"ht_l1_core.schema.{_sub_name}"] = _sub
    except ImportError:
        pass

# Top-level re-exports
from hlpp_l0_contracts import *  # noqa: F401, F403
