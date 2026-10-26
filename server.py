"""Internship Board API - Python standard library only (no installs needed)."""
import json, os, re, sqlite3, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(ROOT, "internships.db"))

WORK_MODES = ("remote", "hybrid", "onsite")
STATUSES = ("draft", "open", "closed")
FIELDS = ["title", "company", "location", "work_mode", "stipend_monthly",
          "duration_weeks", "status", "apply_url", "description"]
REQUIRED = ["title", "company", "location", "work_mode", "duration_weeks"]
DEFAULTS = {"stipend_monthly": None, "status": "open", "apply_url": None, "description": ""}


# ---------- database ----------
def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(seed=True):
    with connect() as con:
        with open(os.path.join(ROOT, "schema.sql")) as f:
            con.executescript(f.read())
        if seed and con.execute("SELECT COUNT(*) FROM internships").fetchone()[0] == 0:
            with open(os.path.join(ROOT, "seed.json")) as f:
                for rec in json.load(f):
                    cols = ", ".join(FIELDS)
                    marks = ", ".join("?" for _ in FIELDS)
                    con.execute(f"INSERT INTO internships ({cols}) VALUES ({marks})",
                                [rec.get(k) for k in FIELDS])


# ---------- validation ----------
def validate(body, partial=False):
    """Return (clean_dict, errors). partial=True allows missing fields (PATCH)."""
    errors, clean = [], {}
    if not isinstance(body, dict):
        return {}, [{"field": "body", "message": "must be a JSON object"}]
    for k in body:
        if k not in FIELDS:
            errors.append({"field": k, "message": "unknown field"})
    if not partial:
        for k in REQUIRED:
            if k not in body:
                errors.append({"field": k, "message": "is required"})

    def text(k, lo, hi, nullable=False):
        if k not in body:
            return
        v = body[k]
        if v is None and nullable:
            clean[k] = None
        elif not isinstance(v, str) or not (lo <= len(v.strip()) <= hi):
            errors.append({"field": k, "message": f"must be a string of {lo}-{hi} characters"})
        else:
            clean[k] = v.strip()

    text("title", 3, 120); text("company", 2, 80); text("location", 2, 80)
    text("description", 0, 2000)
    for k, allowed in (("work_mode", WORK_MODES), ("status", STATUSES)):
        if k in body:
            if body[k] not in allowed:
                errors.append({"field": k, "message": f"must be one of: {', '.join(allowed)}"})
            else:
                clean[k] = body[k]
    if "stipend_monthly" in body:
        v = body["stipend_monthly"]
        if v is None:
            clean["stipend_monthly"] = None
        elif isinstance(v, bool) or not isinstance(v, int) or v < 0:
            errors.append({"field": "stipend_monthly", "message": "must be a non-negative integer or null"})
        else:
            clean["stipend_monthly"] = v
    if "duration_weeks" in body:
        v = body["duration_weeks"]
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 52:
            errors.append({"field": "duration_weeks", "message": "must be an integer from 1 to 52"})
        else:
            clean["duration_weeks"] = v
    if "apply_url" in body:
        v = body["apply_url"]
        if v is None:
            clean["apply_url"] = None
        elif not isinstance(v, str) or not re.match(r"^https?://\S+$", v):
            errors.append({"field": "apply_url", "message": "must be an http(s) URL or null"})
        else:
            clean["apply_url"] = v
    return clean, errors


# ---------- HTTP layer ----------
class ApiError(Exception):
    def __init__(self, status, code, message, details=None, headers=None):
        self.status, self.code, self.message = status, code, message
        self.details, self.headers = details or [], headers or {}


def row_to_dict(r):
    return {k: r[k] for k in r.keys()}


