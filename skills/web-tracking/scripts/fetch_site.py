#!/usr/bin/env python3
"""
Fetch posts published on a specific KST day from a website.

Strategy:
1. Try to discover an RSS/Atom feed from the site URL:
   - Common paths: /rss, /rss/, /feed, /feed/, /feed.xml, /atom.xml, /index.xml, /rss.xml
   - HTML <link rel="alternate" type="application/rss+xml" | "application/atom+xml">
2. Parse the feed and filter items whose publication time falls inside the
   [DATE 00:00 KST, DATE+1 00:00 KST) window.
3. If no feed is found, fall back to HTML scraping: fetch the homepage, find article
   links with <time datetime> hints, and apply the same window.

Output on stdout:
- NO_ITEMS if nothing found for that date.
- Otherwise, each item separated by ---ITEM--- with fields:
    TITLE: ...
    LINK: ...
    PUB: YYYY-MM-DD HH:MM (KST)
    CONTENT_START
    ... plain-text body (max 5000 chars) ...
    CONTENT_END

Stderr is used for progress/diagnostics.

Usage:
    python3 fetch_site.py <site-url> [YYYY-MM-DD]

If the date is omitted, today's KST date is used.
"""

import sys
import re
import html
import ssl
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

# Build a robust SSL context. System-level SSL_CERT_FILE env var may point to
# an incomplete bundle (observed on macOS where users have custom bundles).
# Try certifi first, then fall back to Python's default verification paths.
def _build_ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
        ctx.load_default_certs()
        return ctx

SSL_CTX = _build_ssl_context()

USER_AGENT = "Mozilla/5.0 (compatible; web-tracking-skill/1.0; +https://obsidian.md)"
KST = timezone(timedelta(hours=9))
TIMEOUT = 15
MAX_CONTENT = 5000
MAX_ITEMS_PER_SITE = 20


def kst_day_window(date_str):
    """
    Given a 'YYYY-MM-DD' string (KST), return (start_utc, end_utc) covering
    that KST day — i.e. [DATE 00:00 KST, DATE+1 00:00 KST) in UTC.
    """
    y, m, d = [int(x) for x in date_str.split("-")]
    start_kst = datetime(y, m, d, 0, 0, 0, tzinfo=KST)
    end_kst = start_kst + timedelta(days=1)
    return start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc)

COMMON_FEED_PATHS = [
    "rss.xml",
    "feed.xml",
    "atom.xml",
    "index.xml",
    "rss/",
    "feed/",
    "rss",
    "feed",
    "blog/rss.xml",
    "blog/feed.xml",
]


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def http_get(url, accept=None):
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as resp:
        data = resp.read()
        # Use content-type charset if present; default utf-8
        ctype = resp.headers.get("Content-Type", "")
        charset = "utf-8"
        m = re.search(r"charset=([^\s;]+)", ctype, re.I)
        if m:
            charset = m.group(1).strip().strip('"').strip("'")
        try:
            return data.decode(charset, errors="replace"), resp.geturl()
        except LookupError:
            return data.decode("utf-8", errors="replace"), resp.geturl()


