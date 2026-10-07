"""Personal information and privacy sanitizer for feedback, tracebacks, and logs.

Ensures usernames, user home directories, and sensitive local machine paths are
automatically redacted to <username> or canonical relative paths before saving
bug reports, code reviews, tracebacks, and console logs.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path
import re
from typing import Optional, Set


def get_usernames_to_redact() -> Set[str]:
    """Discover local username candidates and known user identifiers to redact."""
    names: Set[str] = set()
    for env_var in ("USER", "LOGNAME", "USERNAME"):
        val = os.environ.get(env_var)
        if val:
            names.add(val.strip())
    try:
        user = getpass.getuser()
        if user:
            names.add(user.strip())
    except Exception:
        pass
    try:
        home_name = Path.home().name
        if home_name:
            names.add(home_name.strip())
    except Exception:
        pass

    # Explicitly include the user's username per WORM-016
    names.add("daparker")

    # Filter out system or trivial usernames
    reserved = {
        "root",
        "runner",
        "admin",
        "system",
        "user",
        "guest",
        "nobody",
        "bin",
        "daemon",
        "tmp",
        "var",
        "etc",
        "usr",
    }
    return {n for n in names if len(n) >= 3 and n.lower() not in reserved}


def elide_personal_info(text: str, repo_root: Optional[Path] = None) -> str:
    """Elide personal information such as usernames and home directories from text.

    Args:
        text: Input string (such as markdown, console logs, or python tracebacks).
        repo_root: Optional repository root path for computing relative links.

    Returns:
        Sanitized string with usernames and user home directories redacted.
    """
    if not text:
        return "" if text is None else text

    result = str(text)

    # 1. Redact user home directory if known (e.g. /Users/daparker or /home/daparker)
    try:
        home_str = str(Path.home())
        if home_str and home_str != "/" and home_str in result:
            if home_str.startswith("/Users/"):
                result = result.replace(home_str, "/Users/<username>")
            elif home_str.startswith("/home/"):
                result = result.replace(home_str, "/home/<username>")
            else:
                result = result.replace(home_str, "<user_home>")
    except Exception:
        pass

    # 2. Redact usernames across paths, URLs, and text
    usernames = get_usernames_to_redact()
    for name in sorted(usernames, key=len, reverse=True):
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        result = pattern.sub("<username>", result)

    return result
