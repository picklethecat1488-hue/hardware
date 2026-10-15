"""Personal information and privacy sanitizer for feedback, tracebacks, and logs.

Ensures usernames, user home directories, and sensitive local machine paths are
automatically redacted to <username> or canonical relative paths before saving
bug reports, code reviews, tracebacks, and console logs across POSIX and Windows.

Dynamically discovers user names, handles, and emails from git configuration,
GitHub CLI environment, and system directory services with zero hardcoded
personal identifiers in code.
"""

from __future__ import annotations

from functools import lru_cache
import getpass
import os
from pathlib import Path
import re
import subprocess
from typing import List, Optional, Set, Tuple

RESERVED_IDENTIFIERS: Set[str] = {
    "admin",
    "bin",
    "bot",
    "centos",
    "daemon",
    "debian",
    "ec2-user",
    "etc",
    "flint",
    "guest",
    "head",
    "hue",
    "linux",
    "local",
    "main",
    "master",
    "nobody",
    "origin",
    "reviewer",
    "root",
    "runner",
    "system",
    "tmp",
    "tree",
    "ubuntu",
    "user",
    "usr",
    "vagrant",
    "var",
    "working",
    "github-actions",
    "github-actions[bot]",
}

CONSUMER_EMAIL_DOMAINS: Tuple[str, ...] = (
    "gmail",
    "me",
    "icloud",
    "yahoo",
    "outlook",
    "hotmail",
)

STREET_SUFFIXES: str = (
    r"(?:Street|St\.?|Avenue|Ave\.?|Boulevard|Blvd\.?|Road|Rd\.?|Drive|Dr\.?|Lane|Ln\.?|"
    r"Court|Ct\.?|Terrace|Ter\.?|Place|Pl\.?|Parkway|Pkwy\.?|Highway|Hwy\.?)"
)

UNIT_TYPES: str = r"(?:Suite|Ste\.?|Apt\.?|Apartment|Unit|Floor|Fl\.?|Bldg\.?|Building|#)\s*[\w#-]+"

STREET_ADDR_REGEX: re.Pattern[str] = re.compile(
    rf"\b\d{{1,5}}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){{0,2}}\s+{STREET_SUFFIXES}"
    rf"(?:[,\s]+{UNIT_TYPES})?(?:[,\s]+[A-Za-z\s]+[,\s]+[A-Z]{{2}}\s+\d{{5}}(?:-\d{{4}})?)?\b"
)

PO_BOX_REGEX: re.Pattern[str] = re.compile(r"(?i)\b(?:P\.?\s*O\.?\s*Box|Post\s+Office\s+Box)\s+\d+\b")

LABELED_ADDR_REGEX: re.Pattern[str] = re.compile(
    r"(?i)\b((?:Physical|Home|Residential|Billing|Shipping|Delivery|Return)?\s*Address)\s*:\s*([^\n\r]+)"
)

POSTAL_CODE_REGEX: re.Pattern[str] = re.compile(
    r"(?i)(?<![.\w])\b(ZIP(?:\s+Code)?|Postal(?:\s+Code)?)\s*:\s*(?:\d{5}(?:-\d{4})?|\d{3,10}|[A-Za-z]\d[A-Za-z]\s*\d[A-Za-z]\d)\b"
)


def _get_system_usernames() -> Set[str]:
    """Extract local usernames from environment and system calls."""
    res: Set[str] = set()
    for var in ("USER", "LOGNAME", "USERNAME"):
        v = os.environ.get(var)
        if v:
            res.add(v.strip())

    for var in ("USERPROFILE", "HOMEPATH"):
        v = os.environ.get(var)
        if v:
            tail = Path(v.strip().replace("\\", "/")).name
            if tail:
                res.add(tail.strip())

    try:
        u = getpass.getuser()
        if u:
            res.add(u.strip())
    except Exception:
        pass

    try:
        h = Path.home().name
        if h:
            res.add(h.strip())
    except Exception:
        pass

    return {n for n in res if len(n) >= 3 and n.lower() not in RESERVED_IDENTIFIERS}


