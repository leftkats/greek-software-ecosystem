import re

_APPLY_WORKABLE_SLUG = re.compile(
    r"^https?://apply\.workable\.com/([^/?#]+)/?", re.IGNORECASE
)


def extract_workable_apply_slug(careers_url):
    """Slug for apply.workable.com/{slug} careers URLs, or None."""
    if not careers_url:
        return None
    m = _APPLY_WORKABLE_SLUG.match(str(careers_url).strip())
    if not m:
        return None
    slug = m.group(1).strip().rstrip("/")
    return slug or None
