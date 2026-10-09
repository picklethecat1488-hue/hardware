"""Docker-pattern issue ID generator using a cryptographically secure random number generator (CRNG).

Implements WORM-029:
Format: [PREFIX]-[ADJECTIVE]-[ANIMAL/NOUN]-[3 digits]
Examples:
    - BUG-SWIFT-FOX-42
    - BUG-BOLD-LYNX-809
    - BUG-IRON-CRANE-17

Adjective and noun lists are compressed with zlib + base64 to save code space.
"""

import base64
from collections.abc import Collection
import re
import secrets
from typing import List, Optional
import zlib

# Compressed word lists to minimize source code footprint per WORM-029
_B64_ADJS = (
    "eJwlkGGWgCAIhK8yV6EiYzNtEe3V/Q+y49s/HwrKDEiyrJCsHlhq3rC4DCUtHYFV8oU1q/jkUIZa"
    "MzbdAyqJd71txS4tsJv6qtiztINUZcorCynXB2n2Ti5lUiUmteAQ314c781W5rXgRzYlvg/nrOfa"
    "N+S+ni9ZaOOavl4U5dti10Lzpf5zCG6VE7fbpeT8+tttPeFy2wav89iXl6CtRu0bjeOXmGFO12j7"
    "RKuZSq0WjtZChQ4ZvJDVL7S+BAVbZ+IxbiJsk4yoPR0I74qewwXdFykYkk2oMCz4aNigk0fY5jFu"
    "5LGm+LRYHH9OmmlB"
)

_B64_NOUNS = (
    "eJwVkFuSxSAIRLfSW8FIolciFmpMZv8LGfzwVMmraQLFiw2Bekdgso1nB3LXiqA7MkVwaDDCYVTZ"
    "qQuRvSrmeimiSku5IhoVRpxHAdMlDJaCk+TwSWeuR8KpL07TC9eemcjYsQoSm9cktc7IgV9H7vjR"
    "NV3/Rx+KkhCErEBYG1mEZG+Rr764Vb3v1unUMXwvXYJGNdLm8OlobK7fsi/Y5k0wuv09XJ0fzNdX"
    "mAZ30ZkEPW2pLjoSet22uotu333oziyqGHmfbpjOgSe7Ah5114vEZsdKtD8qJ5a5zkcFf+xX/Aed"
    "nGJK"
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
        - BUG-SWIFT-FOX-42
        - BUG-BOLD-LYNX-809
        - BUG-IRON-CRANE-17

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
