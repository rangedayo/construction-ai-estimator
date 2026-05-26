"""`config/length_routing.yaml` 로더 — 라운드 길이-1.

도면별 측정 소스 파일·부호 적용 범위·측정 방법 파라미터를 결정론적으로 로드.
1단계의 `config/symbol_rules.yaml` 패턴과 동일 (pyyaml 부재 시 ImportError).
"""
from __future__ import annotations

import os

from poc_v2.length.ground_truth_length import PROJECT_ROOT

DEFAULT_ROUTING_PATH = os.path.join(PROJECT_ROOT, "config", "length_routing.yaml")


def load_routing(path: str | None = None) -> dict:
    """YAML 라우팅 설정 로드. 누락 키는 호출 측에서 검증."""
    import yaml  # noqa: PLC0415 — optional dep, fail fast at use time

    cfg_path = path or DEFAULT_ROUTING_PATH
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"length_routing.yaml not found: {cfg_path}")
    with open(cfg_path, encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    if "drawings" not in config:
        raise ValueError(f"{cfg_path} 에 `drawings` 키 누락")
    if "methods" not in config:
        raise ValueError(f"{cfg_path} 에 `methods` 키 누락")
    return config


def resolve_source_path(rel_path: str) -> str:
    """yaml 의 상대 경로를 프로젝트 루트 기준 절대 경로로 변환."""
    return os.path.join(PROJECT_ROOT, rel_path.replace("/", os.sep))


def method_params(config: dict, method: str) -> dict:
    """측정 방법 키 → 파라미터 dict. 누락 시 ValueError."""
    methods = config.get("methods") or {}
    if method not in methods:
        raise ValueError(
            f"length_routing.yaml 에 method {method!r} 정의 없음 "
            f"(가능한 키: {list(methods.keys())})"
        )
    return methods[method] or {}
