# Online-Mind2Web Evaluator

Migrated from `_dev/external/evaluation_framework/evaluators/online_mind2web/`.

This evaluator is now fully self-contained within WebAxon's evaluation module.
No dependency on the external evaluation framework.

## Changes from Original

- Flattened `src/` nesting — code lives directly under `evaluator/`.
- Replaced `AIGatewayEngine` / `OpenaiEngine` with generic `EvalLLMEngine` protocol.
- `InferencerEngine` adapter wraps `InferencerBase` from AgentFoundation.
- Replaced `multiprocessing.Process` + `Manager()` with `parallel_process_by_pool` + `ThreadPool` (threading, not multiprocessing — appropriate for I/O-bound LLM API calls).
- `parallel_eval()` and `auto_eval()` accept `engine_factory` callable instead of `args` for model creation.
- All imports use relative paths (no bare imports).
- Dependencies reduced to `pillow` and `beautifulsoup4` only.

## Usage

Invoked from `webaxon.evaluation.scoring.run_eval()` — not run directly.

```python
from webaxon.evaluation.evaluator import parallel_eval, InferencerEngine

engine_factory = lambda: InferencerEngine(OpenaiApiInferencer(model_id="gpt-4o"))
parallel_eval(
    trajectories_dir="runs/sanitized",
    engine_factory=engine_factory,
    mode="WebJudge_Online_Mind2Web_eval",
    num_worker=4,
)
```
