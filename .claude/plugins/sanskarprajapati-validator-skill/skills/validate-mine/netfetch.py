"""A small JSON-over-HTTP client: polite delay, retries with backoff, a day-long cache."""

import hashlib
import http.client
import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "validator-skill/0.1 (+https://github.com/sanskarprajapati/validator-skill)"
RETRY_CODES = (429, 500, 502, 503, 504)
CACHE_TTL = 24 * 3600
RATE_LIMIT_WAIT = 15  # seconds; a 429 means slow down properly, not a quick retry
MAX_WAIT = 120


class FetchError(Exception):
    """A request that failed for good. The message says why, in plain words."""


class Http:
    def __init__(self, cache_dir=None, delay=1.0, retries=3, timeout=30,
                 opener=urllib.request.urlopen, sleep=time.sleep, clock=time.monotonic):
        self.cache_dir, self.delay, self.retries, self.timeout = cache_dir, delay, retries, timeout
        self._open, self._sleep, self._clock = opener, sleep, clock
        self._last = None

    def get_json(self, url):
        cached = self._cache_read(url)
        if cached is not None:
            return cached
        body = self._fetch(url)
        try:
            data = json.loads(body)
        except ValueError:
            raise FetchError("%s did not return JSON (blocked, or the API changed)" % _host(url))
        self._cache_write(url, data)
        return data

    def _fetch(self, url):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        problem, pause, limited = "no attempt made", 0.0, 0
        for attempt in range(self.retries + 1):
            if attempt:
                self._sleep(pause)
            self._wait_turn()
            try:
                with self._open(request, timeout=self.timeout) as response:
                    return response.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as err:
                if err.code not in RETRY_CODES:
                    raise FetchError("%s answered HTTP %d" % (_host(url), err.code))
                problem = "HTTP %d" % err.code
                if err.code == 429:
                    limited += 1
                    pause = _retry_after(err) or RATE_LIMIT_WAIT * (2 ** (limited - 1))
                else:
                    pause = self.delay * (2 ** (attempt + 1))
                pause = min(float(pause), MAX_WAIT)
                continue
            except (urllib.error.URLError, OSError, http.client.HTTPException) as err:
                # OSError covers socket.timeout on Python 3.8 and 3.9, where it is not a TimeoutError
                problem = str(getattr(err, "reason", err)) or type(err).__name__
                pause = min(self.delay * (2 ** (attempt + 1)), MAX_WAIT)
        raise FetchError("%s failed after %d tries: %s" % (_host(url), self.retries + 1, problem))

    def _wait_turn(self):
        now = self._clock()
        if self._last is not None:
            wait = self.delay - (now - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()

    def _cache_path(self, url):
        return os.path.join(self.cache_dir, hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")

    def _cache_read(self, url):
        if not self.cache_dir:
            return None
        path = self._cache_path(url)
        if not os.path.exists(path) or time.time() - os.path.getmtime(path) > CACHE_TTL:
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (ValueError, OSError):
            return None  # a broken cache file is refetched, not trusted

    def _cache_write(self, url, data):
        if not self.cache_dir or not worth_caching(data):
            return
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            handle, tmp = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, self._cache_path(url))
        except OSError:
            pass  # the cache only saves time; failing to write it must not fail the run


def _retry_after(err):
    """Seconds from a Retry-After header, or None if it is missing or a date."""
    try:
        value = float((getattr(err, "headers", None) or {}).get("Retry-After"))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def worth_caching(data):
    """Never cache an outage: an error body, or a page whose lists are all empty."""
    if not data:
        return False
    if isinstance(data, dict):
        if "error" in data:
            return False
        lists = [v for v in data.values() if isinstance(v, list)]
        if lists and not any(lists):
            return False
    return True


def _host(url):
    return urllib.parse.urlparse(url).netloc or url
