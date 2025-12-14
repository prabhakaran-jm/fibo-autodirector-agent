# FIBO AutoDirector Agent

FIBO AutoDirector Agent turns structured inputs (CSV, storyboards, specs)
into deterministic, controllable visual outputs using Bria FIBO’s
JSON-native generation.

Instead of prompt engineering, every image is generated from explicit,
reproducible parameters: camera, lens, lighting, color, and composition.

## Why this exists
Creative teams need scale and consistency.
Text prompts drift.
AutoDirector makes visual generation predictable and repeatable.

## What it does
- Ingests structured inputs (CSV or JSON)
- Expands them into FIBO-compliant JSON
- Generates images with strict parameter control
- Caches outputs by JSON hash for reproducibility
- Allows selective re-rendering with parameter diffs

## Built with
- Bria FIBO (JSON-native generation)
- Agent-based planning layer
- FastAPI backend
- Web UI for review and comparison

## References
- FIBO API Docs: https://docs.bria.ai/
- FIBO Platform Console: https://platform.bria.ai/
- FIBO Overview: https://bria.ai/fibo

## Status
Early scaffold – core ingestion and planning in progress.