def _get_system_full_name() -> Optional[str]:
    """Query directory services for the local user's full real name."""
    try:
        p = subprocess.run(["id", "-F"], capture_output=True, text=True, timeout=2)
        if p.returncode == 0:
            fn = p.stdout.strip()
            if fn and len(fn) >= 3 and fn.lower() not in RESERVED_IDENTIFIERS:
                return fn
    except Exception:
        pass

    try:
        user = getpass.getuser()
        p = subprocess.run(["getent", "passwd", user], capture_output=True, text=True, timeout=2)
        if p.returncode == 0 and p.stdout.strip():
            fields = p.stdout.strip().split(":")
            if len(fields) >= 5 and fields[4]:
                gecos = fields[4].split(",")[0].strip()
                if gecos and len(gecos) >= 3 and gecos.lower() not in RESERVED_IDENTIFIERS:
                    return gecos
    except Exception:
        pass

    return None


def _get_git_author_identities() -> Tuple[Set[str], Set[str]]:
    """Extract author names and emails from git configuration and recent log history."""
    names: Set[str] = set()
    emails: Set[str] = set()

    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        v = os.environ.get(var)
        if v:
            names.add(v.strip())

    for var in ("EMAIL", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        v = os.environ.get(var)
        if v:
            emails.add(v.strip().lower())

    for args in (
        ["config", "user.name"],
        ["config", "user.email"],
        ["config", "--global", "user.name"],
        ["config", "--global", "user.email"],
    ):
        try:
            p = subprocess.run(["git"] + args, capture_output=True, text=True, timeout=2)
            if p.returncode == 0 and p.stdout.strip():
                val = p.stdout.strip()
                if "@" in val:
                    emails.add(val.lower())
                else:
                    names.add(val)
        except Exception:
            pass

    try:
        p = subprocess.run(["git", "log", "-n", "50", "--format=%an%n%ae"], capture_output=True, text=True, timeout=5)
        if p.returncode == 0:
            for raw_line in p.stdout.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if "@" in line:
                    emails.add(line.lower())
                else:
                    names.add(line)
    except Exception:
        pass

    clean_names = {n for n in names if len(n) >= 3 and n.lower() not in RESERVED_IDENTIFIERS}
    clean_emails = {
        e
        for e in emails
        if len(e) >= 3 and not any(r in e.lower() for r in ("noreply", "actions@github.com", "example.com"))
    }
    return clean_names, clean_emails


def _get_github_cli_usernames() -> Set[str]:
    """Read GitHub username and hosts from GitHub CLI config."""
    gh_users: Set[str] = set()
    try:
        gh_path = Path.home() / ".config" / "gh" / "hosts.yml"
        if gh_path.exists():
            for raw_line in gh_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line.startswith("user:") or line.startswith("users:"):
                    u = line.split(":", 1)[1].strip()
                    if u and len(u) >= 3 and u.lower() not in RESERVED_IDENTIFIERS:
                        gh_users.add(u)
                elif line.endswith(":") and not line.startswith("github.com") and not line.startswith("git_protocol"):
                    cand = line.rstrip(":").strip()
                    if cand and len(cand) >= 3 and cand.lower() not in RESERVED_IDENTIFIERS:
                        gh_users.add(cand)
    except Exception:
        pass
    return gh_users


def _derive_subhandles(h: str) -> Set[str]:
    """Derive stem handles and base words by removing digit suffixes or separators."""
    res: Set[str] = set()
    if " " not in h and len(h) >= 3 and h.lower() not in RESERVED_IDENTIFIERS:
        res.add(h)
    for part in re.split(r"[-_\s]", h):
        if len(part) >= 3 and part.lower() not in RESERVED_IDENTIFIERS:
            res.add(part)
            no_digits = re.sub(r"\d+$", "", part)
            if len(no_digits) >= 3 and no_digits.lower() not in RESERVED_IDENTIFIERS:
                res.add(no_digits)
    if " " not in h:
        no_digits_full = re.sub(r"\d+$", "", h)
        if len(no_digits_full) >= 3 and no_digits_full.lower() not in RESERVED_IDENTIFIERS:
            res.add(no_digits_full)
    return res


@lru_cache(maxsize=1)
def get_personal_identifiers() -> Tuple[Set[str], Set[str], Set[str]]:
    """Dynamically discover user names, emails, and handles from system and git.

    Returns:
        Tuple of (all_names, all_emails, all_handles).
    """
    usernames = _get_system_usernames()
    full_name = _get_system_full_name()
    git_names, git_emails = _get_git_author_identities()
    gh_users = _get_github_cli_usernames()

    all_names = set(usernames) | git_names | gh_users
    if full_name:
        all_names.add(full_name)
        for part in full_name.split():
            if len(part) >= 3 and part.lower() not in RESERVED_IDENTIFIERS:
                all_names.add(part)

    all_emails = set(git_emails)
    all_handles: Set[str] = set()

    for em in all_emails:
        h = em.split("@")[0]
        if len(h) >= 3 and h.lower() not in RESERVED_IDENTIFIERS:
            all_handles.update(_derive_subhandles(h))

    for name in list(all_names):
        if len(name) >= 3 and name.lower() not in RESERVED_IDENTIFIERS:
            all_handles.update(_derive_subhandles(name))

    return all_names, all_emails, all_handles


def get_usernames_to_redact() -> Set[str]:
    """Discover local username candidates and known user identifiers to redact."""
    names, _, handles = get_personal_identifiers()
    combined = set(names) | set(handles)
    return {n for n in combined if len(n) >= 3 and " " not in n and n.lower() not in RESERVED_IDENTIFIERS}


def get_author_blacklist() -> List[str]:
    """Retrieve list of personal names and handles to map to 'User'."""
    names, _, handles = get_personal_identifiers()
    return sorted({x for x in (names | handles) if len(x) >= 3 and x.lower() not in RESERVED_IDENTIFIERS})


def get_email_blacklist() -> List[str]:
    """Retrieve list of personal emails and handles to map to 'user@workspace'."""
    _, emails, handles = get_personal_identifiers()
    return sorted({x for x in (emails | handles) if len(x) >= 3 and x.lower() not in RESERVED_IDENTIFIERS})


def elide_personal_info(text: str) -> str:
    """Elide personal information such as usernames, home directories, and addresses from text.

    Architecture Note:
        A dedicated zero-dependency regex sanitizer is used rather than heavyweight
        external PII/NLP packages. This provides instant (<1ms), deterministic path,
        username, email, and address redaction across Windows, macOS, and Linux
        without network or external package dependencies.

    Args:
        text: Input string (such as markdown, console logs, or python tracebacks).

    Returns:
        Sanitized string with usernames, home directories, and addresses redacted.
    """
    if not text:
        return "" if text is None else text

    result = str(text)

    # 1. Redact specific user home directories if known (Windows & POSIX)
    try:
        home_candidates: Set[str] = set()
        home = Path.home()
        home_candidates.add(str(home))
        home_candidates.add(home.as_posix())

        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            userprofile_str = userprofile.strip()
            home_candidates.add(userprofile_str)
            home_candidates.add(userprofile_str.replace("\\", "/"))

        homedrive = os.environ.get("HOMEDRIVE", "").strip()
        homepath = os.environ.get("HOMEPATH", "").strip()
        if homedrive and homepath:
            combined = f"{homedrive}{homepath}"
            home_candidates.add(combined)
            home_candidates.add(combined.replace("\\", "/"))

        for cand in home_candidates:
            cand = cand.rstrip("/\\")
            if not cand or cand in ("/", "\\", "C:", "c:"):
                continue
            if cand in result:
                if re.match(r"(?i)^[a-z]:[/\\]users", cand):
                    sep = "\\" if "\\" in cand else "/"
                    result = result.replace(cand, f"{cand[:2]}{sep}Users{sep}<username>")
                elif cand.startswith("/Users/"):
                    result = result.replace(cand, "/Users/<username>")
                elif cand.startswith("/home/"):
                    result = result.replace(cand, "/home/<username>")
                else:
                    result = result.replace(cand, "<user_home>")
    except Exception:
        pass

    # 2. Structural path pattern matching for Windows and Unix paths
    def _replace_win_user(m: re.Match[str]) -> str:
        prefix, user = m.group(1), m.group(2)
        if user.lower() in RESERVED_IDENTIFIERS:
            return m.group(0)
        return f"{prefix}<username>"

    result = re.sub(
        r"(?i)([A-Za-z]:[/\\](?:Users|Documents and Settings)[/\\])([^/\\\"'\s`]+)",
        _replace_win_user,
        result,
    )

    def _replace_posix_user(m: re.Match[str]) -> str:
        prefix, user = m.group(1), m.group(2)
        if user.lower() in RESERVED_IDENTIFIERS:
            return m.group(0)
        return f"{prefix}<username>"

    result = re.sub(
        r"((?:/Users|/home)/)([^/\\\"'\s`]+)",
        _replace_posix_user,
        result,
    )

    # 3. Redact personal email addresses (dynamically discovered handles and consumer domains)
    names, emails, handles = get_personal_identifiers()
    for h in sorted(handles, key=len, reverse=True):
        if len(h) >= 3 and h.lower() not in RESERVED_IDENTIFIERS:
            result = re.sub(
                rf"(?i)\b[A-Za-z0-9._%+-]*{re.escape(h)}[A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{{2,}}\b",
                "<email>",
                result,
            )

    consumer_pattern = "|".join(CONSUMER_EMAIL_DOMAINS)
    result = re.sub(
        rf"(?i)\b[A-Za-z0-9._%+-]+@(?:{consumer_pattern})\.[A-Za-z]{{2,}}\b",
        "<email>",
        result,
    )

    for em in sorted(emails, key=len, reverse=True):
        if em:
            result = re.sub(rf"(?i)\b{re.escape(em)}\b", "<email>", result)

    # 4. Redact all discovered usernames and names across text
    all_names_and_handles = sorted(names | handles, key=len, reverse=True)
    for name in all_names_and_handles:
        if len(name) >= 3 and name.lower() not in RESERVED_IDENTIFIERS:
            result = re.sub(rf"(?i)\b{re.escape(name)}\b", "<username>", result)

    # Clean up leftover email fragments with <username>
    result = re.sub(
        r"(?i)\b<username>@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "<email>",
        result,
    )

    # 5. Redact physical street addresses, P.O. Boxes, and labeled addresses
    result = PO_BOX_REGEX.sub("<address>", result)
    result = STREET_ADDR_REGEX.sub("<address>", result)
    result = LABELED_ADDR_REGEX.sub(r"\1: <address>", result)
    result = POSTAL_CODE_REGEX.sub(r"\1: <zip>", result)

    return result


def elide_commit_author(author: Optional[str]) -> str:
    """Sanitize commit author name, eliding personal names to 'User'.

    Args:
        author: Commit author name or handle.

    Returns:
        Sanitized author string, or 'User' if personal identity matches.
    """
    if not author:
        return ""
    a = author.strip()
    a_lower = a.lower()

    blacklist = {x.lower() for x in get_author_blacklist()}
    if a_lower in blacklist:
        return "User"

    for b in blacklist:
        if len(b) >= 3 and (b in a_lower or re.search(rf"(?i)\b{re.escape(b)}\b", a)):
            return "User"

    return a


def elide_commit_email(email: Optional[str]) -> str:
    """Sanitize commit author email, eliding personal email addresses.

    Args:
        email: Commit author email address.

    Returns:
        Sanitized email string, or 'user@workspace' if personal email matches.
    """
    if not email:
        return ""
    e = email.strip()
    e_lower = e.lower()

    _, all_emails, all_handles = get_personal_identifiers()
    for em in all_emails:
        if em in e_lower:
            return "user@workspace"

    for h in all_handles:
        if h.lower() in e_lower:
            return "user@workspace"

    for dom in CONSUMER_EMAIL_DOMAINS:
        if f"@{dom}." in e_lower:
            return "user@workspace"

    return e
