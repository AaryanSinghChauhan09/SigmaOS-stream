"""IPTV / internet-radio stream player planner for SigmaOS-stream & radio-stream
(hypnotix / radio.omarchy.org-inspired).

The engine parses M3U channel playlists (tvg-* attributes, group-title),
filters channels, builds an mpv stream-playback argv and manages a favorites
store. Parsing/planning is PURE and fully tested; playing spawns nothing in
self_test() (no subprocess, no network).
Principles: Separation of Concerns, Defensive Programming, Fail-Fast, KISS.
"""
import argparse, os, re, shlex, sys

ENGINE = {
    "name": "sigma-stream",
    "summary": "Parse IPTV/radio M3U playlists and plan stream playback",
    "language": "python",
    "verbs": ["parse-m3u", "channels", "play-plan", "favorites"],
    "principles": ["Separation of Concerns", "Defensive Programming",
                   "Fail-Fast", "KISS", "Deterministic Testing"],
}

cli_doc = """\
$ sigma-stream parse-m3u channels.m3u
BBC News HD  [News]  https://cdn.example.com/bbcnews/master.m3u8
$ sigma-stream channels channels.m3u --group News
$ sigma-stream play-plan http://edge.example.com/cnn/index.m3u8 --title "CNN"
mpv --really-quiet --force-cache --demuxer-max-bytes=1024KiB ...
$ sigma-stream favorites --add "BBC News HD"
"""


class StreamError(Exception):
    pass


_URL_RE = re.compile(r"^https?://", re.I)
_ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
DEFAULT_STORE = os.path.expanduser("~/.config/sigma-stream/favorites")


# --------------------------------------------------------------------------- #
#  PURE parse / plan layer
# --------------------------------------------------------------------------- #
def _split_unquoted(text, sep):
    """Split `text` on `sep` ignoring separators inside double quotes."""
    out, buf, quoted = [], [], False
    for ch in text:
        if ch == '"':
            quoted = not quoted
        if ch == sep and not quoted:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def parse_m3u(text):
    """Parse an extended M3U playlist into a list of channel dicts."""
    channels, pending = [], None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF:"):
            parts = _split_unquoted(line[len("#EXTINF:"):], ",")
            attrs = dict(_ATTR_RE.findall(parts[0]))
            name = ",".join(parts[1:]).strip() or attrs.get("tvg-id", "").strip()
            if not name:
                raise StreamError(f"line {lineno}: #EXTINF has no channel name")
            pending = {
                "name": name,
                "group": attrs.get("group-title") or "Ungrouped",
                "tvg_id": attrs.get("tvg-id", ""),
                "logo": attrs.get("tvg-logo", ""),
                "url": None,
            }
            continue
        if line.startswith("#"):
            continue
        if not _URL_RE.match(line):
            raise StreamError(f"line {lineno}: not a stream URL: {line}")
        if pending is None:
            raise StreamError(f"line {lineno}: stream URL without #EXTINF")
        pending["url"] = line
        channels.append(pending)
        pending = None
    if pending is not None:
        raise StreamError("dangling #EXTINF without a stream URL")
    if not channels:
        raise StreamError("no channels in playlist")
    return channels


def channels(playlist, group=None, query=None):
    """Filter parsed channels by group and/or case-insensitive name query."""
    out = playlist
    if group is not None:
        g = group.strip().lower()
        out = [c for c in out if c["group"].lower() == g]
    if query:
        q = query.strip().lower()
        out = [c for c in out if q in c["name"].lower()]
    return out


def play_plan(url, title=None, cache_kb=1024):
    """Build the mpv argv for one stream URL (pure string building)."""
    if not isinstance(url, str) or not _URL_RE.match(url):
        raise StreamError(f"not an http(s) stream URL: {url!r}")
    try:
        cache_kb = int(cache_kb)
    except (TypeError, ValueError):
        raise StreamError("cache_kb must be an integer")
    if not (64 <= cache_kb <= 65536):
        raise StreamError("cache_kb must be 64..65536")
    argv = ["mpv", "--really-quiet", "--force-cache",
            f"--demuxer-max-bytes={cache_kb}KiB"]
    if title:
        if not isinstance(title, str) or "\n" in title or not title.strip():
            raise StreamError(f"bad stream title: {title!r}")
        argv.append(f"--force-media-title={title}")
    argv += ["--", url]
    return argv


# --------------------------------------------------------------------------- #
#  Favorites store (user-level file; self_test uses tempfile only)
# --------------------------------------------------------------------------- #
def load_favorites(path):
    """Return ordered, de-duplicated favorite channel names."""
    if not os.path.exists(path):
        return []
    names, seen = [], set()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            n = line.strip()
            if not n or n.startswith("#") or n in seen:
                continue
            seen.add(n)
            names.append(n)
    return names


def save_favorites(path, names):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for n in names:
            fh.write(n + "\n")


def add_favorite(path, name):
    name = (name or "").strip()
    if not name:
        raise StreamError("empty favorite name")
    names = load_favorites(path)
    if name not in names:           # idempotent
        names.append(name)
        save_favorites(path, names)
    return names


