"""Subprocess environment sanitization and secret-stripping whitelist."""
from __future__ import annotations

import os
from typing import Dict, List, Optional

WHITELIST_ENV_VARS = frozenset({
    "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
    "PATH", "TEMP", "TMP",
    "USERPROFILE", "LOCALAPPDATA", "APPDATA",
    "PYTHONPATH", "PYTHONHOME",
    "FPF_TASK_ID", "FPF_WORKTREE_PATH",
    "LANG", "LC_ALL", "HOME",
})

SENSITIVE_PATTERNS = (
    "KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH", "CREDENTIAL", "PRIVATE",
    "GITHUB_PAT", "GH_TOKEN", "AWS_ACCESS", "OPENAI_API",
)


def sanitize_env(
    source_env: Optional[Dict[str, str]] = None,
    custom_injections: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Filter environment variables strictly against whitelist, purging sensitive secrets."""
    source = source_env if source_env is not None else os.environ
    clean_env = {}

    for k, v in source.items():
        upper = k.upper()
        if upper in WHITELIST_ENV_VARS:
            # Double check that no sensitive substring crept into a whitelisted name
            if not any(pattern in upper for pattern in SENSITIVE_PATTERNS):
                clean_env[k] = v

    if custom_injections:
        for k, v in custom_injections.items():
            clean_env[k] = v

    return clean_env


def audit_env_leaks(env_dict: Dict[str, str]) -> List[str]:
    """Audit a dictionary of environment variables and return list of leaking secrets."""
    leaks = []
    for k in env_dict:
        upper = k.upper()
        if any(pattern in upper for pattern in SENSITIVE_PATTERNS):
            leaks.append(k)
        elif upper not in WHITELIST_ENV_VARS:
            leaks.append(f"NON_WHITELISTED:{k}")
    return leaks
