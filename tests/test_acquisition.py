import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from acquisition import _extract_tar, _extract_zip, load_yaml


def test_load_yaml_and_sources_config():
    config = load_yaml(Path(__file__).parents[1] / "configs" / "PubMedQA.yaml")
    assert len(config["acquisition"]["sources"]) == 3


def test_extract_zip(tmp_path):
    archive = tmp_path / "data.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("nested/value.txt", "zip data")
    _extract_zip(archive, tmp_path / "output")
    assert (tmp_path / "output" / "nested" / "value.txt").read_text() == "zip data"


def test_extract_tar_gz(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("tar data")
    archive = tmp_path / "data.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(source, arcname="source.txt")
    _extract_tar(archive, tmp_path / "output")
    assert (tmp_path / "output" / "source.txt").read_text() == "tar data"


def test_reject_archive_path_traversal(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../outside.txt", "unsafe")
    with pytest.raises(ValueError):
        _extract_zip(archive, tmp_path / "output")
