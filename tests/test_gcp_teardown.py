from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import cloudlayer.gcp as gcp


def _adapter(monkeypatch, *, state: str, blobs: list[object]):
    cfg = SimpleNamespace(
        project_id="project",
        region="region",
        blob_uri="unused",
        tags=lambda lab: {
            "course": "itcs355",
            "student": "project",
            "lab": str(lab),
        },
    )
    adapter = gcp.GcpAdapter(cfg)
    monkeypatch.setattr(adapter, "_teardown_lab3", Mock(return_value=[]))
    monkeypatch.setattr(adapter, "_gcloud_json", Mock(return_value={}))

    list_response = Mock()
    list_response.json.return_value = {
        "pipelineJobs": [{"name": "pipeline/1", "state": state}]
    }
    list_response.raise_for_status.return_value = None
    session = Mock()
    session.get.return_value = list_response
    session.delete.return_value = Mock(status_code=200)
    session.post.return_value = Mock(status_code=200)
    monkeypatch.setattr(adapter, "_vertex_session", Mock(return_value=session))

    client = Mock()
    client.list_blobs.return_value = blobs
    monkeypatch.setattr(gcp.storage, "Client", Mock(return_value=client))
    monkeypatch.setattr(gcp, "_parse_gs_uri", Mock(return_value=("bucket", "base")))
    return adapter, cfg, session, client


def test_lab5_teardown_deletes_terminal_pipeline_and_prefix(monkeypatch):
    blob = object()
    adapter, cfg, session, client = _adapter(
        monkeypatch,
        state="PIPELINE_STATE_SUCCEEDED",
        blobs=[blob],
    )

    removed = adapter._teardown_lab5(cfg.tags(5))

    session.delete.assert_called_once()
    session.post.assert_not_called()
    assert adapter._gcloud_json.call_count == 2
    client.bucket.return_value.delete_blobs.assert_called_once_with([blob])
    assert removed[0].endswith("/jobs/itcs355-lab5-retrain-weekly")
    assert "pipeline/1" in removed
    assert removed[-1].endswith("/base/lab5/")


def test_lab5_teardown_cancels_nonterminal_pipeline(monkeypatch):
    adapter, cfg, session, _ = _adapter(
        monkeypatch,
        state="PIPELINE_STATE_RUNNING",
        blobs=[],
    )

    removed = adapter._teardown_lab5(cfg.tags(5))

    session.post.assert_called_once()
    session.delete.assert_not_called()
    assert adapter._gcloud_json.call_count == 2
    assert removed[0].endswith("/jobs/itcs355-lab5-retrain-weekly")
    assert removed[-1] == "pipeline/1"