class Handler(BaseHTTPRequestHandler):
    server_version = "InternshipBoard/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("QUIET") != "1":
            super().log_message(fmt, *args)

    # -- helpers
    def send_json(self, status, payload=None, headers=None):
        body = b"" if payload is None else json.dumps(payload, indent=2).encode()
        self.send_response(status)
        if payload is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def read_json(self):
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip()
        if ctype != "application/json":
            raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Content-Type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length > 100_000:
            raise ApiError(413, "PAYLOAD_TOO_LARGE", "Request body is too large")
        try:
            return json.loads(self.rfile.read(length) or b"")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError(400, "INVALID_JSON", "Request body is not valid JSON")

    def dispatch(self):
        try:
            url = urlparse(self.path)
            path = url.path.rstrip("/") or "/"
            if path in ("/", "/index.html") and self.command == "GET":
                return self.serve_index()
            if path == "/api/health":
                return self.send_json(200, {"data": {"status": "ok"}})
            if path == "/api/internships":
                if self.command == "GET":
                    return self.list_items(parse_qs(url.query))
                if self.command == "POST":
                    return self.create_item()
                raise ApiError(405, "METHOD_NOT_ALLOWED", "Use GET or POST", headers={"Allow": "GET, POST"})
            m = re.fullmatch(r"/api/internships/([^/]+)", path)
            if m:
                iid = self.parse_id(m.group(1))
                if self.command == "GET":
                    return self.get_item(iid)
                if self.command in ("PUT", "PATCH"):
                    return self.update_item(iid, partial=self.command == "PATCH")
                if self.command == "DELETE":
                    return self.delete_item(iid)
                raise ApiError(405, "METHOD_NOT_ALLOWED", "Use GET, PUT, PATCH or DELETE",
                               headers={"Allow": "GET, PUT, PATCH, DELETE"})
            raise ApiError(404, "NOT_FOUND", f"No route for {self.command} {path}")
        except ApiError as e:
            self.send_json(e.status, {"error": {"code": e.code, "message": e.message, "details": e.details}}, e.headers)
        except sqlite3.IntegrityError:
            self.send_json(409, {"error": {"code": "CONFLICT", "message":
                            "An internship with this title and company already exists", "details": []}})
        except Exception as e:  # never leak internals
            print("Unhandled error:", repr(e), file=sys.stderr)
            self.send_json(500, {"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong", "details": []}})

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = dispatch

    def do_OPTIONS(self):
        self.send_json(204, None, {"Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                                   "Access-Control-Allow-Headers": "Content-Type"})

    @staticmethod
    def parse_id(raw):
        if not raw.isdigit() or int(raw) < 1:
            raise ApiError(400, "INVALID_ID", "id must be a positive integer",
                           [{"field": "id", "message": "must be a positive integer"}])
        return int(raw)

    def serve_index(self):
        with open(os.path.join(ROOT, "public", "index.html"), "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- handlers
    def fetch(self, con, iid):
        r = con.execute("SELECT * FROM internships WHERE id = ?", (iid,)).fetchone()
        if not r:
            raise ApiError(404, "NOT_FOUND", f"Internship {iid} not found")
        return row_to_dict(r)

    def list_items(self, qs):
        where, args, errors = [], [], []
        status = qs.get("status", [None])[0]
        mode = qs.get("work_mode", [None])[0]
        q = qs.get("q", [None])[0]
        if status:
            if status not in STATUSES: errors.append({"field": "status", "message": f"must be one of: {', '.join(STATUSES)}"})
            else: where.append("status = ?"); args.append(status)
        if mode:
            if mode not in WORK_MODES: errors.append({"field": "work_mode", "message": f"must be one of: {', '.join(WORK_MODES)}"})
            else: where.append("work_mode = ?"); args.append(mode)
        if q:
            where.append("(title LIKE ? OR company LIKE ? OR location LIKE ?)")
            args += [f"%{q}%"] * 3
        try:
            page = int(qs.get("page", ["1"])[0]); limit = int(qs.get("limit", ["10"])[0])
            if page < 1 or not 1 <= limit <= 50: raise ValueError
        except ValueError:
            errors.append({"field": "page/limit", "message": "page must be >= 1 and limit between 1 and 50"})
            page, limit = 1, 10
        if errors:
            raise ApiError(422, "VALIDATION_ERROR", "Invalid query parameters", errors)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        with connect() as con:
            total = con.execute(f"SELECT COUNT(*) FROM internships {clause}", args).fetchone()[0]
            rows = con.execute(f"SELECT * FROM internships {clause} ORDER BY id LIMIT ? OFFSET ?",
                               args + [limit, (page - 1) * limit]).fetchall()
        self.send_json(200, {"data": [row_to_dict(r) for r in rows],
                             "meta": {"page": page, "limit": limit, "total": total,
                                      "total_pages": max(1, -(-total // limit))}})

    def get_item(self, iid):
        with connect() as con:
            self.send_json(200, {"data": self.fetch(con, iid)})

    def create_item(self):
        clean, errors = validate(self.read_json())
        if errors:
            raise ApiError(422, "VALIDATION_ERROR", "Request body failed validation", errors)
        rec = {**DEFAULTS, **clean}
        with connect() as con:
            cur = con.execute(f"INSERT INTO internships ({', '.join(FIELDS)}) VALUES ({', '.join('?' for _ in FIELDS)})",
                              [rec[k] for k in FIELDS])
            item = self.fetch(con, cur.lastrowid)
        self.send_json(201, {"data": item}, {"Location": f"/api/internships/{item['id']}"})

    def update_item(self, iid, partial):
        clean, errors = validate(self.read_json(), partial=partial)
        if errors:
            raise ApiError(422, "VALIDATION_ERROR", "Request body failed validation", errors)
        if partial and not clean:
            raise ApiError(422, "VALIDATION_ERROR", "PATCH body must include at least one field",
                           [{"field": "body", "message": "no fields to update"}])
        with connect() as con:
            self.fetch(con, iid)  # 404 first
            rec = clean if partial else {**DEFAULTS, **clean}
            sets = ", ".join(f"{k} = ?" for k in rec) + ", updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')"
            con.execute(f"UPDATE internships SET {sets} WHERE id = ?", list(rec.values()) + [iid])
            item = self.fetch(con, iid)
        self.send_json(200, {"data": item})

    def delete_item(self, iid):
        with connect() as con:
            self.fetch(con, iid)
            con.execute("DELETE FROM internships WHERE id = ?", (iid,))
        self.send_json(204)


def main():
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    print(f"Internship Board API running at http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