def strip_html(s, block_sep=" "):
    """
    Strip HTML tags, collapsing whitespace. If block_sep is a non-space string
    (e.g. "\n"), insert it between block-level elements so downstream code can
    find boundaries between adjacent chunks like <h2>title</h2><p>subtitle</p>.
    """
    if not s:
        return ""
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
    if block_sep != " ":
        # Replace block-level closing tags with a marker so we can detect
        # boundaries. List covers common "title then subtitle" cases.
        s = re.sub(
            r"</(?:h[1-6]|p|div|li|article|section|header|footer|nav|main)\s*>",
            block_sep,
            s,
            flags=re.I,
        )
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    if block_sep != " ":
        # Collapse spaces around the separator and collapse multiple separators.
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\s*" + re.escape(block_sep) + r"\s*", block_sep, s)
        s = re.sub(re.escape(block_sep) + r"+", block_sep, s)
        s = s.strip(block_sep + " \n\r\t")
    else:
        s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_date_any(s):
    """Parse a date string from RSS/Atom into aware datetime, else None."""
    if not s:
        return None
    s = s.strip()
    # RFC 2822 (RSS)
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    # ISO 8601 (Atom)
    try:
        iso = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    # Common fallback formats — add human-readable variants for HTML fallback
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d %b %Y",
        "%b %d, %Y",        # Mar 25, 2026 (Anthropic engineering)
        "%B %d, %Y",        # March 25, 2026
        "%b %d %Y",         # Mar 25 2026
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def discover_feed_url(site_url):
    """Return a feed URL or None."""
    parsed = urllib.parse.urlparse(site_url)
    if not parsed.scheme:
        site_url = "https://" + site_url
        parsed = urllib.parse.urlparse(site_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    # 1. Fetch homepage and look for <link rel="alternate" type="application/rss+xml">
    try:
        html_text, _ = http_get(site_url, accept="text/html,application/xhtml+xml")
        for m in re.finditer(
            r'<link\s+[^>]*rel=["\']alternate["\'][^>]*>', html_text, re.I
        ):
            tag = m.group(0)
            if not re.search(r'type=["\'](application/(rss|atom)\+xml|application/xml)["\']', tag, re.I):
                continue
            href_m = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
            if href_m:
                href = html.unescape(href_m.group(1))
                return urllib.parse.urljoin(site_url, href)
    except Exception as e:
        log(f"  homepage fetch failed: {e}")

    # 2. Try common feed paths
    for path in COMMON_FEED_PATHS:
        candidate = urllib.parse.urljoin(base + "/", path)
        try:
            text, _ = http_get(candidate, accept="application/rss+xml,application/atom+xml,application/xml")
            # Sanity check: looks like XML feed
            head = text.lstrip()[:500].lower()
            if "<rss" in head or "<feed" in head or "<rdf" in head:
                return candidate
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            log(f"  {candidate}: HTTP {e.code}")
        except Exception as e:
            log(f"  {candidate}: {e}")

    return None


def parse_feed(feed_xml, feed_url):
    """Parse RSS 2.0, Atom, or RDF. Return list of (title, link, pub_dt, summary_text)."""
    items = []
    try:
        # Strip BOM if any
        feed_xml = feed_xml.lstrip("\ufeff")
        root = ET.fromstring(feed_xml)
    except ET.ParseError as e:
        log(f"  feed parse error: {e}")
        return items

    tag = root.tag.lower()
    # Atom
    if tag.endswith("feed"):
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns):
            title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
            link = ""
            for l in entry.findall("a:link", ns):
                rel = l.get("rel", "alternate")
                if rel == "alternate" or not link:
                    link = l.get("href", "")
            pub_str = (
                entry.findtext("a:published", default="", namespaces=ns)
                or entry.findtext("a:updated", default="", namespaces=ns)
            )
            pub_dt = parse_date_any(pub_str)
            summary = (
                entry.findtext("a:content", default="", namespaces=ns)
                or entry.findtext("a:summary", default="", namespaces=ns)
                or ""
            )
            items.append((title, urllib.parse.urljoin(feed_url, link), pub_dt, summary))
        return items

    # RSS 2.0 / RDF
    channel = root.find("channel")
    if channel is None:
        # RDF has items at root level
        candidates = root.findall("{http://purl.org/rss/1.0/}item")
    else:
        candidates = channel.findall("item")

    for item in candidates:
        title = (item.findtext("title", default="") or "").strip()
        link = (item.findtext("link", default="") or "").strip()
        pub_str = (
            item.findtext("pubDate", default="")
            or item.findtext("{http://purl.org/dc/elements/1.1/}date", default="")
            or ""
        )
        pub_dt = parse_date_any(pub_str)
        # Prefer content:encoded then description
        content = item.findtext(
            "{http://purl.org/rss/1.0/modules/content/}encoded", default=""
        ) or item.findtext("description", default="") or ""
        items.append((title, urllib.parse.urljoin(feed_url, link), pub_dt, content))

    return items


