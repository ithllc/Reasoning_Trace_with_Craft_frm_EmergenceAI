# Dashboard voice assistant

The optional voice assistant has two local pieces:

- The browser provides speech-to-text and text-to-speech through the Web Speech API. Audio is not uploaded to this repository. Browser and operating-system speech services may process audio according to their own policies.
- `ui/voice_server.py` answers questions through a configured Nebius OpenAI-compatible inference model. It fetches fresh dashboard JSON for each question and instructs the model to answer only from that data.

On dashboard load, the browser initializes its speech-recognition object, warms the available speech-synthesis voices, and checks the Q&A subprocess. Three indicators independently report Q&A, microphone/STT, and speaker/TTS readiness. Browsers still require the user's button press before microphone capture; the initialized recognizer starts on that gesture. Successful answers are spoken automatically, and **Read answer** remains available to replay them.

Run `python3 ui/server.py` and `python3 ui/voice_server.py` in separate terminals, then open `http://127.0.0.1:8765`.

Copy the voice settings from `.env.example` into the ignored `.env`. The authenticated catalog and a live 290-token request verified `Qwen/Qwen3-30B-A3B-Instruct-2507` at `$0.10` per million input tokens and `$0.30` per million output tokens; the test cost was approximately `$0.00007`. Re-check prices before long-lived use. The service refuses inference when pricing, the model, or the API key is absent, or when its configured ceiling exceeds `$75`.

Before every request, the service reserves a deliberately conservative estimate using one token per prompt character plus the full output allowance. If that estimate would cross the ceiling, no paid request is sent. After a response, actual API usage updates `runs/voice-budget.json`. Requests are serialized around the budget check so concurrent questions cannot race past the limit.

The ledger enforces a `$50` voice allocation. The remaining `$25` of the user's `$75` project ceiling is reserved for fine-tuning and evaluation, whose duration is bounded per run because the available API does not expose an account-wide dollar stop. The latest expanded run used a 600-second guard. Browser STT/TTS is not charged through this Nebius ledger.

The Q&A subprocess currently calls the unmodified base model. It does not call any LoRA checkpoint until that checkpoint is deployed and passes the identical-prompt base-versus-adapter evaluation.

## Grounded project knowledge

Questions about architecture, Digital Analytics catalogs, and platform features are grounded in an explicit allowlist: `README.md`, all four project guides in `docs/`, `config/pipeline.json`, the evaluation guide/configuration/results, and dataset manifest/review JSON. Raw datasets, `.env`, OAuth credentials, and arbitrary workspace files are excluded. The dashboard status shows how many sources loaded.

Answers must cite repository paths and distinguish:

- **used:** CRAFT catalog discovery/schema metadata, Firebase/GA4 snapshots, Nebius model discovery, file upload, LoRA jobs, monitoring, checkpoints, and base-model inference;
- **available:** tools documented or exposed but not exercised by this workflow;
- **pending:** LoRA deployment, identical-prompt base-versus-adapter scoring, and promotion.
