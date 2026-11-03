from pathlib import Path

import pytest

from scripts import media_distribution


def test_media_gate_receives_the_same_absolute_artifact_path(tmp_path, monkeypatch):
    root = tmp_path / "source"
    checker = root / "frontend" / "scripts" / "check-media-distribution.mjs"
    checker.parent.mkdir(parents=True)
    checker.write_text("// isolated test checker", encoding="utf-8")
    artifact = tmp_path / "build output" / "dist" / "PTTI-R4"
    artifact.mkdir(parents=True)
    captured = {}

    monkeypatch.setattr(media_distribution.shutil, "which", lambda name: "node-test")
    monkeypatch.setattr(
        media_distribution.subprocess,
        "run",
        lambda command, **kwargs: captured.update(command=command, kwargs=kwargs),
    )

    media_distribution.verify_media_distribution(root, artifact, package=True)

    assert captured["command"][0] == "node-test"
    assert captured["command"][1] == str(checker.resolve())
    assert captured["command"][2] == str(artifact.resolve())
    assert captured["command"][-2:] == ["--windows", "--package"]
    assert captured["kwargs"]["cwd"] == root / "frontend"
    assert captured["kwargs"]["check"] is True


def test_media_gate_rejects_missing_artifact_with_exact_absolute_path(tmp_path, monkeypatch):
    root = tmp_path / "source"
    checker = root / "frontend" / "scripts" / "check-media-distribution.mjs"
    checker.parent.mkdir(parents=True)
    checker.write_text("// isolated test checker", encoding="utf-8")
    missing = tmp_path / "not-built" / "dist" / "PTTI-R4"

    monkeypatch.setattr(media_distribution.shutil, "which", lambda name: "node-test")
    monkeypatch.setattr(
        media_distribution.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("the gate must not run for a missing artifact"),
    )

    with pytest.raises(RuntimeError, match="Media distribution artifact path is not a directory") as error:
        media_distribution.verify_media_distribution(root, missing, package=True)

    assert str(missing.resolve()) in str(error.value)

