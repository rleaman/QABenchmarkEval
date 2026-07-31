# Dataset schema analysis and proposed unified schema

This document records a best-effort interpretation of the cached data in
`datasets/`. It describes the physical formats, the apparent task, and the
role of each field. “Required” means required for the task represented by the
dataset, not necessarily required for every future model interface.

The analysis is based on the cached files available on 2026-07-30. The raw
datasets should remain authoritative: several fields have dataset-specific
semantics and some labels are only interpretable with the original dataset
documentation.

## Role vocabulary

- **Input**: information a system may receive when answering the question.
- **Output**: the expected answer or target label.
- **Required**: needed to define or solve the benchmark example.
- **Optional**: useful evidence, candidates, metadata, or evaluation material,
  but not universally necessary to run the task.
- **Annotation**: reference information used for scoring, analysis, or
  interpretation rather than necessarily supplied to the model.

## Dataset inventory

| Dataset | Physical format | Apparent task |
|---|---|---|
| BioASQ | JSON object containing `questions` | Biomedical factoid, list, yes/no, and summary QA with document evidence |
| BioHopR | JSON array | One-hop/two-hop biomedical knowledge-graph question answering |
| BioRead | Sharded plain text | Masked biomedical entity/text completion with entity aliases |
| COVID-QA | SQuAD-like JSON | Extractive reading comprehension over biomedical paragraphs |
| MedHop | QAngaroo JSON arrays | Multi-hop relation reasoning with candidates; includes MedHop and WikiHop |
| MedREQAL | CSV | Evidence-based medical review verdict classification |
| PubMedQA | Three JSON mappings keyed by publication ID | Abstract understanding: answer generation/classification and reasoning labels |

## Per-dataset interpretation

### BioASQ

Observed root shape: `{ "questions": [...] }`; the cached training file has
5,729 questions, with types `factoid`, `list`, `yesno`, and `summary`.

| Field | Type | Interpretation | Role |
|---|---|---|---|
| `body` | string | Natural-language biomedical question | Input; required |
| `documents` | list[string] | PubMed/document URLs judged relevant | Input evidence or retrieval targets; optional for an answer-only setting, important for evidence-aware evaluation |
| `snippets` | list[object] | Evidence excerpts with document URL, section, offsets, and text | Input evidence when supplied; optional if the task is closed-book |
| `ideal_answer` | list[string] | Reference free-text answer(s) | Output annotation; required for summary-style scoring, absent or less central for other question types |
| `concepts` | list[string] | Disease Ontology/MeSH concept URLs | Annotation; optional |
| `type` | string | Answer regime: factoid, list, yes/no, or summary | Task metadata; required to interpret the expected output |
| `id` | string | Example identifier | Metadata; optional for solving, required for traceability |

Best attempt: `body` is the input question. `type` controls output shape:
yes/no is a boolean-like answer, list is a set/list of entities, factoid is a
short entity or phrase, and summary is free text. `documents` and `snippets`
are retrieval/evidence annotations that can also be exposed as model context.
The reference answer is `ideal_answer`; BioASQ’s original evaluation may use
additional answer fields for some task releases, so normalization should not
discard the original record.

Source: `datasets/BioASQ/BioASQ-training14b/training14b.json`.

### BioHopR

Observed root shape: a JSON array of 7,633 records. Records contain an
intermediate entity (`hop1`), a second entity (`hop2`), relation labels, a
target type, generated prompts, and an `answer` list.

| Field | Type | Interpretation | Role |
|---|---|---|---|
| `prompt` | string | Fully rendered instruction/question, including an answer delimiter | Input; required for the generated-prompt task |
| `system` | string | Model/system instruction | Input metadata; optional if benchmark harness supplies its own instruction |
| `hop1`, `hop1_type` | string | First-hop entity and semantic type | Structured input/trace; optional when using `prompt`, useful for graph analysis |
| `hop2`, `hop2_type` | string | Second-hop entity and semantic type | Structured input/trace; optional when using `prompt` |
| `relation_hop1`, `relation_hop2` | string | Relations traversed in the graph | Structured input/trace; optional when using `prompt`, useful for task characterization |
| `target_type` | string | Type of the answer entity | Output constraint/metadata; optional to a free-form solver, useful for evaluation |
| `hop1_question`, `hop2_question` | string | Singular one-hop and two-hop question renderings | Alternative inputs; optional |
| `hop1_question_multi`, `hop2_question_multi` | string | Multi-answer renderings | Alternative inputs; optional |
| `answer` | list[string] | One or more valid target entities | Output annotation; required |

Best attempt: the primary task is to name a target biomedical entity from a
relation chain. The prompt or one of the question renderings is the input;
`answer` is the expected output and is inherently multi-valued. The hop and
relation fields should be preserved because they explain how the answer was
constructed, even if they are not exposed to the model.

Source: `datasets/BioHopR/BioHopR.json`.

### BioRead

Observed format: very large UTF-8 text shards. Each example is a sequence of
segments separated by `------------------------------`:

1. a biomedical context/article passage, with entity mentions replaced by
   tokens such as `@entity11`;
