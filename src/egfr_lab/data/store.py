"""원 응답과 실행 상태를 원자적으로 보관한다."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import uuid


class CollectionError(ValueError):
    """수집 완료 조건을 만족하지 못했다."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def atomic_bytes(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".partial-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())


@contextmanager
def exclusive_run(path):
    # flock is released by the OS on interruption; the harmless file may remain.
    import fcntl
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    with (path / ".collection.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CollectionError("같은 수집 폴더를 다른 프로세스가 사용 중입니다.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class RunStore:
    def __init__(self, path, options=None, resume=False):
        self.path = Path(path).resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        manifest_path = self.path / "manifest.json"
        if manifest_path.exists():
            if not resume:
                raise CollectionError("기존 실행 폴더입니다. --resume을 지정하거나 새 경로를 사용하세요.")
            self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if self.manifest.get("schema_version") != 1:
                raise CollectionError("지원하지 않는 매니페스트 버전입니다.")
            if options is not None and self.manifest["options"] != options:
                raise CollectionError("재시작 조건이 원래 수집 조건과 다릅니다. 새 실행 폴더를 사용하세요.")
        elif resume:
            raise CollectionError("재시작할 manifest.json이 없습니다.")
        else:
            self.manifest = {"schema_version": 1, "run_id": uuid.uuid4().hex,
                             "created_at_utc": utc_now(), "state": "created",
                             "options": options, "requests": {}, "streams": {}, "errors": [],
                             "attempts": [], "exports": {}}
            self.save()

    def save(self):
        with self._lock:
            self.manifest["updated_at_utc"] = utc_now()
            atomic_json(self.path / "manifest.json", self.manifest)
            atomic_json(self.path / "checkpoint.json", {
                "state": self.manifest["state"], "updated_at_utc": self.manifest["updated_at_utc"],
                "successful_requests": len(self.manifest["requests"]),
                "completed_streams": sorted(self.manifest["streams"]),
                "note": "manifest.json이 기준 기록이며 이 파일은 진행 상태 요약입니다."})

    def update(self, **values):
        with self._lock:
            self.manifest.update(values)
            self.save()

    def error(self, value):
        with self._lock:
            self.manifest["errors"].append({"at_utc": utc_now(), **value})
            self.save()

    def read(self, key, expected_url=None):
        record = self.manifest["requests"].get(key)
        if record is None:
            return None
        if expected_url is not None and record["url"] != expected_url:
            raise CollectionError(f"보관 요청 URL 불일치: {key}")
        path = self.path / record["file"]
        if not path.is_file():
            raise CollectionError(f"원 응답 파일 누락: {record['file']}")
        body = path.read_bytes()
        if digest(body) != record["sha256"] or len(body) != record["bytes"]:
            raise CollectionError(f"원 응답 해시·크기 불일치: {key}. 원본을 보존하고 새 실행으로 재수집하세요.")
        try:
            value = json.loads(body)
        except ValueError as exc:
            raise CollectionError(f"보관 JSON 해석 실패: {key}") from exc
        if not isinstance(value, dict):
            raise CollectionError(f"JSON 객체가 아닌 응답: {key}")
        return value

    def put(self, key, url, response):
        value = response.json()
        if not isinstance(value, dict):
            raise CollectionError(f"JSON 객체가 아닌 응답: {key}")
        filename = f"responses/{key}.json"
        body = response.content
        with self._lock:
            atomic_bytes(self.path / filename, body)
            self.manifest["requests"][key] = {
                "url": url, "file": filename, "sha256": digest(body), "bytes": len(body),
                "http_status": response.status_code, "retrieved_at_utc": utc_now(),
                "server_date": response.headers.get("Date"),
                "content_type": response.headers.get("Content-Type")}
            self.save()
        return value

    def stream(self, name, value):
        with self._lock:
            self.manifest["streams"][name] = value
            self.save()

    def export(self, name, path):
        path = Path(path).resolve()
        with self._lock:
            self.manifest["exports"][name] = {
                "path": os.path.relpath(path, self.path), "bytes": path.stat().st_size,
                "sha256": digest(path.read_bytes())}
            self.save()