def fetch_article_body(url):
    """Fetch article page and try to extract readable text. Best-effort."""
    try:
        text, _ = http_get(url, accept="text/html,application/xhtml+xml")
    except Exception as e:
        log(f"  article fetch failed ({url}): {e}")
        return ""
    # Try to isolate <article> or <main>
    m = re.search(r"<article\b[^>]*>([\s\S]*?)</article>", text, re.I)
    if not m:
        m = re.search(r"<main\b[^>]*>([\s\S]*?)</main>", text, re.I)
    body_html = m.group(1) if m else text
    return strip_html(body_html)[:MAX_CONTENT]


def fetch_article_date(url):
    """
    Fetch the article page and try to extract its publication date.

    Used when a feed provides links but omits pubDate/published/updated fields
    (observed on developers.googleblog.com). Tries, in order:
      1. JSON-LD "datePublished"
      2. <meta property="article:published_time">
      3. <meta name="pubdate"> / "date"
      4. <time datetime="...">
    Returns an aware datetime or None.
    """
    try:
        text, _ = http_get(url, accept="text/html,application/xhtml+xml")
    except Exception as e:
        log(f"  date fetch failed ({url}): {e}")
        return None

    # 1. JSON-LD
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', text)
    if m:
        dt = parse_date_any(m.group(1))
        if dt:
            return dt

    # 2. Open Graph / article:published_time
    m = re.search(
        r'<meta[^>]*(?:property|name)=["\'](?:article:published_time|og:article:published_time)["\'][^>]*content=["\']([^"\']+)',
        text,
        re.I,
    )
    if m:
        dt = parse_date_any(m.group(1))
        if dt:
            return dt

    # 3. Generic meta pubdate/date
    m = re.search(
        r'<meta[^>]*name=["\'](?:pubdate|date|dc\.date|DC\.date\.issued)["\'][^>]*content=["\']([^"\']+)',
        text,
        re.I,
    )
    if m:
        dt = parse_date_any(m.group(1))
        if dt:
            return dt

    # 4. <time datetime="...">
    m = re.search(r'<time[^>]*datetime=["\']([^"\']+)', text, re.I)
    if m:
        dt = parse_date_any(m.group(1))
        if dt:
            return dt

    return None


