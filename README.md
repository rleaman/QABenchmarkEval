# QABenchmarkEval

QABenchmarkEval is a command-line Python project for acquiring biomedical question-answering datasets, converting them into a common representation, characterizing them, and visualizing the results. The current implementation provides the first acquisition stage: it downloads configured source files, caches them under `datasets/`, and expands ZIP or TAR.GZ archives.

## Setup

Create and activate a virtual environment, then install the dependencies:

```text
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Update datasets

From the repository root:

```text
python src/main.py update configs/config.yaml
```

Convenience launchers are also provided:

```text
scripts\run.bat
scripts\run.ps1
./scripts/run.sh
```

Each launcher accepts an optional path to a different top-level configuration file. Existing files and completed extractions are skipped. Downloaded archives are retained beside their extracted contents.

After acquisition, `update` runs each dataset's configured parser. Normalized
records are written as newline-delimited JSON (`.jsonl`), one record per line.
Existing normalized output files are skipped. Parser jobs and their input and
output paths are defined in each dataset configuration under `parsing`:

```yaml
parsing:
  parser: pubmedqa
  jobs:
    - split: labeled
      input: datasets/PubMedQA/ori_pqal.json
      output: datasets/PubMedQA/normalized/ori_pqal.jsonl
```

The normalized record structure is documented in
[`DATASET_SCHEMA.md`](DATASET_SCHEMA.md). Dataset-specific source fields are
retained under `source_record`; large inputs such as BioRead are processed as
streams, and its train/validation/test and lite variants are written to
separate files.

## Run tests

Use the platform-specific test launcher from the repository root:

```text
scripts\test.bat
scripts\test.ps1
./scripts/test.sh
```

## Configuration

The top-level file defines logging and dataset configuration paths:

```yaml
logging:
  level: INFO
datasets:
  BioRead: configs/BioRead.yaml
```

Each dataset uses a list of sources:

```yaml
name: BioRead
acquisition:
  sources:
    - url: https://example.org/data.tar.gz
      target: datasets/BioRead/data.tar.gz
      format: tar.gz
```

`format` is optional. Supported archive formats are `zip` and `tar.gz`; files without a format are cached as downloaded. HTTP(S) sources use the built-in downloader, while Google Drive URLs use `gdown`.

## Cache layout

Targets are resolved relative to the repository root. For an archive, extraction occurs in the target’s parent directory. A small `.extracted` marker records a completed extraction so repeated updates remain inexpensive.

## Current limitations

Semantic question/answer normalization, dataset characterization, and visualization are not implemented yet. A future stage will define the common QA schema and per-dataset field mappings before transforming the cached raw data.
