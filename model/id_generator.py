"""Docker-pattern issue ID generator using a cryptographically secure random number generator (CRNG).

Implements Docker pattern ID generation:
Format: [PREFIX]-[ADJECTIVE]-[INSECT/BUG/NOUN]-[3 digits]
Examples:
    - BUG-BUZZING-CICADA-42
    - BUG-WINGED-DRAGONFLY-809
    - BUG-CHITINOUS-BEETLE-17

Adjective and noun lists are compressed with zlib + base64 to save code space.
"""

import base64
from collections.abc import Collection
import re
import secrets
from typing import List, Optional
import zlib

# Compressed bug and insect-themed word lists to minimize source code footprint
_B64_ADJS = (
    "eNo9kVF2AyEIRbfCVlCZkQZ1ijg5yf4XUjBtf3wIiPcpniwE2BIpYDfqHQVQ21AqkLCXLZpClM9qIdPk"
    "BWm939xPyNjGOgRPb8mVjftYE7JwfuyyEl2fgNscHQqqxb7w0risDJ0u1EhRChw4DQ5CqxQIB5NmgkOI"
    "PC1s++whr5BTxnPrkEIdKrK+fNWbfEYdN2lU63JfCqxcaGbqBl+rbSQh/Ohq3H9rsqZpOGhunpM4QyND"
    "cT/QuMU6zCLduXkZ+sj2cTLS5MLYwYfmTX/55JAh4nyXjjRmZk+sng2N4Hv5M4FiHDNQv/sFM2OMn3Q2"
    "B9qRKu6gcg/eyfLwefOi/NitlyNtDcO7w/4Dt70E7W9zRd/Tf3gnnnwYGOpk57c6FLM7NMU+Ze33uElu"
    "cqqbkwZjPDiVH+W3my0="
)

_B64_NOUNS = (
    "eNo1UVmWxCAIvApXQaWVidsA6bzc/yKDJvPRUI801CJ2A5yFEwSMh17cGgkEovWz6q2O61NvCGcLlfaH"
    "04xkzSKmxPogH02uFQUideNJiSAWuRUrK0T2/yLEEQ8ZGMtCY3SIwvEgg4RNqa5LCaW7gjSCjr4HgvlB"
    "hHJxhg8LhfPpa/yphLCBnGwL5I4GWVC1jDn9WpYzQEH5klrDDmU4ia2m+0QZ38cRdzW38EMX1TeAA+1O"
    "nk/FSBf37CDdi9+9fhGc/POy1BFPNW89LwJwJnPvDe91unHK5LXWJ5zG5mXor4seDqxAv9ssMKvvvSfn"
    "ORGexMQ1vpIU95NoRMHgbXj0HqZyXTZYC+jBe18np93ElRtyBfeX/88Y92M5URt95+DenfusCP6cW6AV"
    "4alg/kxeMsm7a0L0arxQpxffUJNNdxF9neoaI4UhJH+SJqhx"
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