def html_fallback(site_url):
    """
    Last resort: fetch homepage and try to extract article entries.

    Two strategies, tried in order:
    1. <article> blocks containing <a href> + <time datetime>
    2. Proximity heuristic: each <a href> to a "post-like" URL paired with the
       nearest following "Mon DD, YYYY" string, with the anchor's cleaned text
       used as the title. Handles sites like Anthropic's engineering blog that
       render lists without <time> tags or RSS feeds.
    """
    try:
        text, resolved = http_get(site_url, accept="text/html,application/xhtml+xml")
    except Exception as e:
        log(f"  homepage fetch failed: {e}")
        return []

    items = []
    seen = set()

    # Strategy 1: <article> + <time datetime>
    for block in re.finditer(r"<article\b[\s\S]*?</article>", text, re.I):
        chunk = block.group(0)
        a_m = re.search(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', chunk, re.I)
        time_m = re.search(r'<time\s+[^>]*datetime=["\']([^"\']+)["\']', chunk, re.I)
        if not a_m or not time_m:
            continue
        href = urllib.parse.urljoin(resolved, a_m.group(1))
        title = strip_html(a_m.group(2))
        pub_dt = parse_date_any(time_m.group(1))
        if not pub_dt or not title or href in seen:
            continue
        seen.add(href)
        items.append((title, href, pub_dt, ""))

    if items:
        return items

    # Strategy 1.5: Reverse proximity — heading + date BEFORE link
    # Handles Webflow CMS and similar layouts where <h2>Title</h2> and date
    # text appear before the <a href> in the DOM (e.g. claude.com/blog).
    parsed = urllib.parse.urlparse(site_url)
    path_parts = [p for p in parsed.path.split("/") if p]
    prefix = "/" + path_parts[0] + "/" if path_parts else "/"
    if prefix == "//":
        prefix = "/"

    date_re = re.compile(
        r'(?:[A-Z][a-z]{2,8}\s\d{1,2},\s20\d{2})',  # "Apr 10, 2026" or "April 10, 2026"
    )
    for date_m in date_re.finditer(text):
        date_str = date_m.group(0)
        pub_dt = parse_date_any(date_str)
        if not pub_dt:
            continue

        # Look backward up to 500 chars for an <h2>/<h3> title
        before = text[max(0, date_m.start() - 500):date_m.start()]
        h_m = re.search(r'<h[2-3][^>]*>([\s\S]*?)</h[2-3]>\s*(?:<[^>]*>\s*)*$', before, re.I)
        if not h_m:
            continue
        title = strip_html(h_m.group(1))
        if not title or len(title) < 5:
            continue

        # Look forward up to 2000 chars for an <a href> matching post prefix
        after = text[date_m.end():date_m.end() + 2000]
        href_m = re.search(
            r'href=["\'](' + re.escape(prefix) + r'[^"\'#?]+?)["\']', after
        )
        if not href_m:
            continue

        raw_href = href_m.group(1)
        sub = raw_href[len(prefix):].strip("/")
        if not sub:
            continue

        href = urllib.parse.urljoin(resolved, raw_href)
        if href in seen:
            continue

        seen.add(href)
        items.append((title, href, pub_dt, ""))

    if items:
        return items

    # Strategy 2: Proximity heuristic
    # Derive a "post-like" URL prefix from the page path. For /engineering we
    # look for href="/engineering/<slug>"; for /blog we look for /blog/<slug>.
    parsed = urllib.parse.urlparse(site_url)
    path_parts = [p for p in parsed.path.split("/") if p]
    prefix = "/" + path_parts[0] + "/" if path_parts else "/"
    # Skip if the only path segment is blank (would match everything)
    if prefix == "//":
        prefix = "/"

    # Regex: href with prefix, up to 3000 chars of fluff, then "Mon DD, YYYY".
    # The cleaned text between them is used as the title.
    pattern = re.compile(
        r'href=["\'](' + re.escape(prefix) + r'[^"\'#?]+?)["\'](.{0,3000}?)([A-Z][a-z]{2}\s\d{1,2},\s20\d{2})',
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        raw_href = match.group(1)
        between = match.group(2)
        date_str = match.group(3)

        # Skip hrefs that are themselves the index (e.g. /engineering/ or /engineering)
        sub = raw_href[len(prefix):].strip("/")
        if not sub:
            continue

        href = urllib.parse.urljoin(resolved, raw_href)
        if href in seen:
            continue

        # Parse "between" block with block-level separator so we can split
        # title from subtitle/blurb that follow in adjacent <p>/<h2> tags.
        block_text = strip_html(between, block_sep="\u241F").strip()
        # Remove leading bullet/marker characters like "> " used as list separators
        block_text = re.sub(r"^[>\-\*\u2022\s\u241F]+", "", block_text)
        # Strip "Featured" label that some sites prefix to hero cards
        block_text = re.sub(r"^Featured\s*\u241F?\s*", "", block_text, flags=re.I)
        # The first block-separated segment is usually the title; remaining
        # segments are subtitle/blurb that we discard.
        segments = [seg.strip() for seg in block_text.split("\u241F") if seg.strip()]
        if not segments:
            continue
        title = segments[0]
        # Safety truncation for sites that don't expose block boundaries.
        if len(title) > 160:
            title = title[:160].rsplit(" ", 1)[0]
        if not title:
            continue

        pub_dt = parse_date_any(date_str)
        if not pub_dt:
            continue

        seen.add(href)
        items.append((title, href, pub_dt, ""))

    return items


def format_item(title, link, pub_dt, content_text):
    pub_kst = pub_dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    body = content_text.strip()
    if len(body) > MAX_CONTENT:
        body = body[:MAX_CONTENT] + "..."
    return (
        f"TITLE: {title}\n"
        f"LINK: {link}\n"
        f"PUB: {pub_kst}\n"
        f"CONTENT_START\n"
        f"{body}\n"
        f"CONTENT_END"
    )


def main():
    # Parse args: <site-url> [<YYYY-MM-DD>] [--debug]
    argv = [a for a in sys.argv[1:]]
    debug = False
    if "--debug" in argv:
        debug = True
        argv = [a for a in argv if a != "--debug"]

    if not argv:
        print("ERROR: site URL required", file=sys.stderr)
        sys.exit(2)
    site_url = argv[0].strip()
    if not re.match(r"^https?://", site_url):
        site_url = "https://" + site_url

    # Optional second positional arg: YYYY-MM-DD (KST). Defaults to today KST.
    if len(argv) >= 2 and argv[1].strip():
        date_str = argv[1].strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            print(f"ERROR: date must be YYYY-MM-DD, got: {date_str}", file=sys.stderr)
            sys.exit(2)
    else:
        date_str = datetime.now(KST).strftime("%Y-%m-%d")

    try:
        window_start, window_end = kst_day_window(date_str)
    except Exception as e:
        print(f"ERROR: invalid date {date_str}: {e}", file=sys.stderr)
        sys.exit(2)

    log(f"[web-tracking] site={site_url} date={date_str} (KST)")

    feed_url = discover_feed_url(site_url)
    raw_items = []
    if feed_url:
        log(f"  feed: {feed_url}")
        try:
            feed_xml, _ = http_get(feed_url, accept="application/rss+xml,application/atom+xml,application/xml")
            raw_items = parse_feed(feed_xml, feed_url)
        except Exception as e:
            log(f"  feed fetch failed: {e}")
            raw_items = []
    else:
        log("  no feed discovered, falling back to HTML scraping")
        raw_items = html_fallback(site_url)

    if not raw_items:
        print("NO_ITEMS")
        return

    # If the feed returned items but none have dates (observed on Google's
    # developers blog where the RSS omits pubDate), hydrate dates by visiting
    # each article and reading JSON-LD / meta tags. This is expensive, so we
    # only trigger it when no items have a pub_dt.
    if all(item[2] is None for item in raw_items):
        log("  feed items lack dates, hydrating via per-article JSON-LD/meta")
        hydrated = []
        # Only try the newest slice; each article fetch is ~1-2s.
        for title, link, _pub_dt, summary in raw_items[: MAX_ITEMS_PER_SITE + 5]:
            if not link:
                continue
            dt = fetch_article_date(link)
            if dt:
                hydrated.append((title, link, dt, summary))
        raw_items = hydrated

    if debug:
        log(f"  [debug] raw_items: {len(raw_items)}")
        log(f"  [debug] window: {window_start.astimezone(KST)} ~ {window_end.astimezone(KST)} (KST)")
        for i, (t, l, p, _) in enumerate(raw_items[:20]):
            pstr = p.astimezone(KST).strftime("%Y-%m-%d %H:%M") if p else "NO DATE"
            in_window = (p is not None and window_start <= p < window_end)
            marker = "✓" if in_window else " "
            log(f"  [debug] {marker} [{i}] {pstr}  {t[:60] if t else '(no title)'}")

    # Filter by the specified KST day: [start, end)
    fresh = []
    for title, link, pub_dt, summary in raw_items:
        if not pub_dt or not title or not link:
            continue
        if pub_dt < window_start or pub_dt >= window_end:
            continue
        fresh.append((title, link, pub_dt, summary))

    fresh.sort(key=lambda x: x[2], reverse=True)
    fresh = fresh[:MAX_ITEMS_PER_SITE]

    if not fresh:
        print("NO_ITEMS")
        return

    out_chunks = []
    for title, link, pub_dt, summary in fresh:
        content_text = strip_html(summary)
        # If feed summary is very short, try to fetch the full article body
        if len(content_text) < 400:
            fetched = fetch_article_body(link)
            if fetched and len(fetched) > len(content_text):
                content_text = fetched
        out_chunks.append(format_item(title, link, pub_dt, content_text))

    print("\n---ITEM---\n".join(out_chunks))


if __name__ == "__main__":
    main()