2. a target sentence containing `XXXXXX`, the masked text/entity;
3. a list of aliases in the form `@entity-id:surface name`.

The first segment also contains title-like text and a `====` boundary in many
examples. The cached `bioread` and `bioread_lite` directories contain train,
validation, and test shards.

| Value | Interpretation | Role |
|---|---|---|
| Context passage before the first separator | Biomedical document context with anonymized entity mentions | Input evidence; required when the intended task uses context |
| Target sentence containing `XXXXXX` | Cloze/template sentence with one missing span | Input; required |
| `XXXXXX` | Missing entity, phrase, or text span to reconstruct | Output location; required |
| `@entityN` tokens | Stable anonymized entity identifiers | Input and/or intermediate representation; required to preserve task structure |
| `@entityN:name` lines | Entity-ID-to-surface-form mapping/candidate aliases | Output annotation and decoding vocabulary; required to interpret entity answers, optional for a model that predicts IDs |
| Section/topic/title fragments | Document metadata and retrieval context | Optional input |

Best attempt: this is not ordinary extractive QA. It appears to be masked
entity/text completion, where the system reconstructs the text represented by
`XXXXXX`, with the alias lines providing the reference vocabulary. The
normalizer should preserve the raw segments and should not assume that every
mask has exactly one token or that every answer is a single entity.

Source examples: `datasets/BioRead/bioread_dataset/bioread_lite/*_part_0.txt`.

### COVID-QA

Observed root shape: `{ "data": [...] }`, with SQuAD-like article and
paragraph nesting.

| Field | Type | Interpretation | Role |
|---|---|---|---|
| `data` | list[object] | Article groups | Structural; required for the raw format |
| `paragraphs` | list[object] | Context/question groups | Structural; required |
| `context` | string | Biomedical passage | Input evidence; required |
| `document_id` | string/int-like | Source document identifier | Metadata; optional for solving |
| `qas` | list[object] | Questions associated with a context | Structural; required |
| `question` | string | Natural-language question | Input; required |
| `id` | integer | QA example identifier | Metadata; optional for solving |
| `answers` | list[object] | Reference answer spans | Output annotation; required for supervised evaluation |
| `answers[].text` | string | Answer text extracted from the context | Expected output; required |
| `answers[].answer_start` | integer | Character offset into `context` | Evidence/alignment annotation; optional for answer-only scoring |
| `is_impossible` | boolean | Whether no answer is available | Output/task metadata; required to distinguish answerable examples |

Best attempt: this is extractive reading comprehension. The required model
input is `question` plus `context`; the expected output is one answer span,
or an explicit unanswerable result when `is_impossible` is true. The offset is
not an answer itself, but validates that the answer occurs in the supplied
context.

Source: `datasets/COVID-QA/COVID-QA.json`.

### MedHop

The archive contains two related tasks, each represented as a JSON array of
records with the same core fields:

- `medhop`: biomedical/drug-protein relation questions;
- `wikihop`: broader entity-relation questions.

Both have ordinary and `.masked.json` files. The masked variant replaces
some entity surface forms with placeholders such as `___MASK51___` and is
intended to reduce lexical shortcuts.

| Field | Type | Interpretation | Role |
|---|---|---|---|
| `query` | string | Relation query such as `interacts_with DB00773?` | Input; required |
| `supports` | list[string] | Retrieved passages used to connect multiple reasoning hops | Input evidence; required for the intended multi-hop task |
| `candidates` | list[string] | Candidate answer entities | Input constraint; required for the multiple-choice formulation |
| `answer` | string | Correct candidate/entity | Output annotation; required |
| `id` | string | Example identifier | Metadata; optional for solving |

Best attempt: the task is constrained multi-hop classification. A solver sees
the query, support documents, and candidate list, then returns exactly one
candidate. `answer` should be normalized as a scalar string while retaining
the candidate list and supports. The masked files are a variant of the input,
not separate semantic labels.

Sources: `datasets/MedHop/qangaroo_v1.1/medhop/*.json` and
`datasets/MedHop/qangaroo_v1.1/wikihop/*.json`.

### MedREQAL

Observed format: UTF-8 CSV with 2,786 rows. The first column is unnamed and
acts as a row/index identifier.

| Column | Type | Interpretation | Role |
|---|---|---|---|
| unnamed first column | string/integer-like | Row identifier | Metadata; optional |
| `question` | string | Review question about intervention/evidence | Input; required |
| `background` | string | Clinical and problem background | Input evidence/context; required for the intended task |
| `objective` | string | Review objective and comparison | Input context; required to interpret the question |
| `conclusion` | string | Evidence synthesis/conclusion | Input evidence; required for verdict prediction |
| `verdicts` | categorical string | `SUPPORTED`, `REFUTED`, or `NOT ENOUGH INFORMATION` | Expected output; required |
| `strength` | categorical string | Evidence strength, mostly LOW/MEDIUM/HIGH | Output annotation or auxiliary target; optional unless strength prediction is evaluated |
| `label` | categorical string | Numeric encoding with observed values `0`, `1`, `2` | Encoded output label; required for a classification implementation, but mapping must be explicitly configured |
| `category` | string | Medical topic/category | Metadata or optional stratification input |

