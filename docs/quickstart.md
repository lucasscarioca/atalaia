# Quickstart

1. Install dependencies:

   ```bash
   uv sync --dev
   ```

2. Initialize the sample suite:

   ```bash
   uv run oak-eval init
   ```

3. Run it locally:

   ```bash
   uv run oak-eval run --suite evals.sample:suite
   ```

4. Try a remote run when your API is available:

   ```bash
   uv run oak-eval run --suite evals.sample:suite --remote --wait
   ```

5. Compare against a reference run:

   ```bash
   uv run oak-eval check --run-id <run-id> --against <reference-run-id>
   ```

## Next step

Edit `evals/sample.py` or add a new module under `evals/`.