def remove_favorite(path, name):
    names = [n for n in load_favorites(path) if n != (name or "").strip()]
    save_favorites(path, names)
    return names


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"], description=ENGINE["summary"])
    p.add_argument("--store", default=DEFAULT_STORE, help="favorites store path")
    sub = p.add_subparsers(dest="cmd", required=True)
    pm = sub.add_parser("parse-m3u", help="parse an extended M3U playlist")
    pm.add_argument("file")
    ch = sub.add_parser("channels", help="list/filter channels")
    ch.add_argument("file")
    ch.add_argument("--group", default=None)
    ch.add_argument("--query", default=None)
    pl = sub.add_parser("play-plan", help="build an mpv stream invocation")
    pl.add_argument("url")
    pl.add_argument("--title", default=None)
    pl.add_argument("--cache-kb", type=int, default=1024)
    fv = sub.add_parser("favorites", help="list/add/remove favorite channels")
    fv.add_argument("--add", default=None, metavar="NAME")
    fv.add_argument("--remove", default=None, metavar="NAME")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "parse-m3u":
            for c in parse_m3u(_read(args.file)):
                print(f'{c["name"]}  [{c["group"]}]  {c["url"]}')
        elif args.cmd == "channels":
            found = channels(parse_m3u(_read(args.file)), args.group, args.query)
            for c in found:
                print(f'{c["name"]}  [{c["group"]}]')
            print(f"{len(found)} channel(s)", file=sys.stderr)
        elif args.cmd == "play-plan":
            plan = play_plan(args.url, args.title, args.cache_kb)
            print(" ".join(shlex.quote(a) for a in plan))
        elif args.cmd == "favorites":
            if args.add:
                names = add_favorite(args.store, args.add)
                print(f"added ({len(names)} total)")
            elif args.remove:
                remove_favorite(args.store, args.remove)
                print("removed")
            else:
                for n in load_favorites(args.store):
                    print(n)
        return 0
    except (StreamError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


# --------------------------------------------------------------------------- #
#  Tests (pure parse/plan layer; filesystem use limited to tempfile)
# --------------------------------------------------------------------------- #
SAMPLE_M3U = """#EXTM3U
#EXTINF:-1 tvg-id="BBCNews.uk" tvg-logo="https://img.example.com/bbc.png" group-title="News",BBC News HD
https://cdn.example.com/bbcnews/master.m3u8
#EXTINF:-1 tvg-id="CNNi.us" group-title="News",CNN International
http://edge.example.com/cnn/index.m3u8
#EXTINF:-1 tvg-id="Eurosport1.de" group-title="Sports",Eurosport 1 HD
https://sport.example.com/eurosport1/playlist.m3u8
#EXTINF:0 group-title="",Local Radio
https://radio.example.com/stream
"""


def self_test() -> None:
    ch = parse_m3u(SAMPLE_M3U)
    assert len(ch) == 4, ch
    assert ch[0]["name"] == "BBC News HD"
    assert ch[0]["group"] == "News"
    assert ch[0]["tvg_id"] == "BBCNews.uk"
    assert ch[0]["logo"] == "https://img.example.com/bbc.png"
    assert ch[0]["url"] == "https://cdn.example.com/bbcnews/master.m3u8"
    assert ch[1]["url"].startswith("http://edge.example.com/cnn")
    assert ch[3]["group"] == "Ungrouped"      # empty group-title
    # a channel name containing a comma must survive quote-aware splitting
    weird = ('#EXTM3U\n#EXTINF:-1 tvg-logo="http://x/a,b.png",News, 24x7\n'
             'https://cdn.example.com/news.m3u8\n')
    assert parse_m3u(weird)[0]["name"] == "News, 24x7"
    for bad in ("", "#EXTM3U\njust a comment\n",
                "https://cdn.example.com/x.m3u8\n",
                "#EXTM3U\n#EXTINF:-1,No URL follows\n"):
        try:
            parse_m3u(bad)
        except StreamError:
            pass
        else:
            raise AssertionError(f"bad m3u not rejected: {bad!r}")

    assert len(channels(ch, group="news")) == 2        # case-insensitive
    assert [c["name"] for c in channels(ch, query="cnn")] == ["CNN International"]
    assert channels(ch, query="zzz-no-match") == []

    argv = play_plan("http://edge.example.com/cnn/index.m3u8", title="CNN")
    assert argv[0] == "mpv" and "--force-cache" in argv
    assert "--force-media-title=CNN" in argv and argv[-1].endswith("/cnn/index.m3u8")
    assert "--demuxer-max-bytes=1024KiB" in play_plan("https://x/y", cache_kb=1024)
    for bad in (("ftp://x/y", None, 512), ("https://x/y", None, 8),
                ("https://x/y", None, "big"), ("", None, 512),
                ("https://x/y", "bad\ntitle", 512)):
        try:
            play_plan(*bad)
        except StreamError:
            pass
        else:
            raise AssertionError(f"bad play plan not rejected: {bad!r}")

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        store = os.path.join(d, "favorites")
        assert load_favorites(store) == []           # missing store -> empty
        add_favorite(store, "BBC News HD")
        add_favorite(store, "CNN International")
        add_favorite(store, "BBC News HD")           # idempotent
        assert load_favorites(store) == ["BBC News HD", "CNN International"]
        remove_favorite(store, "BBC News HD")
        assert load_favorites(store) == ["CNN International"]
        try:
            add_favorite(store, "   ")
        except StreamError:
            pass
        else:
            raise AssertionError("empty favorite not rejected")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
