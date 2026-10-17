from youseela.benchmark import benchmark


def test_benchmark_consumes_validated_outputs_and_labels_synthetic_work() -> None:
    result=benchmark([3,6],runs=2)
    assert result["data_kind"] == "synthetic_performance_fixture"
    assert [row["areas"] for row in result["measurements"]] == [3,6]
    assert all(row["output_bytes"] > 0 and row["score_median_seconds"] > 0 for row in result["measurements"])
    assert result["image_api"]["status"] == "unmeasured"
