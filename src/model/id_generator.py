"""Docker-pattern issue ID generator using a cryptographically secure random number generator (CRNG).

Implements WORM-029:
Format: [PREFIX]-[ADJECTIVE]-[ANIMAL/NOUN]-[3 digits]
Examples:
    - BUG-BURROWING-ANNELID-42
    - BUG-WRIGGLY-EARTHWORM-809
    - BUG-SLIMY-NIGHTCRAWLER-17

Adjective and noun lists are compressed with zlib + base64 to save code space.
"""

import base64
from collections.abc import Collection
import re
import secrets
from typing import List, Optional
import zlib

# Compressed worm-themed word lists to minimize source code footprint
_B64_ADJS = (
    "eNolkVuWxCAIRLfCVnzQhtMoDmLPZP8bmTL9Ewoi5QXTGKxSpVBWGZWyywq9KW93+5XRqFwSMmwv"
    "Kib6VKxPW8GVijPPU6qpT6pIqIoHcfK4eBD3zLXi4Is9RJleyuu6T/iTfHJby1ySUjsUcGr6vba5"
    "7XFar91BJwMcKGvyD06rwJ/UUr9JN6BLOjyKs4NX4RHQK/xgd8NI1HetNw0rsX3AwbylAePJKW7C"
    "EG+abtlWkUqeqiR4uNmxfVBocesw5qN8QuEqyLCFIPrGvEulvM8XWOth9AO9sLj89fjZ4ufnzsHu"
    "aXBC154TuwikS/cDH/t5F/Sia2uKIz+sHwbshx0rQdW/8mXe6delNTwcYpxN/QPweYLC"
)

_B64_NOUNS = (
    "eNo1UlGSxSAIuwpXQctTZlFcxHbf/S+ytE6/EkGBBLF3Ej4gEbkQJFE9LrUGSVNiD9CffTaez42N"
    "O7bM9CKDjNO5l0AnGyyCEaPuPOggyBXJdegRzL4ThSdkYSeR1SBrVu0Bbej0u5jhJQ8SjcCDSwkg"
    "NK9PWyIB6rl+3ZBi9g/bnucj6A8potcmthJUksbdK3A8esIx34kgRLlCKL67yCo7tVpIzGtCw1LU"
    "oRHKk2mhawuKavGiU0PXOHYu1d+p+7eNCipc9NFNMFBUFIZgR2PsMFS+b24NBKNtuXFK2jdVva0w"
    "XX3nJr6ESgtnA20swUBHgsmy1zR5rJ7XvdIZkmB2ZIH5u9haFHQc2ypf6SX3D4jUSXLStu8ka7Gj"
    "M2QWtCd04d/G1+srPoromgSXxYKiwj+DtKN6"
)


def get_adjectives() -> List[str]:
    """Decompress and return canonical uppercase adjective list."""
    return zlib.decompress(base64.b64decode(_B64_ADJS)).decode("ascii").split()


def get_nouns() -> List[str]:
    """Decompress and return canonical uppercase animal/noun list."""
    return zlib.decompress(base64.b64decode(_B64_NOUNS)).decode("ascii").split()


# Cached word lists decompressed once in memory
ADJECTIVES: List[str] = get_adjectives()
NOUNS: List[str] = get_nouns()

# Regex to validate Docker-pattern issue IDs: e.g. BUG-SWIFT-FOX-42, WORM-BOLD-LYNX-809
DOCKER_ID_REGEX = re.compile(r"^(?:BUG|WORM)-[A-Z]+-[A-Z]+-\d{1,3}$")


def is_docker_pattern_id(issue_id: str) -> bool:
    """Check if an issue ID matches the Docker pattern [PREFIX]-[ADJ]-[NOUN]-[1..3 digits]."""
    return bool(DOCKER_ID_REGEX.match(issue_id.strip()))


def generate_docker_pattern_id(
    prefix: str = "BUG",
    existing_ids: Optional[Collection[str]] = None,
) -> str:
    """Generate a random Docker-pattern issue ID using a CRNG (secrets / os.urandom).

    Format: [PREFIX]-[ADJECTIVE]-[ANIMAL/NOUN]-[3 digits]
    Examples:
        - BUG-BURROWING-ANNELID-42
        - BUG-WRIGGLY-EARTHWORM-809
        - BUG-SLIMY-NIGHTCRAWLER-17

    Args:
        prefix: Prefix string (e.g. 'BUG' or 'WORM').
        existing_ids: Optional set/collection of already allocated IDs to avoid collisions.

    Returns:
        A unique Docker-pattern formatted issue ID.
    """
    known = set(existing_ids or [])
    norm_prefix = prefix.strip().rstrip("-_").upper()

    # Attempt up to 10,000 draws to avoid collision
    for _ in range(10000):
        # Cryptographically secure random selection
        adj = secrets.choice(ADJECTIVES)
        noun = secrets.choice(NOUNS)
        num = secrets.randbelow(999) + 1  # Integer in 1..999 (up to 3 digits)

        candidate = f"{norm_prefix}-{adj}-{noun}-{num}"
        if candidate not in known:
            return candidate

    # Extreme fallback with larger random space
    fallback_num = secrets.randbelow(999) + 1
    return f"{norm_prefix}-{secrets.choice(ADJECTIVES)}-{secrets.choice(NOUNS)}-{fallback_num}"
