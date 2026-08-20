# Capella AI Data Plane — Sizing & Pricing Calculator

Interactive sizing, hardware throughput modeling, and pricing estimation toolset for the **Couchbase Capella AI Data Plane (AWS us-east-1)**.

![Capella AI Data Plane](https://img.shields.io/badge/Couchbase-Capella_AI-EA2328?style=for-the-badge&logo=couchbase&logoColor=white)
![AWS Region](https://img.shields.io/badge/AWS_Region-us--east--1-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

---

## Overview

When sizing an AI workload on Couchbase Capella, customers and solutions engineers need to estimate three core components:
1. **Model Compute Nodes**: GPU VRAM and vCPU required for embedding pipelines and LLM inference hosting.
2. **Workflows Ingestion**: Data processing fees for external structured (JSON) and unstructured documents (PDF/OCR). Capella native data is 100% Free.
3. **Hardware Throughput & Sizing**: Real-time modeling of embedding speed (`docs/sec`), initial historical dataset backfill time (`hours`), generational output speed (`tokens/sec`), response latency (`seconds`), and concurrent user capacity without queuing.

---

## Official Rate Matrix (AWS us-east-1 / N. Virginia)

### 1. Model Compute Nodes (Hosting & Inference)
| Model Node Size | vCPU | GPU VRAM | Capella Credits / hr | Enterprise List $/hr | Target Workloads |
|---|---|---|---|---|---|
| **Extra Small** | 4 | 24 GB | **3.06** | **$5.36** | Lightweight embeddings, text classification, <3B models |
| **Small** | 4 | 48 GB | **4.75** | **$8.31** | High-dim embeddings, 7B/8B FP16 models (Llama 3 8B, Mistral 7B) |
| **Medium** | 48 | 192 GB | **20.96** | **$36.68** | Multi-GPU inference, 70B AWQ quantized, high concurrency |
| **Large** | 96 | 687 GB | **45.68** | **$79.94** | 70B full precision (FP16/BF16), complex multi-modal vision |
| **Extra Large** | 192 | 687 GB | **84.31** | **$147.54** | Enterprise production clusters, massive parallel CDC streams |

*Standard Enterprise list conversion: **$1.75 per Capella Credit**.*

### 2. Data Processing Services (Workflows & Ingestion)
| Data Source & Type | Unit of Measure | Format | Credits / Unit | Enterprise $/Unit | Notes |
|---|---|---|---|---|---|
| **Data from Capella** | N/A | JSON | **FREE (0.00)** | **Free** | Zero data processing charges for Capella-native buckets |
| **Structured Data (External)** | GiB | JSON | **0.05** / GiB | **$0.09** / GiB | Relational / NoSQL external database tables |
| **Unstructured Data (External)** | 1,000 Pages | PDF / Docs / Other | **15.625** / 1K Pgs | **$27.34** / 1K Pgs | Document parsing, OCR, and unstructured extraction |

### 3. Add-Ons & Ancillary Costs
- **Caching & Asynchronous Processing**: **0.50 credits / hr** ($0.875/hr Enterprise list = 365 credits/month flat fee per tenant/region).
- **Data Transfer Buffer**: Recommended **5% - 10%** allowance for inter-AZ and egress traffic.

---

## Hardware Throughput Benchmarks

### A. Embedding Speed (2 KB JSON Records / Documents)
- **Extra Small (24 GB GPU)**: ~1,000 docs/sec (3.6M docs/hr) $\rightarrow$ 10M records vectorized in **2.8 hours**.
- **Small (48 GB GPU)**: ~2,200 docs/sec (7.9M docs/hr) $\rightarrow$ 10M records vectorized in **1.3 hours**.
- **Medium (192 GB GPU)**: ~8,500 docs/sec (30.6M docs/hr) $\rightarrow$ 10M records vectorized in **20 minutes**.
- **Large (687 GB GPU)**: ~22,000 docs/sec (79.2M docs/hr) $\rightarrow$ 10M records vectorized in **7.5 minutes**.

### B. Generative LLM Inference & Concurrency (250-Token Output)
- **Extra Small**: ~100 tok/s | ~2.5s latency | Max 3–4 concurrent queries.
- **Small (8B FP16)**: ~300 tok/s | ~1.1s latency | Max 8–12 concurrent queries.
- **Medium (70B AWQ)**: ~1,000 tok/s | ~1.6s latency | Max 25–40 concurrent queries.
- **Large (70B Full)**: ~2,500 tok/s | ~1.0s latency | Max 60–100 concurrent queries.

---

## Quick Start: WebUI Dashboard

Launch the interactive web calculator locally:

```bash
# Option 1: Python WebUI Launcher (Auto-opens browser)
python3 run_webui.py

# Option 2: Shell script launcher
./start_webui.sh

# Option 3: Direct browser opening
open pricing_calculator.html
```

### WebUI Capabilities:
- **Customer Workload Sizing Advisor**: Input database record count, document size (1 KB, 2 KB, 5 KB), PDF pages, and concurrency to auto-calculate vector RAM, embedding rate, and node recommendation.
- **Interactive Light & Dark Theme**: Toggle between crisp enterprise light mode and dark mode.
- **Real-Time Cost Breakdown**: Dynamic progress bar chart showing Compute vs Ingestion vs Caching vs Network.
- **One-Click Export**: Download structured JSON quotes, copy summaries to clipboard, or generate printable PDF quotes.

---

## CLI Usage: Python Sizing Engine

The standalone Python CLI allows automated sizing and programmatic scripting:

```bash
# 1. Size directly from 5,000,000 Database Records (Postgres/Mongo) for 12 concurrent users:
python3 pricing_calculator.py --db-records 5000000 --db-record-kb 2.0 --model-tier fast-assistant --concurrency 12

# 2. Size from 250,000 PDF document pages with deep reasoning (70B LLM):
python3 pricing_calculator.py --pdf-pages 250000 --model-tier deep-reasoning --concurrency 25

# 3. Run interactive terminal wizard:
python3 pricing_calculator.py --interactive

# 4. Output as JSON:
python3 pricing_calculator.py --preset compliance-rag --json
```

---

## Repository Structure

```text
├── pricing_calculator.html   # Standalone interactive WebUI calculator
├── pricing_calculator.py     # Python sizing & pricing CLI engine
├── pricing_workflow.md       # Sizing methodology, formulas, & discovery guide
├── run_webui.py              # Python local HTTP launcher script
├── start_webui.sh            # Shell launch script
├── README.md                 # Project documentation
└── .gitignore                # Git ignore configuration
```

---

## License
Apache 2.0 / MIT.
