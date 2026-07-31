import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from parsers import (
    parse_bioasq,
    parse_biohopr,
    parse_bioread,
    parse_covid_qa,
    parse_medhop,
    parse_medreqal,
    parse_pubmedqa,
    parse_config,
)


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_json_parsers_emit_common_shape(tmp_path):
    cases = [
        ("bioasq", {"questions": [{"id": "b1", "body": "Q", "ideal_answer": ["A"], "type": "factoid", "documents": [], "snippets": [], "concepts": []}]}, parse_bioasq),
        ("biohopr", [{"id": "h1", "prompt": "Q", "answer": ["A"]}], parse_biohopr),
        ("covid", {"data": [{"paragraphs": [{"context": "C", "document_id": "d", "qas": [{"id": 1, "question": "Q", "answers": [{"text": "A", "answer_start": 0}], "is_impossible": False}]}]}]}, parse_covid_qa),
        ("medhop", [{"id": "m1", "query": "Q", "supports": ["C"], "candidates": ["A"], "answer": "A"}], parse_medhop),
        ("pubmedqa", {"p1": {"QUESTION": "Q", "CONTEXTS": ["C"], "LONG_ANSWER": "A", "final_decision": "yes"}}, parse_pubmedqa),
    ]
    for name, data, parser in cases:
        source = tmp_path / f"{name}.json"
        source.write_text(json.dumps(data), encoding="utf-8")
        output = tmp_path / f"{name}.jsonl"
        parser([source], output, name, "test")
        record = read_jsonl(output)[0]
        assert {"id", "dataset", "split", "task_type", "input", "target", "evidence", "metadata", "annotations", "source_record"} <= record.keys()


def test_medreqal_parser_preserves_verdict_and_label(tmp_path):
    source = tmp_path / "medreqal.csv"
    source.write_text("question,background,objective,conclusion,verdicts,strength,label,category\nQ,B,O,C,SUPPORTED,LOW,1,cat\n", encoding="utf-8")
    output = tmp_path / "medreqal.jsonl"
    parse_medreqal([source], output, "MedREQAL", "all")
    record = read_jsonl(output)[0]
    assert record["target"]["decision"] == "SUPPORTED"
    assert record["annotations"]["label"] == "1"


def test_bioread_parser_streams_mask_and_aliases(tmp_path):
    source = tmp_path / "train_part_0.txt"
    source.write_text("context\n------------------------------\nmasked XXXXXX\n------------------------------\n@entity1:entity name\nnext context\n------------------------------\nnext mask XXXXXX\n------------------------------\n@entity2:other\n", encoding="utf-8")
    output = tmp_path / "bioread.jsonl"
    parse_bioread([source], output, "BioRead", "train")
    records = read_jsonl(output)
    assert len(records) == 2
    assert records[0]["input"]["masked_text"] == "masked XXXXXX"
    assert records[0]["annotations"]["aliases"] == {"@entity1": "entity name"}
    assert records[0]["target"]["answer_text"] is None


def test_parser_job_skips_existing_output(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps([{"id": "1", "query": "Q", "supports": [], "candidates": ["A"], "answer": "A"}]), encoding="utf-8")
    output = tmp_path / "output.jsonl"
    output.write_text("sentinel\n", encoding="utf-8")
    parse_config("MedHop", {"parsing": {"parser": "medhop", "jobs": [{"input": "source.json", "output": "output.jsonl"}]}}, tmp_path)
    assert output.read_text(encoding="utf-8") == "sentinel\n"
