"""Configuration loading and dataset acquisition."""

from __future__ import annotations

import logging
import tarfile
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any

import yaml

from utils.download import download_file

logger = logging.getLogger(__name__)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuration must be a mapping: {path}")
    return data


def _sources(dataset_config: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    acquisition = dataset_config.get("acquisition", {})
    if not isinstance(acquisition, dict):
        raise ValueError(f"acquisition must be a mapping: {path}")
    sources = acquisition.get("sources")
    if sources is None and acquisition.get("source") is not None:
        sources = [acquisition["source"]]
    if not isinstance(sources, list):
        raise ValueError(f"acquisition.sources must be a list: {path}")
    result = []
    for source in sources:
        if not isinstance(source, dict) or not source.get("url") or not source.get("target"):
            raise ValueError(f"Each source needs url and target: {path}")
        result.append(source)
    return result


def _safe_extract_path(destination: Path, member_name: str) -> Path:
    destination = destination.resolve()
    target = (destination / member_name).resolve()
    if target != destination and destination not in target.parents:
        raise ValueError(f"Archive member escapes destination: {member_name}")
    return target


def _extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            _safe_extract_path(destination, member.filename)
        handle.extractall(destination)


def _extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, mode="r:gz") as handle:
        members = handle.getmembers()
        for member in members:
            _safe_extract_path(destination, member.name)
        handle.extractall(destination, filter="data")


def _download(url: str, target: Path) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() in {"drive.google.com", "docs.google.com"}:
        try:
            import gdown
        except ImportError as exc:
            raise RuntimeError("Google Drive support requires the gdown package") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        try:
            if not gdown.download(url, str(temporary), quiet=True):
                raise RuntimeError(f"Google Drive download failed: {url}")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        download_file(url, target)


def acquire(config_path: Path) -> None:
    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = load_yaml(config_path)
    datasets = config.get("datasets", {})
    if not isinstance(datasets, dict):
        raise ValueError("datasets must be a mapping")

    failures = 0
    for dataset_name, dataset_path in datasets.items():
        dataset_config_path = (root / str(dataset_path)).resolve()
        dataset_config = load_yaml(dataset_config_path)
        logger.info("Processing %s", dataset_name)
        try:
            for source in _sources(dataset_config, dataset_config_path):
                target = (root / str(source["target"])).resolve()
                if target.exists():
                    logger.info("Skipping cached file: %s", target)
                else:
                    logger.info("Downloading %s to %s", source["url"], target)
                    _download(str(source["url"]), target)

                format_name = str(source.get("format", "")).lower()
                if format_name in {"zip", "tar.gz"}:
                    destination = target.parent
                    marker = destination / (target.name + ".extracted")
                    if marker.exists():
                        logger.info("Skipping cached extraction: %s", destination)
                    else:
                        logger.info("Extracting %s", target)
                        if format_name == "zip":
                            _extract_zip(target, destination)
                        else:
                            _extract_tar(target, destination)
                        marker.touch()
        except Exception:
            failures += 1
            logger.exception("Failed to process %s", dataset_name)
    if failures:
        raise RuntimeError(f"{failures} dataset(s) failed")
