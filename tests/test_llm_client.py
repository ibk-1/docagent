"""The LLM client against a fake OpenAI-compatible server (no model needed)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from docagent.generate import generate
from docagent.llm import extract_plain


def _serve(reply: str):
    seen = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps({"choices": [{"message": {"content": reply}}], "usage": {"total_tokens": 1}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    return srv, seen


def test_extract_plain_parses_json_and_sends_schema():
    doc = generate(1, seed=11)[0]
    srv, seen = _serve(json.dumps(doc["gold"]))
    out = extract_plain(doc["text"], f"http://127.0.0.1:{srv.server_port}")
    assert out["pred"] == doc["gold"]
    assert seen["body"]["response_format"]["type"] == "json_schema"
    assert doc["text"] in seen["body"]["messages"][1]["content"]


def test_extract_plain_handles_broken_json():
    srv, _ = _serve("not json")
    out = extract_plain("Rechnung", f"http://127.0.0.1:{srv.server_port}")
    assert out["pred"] is None and out["raw"] == "not json"
