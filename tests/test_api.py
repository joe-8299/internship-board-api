import json, os, tempfile, threading, unittest, urllib.request, urllib.error
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["QUIET"] = "1"
import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server
from http.server import ThreadingHTTPServer

VALID = {"title": "Test Intern", "company": "Acme Test", "location": "Chennai",
         "work_mode": "remote", "duration_weeks": 8}
BASE = ""

def call(method, path, body=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None: req.add_header("Content-Type", ctype)
    try:
        r = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        r = e
    text = r.read().decode()
    return r.status, (json.loads(text) if text else None), r.headers

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global BASE
        server.init_db()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        BASE = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.httpd.shutdown()

    def test_list_and_filters(self):
        s, b, _ = call("GET", "/api/internships")
        self.assertEqual(s, 200); self.assertGreaterEqual(b["meta"]["total"], 8)
        s, b, _ = call("GET", "/api/internships?status=closed&limit=1")
        self.assertEqual(len(b["data"]), 1); self.assertEqual(b["meta"]["total"], 2)
        self.assertEqual(call("GET", "/api/internships?status=nope")[0], 422)
    def test_detail_and_errors(self):
        self.assertEqual(call("GET", "/api/internships/1")[0], 200)
        self.assertEqual(call("GET", "/api/internships/9999")[0], 404)
        self.assertEqual(call("GET", "/api/internships/abc")[0], 400)
        self.assertEqual(call("GET", "/api/nothing")[0], 404)
        self.assertEqual(call("PUT", "/api/internships", {})[0], 405)
    def test_crud_flow(self):
        s, b, h = call("POST", "/api/internships", VALID)
        self.assertEqual(s, 201); iid = b["data"]["id"]
        self.assertEqual(h["Location"], f"/api/internships/{iid}")
        self.assertEqual(b["data"]["status"], "open")
        s, b, _ = call("PATCH", f"/api/internships/{iid}", {"status": "closed"})
        self.assertEqual((s, b["data"]["status"], b["data"]["company"]), (200, "closed", "Acme Test"))
        s, b, _ = call("PUT", f"/api/internships/{iid}", {**VALID, "title": "Renamed Intern"})
        self.assertEqual((s, b["data"]["title"], b["data"]["status"]), (200, "Renamed Intern", "open"))
        self.assertEqual(call("DELETE", f"/api/internships/{iid}")[0], 204)
        self.assertEqual(call("GET", f"/api/internships/{iid}")[0], 404)
        self.assertEqual(call("DELETE", f"/api/internships/{iid}")[0], 404)
    def test_validation(self):
        s, b, _ = call("POST", "/api/internships", {"title": "x", "work_mode": "moon", "duration_weeks": 99, "bogus": 1})
        self.assertEqual(s, 422); self.assertEqual(b["error"]["code"], "VALIDATION_ERROR")
        fields = {d["field"] for d in b["error"]["details"]}
        self.assertTrue({"title", "company", "location", "work_mode", "duration_weeks", "bogus"} <= fields)
        self.assertEqual(call("POST", "/api/internships", raw=b"{bad")[0], 400)
        self.assertEqual(call("POST", "/api/internships", raw=b"{}", ctype="text/plain")[0], 415)
        self.assertEqual(call("PATCH", "/api/internships/1", {})[0], 422)
        self.assertEqual(call("PUT", "/api/internships/1", {"title": "Only title"})[0], 422)
    def test_duplicate(self):
        self.assertEqual(call("POST", "/api/internships", {**VALID, "title": "Dup Intern"})[0], 201)
        s, b, _ = call("POST", "/api/internships", {**VALID, "title": "Dup Intern"})
        self.assertEqual((s, b["error"]["code"]), (409, "CONFLICT"))

if __name__ == "__main__":
    unittest.main()
