"""Round 47: Kubernetes deployment template tests.

Validates deploy/k8s/deployment.yaml is present and contains
all required resources (Namespace, Deployment, Service, Ingress, HPA).
"""

import os
import yaml  # type: ignore


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_k8s_manifests() -> list[dict]:
    """Load all YAML docs from the K8s deployment file."""
    path = os.path.join(REPO, "deploy", "k8s", "deployment.yaml")
    assert os.path.exists(path), "Missing deploy/k8s/deployment.yaml"
    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    return [d for d in docs if d is not None]


def test_k8s_file_exists() -> None:
    manifests = _read_k8s_manifests()
    assert len(manifests) >= 4


def test_k8s_has_namespace() -> None:
    manifests = _read_k8s_manifests()
    ns = next(m for m in manifests if m.get("kind") == "Namespace")
    assert ns["metadata"]["name"] == "apiforge"


def test_k8s_deployment() -> None:
    manifests = _read_k8s_manifests()
    dep = next(m for m in manifests if m.get("kind") == "Deployment")
    assert dep["spec"]["replicas"] == 2
    container = dep["spec"]["template"]["spec"]["containers"][0]
    assert container["name"] == "api"
    assert container["ports"][0]["containerPort"] == 8000


def test_k8s_deployment_resources() -> None:
    manifests = _read_k8s_manifests()
    dep = next(m for m in manifests if m.get("kind") == "Deployment")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    assert "resources" in container
    assert "requests" in container["resources"]
    assert "limits" in container["resources"]
    assert container["resources"]["limits"]["cpu"] == "500m"


def test_k8s_deployment_probes() -> None:
    manifests = _read_k8s_manifests()
    dep = next(m for m in manifests if m.get("kind") == "Deployment")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    assert "livenessProbe" in container
    assert "readinessProbe" in container
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert container["readinessProbe"]["httpGet"]["path"] == "/health"


def test_k8s_deployment_security() -> None:
    manifests = _read_k8s_manifests()
    dep = next(m for m in manifests if m.get("kind") == "Deployment")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    assert container["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["runAsUser"] == 1000


def test_k8s_service() -> None:
    manifests = _read_k8s_manifests()
    svc = next(m for m in manifests if m.get("kind") == "Service")
    assert svc["spec"]["type"] == "ClusterIP"
    assert svc["spec"]["ports"][0]["port"] == 8000


def test_k8s_ingress() -> None:
    manifests = _read_k8s_manifests()
    ing = next(m for m in manifests if m.get("kind") == "Ingress")
    assert "rules" in ing["spec"]
    rule = ing["spec"]["rules"][0]
    assert "apiforge.local" in rule["host"]


def test_k8s_hpa() -> None:
    manifests = _read_k8s_manifests()
    hpa = next(m for m in manifests if m.get("kind") == "HorizontalPodAutoscaler")
    assert hpa["spec"]["minReplicas"] == 2
    assert hpa["spec"]["maxReplicas"] == 10
    assert hpa["spec"]["scaleTargetRef"]["name"] == "apiforge-api"
    # CPU-based scaling
    metrics = hpa["spec"]["metrics"]
    assert metrics[0]["resource"]["name"] == "cpu"
    assert metrics[0]["resource"]["target"]["averageUtilization"] == 70


def test_k8s_prometheus_annotations() -> None:
    manifests = _read_k8s_manifests()
    dep = next(m for m in manifests if m.get("kind") == "Deployment")
    annotations = dep["spec"]["template"]["metadata"]["annotations"]
    assert annotations.get("prometheus.io/scrape") == "true"
    assert annotations.get("prometheus.io/path") == "/metrics"
