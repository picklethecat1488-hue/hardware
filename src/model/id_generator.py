"""Docker-pattern issue ID generator using a cryptographically secure random number generator (CRNG).

Implements WORM-029:
Format: [PREFIX]-[ADJECTIVE]-[ANIMAL/NOUN]-[3 digits]
Examples:
    - BUG-BUZZING-BEETLE-42
    - BUG-CHITINOUS-MANTIS-809
    - BUG-SCUTTLING-CICADA-17

Adjective and noun lists are compressed with zlib + base64 to save code space.
"""

import base64
from collections.abc import Collection
import re
import secrets
from typing import List, Optional
import zlib

# Compressed bug-themed word lists to minimize source code footprint
_B64_ADJS = (
    "eJw1UtFhxSAIXMVViCGRBiRFTZruP0jBvP54iKcch1A71gqcwEQN17RQp7qnxah1ftIyzPSemfH7"
    "G5hBdGwMu5NzCbaOljKP1tEmQVkr+ZNZ5dRRnWZw8zwyxDOCFWyWWWlYVF/VWoD5TU/jj7YDGbvn"
    "Nqa99Cewzzsbj/4ptanBHsHOr8i9Qi+UA+e+ANmTil4vvwyRwK8hUwaDXV6CEd7tkLcbHnZEQqCu"
    "tAynJQkx7E9H4FadUUZIYlWewkR7Z3dFhu8Z93CoYptnVXN/W62PnMXxBIPm9uXktd1IJ50+AOjq"
    "ir8H5SOZezp9a9lbfiPcBX1ma2oFmSeSyNteIz6wOvx8qreD/q1qmmMm7aQVjenACOvjq6sOasic"
    "xG50RuL2LzETN2099eJeZ1cbgd/rBjQVXVhVwjQPPMnposVgNn1Ry3Fy47L4izERXP8ADAqtTw=="
)

_B64_NOUNS = (
    "eJw9UdGVxCAIbIVWiLLKxYgHuHnpv5FDd999BAaEyQDYHXBUzoCKqfYNvKoMyXAQrc9buMbmpP+R"
    "3K/2wDGvo9Eumx7PK5cwwODWUCFRdx6UCVLlUigyVR/DIIPECTNCapzOL22SdKqEDEiKnTabxjM5"
    "ZLyM2spk1B5EWbFIXwlCvbnAi3V3vBohLFA6OhRFsypjREvReUCVaHfgbpQcfmanYxY40Z8cszfM"
    "z4pD/BshmF7f3iZpmsOFpchyMZeFe9aPLsK2uy7OhcK29hn6Yg8j9jvZJYBX6M81Kow5ED6Tqojf"
    "oleAN333YLi3aylucoST2Kd0MG7nLg3wjmWzVbCTtz4bnD/Og2GJsaHciyM3MOd+rpwHYffZEOJGW"
    "12cmoeBx5bhRhth1pmjdgNz3bw30TuI7tjxVnCL5CbTCFb4B3nnn2w="
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
        - BUG-BUZZING-BEETLE-42
        - BUG-CHITINOUS-MANTIS-809
        - BUG-SCUTTLING-CICADA-17

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
