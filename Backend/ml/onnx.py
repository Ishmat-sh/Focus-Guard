"""Optional ONNX export and benchmark helpers for trained sklearn models."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import joblib
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType


def export_model(
    model_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    model_path = Path(model_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = joblib.load(model_path)
    vectorizer = model.named_steps["vectorizer"]
    feature_count = len(vectorizer.get_feature_names_out())
    onnx_model = convert_sklearn(
        model,
        initial_types=[("features", FloatTensorType([None, feature_count]))],
        options={id(model.named_steps["classifier"]): {"zipmap": False}},
    )
    output_path.write_bytes(onnx_model.SerializeToString())
    return {
        "model_path": str(model_path.resolve()),
        "onnx_path": str(output_path.resolve()),
        "feature_count": feature_count,
    }


def benchmark_model(
    model_path: str | Path,
    onnx_path: str | Path,
    features: list[dict[str, float]],
    repeats: int = 100,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be at least one")
    if not features:
        raise ValueError("at least one feature vector is required")

    import numpy as np
    import onnxruntime as ort

    sklearn_model = joblib.load(model_path)
    vectorized = sklearn_model.named_steps["vectorizer"].transform(features)

    started = time.perf_counter()
    for _ in range(repeats):
        sklearn_model.predict(vectorized)
    sklearn_ms = (time.perf_counter() - started) * 1000.0 / repeats

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    array = np.asarray(vectorized, dtype=np.float32)
    started = time.perf_counter()
    for _ in range(repeats):
        session.run(None, {input_name: array})
    onnx_ms = (time.perf_counter() - started) * 1000.0 / repeats

    result = {
        "sklearn_ms_per_batch": sklearn_ms,
        "onnx_ms_per_batch": onnx_ms,
        "faster": "onnx" if onnx_ms < sklearn_ms else "sklearn",
        "repeats": repeats,
    }
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Export a Focus Guard model to ONNX")
    parser.add_argument("model_path")
    parser.add_argument("onnx_path")
    parser.add_argument("--report", default="models/onnx_benchmark.json")
    arguments = parser.parse_args()
    result = export_model(arguments.model_path, arguments.onnx_path)
    Path(arguments.report).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
