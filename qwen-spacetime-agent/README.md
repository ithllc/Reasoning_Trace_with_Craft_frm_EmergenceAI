# Qwen 3.5 9B streaming agent with SpacetimeDB

This standalone TypeScript project runs a small tool-using agent against Qwen 3.5 9B served by
llama.cpp. Tokens stream through llama.cpp's OpenAI-compatible API while jobs, messages, tool
results, completion state, and errors are written to a local SpacetimeDB database.

## Prerequisites

- Node.js 18 or newer
- SpacetimeDB CLI 2.x
- A recent llama.cpp build containing the `llama-server` executable

The default endpoint is `http://127.0.0.1:8080/v1`. The included script asks llama.cpp to download
the `Q4_K_M` GGUF from Hugging Face. Set `LLAMA_MODEL_PATH` to use an existing local GGUF instead.

## Setup

```bash
cd qwen-spacetime-agent
npm install
cp .env.example .env
spacetime start
npm run db:publish
```

Build or install llama.cpp, ensure `llama-server` is on `PATH`, then start Qwen with its embedded
Jinja tool template enabled:

```bash
npm run model:serve
```

The script defaults to a Q4_K_M quantization and 32K context to reduce local memory pressure.
Adjust `LLAMA_GPU_LAYERS` and `LLAMA_CONTEXT_SIZE` for the available CPU, GPU, and memory. In
separate terminals, start SpacetimeDB and run a task:

```bash
spacetime start
npm run agent -- "Calculate 37 * 19 and explain the result"
```

The response streams immediately. The calculator call and every conversation message are saved as
one training trajectory. Inspect stored rows with:

```bash
spacetime sql --server local qwen-agent-jobs "SELECT * FROM job"
spacetime sql --server local qwen-agent-jobs "SELECT * FROM message ORDER BY job_id, sequence"
```

Export completed trajectories:

```bash
npm run export -- data/training-export.txt
```

The export intentionally stays lossless and tabular. Convert reviewed rows into the exact chat
template required by the model and trainer; exclude failed, low-quality, sensitive, and duplicate
runs before training.

## Fine-tune and return to llama.cpp

Every successfully completed job is stored in SpacetimeDB and appended to
`data/trajectories.jsonl`. The JSONL retains system, user, assistant, tool-call, and tool-result
messages. Review it before training; generated data should not be treated as correct merely because
the job completed.

Create a separate GPU training environment and install the training dependencies:

```bash
python -m venv .train-venv
source .train-venv/bin/activate
pip install -r training/requirements.txt
```

Validate and run text-only QLoRA:

```bash
npm run train:qlora
```

Build and validate the five reviewed Craft/GitHub proof-of-concept runs:

```bash
npm run dataset:craft
```

The reusable agent policy and dataset scope are defined in
`configs/craft-github-agent.json`.

This writes `data/craft-github-5-runs.train.jsonl`. Each trajectory contains concise decision
summaries, exact tool calls, tool results, and a grounded final answer. It intentionally excludes
private chain-of-thought. To train on it, pass the file to `training/train_qlora.py --dataset`.

The trainer loads the original Hugging Face checkpoint in 4-bit NF4, freezes the vision encoder,
and applies LoRA only to language-model attention, gated-delta, and MLP projections. Defaults target
a single GPU with a batch size of one, gradient accumulation of eight, and 4K-token samples. Adjust
the `TRAIN_*` environment values for available VRAM and dataset characteristics. QLoRA still needs
a CUDA GPU and substantial memory; llama.cpp GGUF files are inference artifacts and are not used as
training checkpoints.

After training, merge the adapter into the original checkpoint and convert it to a llama.cpp GGUF:

```bash
export LLAMA_CPP_DIR=/absolute/path/to/llama.cpp
npm run train:gguf
```

Serve the fine-tuned model by changing `.env`:

```dotenv
LLAMA_MODEL_PATH=/absolute/path/to/qwen35-agent-q4_k_m.gguf
```

Before replacing the baseline model, evaluate held-out tasks for final-answer quality, tool-call
validity, task completion, hallucinations, and regressions. Keep training and evaluation job IDs
disjoint.

## Data model

- `job`: prompt, model, status, timestamps, final answer, and failure details
- `message`: ordered system/user/assistant/tool content plus tool-call identifiers

SpacetimeDB reducers are the only write path, so each job mutation is transactional. The tables are
public for simple local development; tighten visibility and authentication before remote deployment.
