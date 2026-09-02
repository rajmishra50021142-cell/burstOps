"""Upgrade D: OpenTelemetry tracing — provider, sampler, exporter, hooks.

gateway.py is NEVER touched by this upgrade: instrumentation is attached
from outside (FastAPIInstrumentor / HTTPXClientInstrumentor patch the
running app/client), wired in by gateway_entrypoint.py.

Exporter is env-switched:
  OTEL_TRACES_EXPORTER = none (default; zero spans) | console | otlp | azure_monitor
Unknown value -> warning + none. A typo must never stop traffic.

W3C traceparent rides along freely: the HMAC signature covers
f"{timestamp}:" + body ONLY — headers are outside the signed payload.
(Flip side: trace headers are unsigned; a caller could graft spans onto
your traces. Acceptable for an internal demo; noted, not "fixed".)
"""
import logging
import os
import socket

logger = logging.getLogger("burstops.tracing")

NOOP = object()  # sentinel: tracing disabled


class RoutingAwareSampler:
    """100% of burst-window traffic, a small fraction of baseline.

    The gateway already knows its mode BEFORE handling a request, so head
    sampling can consult it. Wrapped in ParentBased(...) at install time so
    an inbound sampled traceparent is honoured; the actual ratio decision
    delegates to TraceIdRatioBased for trace-id determinism (never roll
    your own random() here — a sampled trace must not produce unsampled
    children in another process).

    Must never raise and must never touch Redis/Prometheus/any I/O — it
    runs on every request, before the handler.
    """

    def __init__(self, delegate, baseline_ratio: float) -> None:
        self._delegate = delegate
        self._baseline_ratio = baseline_ratio

    def should_sample(self, parent_context, trace_id, name, *args, **kwargs):
        try:
            import gateway  # late import: module constants live there

            hot = gateway.routing_state.mode is gateway.Mode.BURST
        except Exception:  # noqa: BLE001 — never raise from the sampler
            hot = False
        try:
            ratio = 1.0 if hot else self._baseline_ratio
            return self._delegate(ratio).should_sample(
                parent_context, trace_id, name, *args, **kwargs
            )
        except Exception:  # noqa: BLE001
            from opentelemetry.trace import Decision, SamplingResult

            return SamplingResult(Decision.DROP)


def _build_exporter(mode: str):
    """none -> None; console -> ConsoleSpanExporter; otlp -> OTLP gRPC;
    azure_monitor -> azure-monitor-opentelemetry exporter (in-process; App
    Insights does not ingest raw OTLP — never run a Collector pod for this)."""
    if mode == "none":
        return None
    if mode == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        return ConsoleSpanExporter()
    if mode == "otlp":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter()
    if mode == "azure_monitor":
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

        cs = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
        if not cs:
            logger.warning("azure_monitor exporter requested but no connection string; tracing off")
            return None
        return AzureMonitorTraceExporter(connection_string=cs)
    logger.warning("unknown OTEL_TRACES_EXPORTER=%r; tracing off", mode)
    return None


def configure_tracing():
    """Build the TracerProvider. Returns None when tracing is off (the
    default) — callers must treat that as a no-op, never an error."""
    mode = os.environ.get("OTEL_TRACES_EXPORTER", "none").strip().lower()
    exporter = _build_exporter(mode)
    if exporter is None:
        return None

    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "burstops-gateway"),
            "service.version": os.environ.get("IMAGE_TAG", "dev"),
            "deployment.environment": os.environ.get("DEPLOY_ENV", "local"),
            # HOSTNAME = pod name for free under K8s; distinguishes replicas
            "service.instance.id": os.environ.get("HOSTNAME", socket.gethostname()),
        }
    )

    baseline_ratio = float(os.environ.get("OTEL_BASELINE_SAMPLE_RATIO", "0.05"))
    sampler = ParentBased(
        root=RoutingAwareSampler(TraceIdRatioBased, baseline_ratio)
    )

    provider = TracerProvider(resource=resource, sampler=sampler)
    # BatchSpanProcessor ALWAYS in production config — SimpleSpanProcessor
    # would put exporter network latency inside the measured request.
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    try:  # flush the last batch on shutdown instead of dropping it
        import atexit

        atexit.register(lambda: provider.shutdown())
    except Exception:  # noqa: BLE001
        pass
    return provider


# contextvar lifting burstops.route from the client hook to the server span
import contextvars  # noqa: E402

_current_route = contextvars.ContextVar("burstops_route", default=None)
_current_function_meta = contextvars.ContextVar("burstops_fn_meta", default=None)


