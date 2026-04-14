# Research: Cloud GPU Training Providers for Hybrid Local/Cloud Fine-Tuning

## Summary

Cloud GPU providers fall into three tiers: (1) serverless job platforms like Modal and RunPod Serverless that charge per-second with no idle cost, (2) on-demand instance providers like Lambda Labs and Vast.ai that rent persistent VMs, and (3) training-as-a-service APIs like Together AI and HuggingFace AutoTrain that abstract away infrastructure entirely. For a local fine-tuning workbench, Modal offers the best developer experience for job-based dispatch, while Together AI provides the simplest path for API-only training integration.

## Authoritative Sources

- [Modal Pricing](https://modal.com/pricing): Per-second GPU billing, Python-native SDK
- [RunPod Pricing](https://www.runpod.io/pricing): Both pods and serverless GPU endpoints
- [Lambda Labs Pricing](https://lambda.ai/pricing): On-demand GPU instances, zero egress fees
- [Vast.ai Pricing](https://vast.ai/pricing): Marketplace model, lowest floor prices
- [Together AI Fine-Tuning Docs](https://docs.together.ai/docs/fine-tuning-pricing): Token-based training billing
- [HuggingFace Jobs](https://huggingface.co/docs/huggingface_hub/en/guides/jobs): Managed compute for training
- [W&B Launch](https://docs.wandb.ai/platform/hosting/self-managed/ref-arch): Queue-based remote dispatch

---

## 1. Cloud GPU Providers

### 1.1 Modal (modal.com) -- Serverless GPU

**Model:** Serverless, per-second billing, Python-native SDK.

| GPU | $/second | $/hour (approx) |
|-----|----------|-----------------|
| B200 | $0.001736 | $6.25 |
| H200 | $0.001261 | $4.54 |
| H100 | $0.001097 | $3.95 |
| A100 80GB | $0.000694 | $2.50 |
| A100 40GB | $0.000583 | $2.10 |
| L40S | $0.000542 | $1.95 |
| A10 | $0.000306 | $1.10 |
| L4 | $0.000222 | $0.80 |
| T4 | $0.000164 | $0.59 |

**Job-Based Training:** Yes. Core design is job-based. Define a Python function decorated with `@app.function(gpu="A100")`, run with `modal run --detach`. Supports long-running resumable training jobs.

**API/SDK:** Python SDK (`pip install modal`). Declarative infrastructure-as-code. Define container images, volumes, secrets, GPU requirements in Python. Sub-4-second cold starts.

**HuggingFace/LoRA Support:** First-class. Official examples for fine-tuning with axolotl, torchtune, Unsloth, and raw HF Trainer. LoRA, QLoRA, DeepSpeed ZeRO all supported.

**Free Tier:** $30/month free credits on Starter plan. Up to $25k for startups, $10k for academics.

**Integration Notes:**
- Best DX for a Python backend -- training scripts can be defined as Modal functions and dispatched programmatically
- Built-in volume mounts for checkpoints and datasets
- W&B integration via environment variables
- `modal run --detach` for fire-and-forget training
- Webhook callbacks available for job completion notification

---

### 1.2 RunPod (runpod.io) -- GPU Cloud + Serverless

**Model:** Both persistent pods (VMs) and serverless endpoints. Per-second and per-hour billing.

| GPU | On-Demand $/hr (Pod) | Serverless Flex $/hr |
|-----|---------------------|---------------------|
| H100 SXM 80GB | ~$2.69 | ~$4.18 |
| A100 SXM 80GB | ~$1.39 | -- |
| A100 PCIe 80GB | ~$1.19 | -- |
| RTX 4090 24GB | ~$0.44 | ~$1.10 |
| L4 24GB | ~$0.34 | -- |

**Job-Based Training:** Partial. Serverless endpoints are designed for inference, not training. For training, use Pods (persistent instances). Can be scripted via API to create/destroy pods.

**API/SDK:** Python SDK (`pip install runpod`). REST API for pod management (create, start, stop, terminate). Serverless SDK for building custom workers.

**HuggingFace/LoRA Support:** No native training service. You provision a pod and run your own training scripts. RunPod provides Docker templates with common ML stacks pre-installed.

**Free Tier:** Random $5-$500 bonus credit after first $10 spend. Startup program with 1:1 credit match up to $25k.

**Integration Notes:**
- Good for persistent training environments but less suited for job dispatch
- API allows programmatic pod lifecycle management
- Custom serverless workers possible but designed for inference patterns
- Community Cloud option is cheaper but less reliable

---

### 1.3 Lambda Labs (lambdalabs.com) -- GPU Cloud

**Model:** On-demand GPU instances. Hourly billing. Zero egress fees.

| GPU | $/hr |
|-----|------|
| H100 SXM 80GB | $2.99 |
| A100 80GB | $1.10 |
| A10 24GB | $0.75 |

**Job-Based Training:** No. Instance-based only. You SSH into a VM, run training, then terminate. No job submission API.

**API/SDK:** REST API for instance management (launch, list, terminate). No training-specific SDK.

**HuggingFace/LoRA Support:** Instances come with PyTorch, CUDA, and common ML libraries pre-installed. You run your own training scripts.

**Free Tier:** None. No free credits for new users.

**Integration Notes:**
- Simple VM provisioning, good pricing, but requires more orchestration work
- Frequent capacity shortages for popular GPU types
- Zero egress fees is a meaningful cost advantage for large model downloads
- Best suited for researchers who want a simple SSH-based workflow

---

### 1.4 Vast.ai -- GPU Marketplace

**Model:** Peer-to-peer marketplace. Prices set by hosts, vary by supply/demand. Per-second billing.

| GPU | Typical $/hr Range |
|-----|--------------------|
| H100 80GB (verified DC) | $1.50 - $1.87 |
| A100 80GB | $0.80 - $1.40 |
| RTX 4090 24GB | $0.34 - $0.50 |
| RTX 3090 24GB | $0.20 - $0.35 |

**Job-Based Training:** No native job API. You rent instances and run scripts. Can be automated via their REST API for instance lifecycle.

**API/SDK:** REST API for searching offers, creating/destroying instances. Python client available.

**HuggingFace/LoRA Support:** Docker-based instances. You bring your own container image with training stack.

**Free Tier:** None.

**Integration Notes:**
- Lowest prices available, but reliability and security vary by host
- "Verified datacenter" hosts are more reliable
- Interruptible instances save up to 50% but can be preempted
- Good for cost-sensitive batch training, poor for production reliability
- Requires more defensive coding (checkpoint frequently, handle interruptions)

---

### 1.5 Replicate -- Training API

**Model:** Per-second billing for training jobs. Submit training via API, get model back.

**Job-Based Training:** Yes. Native training API -- submit a training job, monitor progress, get results.

**API/SDK:** REST API + Python client. `replicate.trainings.create()` to submit jobs.

**HuggingFace/LoRA Support:** Supports LoRA fine-tuning for specific model architectures (primarily diffusion models, expanding to LLMs).

**Free Tier:** No dedicated free tier for training.

**Integration Notes:**
- Strong for image model fine-tuning (FLUX, SDXL)
- LLM fine-tuning support is more limited
- Simple API but less control over training configuration
- Good model for "submit job, get callback" pattern

---

## 2. Training-as-a-Service (API-Based Fine-Tuning)

### 2.1 Together AI Fine-Tuning API

**Pricing (per 1M tokens processed):**

| Model Size | SFT LoRA | SFT Full | DPO LoRA | DPO Full |
|-----------|----------|----------|----------|----------|
| Up to 16B | $0.48 | $0.54 | $1.20 | $1.35 |
| 17B - 69B | $1.50 | $1.65 | $3.75 | $4.12 |
| 70B - 100B | $2.90 | $3.20 | $7.25 | $8.00 |

**Supported Models:** Llama, Mistral, Qwen, DeepSeek, and other popular open-source models.

**API Example:**
```python
from together import Together
client = Together()

response = client.fine_tuning.create(
    training_file="file-abc123",
    model="meta-llama/Meta-Llama-3.1-8B",
    n_epochs=3,
    batch_size=4,
    learning_rate=1e-5,
    lora=True,
    suffix="my-finetune",
)
job_id = response.id
```

**Integration Notes:**
- Simplest integration path -- upload JSONL data, call API, poll for completion
- No infrastructure management required
- Cost estimation available before launching jobs
- Fine-tuned models served at base model inference prices
- Supports cancellation with prorated billing
- File upload via `client.files.upload()`, then reference file ID in training call

---

### 2.2 HuggingFace AutoTrain + Jobs

**Pricing:** Pay-as-you-go based on hardware used. Pricing per minute of compute. Available to Pro users ($9/month) and Team/Enterprise organizations.

**Two Options:**
1. **AutoTrain:** Zero-code fine-tuning through the HuggingFace UI. Upload dataset, select model, configure hyperparameters, train.
2. **HuggingFace Jobs:** Submit arbitrary training scripts to HuggingFace-managed infrastructure via CLI or Python SDK.

**Jobs API Example:**
```python
from huggingface_hub import HfApi
api = HfApi()

job = api.run_job(
    command="python train.py",
    image="pytorch/pytorch:2.5.0-cuda12.4-cudnn9-runtime",
    flavor="a100-80gb",
    secrets={"HF_TOKEN": "hf_..."},
    timeout=3600,
)
```

**Integration Notes:**
- AutoTrain is opinionated but zero-configuration
- Jobs API is flexible -- run any training script on managed compute
- Native integration with HuggingFace Hub for model/dataset storage
- 30-minute default timeout (configurable)
- Good for teams already in the HuggingFace ecosystem

---

### 2.3 OpenPipe

**Model:** Capture prompt-completion pairs via SDK, then fine-tune from collected data.

**Key Features:**
- SDK acts as a drop-in replacement for OpenAI client
- Automatically captures training data from production traffic
- Fine-tuning launched from dashboard or API
- Acquired by CoreWeave in 2025 -- now integrated with CoreWeave GPU infrastructure
- Agent Reinforcement Trainer (ART) for multi-step agent training via GRPO

**Integration Notes:**
- Best suited for replacing expensive API models with fine-tuned cheaper models
- Less relevant for custom dataset fine-tuning workflows
- The capture-then-train pattern does not fit a workbench UI where users bring their own data

---

## 3. Architecture Patterns for Hybrid Local/Cloud Training

### 3.1 W&B Launch Pattern (Queue + Agent)

Weights & Biases Launch uses a queue-based architecture:

1. **Local UI/CLI** enqueues a job with configuration (hyperparameters, dataset, model) to a W&B Launch Queue
2. **Launch Agent** (long-running process on cloud infrastructure) polls the queue FIFO
3. Agent receives job + queue configuration, provisions compute, runs training
4. Training logs, metrics, and artifacts stream back to W&B server
5. Job completion triggers callbacks

**Key Design Decisions:**
- Queues are bound to a specific compute target (K8s cluster, cloud provider)
- Agents handle resource provisioning and job lifecycle
- Configuration is declarative -- the queue config determines the execution environment
- Decouples job submission from execution

### 3.2 MLflow Remote Execution Pattern

MLflow uses a project-based pattern:

1. Define training as an MLflow Project (code + dependencies + entry points)
2. Submit project to a remote backend (Azure ML, Databricks, K8s)
3. Remote backend provisions compute and runs the project
4. Metrics and artifacts log to a central MLflow Tracking Server
5. Models register in MLflow Model Registry

### 3.3 Recommended Pattern for This Workbench

Based on the research, the recommended architecture for integrating cloud training into the LLM Fine-Tuning Workbench:

```
┌─────────────────────────────────────────────────┐
│  Frontend (React)                                │
│  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ Training      │  │ Provider Config          │  │
│  │ Config Editor │  │ (API keys, preferences)  │  │
│  └──────┬───────┘  └────────────┬────────────┘  │
│         │                       │                │
│         ▼                       ▼                │
│  ┌──────────────────────────────────────────┐   │
│  │  Launch Training Button                   │   │
│  │  [Local GPU] [Modal] [Together AI]        │   │
│  └──────────────────┬───────────────────────┘   │
└─────────────────────┼───────────────────────────┘
                      │ REST: POST /runs
                      ▼
┌─────────────────────────────────────────────────┐
│  Backend (FastAPI)                               │
│  ┌──────────────────────────────────────────┐   │
│  │  TrainingDispatcher (service)             │   │
│  │  ┌────────────┐ ┌──────────┐ ┌────────┐ │   │
│  │  │LocalAdapter│ │ModalAdptr│ │Together│ │   │
│  │  │            │ │          │ │Adapter │ │   │
│  │  └────────────┘ └──────────┘ └────────┘ │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  RunMonitor (background worker)           │   │
│  │  - Polls remote job status                │   │
│  │  - Streams logs/metrics via WebSocket     │   │
│  │  - Downloads artifacts on completion      │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

**Adapter Interface:**
```python
class CloudTrainingAdapter(Protocol):
    async def submit_training_job(
        self, *, config: TrainingConfig, dataset_path: Path
    ) -> RemoteJobHandle: ...

    async def poll_job_status(
        self, *, job_handle: RemoteJobHandle
    ) -> JobStatus: ...

    async def stream_logs(
        self, *, job_handle: RemoteJobHandle
    ) -> AsyncIterator[LogEntry]: ...

    async def download_artifacts(
        self, *, job_handle: RemoteJobHandle, destination: Path
    ) -> ArtifactManifest: ...

    async def cancel_job(
        self, *, job_handle: RemoteJobHandle
    ) -> None: ...
```

**Implementation Priority:**

| Priority | Provider | Reason |
|----------|----------|--------|
| 1 | Local GPU | Already exists in the workbench |
| 2 | Modal | Best Python SDK, job-native, per-second billing, LoRA examples |
| 3 | Together AI | Simplest API, no infrastructure, good for smaller models |
| 4 | HuggingFace Jobs | Good ecosystem fit, flexible compute |
| 5 | RunPod | Good pricing but requires more orchestration |

**Key Design Decisions:**

1. **Adapter pattern** -- each cloud provider implements the same interface, the dispatcher selects based on user configuration
2. **Polling over webhooks** -- simpler to implement, works behind NAT/firewalls; the backend polls job status and pushes updates to the frontend via the existing WebSocket connection
3. **Dataset upload** -- datasets must be uploaded to the provider before training starts; the adapter handles provider-specific upload (Modal Volumes, Together Files API, HF Hub)
4. **Checkpoint download** -- on job completion, the adapter downloads LoRA adapters/merged weights to local storage for evaluation
5. **Cost estimation** -- expose provider pricing in the UI so users can estimate cost before launching

---

## 4. Provider Comparison Matrix

| Feature | Modal | RunPod | Lambda | Vast.ai | Together AI | HF Jobs |
|---------|-------|--------|--------|---------|-------------|---------|
| Job-based dispatch | Yes | No (pods) | No | No | Yes | Yes |
| Per-second billing | Yes | Yes | No | Yes | Per-token | Per-minute |
| Python SDK | Excellent | Good | Basic | Basic | Good | Good |
| Native LoRA support | Via examples | DIY | DIY | DIY | Built-in | Via AutoTrain |
| Free credits | $30/mo | $5-500 bonus | None | None | None listed | Pro plan req |
| H100 $/hr | $3.95 | $2.69 | $2.99 | $1.50-1.87 | N/A (token) | Pay-as-you-go |
| A100 $/hr | $2.50 | $1.19-1.39 | $1.10 | $0.80-1.40 | N/A (token) | Pay-as-you-go |
| T4 $/hr | $0.59 | ~$0.20 | N/A | ~$0.15 | N/A | Pay-as-you-go |
| Cold start | <4 sec | N/A (pods) | N/A | N/A | N/A | Minutes |
| Reliability | High | High (secure) | Medium* | Variable | High | High |

*Lambda has frequent capacity shortages.

---

## 5. Cost Estimates for Typical Fine-Tuning Jobs

Assuming LoRA fine-tuning of a 7B parameter model on 10k examples, 3 epochs (~2 hours on A100):

| Provider | GPU | Estimated Cost |
|----------|-----|---------------|
| Modal | A100 40GB | ~$4.20 |
| RunPod | A100 PCIe 80GB | ~$2.38 |
| Lambda | A100 80GB | ~$2.20 |
| Vast.ai | A100 80GB | ~$1.60-2.80 |
| Together AI | LoRA SFT <16B | ~$0.48-2.00 (depends on dataset tokens) |

Together AI is cheapest for standard LoRA fine-tuning of supported models but offers less control over the training loop. Modal is more expensive per-hour but the per-second billing and zero idle time often result in lower actual costs for interactive/iterative workflows.
