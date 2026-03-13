# Online-Mind2Web Dataset Artifacts

This folder stores the downloaded and preprocessed dataset artifacts.

Structure:

```
Online-Mind2Web/
  raw/                 # Raw JSONL dump from Hugging Face (per split)
  processed/           # Normalized tasks.jsonl
  metadata/            # Download metadata
```

Preprocess:

```
python -m src.scripts.preprocess --split test
```

Token:
- Set `HF_TOKEN` or pass `--hf_token` at runtime.
