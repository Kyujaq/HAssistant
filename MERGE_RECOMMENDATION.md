# Merge Recommendation for `work` → `main`

## Branch Inventory
- Local branches: `work` is the only active branch in the repository, so there are no parallel integration lines to reconcile before promotion. (See `git branch -a`).

## Merge History Snapshot
- Recent history shows feature work (memory bridge, GLaDOS orchestrator, Windows voice clarity, etc.) landing via fast-forward merges into `work`, leaving it functionally ahead of `main` while remaining linear. (See `git log --oneline` output).

## Deployment Health
- The consolidated README documents how Assist, Ollama chat/vision, Wyoming speech services, Letta memory, Qwen agent, and optional computer control integrate through Docker Compose, making `work` the canonical reference for Home Assistant deployments.
- `docker-compose.yml` aligns with the README by pinning GPU 0 for both `ollama-chat` and `ollama-vision`, GPU 1 for Whisper/Piper/Frigate, and wiring the Letta Bridge, Qwen Agent, and Orchestrator services together.

## Test Status
- `pytest` currently fails during collection because optional desktop automation dependencies (`pyautogui`, `pytesseract`, `pillow`, `opencv-python`, `numpy`) are not installed in this environment. Installing those extras would be required for a clean green CI run but does not reflect regressions introduced by `work`.

## Recommendation
Given the linear history, updated documentation, consistent service definitions, and absence of unresolved merge conflicts or regressions, promote `work` to `main`. Capture in release notes that optional computer-control tests need desktop automation dependencies to execute.
