import json
import logging

from logging_config import JsonFormatter, run_id_var


def test_json_log_line_contains_run_id_and_fields():
    record = logging.LogRecord("confirmai.test", logging.INFO, __file__, 1, "Tolerance evaluated", (), None)
    record.run_id = "abc123"
    record.fields = {"status": "NEGATIVE", "difference": 130.0}

    line = json.loads(JsonFormatter().format(record))

    assert line["msg"] == "Tolerance evaluated"
    assert line["run_id"] == "abc123"
    assert line["status"] == "NEGATIVE"
    assert line["difference"] == 130.0
    assert "ts" in line and line["level"] == "INFO"


def test_run_id_defaults_to_dash():
    assert run_id_var.get() == "-"
