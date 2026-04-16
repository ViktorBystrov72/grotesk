import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from grotesk.infrastructure.db.config import DBConfig
from grotesk.infrastructure.db.init_data import initialize_database
from grotesk.infrastructure.db.session import build_engine, build_session_factory


class RequestHandler(BaseHTTPRequestHandler):
    def _write_json(self, payload: dict[str, object], status_code: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._write_json(
                {
                    "status": "ok",
                    "service": os.getenv("APP_NAME", "grotesk-app"),
                    "environment": os.getenv("APP_ENV", "development"),
                },
            )
            return

        self._write_json(
            {
                "service": os.getenv("APP_NAME", "grotesk-app"),
                "environment": os.getenv("APP_ENV", "development"),
                "message": "Grotesk app is running behind web-proxy.",
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        return None


def main() -> None:
    db_config = DBConfig.from_env()
    engine = build_engine(db_config)
    session_factory = build_session_factory(engine)
    asyncio.run(initialize_database(engine, session_factory))
    asyncio.run(engine.dispose())

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), RequestHandler)
    print(f"Starting app on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
