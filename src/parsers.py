"""Dataset-specific converters to the project's normalized JSONL schema."""

from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)
SEPARATOR = "------------------------------"
BIOREAD_ALIAS = re.compile(r"^(@entity\d+):(.*)$")


def _write_records(output: Path, records: Iterable[dict[str, Any]]) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    count = 0
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")
                count += 1
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    logger.info("Wrote %d normalized records to %s", count, output)
    return count


def _base(dataset: str, split: str | None, record_id: str, task_type: str) -> dict[str, Any]:
    return {
        "id": record_id,
        "dataset": dataset,
        "split": split,
        "task_type": task_type,
        "input": {
            "question": None,
            "context": None,
            "passages": [],
            "candidates": [],
            "masked_text": None,
            "system_instruction": None,
        },
        "target": {
            "answer_text": None,
            "answers": [],
            "decision": None,
            "answer_type": None,
        },
        "evidence": {"source_ids": [], "snippets": [], "answer_spans": []},
        "metadata": {
            "source_id": None,
            "year": None,
            "category": None,
            "concepts": [],
            "meshes": [],
            "relation_chain": [],
            "evidence_strength": None,
        },
        "annotations": {
            "question_type": None,
            "reasoning_required": None,
            "is_impossible": None,
            "aliases": {},
            "label": None,
        },
        "source_record": None,
    }


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_bioasq(inputs: list[Path], output: Path, dataset: str, split: str | None) -> int:
    data = _read_json(inputs[0])
    questions = data.get("questions", [])

    def records() -> Iterable[dict[str, Any]]:
        for question in questions:
            answers = question.get("ideal_answer") or []
            record = _base(dataset, split, str(question["id"]), "generative_qa")
            record["input"].update({
                "question": question.get("body"),
                "passages": [snippet.get("text", "") for snippet in question.get("snippets", [])],
            })
            record["target"].update({
                "answer_text": answers[0] if answers else None,
                "answers": answers,
                "answer_type": question.get("type"),
            })
            record["evidence"].update({
                "source_ids": question.get("documents", []),
                "snippets": question.get("snippets", []),
            })
            record["metadata"]["concepts"] = question.get("concepts", [])
            record["annotations"]["question_type"] = question.get("type")
            record["source_record"] = question
            yield record

    return _write_records(output, records())


def parse_biohopr(inputs: list[Path], output: Path, dataset: str, split: str | None) -> int:
    data = _read_json(inputs[0])

    def records() -> Iterable[dict[str, Any]]:
        for index, item in enumerate(data):
            answers = item.get("answer") or []
            record = _base(dataset, split, str(item.get("id", index)), "list_qa")
            record["input"].update({
                "question": item.get("prompt") or item.get("hop2_question"),
                "system_instruction": item.get("system"),
            })
            record["target"].update({
                "answer_text": answers[0] if answers else None,
                "answers": answers,
                "answer_type": "list",
            })
            record["metadata"]["relation_chain"] = [
                {"relation": item.get("relation_hop1"), "entity": item.get("hop1"), "type": item.get("hop1_type")},
                {"relation": item.get("relation_hop2"), "entity": item.get("hop2"), "type": item.get("hop2_type")},
            ]
            record["metadata"]["category"] = item.get("target_type")
            record["source_record"] = item
            yield record

    return _write_records(output, records())


def parse_covid_qa(inputs: list[Path], output: Path, dataset: str, split: str | None) -> int:
    data = _read_json(inputs[0])

    def records() -> Iterable[dict[str, Any]]:
        for article in data.get("data", []):
            for paragraph in article.get("paragraphs", []):
                for qa in paragraph.get("qas", []):
                    answers = qa.get("answers") or []
                    record = _base(dataset, split, str(qa.get("id")), "extractive_qa")
                    record["input"].update({
                        "question": qa.get("question"),
                        "context": paragraph.get("context"),
                        "passages": [paragraph.get("context", "")],
                    })
                    record["target"].update({
                        "answer_text": answers[0].get("text") if answers else None,
                        "answers": [answer.get("text") for answer in answers],
                        "answer_type": "span",
                    })
                    record["evidence"]["answer_spans"] = [
                        {"text": answer.get("text"), "start": answer.get("answer_start"),
                         "end": (answer.get("answer_start") + len(answer.get("text", "")))
                         if answer.get("answer_start") is not None else None}
                        for answer in answers
                    ]
                    record["metadata"]["source_id"] = paragraph.get("document_id")
                    record["annotations"]["is_impossible"] = qa.get("is_impossible")
                    record["source_record"] = {"paragraph": paragraph, "qa": qa}
                    yield record

    return _write_records(output, records())


def parse_medhop(inputs: list[Path], output: Path, dataset: str, split: str | None) -> int:
    data = _read_json(inputs[0])

    def records() -> Iterable[dict[str, Any]]:
        for index, item in enumerate(data):
            answer = item.get("answer")
            record = _base(dataset, split, str(item.get("id", index)), "multi_hop_choice")
            record["input"].update({
                "question": item.get("query"),
                "passages": item.get("supports", []),
                "candidates": item.get("candidates", []),
            })
            record["target"].update({
                "answer_text": answer,
                "answers": [answer] if answer is not None else [],
                "answer_type": "candidate",
            })
            record["source_record"] = item
            yield record

    return _write_records(output, records())


