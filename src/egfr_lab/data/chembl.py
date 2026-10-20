"""ChEMBL GET 요청·재시도·페이지 무결성 검사."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time
import threading
from urllib.parse import parse_qsl, urljoin, urlsplit

import httpx

from .store import CollectionError


BASE = "https://www.ebi.ac.uk/chembl/api/data/"
RESOURCES = {"activity": ("activities", "activity_id"), "assay": ("assays", "assay_chembl_id"),
             "molecule": ("molecules", "molecule_chembl_id"), "document": ("documents", "document_chembl_id")}


def url_for(resource, params=None):
    return str(httpx.URL(BASE + resource + ".json", params=params))


def next_url(current, next_value, params, resource, offset):
    if not isinstance(next_value, str):
        raise CollectionError("다음 페이지 URL 형식이 잘못됐습니다.")
    url = urljoin(current, next_value)
    parsed, reference = urlsplit(url), urlsplit(url_for(resource))
    if (parsed.scheme, parsed.netloc, parsed.path) != (reference.scheme, reference.netloc, reference.path):
        raise CollectionError("다음 페이지가 원래 ChEMBL 자원 경로를 벗어났습니다.")
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = dict(pairs)
    if len(query) != len(pairs):
        raise CollectionError("다음 페이지에 중복 요청 조건이 있습니다.")
    expected = {k: str(v) for k, v in params.items() if k not in {"offset", "limit"}}
    actual = {k: v for k, v in query.items() if k not in {"offset", "limit"}}
    try:
        valid = actual == expected and int(query["offset"]) == offset and int(query["limit"]) > 0
    except (KeyError, ValueError):
        valid = False
    if not valid:
        raise CollectionError("다음 페이지의 필터 또는 offset이 일관되지 않습니다.")
    return url


def validate_page(value, resource, offset, total, seen, previous_id):
    plural, id_field = RESOURCES[resource]
    rows, meta = value.get(plural), value.get("page_meta")
    if not isinstance(rows, list) or not isinstance(meta, dict):
        raise CollectionError(f"페이지 스키마 누락: {resource}")
    for field in ("offset", "limit", "total_count"):
        if type(meta.get(field)) is not int:
            raise CollectionError(f"잘못된 페이지 메타데이터: {field}")
    if meta["offset"] != offset or meta["limit"] <= 0 or meta["total_count"] < 0:
        raise CollectionError("페이지 범위가 일관되지 않습니다.")
    if total is not None and meta["total_count"] != total:
        raise CollectionError("조회 중 total_count가 변경됐습니다.")
    if len(rows) > meta["limit"] or offset + len(rows) > meta["total_count"]:
        raise CollectionError("페이지 행 수가 API 집계 범위를 벗어났습니다.")
    for row in rows:
        if not isinstance(row, dict) or row.get(id_field) is None:
            raise CollectionError(f"필수 식별자 누락: {id_field}")
        identifier = row[id_field]
        if identifier in seen:
            raise CollectionError(f"중복 식별자: {identifier}")
        if previous_id is not None and identifier <= previous_id:
            raise CollectionError(f"식별자 정렬 불일치: {identifier}")
        seen.add(identifier)
        previous_id = identifier
    if not rows and meta.get("next"):
        raise CollectionError("빈 페이지가 다음 페이지를 가리킵니다.")
    if not meta.get("next") and offset + len(rows) != meta["total_count"]:
        raise CollectionError("마지막 페이지에 도달했지만 전체 건수가 맞지 않습니다.")
    return rows, meta, previous_id


class ChEMBLClient:
    def __init__(self, store, client=None, retries=3, sleeper=time.sleep):
        self.store = store
        self.client = client or httpx.Client(timeout=httpx.Timeout(60, connect=15), follow_redirects=False,
                                             headers={"User-Agent": "egfr-evidence-lab/0.1 collector",
                                                      "Accept": "application/json"})
        self.owns_client = client is None
        self.retries = retries
        self.sleeper = sleeper
        self.cancelled = threading.Event()

    def close(self):
        if self.owns_client:
            self.client.close()

    def get(self, key, url):
        cached = self.store.read(key, url)
        if cached is not None:
            return cached
        for attempt in range(self.retries):
            if self.cancelled.is_set():
                raise CollectionError("다른 요청의 실패·중단으로 새 요청을 취소했습니다.")
            response = None
            try:
                response = self.client.get(url)
                response.raise_for_status()
                return self.store.put(key, url, response)
            except (httpx.HTTPError, ValueError) as exc:
                status = response.status_code if response is not None else None
                self.store.error({"key": key, "url": url, "attempt": attempt + 1,
                                  "http_status": status, "error": str(exc)})
                retryable = status is None or status in {408, 429} or status >= 500 or status == 200
                if not retryable or attempt + 1 == self.retries:
                    raise CollectionError(f"요청 실패: {key}: {exc}") from exc
                delay = 2 ** attempt
                if response is not None and response.headers.get("Retry-After"):
                    raw = response.headers["Retry-After"]
                    try:
                        delay = max(delay, float(raw))
                    except ValueError:
                        try:
                            when = parsedate_to_datetime(raw)
                            if when.tzinfo is None:
                                when = when.replace(tzinfo=timezone.utc)
                            delay = max(delay, (when - datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError, OverflowError):
                            pass
                # Longer server cooldowns stop safely; a later resume can continue.
                if delay > 60:
                    raise CollectionError(f"서버가 {delay:.0f}초 대기를 요청했습니다. 이후 --resume으로 재개하세요.")
                if self.sleeper is time.sleep:
                    self.cancelled.wait(max(0, delay))
                else:
                    self.sleeper(max(0, delay))

    def pages(self, name, resource, params, max_pages=None, progress=None):
        keys, rows, seen = [], [], set()
        url, total, offset, previous_id = url_for(resource, params), None, 0, None
        urls = set()
        partial = False
        while True:
            if url in urls:
                raise CollectionError("페이지 URL이 반복됐습니다.")
            urls.add(url)
            key = f"{name}_{len(keys):06d}"
            value = self.get(key, url)
            page, meta, previous_id = validate_page(value, resource, offset, total, seen, previous_id)
            total = meta["total_count"]
            rows.extend(page)
            keys.append(key)
            offset += len(page)
            if progress:
                progress(len(rows), total)
            if not meta.get("next"):
                break
            following = next_url(url, meta["next"], params, resource, offset)
            if max_pages is not None and len(keys) >= max_pages:
                partial = True
                break
            url = following
        self.store.stream(name, {"resource": resource, "params": params, "keys": keys,
                                 "total_count": total, "partial": partial})
        return rows
