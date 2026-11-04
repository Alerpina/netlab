"""OpenTelemetry opcional: liga só quando OTEL_EXPORTER_OTLP_ENDPOINT estiver definido.

Sem a variável (CI, testes, máquina sem o Alloy), tudo vira no-op e nada é exportado.
O contexto do trace passa entre processos pela variável TRACEPARENT (W3C Trace Context),
o mesmo padrão que o callback OpenTelemetry do Ansible usa.
"""

from __future__ import annotations

import atexit
import os
from collections.abc import Mapping

from opentelemetry import context, metrics, trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .logging_setup import run_context

SERVICE_NAME = "netauto"
_propagator = TraceContextTextMapPropagator()
_enabled = False


def enabled() -> bool:
    return _enabled


def setup(service: str = SERVICE_NAME) -> bool:
    """Configura traces e métricas OTLP/HTTP. Retorna True se ligou."""
    global _enabled
    if _enabled:
        return True
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False

    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    ctx = run_context()
    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", service),
            "service.version": ctx["commit"],
            "deployment.environment.name": os.getenv("NETAUTO_ENV", "lab"),
            "netauto.run_id": ctx["run_id"],
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=30_000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    # Exporta o que estiver pendente quando o processo terminar (inclusive em sys.exit)
    atexit.register(meter_provider.shutdown)
    atexit.register(tracer_provider.shutdown)
    _enabled = True
    return True


def tracer() -> trace.Tracer:
    return trace.get_tracer("netauto")


def meter() -> metrics.Meter:
    return metrics.get_meter("netauto")


def parent_from_env(env: Mapping[str, str] | None = None) -> context.Context:
    """Contexto do processo pai (TRACEPARENT), para o span deste processo virar filho."""
    env = os.environ if env is None else env
    carrier = {"traceparent": env["TRACEPARENT"]} if env.get("TRACEPARENT") else {}
    return _propagator.extract(carrier)


def child_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Ambiente para um subprocesso, com o TRACEPARENT do span atual."""
    env = dict(os.environ if base is None else base)
    carrier: dict[str, str] = {}
    _propagator.inject(carrier)
    if "traceparent" in carrier:
        env["TRACEPARENT"] = carrier["traceparent"]
    return env
