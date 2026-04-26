from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

REQUEST_COUNT = Counter("api_requests_total", "Total API requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("api_request_latency_seconds", "API request latency", ["method", "path"])
TOKENS_IN = Counter("tokens_input_total", "Total tokens input", ["model"])
TOKENS_OUT = Counter("tokens_output_total", "Total tokens output", ["model"])
ACTIVE_STREAMS = Counter("active_stream_sessions_total", "Total stream sessions", ["type"])


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
