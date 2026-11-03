from scripts.resource_measurement import cpu_percent_from_cpu_times, summarize_samples


def test_resource_summary_reports_median_and_peak_without_hiding_samples():
    result = summarize_samples(
        [
            {"available_ram_bytes": 3, "process_tree_rss_bytes": 8},
            {"available_ram_bytes": 2, "process_tree_rss_bytes": 10},
            {"available_ram_bytes": 1, "process_tree_rss_bytes": 12},
        ]
    )

    assert result["sample_count"] == 3
    assert result["available_ram_bytes"] == {"median": 2, "min": 1, "peak": 3}
    assert result["process_tree_rss_bytes"] == {"median": 10, "min": 8, "peak": 12}


def test_resource_summary_ignores_unmeasured_values_but_reports_them_as_null():
    result = summarize_samples(
        [
            {"gpu_free_bytes": None, "process_tree_uss_bytes": 4},
            {"gpu_free_bytes": None, "process_tree_uss_bytes": None},
        ]
    )

    assert result["gpu_free_bytes"] is None
    assert result["process_tree_uss_bytes"] == {"median": 4, "min": 4, "peak": 4}


def test_resource_summary_marks_empty_capture_explicitly():
    assert summarize_samples([]) == {"sample_count": 0, "metrics": {}}


def test_cpu_usage_uses_cumulative_delta_and_marks_first_sample_unmeasured():
    assert cpu_percent_from_cpu_times(None, 1.0, 2.0) is None
    assert cpu_percent_from_cpu_times(10.0, 10.5, 2.0) == 25.0
    assert cpu_percent_from_cpu_times(10.5, 10.5, 2.0) == 0.0
    assert cpu_percent_from_cpu_times(10.5, 10.0, 2.0) == 0.0
