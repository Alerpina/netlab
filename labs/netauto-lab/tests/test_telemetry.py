from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider

from netauto import telemetry
from netauto.drift import record_metrics


def test_sem_endpoint_fica_desligado(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert telemetry.setup() is False


def test_traceparent_passa_para_o_subprocesso_e_volta():
    tracer = TracerProvider().get_tracer("t")
    with tracer.start_as_current_span("pai") as span:
        env = telemetry.child_env({})
    trace_id = format(span.get_span_context().trace_id, "032x")
    assert env["TRACEPARENT"].split("-")[1] == trace_id

    from opentelemetry import trace

    parent = trace.get_current_span(telemetry.parent_from_env(env)).get_span_context()
    assert parent.trace_id == span.get_span_context().trace_id


def test_sem_span_ativo_nao_inventa_traceparent():
    assert "TRACEPARENT" not in telemetry.child_env({})


def test_metricas_de_drift():
    reader = InMemoryMetricReader()
    meter = MeterProvider(metric_readers=[reader]).get_meter("t")
    record_metrics(
        {
            "hosts": {
                "leaf1": {"drift": [{"path": "/x"}]},
                "leaf2": {"drift": []},
                "spine1": {"error": "timeout"},
            }
        },
        meter,
    )
    data = reader.get_metrics_data()
    points = {
        (m.name, dict(p.attributes).get("host")): p.value
        for rm in data.resource_metrics
        for sm in rm.scope_metrics
        for m in sm.metrics
        for p in m.data.data_points
    }
    assert points[("netauto.drift.items", "leaf1")] == 1
    assert points[("netauto.drift.items", "leaf2")] == 0
    assert ("netauto.drift.items", "spine1") not in points
    assert points[("netauto.drift.reachable", "spine1")] == 0
    assert points[("netauto.drift.reachable", "leaf1")] == 1
    assert points[("netauto.drift.last_run", None)] > 1_700_000_000