def parse_medreqal(inputs: list[Path], output: Path, dataset: str, split: str | None) -> int:
    def records() -> Iterable[dict[str, Any]]:
        with inputs[0].open("r", encoding="utf-8-sig", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle)):
                record_id = row.get("") or str(index)
                record = _base(dataset, split, record_id, "evidence_verdict")
                record["input"].update({
                    "question": row.get("question"),
                    "context": row.get("conclusion"),
                    "passages": [row.get("background", ""), row.get("objective", ""), row.get("conclusion", "")],
                })
                record["target"].update({
                    "answer_text": row.get("verdicts"),
                    "answers": [row.get("verdicts")] if row.get("verdicts") else [],
                    "decision": row.get("verdicts"),
                    "answer_type": "verdict",
                })
                record["metadata"].update({
                    "category": row.get("category"),
                    "evidence_strength": row.get("strength"),
                })
                record["annotations"]["label"] = row.get("label")
                record["source_record"] = row
                yield record

    return _write_records(output, records())


def parse_pubmedqa(inputs: list[Path], output: Path, dataset: str, split: str | None) -> int:
    data = _read_json(inputs[0])

    def records() -> Iterable[dict[str, Any]]:
        for publication_id, item in data.items():
            answer = item.get("LONG_ANSWER")
            decision = item.get("final_decision")
            record = _base(dataset, split, str(publication_id), "yes_no_qa")
            record["input"].update({
                "question": item.get("QUESTION"),
                "passages": item.get("CONTEXTS", []),
            })
            record["target"].update({
                "answer_text": answer,
                "answers": [answer] if answer else [],
                "decision": decision,
                "answer_type": "boolean" if decision is not None else "text",
            })
            record["metadata"].update({"source_id": str(publication_id), "year": item.get("YEAR"), "meshes": item.get("MESHES", [])})
            record["annotations"].update({
                "question_type": "yes_no",
                "reasoning_required": item.get("reasoning_required_pred"),
            })
            record["source_record"] = item
            yield record

    return _write_records(output, records())


def _parse_bioread_record(parts: list[list[str]], dataset: str, split: str, index: int) -> dict[str, Any] | None:
    if len(parts) < 3:
        return None
    context = "\n".join(parts[0]).strip()
    masked_text = "\n".join(parts[1]).strip()
    aliases: dict[str, str] = {}
    for line in parts[2]:
        match = BIOREAD_ALIAS.match(line.strip())
        if match:
            aliases[match.group(1)] = match.group(2)
    record = _base(dataset, split, f"{split}-{index}", "entity_completion")
    record["input"].update({"context": context, "passages": [context], "masked_text": masked_text})
    record["target"]["answer_type"] = "entity"
    record["annotations"]["aliases"] = aliases
    record["source_record"] = {"context": context, "masked_text": masked_text, "aliases": aliases}
    return record


def parse_bioread(inputs: list[Path], output: Path, dataset: str, split: str | None) -> int:
    split_name = split or "all"

    def records() -> Iterable[dict[str, Any]]:
        index = 0
        parts: list[list[str]] = [[]]
        for path in inputs:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for raw_line in handle:
                    line = raw_line.rstrip("\r\n")
                    if line.strip() == SEPARATOR:
                        parts.append([])
                        continue
                    if len(parts) == 3 and parts[2] and not BIOREAD_ALIAS.match(line.strip()):
                        record = _parse_bioread_record(parts, dataset, split_name, index)
                        if record:
                            yield record
                            index += 1
                        parts = [[line]]
                    else:
                        parts[-1].append(line)
        record = _parse_bioread_record(parts, dataset, split_name, index)
        if record:
            yield record

    return _write_records(output, records())


PARSERS: dict[str, Callable[[list[Path], Path, str, str | None], int]] = {
    "bioasq": parse_bioasq,
    "biohopr": parse_biohopr,
    "bioread": parse_bioread,
    "covid_qa": parse_covid_qa,
    "medhop": parse_medhop,
    "medreqal": parse_medreqal,
    "pubmedqa": parse_pubmedqa,
}


def _resolve_inputs(root: Path, value: Any) -> list[Path]:
    values = value if isinstance(value, list) else [value]
    paths: list[Path] = []
    for item in values:
        pattern = root / str(item)
        if any(character in str(pattern) for character in "*?["):
            paths.extend(sorted(pattern.parent.glob(pattern.name)))
        elif pattern.exists():
            paths.append(pattern)
    if not paths:
        raise FileNotFoundError(f"No parser input files found for {value}")
    return paths


def parse_config(dataset_name: str, dataset_config: dict[str, Any], root: Path) -> None:
    parsing = dataset_config.get("parsing")
    if not isinstance(parsing, dict):
        raise ValueError(f"Missing parsing configuration for {dataset_name}")
    parser_name = str(parsing.get("parser", "")).lower()
    parser = PARSERS.get(parser_name)
    if parser is None:
        raise ValueError(f"Unknown parser {parser_name!r} for {dataset_name}")
    jobs = parsing.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError(f"parsing.jobs must be a non-empty list for {dataset_name}")
    for job in jobs:
        if not isinstance(job, dict) or not job.get("input") or not job.get("output"):
            raise ValueError(f"Each parsing job needs input and output for {dataset_name}")
        output = root / str(job["output"])
        if output.exists():
            logger.info("Skipping cached parsed output: %s", output)
            continue
        inputs = _resolve_inputs(root, job["input"])
        parser(inputs, output, dataset_name, job.get("split"))


def parse_all(config_path: Path) -> None:
    config_path = config_path.resolve()
    root = config_path.parent.parent
    with config_path.open("r", encoding="utf-8") as handle:
        import yaml
        config = yaml.safe_load(handle) or {}
    for dataset_name, dataset_path in config.get("datasets", {}).items():
        dataset_config_path = (root / str(dataset_path)).resolve()
        with dataset_config_path.open("r", encoding="utf-8") as handle:
            import yaml
            dataset_config = yaml.safe_load(handle) or {}
        logger.info("Parsing %s", dataset_name)
        parse_config(str(dataset_name), dataset_config, root)