Best attempt: the primary task is textual evidence judgment: given the
question and review material, predict the three-way `verdicts` label. The
numeric `label` is likely an encoding of that verdict, but the mapping should
not be guessed globally without verifying it against the source release.
`strength` is a second possible prediction target, not merely an input fact.

Source: `datasets/MedREQAL/MedREQAL.csv`.

### PubMedQA

The three JSON files are mappings from publication/PubMed IDs to records:

- `ori_pqal.json`: labeled records with reasoning-required/free predictions
  and final decisions;
- `ori_pqau.json`: records with question, abstract contexts, section labels,
  and long answer, but no decision fields in the inspected schema;
- `ori_pqaa.json`: records with a `final_decision` field but no reasoning
  prediction fields in the inspected schema.

The common fields are:

| Field | Type | Interpretation | Role |
|---|---|---|---|
| mapping key | string | PubMed/publication identifier | Metadata; useful required key for traceability |
| `QUESTION` | string | Yes/no biomedical research question | Input; required |
| `CONTEXTS` | list[string] | Abstract sections or evidence passages | Input evidence; required for the intended task |
| `LABELS` | list[string] | Section labels aligned to `CONTEXTS`, e.g. BACKGROUND, METHODS, RESULTS | Input structure; optional if contexts are concatenated, useful for evidence-aware models |
| `MESHES` | list[string] | MeSH subject terms | Metadata/optional input |
| `YEAR` | string | Publication year | Metadata/optional input |
| `LONG_ANSWER` | string | Free-text answer/rationale | Expected output annotation; required for long-answer generation evaluation |
| `final_decision` | string | Yes/no decision | Expected output; required for decision classification |
| `reasoning_required_pred` | string | Whether reasoning was judged necessary | Auxiliary annotation/target; optional |
| `reasoning_free_pred` | string | Whether a reasoning-free answer was predicted | Auxiliary annotation/target; optional |

Best attempt: the core task is answer a yes/no biomedical question from
abstract context. The output can be represented as both a normalized
decision and an optional explanatory long answer. `CONTEXTS` and `QUESTION`
are the minimum useful input; section labels, MeSH terms, and year support
analysis or controlled experiments.

Sources: `datasets/PubMedQA/ori_pqal.json`, `ori_pqau.json`, and
`ori_pqaa.json`.

## Proposed unified schema

The following schema separates the common task interface from source-specific
annotations. It is intentionally permissive: not every dataset supplies every
field, and normalization should retain the original record in `source_record`
so information is never lost.

```yaml
id: string
dataset: string
split: string|null
task_type: one_of:
  - extractive_qa
  - generative_qa
  - yes_no_qa
  - list_qa
  - multi_hop_choice
  - entity_completion
  - evidence_verdict

input:
  question: string|null
  context: string|null
  passages: [string]
  candidates: [string]
  masked_text: string|null
  system_instruction: string|null

target:
  answer_text: string|null
  answers: [string]
  decision: string|null
  answer_type: one_of: [text, span, boolean, list, entity, candidate, verdict]

evidence:
  source_ids: [string]
  snippets: [object]
  answer_spans:
    - text: string
      start: integer|null
      end: integer|null

metadata:
  source_id: string|null
  year: string|integer|null
  category: string|null
  concepts: [string]
  meshes: [string]
  relation_chain: [object]
  evidence_strength: string|null

annotations:
  question_type: string|null
  reasoning_required: string|boolean|null
  is_impossible: boolean|null
  aliases: {entity_id: string}
  label: string|integer|null

source_record: object
```

### Mapping rules

1. **Always retain provenance.** `id`, `dataset`, `source_id`, and the full
   `source_record` should be populated whenever available.
2. **Use `input.question` for the user-facing query.** Map BioASQ `body`,
   COVID-QA `question`, PubMedQA `QUESTION`, MedREQAL `question`, MedHop
   `query`, and the rendered BioHopR prompt here. BioRead has no conventional
   question, so `masked_text` is primary and `question` may be null.
3. **Use `input.context`/`passages` for supplied evidence.** Preserve passage
   boundaries where the source provides them; do not flatten BioASQ snippets,
   PubMedQA contexts, or MedHop supports irreversibly.
4. **Represent outputs explicitly.** Use `target.decision` for yes/no or
   verdict labels, `target.answers` for BioASQ lists/BioHopR multi-answer
   outputs, and `target.answer_text` for summaries, explanations, spans, and
   entity completions.
5. **Keep evaluation annotations separate from model inputs.** Offsets,
   source URLs, MeSH/concept identifiers, reasoning flags, evidence strength,
   and numeric label encodings should not silently become model input.
6. **Preserve ambiguity.** In particular, retain both `verdicts` and `label`
   for MedREQAL until their encoding is verified, and retain both BioRead
   entity IDs and surface aliases.

This schema is a proposed interchange format, not a claim that all datasets
share the same task. A future converter should emit one normalized record per
question/example plus a dataset-specific metadata manifest describing which
fields were available and which were used as model inputs.