def install_instrumentation(app):
    """Attach FastAPI + httpx auto-instrumentation + attribute hooks.

    HTTPXClientInstrumentor patches the transport classes, so the
    module-level client gateway.py created at import time is still
    instrumented even though it exists before this call.
    """
    try:
        import gateway

        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        def _response_hook(span, request, response=None, *_a, **_kw):
            try:  # a hook that raises would turn observability into an outage
                import gateway

                url = str(getattr(request, "url", ""))
                if gateway.FUNCTION_UPSTREAM and gateway.FUNCTION_UPSTREAM in url:
                    _current_route.set("serverless")
                    span.set_attribute("burstops.route", "serverless")
                    body = getattr(response, "read", None)
                    if body:
                        import json

                        try:
                            payload = json.loads(body())
                            if "cold_start" in payload:
                                span.set_attribute(
                                    "burstops.cold_start", bool(payload["cold_start"])
                                )
                            if payload.get("instance_id"):
                                span.set_attribute(
                                    "burstops.function_instance_id",
                                    str(payload["instance_id"]),
                                )
                        except Exception:  # noqa: BLE001
                            pass
                elif gateway.K8S_UPSTREAM and gateway.K8S_UPSTREAM.split("//")[-1].split(":")[0] in url:
                    _current_route.set("k8s")
                    span.set_attribute("burstops.route", "k8s")
            except Exception:  # noqa: BLE001
                pass

        def _request_hook(span, request, *_a, **_kw):
            # URL is known before send — set burstops.route here (no body
            # read, no response parsing). try/except: a hook that raises
            # would turn observability into an outage.
            try:
                if span is None:
                    return
                import gateway

                url = str(getattr(request, "url", ""))
                if gateway.FUNCTION_UPSTREAM and gateway.FUNCTION_UPSTREAM in url:
                    _current_route.set("serverless")
                    span.set_attribute("burstops.route", "serverless")
                elif gateway.K8S_UPSTREAM and (
                    gateway.K8S_UPSTREAM in url
                    or gateway.K8S_UPSTREAM.split("//")[-1].split(":")[0] in url
                    or "calculate" in url
                ):
                    _current_route.set("k8s")
                    span.set_attribute("burstops.route", "k8s")
            except Exception:  # noqa: BLE001
                pass

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="metrics,health",
        )
        # Patch BOTH the class (for any future clients) and the already-created
        # module-level instance in gateway.py — patching the transport classes
        # alone proved insufficient for the import-time AsyncClient in this
        # OTel/uvicorn combination, leaving zero client spans.
        HTTPXClientInstrumentor().instrument(
            request_hook=_request_hook, response_hook=_response_hook
        )
        async def _async_request_hook(span, request, *_a, **_kw):
            # AsyncClient takes the ASYNC hook signature; delegate to the
            # shared logic. Never raises.
            _request_hook(span, request, *_a, **_kw)

        async def _async_response_hook(span, request, response, *_a, **_kw):
            _response_hook(span, request, response, *_a, **_kw)

        try:
            existing = gateway._get_client()
            if existing is not None:
                HTTPXClientInstrumentor().instrument_client(
                    existing,
                    request_hook=_async_request_hook,
                    response_hook=_async_response_hook,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("httpx instance instrumentation skipped: %s", exc)

        # Server-span attributes: mode/cpu/ratio read from module state —
        # zero gateway.py changes needed.
        from opentelemetry import trace

        class _AttributesMiddleware:
            """Pure-ASGI middleware: copies burstops.* attributes onto the
            server span as the response starts. try/except everywhere — a
            tracing bug must never become an outage."""

            def __init__(self, app):
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope.get("type") != "http":
                    await self.app(scope, receive, send)
                    return

                async def _send(message):
                    if message["type"] == "http.response.start":
                        try:
                            span = trace.get_current_span()
                            if span and span.is_recording():
                                import gateway

                                span.set_attribute(
                                    "burstops.routing_mode",
                                    gateway.routing_state.mode.value,
                                )
                                span.set_attribute(
                                    "burstops.cpu_observed_percent",
                                    gateway.routing_state.cpu_observed,
                                )
                                ratio = getattr(
                                    gateway.routing_state, "deflect_ratio", None
                                )
                                if ratio is not None:
                                    span.set_attribute(
                                        "burstops.deflect_ratio", ratio
                                    )
                                route = _current_route.get()
                                if route:
                                    span.set_attribute("burstops.route", route)
                        except Exception:  # noqa: BLE001
                            pass
                    await send(message)

                await self.app(scope, receive, _send)

        app.add_middleware(_AttributesMiddleware)  # type: ignore[arg-type]
        return True
    except Exception as exc:  # noqa: BLE001 — tracing must never break serving
        logger.warning("tracing instrumentation failed (serving continues): %s", exc)
        return False
