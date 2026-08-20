# Capella AI Data Plane — Sizing & Pricing Calculator

Interactive sizing, hardware throughput modeling, and pricing estimation toolset for the **Couchbase Capella AI Data Plane (AWS us-east-1)**.

![Capella AI Data Plane](https://img.shields.io/badge/Couchbase-Capella_AI-EA2328?style=for-the-badge&logo=couchbase&logoColor=white)
![AWS Region](https://img.shields.io/badge/AWS_Region-us--east--1-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white)
![License](https://img.shields.io/badge/License-Apache_2.0-blue?style=for-the-badge)

---

## Table of Contents
1. [Overview](#overview)
2. [Official AWS Rate Matrix](#official-rate-matrix-aws-us-east-1)
3. [Hardware Throughput Benchmarks (Embedding & Generative)](#hardware-throughput-benchmarks)
4. [Sizing Methodology & Mathematical Formulas](#sizing-methodology--mathematical-formulas)
5. [Quick Start: WebUI Dashboard](#quick-start-webui-dashboard)
6. [CLI Usage: Python Sizing Engine](#cli-usage-python-sizing-engine)
7. [Repository Structure](#repository-structure)

---

## Overview

When sizing an AI workload on Couchbase Capella, architects and solutions engineers need to estimate three core components:
1. **Model Compute Nodes**: Dedicated GPU VRAM and vCPU required for hosting embedding pipelines and LLM generative inference.
2. **Workflows Ingestion**: Data processing fees for external structured (JSON) and unstructured documents (PDF/OCR). Capella-native bucket data is **100% Free ($0.00)**.
3. **Hardware Throughput & Sizing**: Real-time modeling of:
   - **Embedding Pipeline Throughput**: `docs/sec` and historical backfill time in `hours`.
   - **Generative Inference Output**: Total cluster `tokens/sec`, per-query response `latency (sec)`, and max `concurrent active streams` without queuing.

---

## Official Rate Matrix (AWS us-east-1 / N. Virginia)

### 1. Model Compute Nodes (Hosting & Inference)
| Model Node Size | vCPU | GPU VRAM | Capella Credits / hr | Enterprise List $/hr | Dev Pro $/hr | Primary Target Workloads |
|---|---|---|---|---|---|---|
| **Extra Small** | 4 | 24 GB | **3.06** | **$5.36** | N/A | Lightweight embeddings, text classification, <3B models |
| **Small** | 4 | 48 GB | **4.75** | **$8.31** | N/A | High-dim embeddings, 7B/8B FP16 models (Llama 3 8B, Mistral 7B) |
| **Medium** | 48 | 192 GB | **20.96** | **$36.68** | N/A | Multi-GPU inference, 70B AWQ quantized, high concurrency |
| **Large** | 96 | 687 GB | **45.68** | **$79.94** | N/A | 70B full precision (FP16/BF16), complex multi-modal vision |
| **Extra Large** | 192 | 687 GB | **84.31** | **$147.54** | N/A | Enterprise production clusters, massive parallel CDC streams |

*Standard Enterprise list conversion: **$1.75 per Capella Credit**.*

### 2. Data Processing Services (Workflows & Ingestion)
| Data Source & Type | Unit of Measure | Format | Credits / Unit | Enterprise $/Unit | Dev Pro $/Unit | Notes |
|---|---|---|---|---|---|---|
| **Data from Capella** | N/A | JSON | **FREE (0.00)** | **Free** | Free | Zero data processing charges for Capella-native buckets |
| **Structured Data (External)** | GiB | JSON | **0.05** / GiB | **$0.09** / GiB | $0.06 / GiB | Relational / NoSQL external database tables |
| **Unstructured Data (External)** | 1,000 Pages | PDF / Docs / Other | **15.625** / 1K Pgs | **$27.34** / 1K Pgs | $19.53 / 1K Pgs | Document parsing, OCR, and unstructured extraction |

### 3. Add-Ons & Ancillary Costs
- **Caching & Asynchronous Processing**: **0.50 credits / hr** ($0.875/hr Enterprise list = 365 credits/month flat fee per tenant/region).
- **Data Transfer Buffer**: Recommended **5% - 10%** allowance for inter-AZ and egress traffic.

---

## Hardware Throughput Benchmarks

### A. Embedding Speed (2 KB JSON Records / Documents)
*Governed by GPU batch matrix compute cores:*

| Model Node Size | GPU VRAM | Embedding Model Family | Embedding Throughput (2 KB Docs/sec) | Hourly Processing Capacity | Time to Vectorize 10 Million Records |
|---|---|---|---|---|---|
| **Extra Small** | 24 GB | MiniLM, BAAI-bge-base (384/768-dim) | **~1,000 docs/sec** | **3.6 Million docs/hr** | **2.78 hours** |
| **Small** | 48 GB | BAAI-bge-large, E5-v2 (1024/1536-dim) | **~2,200 docs/sec** | **7.9 Million docs/hr** | **1.26 hours** |
| **Medium** | 192 GB | Multi-GPU batch embedding cluster | **~8,500 docs/sec** | **30.6 Million docs/hr** | **19.6 minutes** |
| **Large** | 687 GB | High-throughput enterprise pipeline | **~22,000 docs/sec** | **79.2 Million docs/hr** | **7.5 minutes** |
| **Extra Large** | 687 GB | Massive parallel CDC streaming | **~45,000 docs/sec** | **162.0 Million docs/hr** | **3.7 minutes** |

> **Real-time CDC Headroom**: If a customer has an incoming Change Data Capture (CDC) stream of **100 writes/second**, an **Extra Small node (1,000 docs/sec)** handles the live embedding load with 90% headroom remaining.

### B. Generative LLM Inference & Concurrency (250-Token Output)
*Governed by GPU memory bandwidth and KV-Cache capacity:*

| Model Node Size | Target Model Family | Total Generative Token Pool | Latency for 250-token Answer | Max Concurrent Streams (Zero Queue Delay) |
|---|---|---|---|---|
| **Extra Small** (24 GB GPU) | 3B LLM / Quantized 7B | **~100 tokens/sec** | **~2.5 seconds** | **3 – 4 concurrent queries** |
| **Small** (48 GB GPU) | 8B FP16 (Llama 3 8B, Mistral 7B) | **~300 tokens/sec** | **~1.1 seconds** | **8 – 12 concurrent queries** |
| **Medium** (192 GB GPU) | 70B AWQ Quantized (or 4x 8B) | **~1,000 tokens/sec** | **~1.6 seconds** | **25 – 40 concurrent queries** |
| **Large** (687 GB GPU) | 70B Full Precision (FP16/BF16) | **~2,500 tokens/sec** | **~1.0 seconds** | **60 – 100 concurrent queries** |
| **Extra Large** (687 GB GPU) | Enterprise Multi-Model Cluster | **~5,000+ tokens/sec** | **< 1.0 second** | **150+ concurrent queries** |

---

## Sizing Methodology & Mathematical Formulas

### 1. Vector Index RAM Sizing (Couchbase Search)
To ensure sub-second vector search performance using Couchbase's HNSW index:

$$\text{Vector RAM (GB)} = \frac{\text{Total Vectors} \times \text{Dimensions} \times 4 \text{ bytes (float32)} \times 1.35 \text{ (HNSW graph overhead)}}{1024^3}$$

- **100,000 document pages** ($\approx 120,000$ vectors @ 1536-dim) $\approx \mathbf{0.93\text{ GB RAM}}$.
- **1,000,000 database records** (@ 1536-dim) $\approx \mathbf{7.72\text{ GB RAM}}$.
- **5,000,000 database records** (@ 1536-dim) $\approx \mathbf{38.62\text{ GB RAM}}$.

### 2. Database Ingestion Conversions
- **1 KB / doc**: ~1,048,576 records per GiB
- **2 KB / doc**: ~524,288 records per GiB
- **5 KB / doc**: ~209,715 records per GiB

*Example: 5,000,000 records @ 2 KB = **9.54 GiB** = **0.48 Credits ($0.83)** for initial bulk ingestion.*

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

### WebUI Features:
- **☀️ Light / 🌙 Dark Mode**: Clean modern enterprise light theme with persistent toggle.
- **Customer Workload Sizing Advisor**: Input database record count, document size (1 KB, 2 KB, 5 KB), PDF pages, and concurrency to auto-calculate vector RAM, embedding rate, and node recommendation.
- **Live Hardware Counters**: Real-time cards showing embedding docs/sec, initial backfill time, generation tokens/sec, and response latency.
- **Visual Cost Breakdown**: Dynamic progress bar chart showing Compute vs Ingestion vs Caching vs Network.
- **One-Click Export**: Download structured JSON quotes, copy formatted summaries to clipboard, or generate printable PDF quotes.

---

## CLI Usage: Python Sizing Engine

The standalone Python CLI allows automated sizing and programmatic scripting:

```bash
# 1. Size from 5,000,000 Database Records (Postgres/Mongo) for 12 concurrent users:
python3 pricing_calculator.py --db-records 5000000 --db-record-kb 2.0 --model-tier fast-assistant --concurrency 12

# 2. Size from 250,000 PDF document pages with deep reasoning (70B LLM):
python3 pricing_calculator.py --pdf-pages 250000 --model-tier deep-reasoning --concurrency 25

# 3. Load pre-configured scenario presets:
python3 pricing_calculator.py --preset compliance-rag

# 4. Run interactive terminal wizard:
python3 pricing_calculator.py --interactive

# 5. Output structured JSON quote:
python3 pricing_calculator.py --preset compliance-rag --json
```

---

## Repository Structure

```text
capella-ai-pricing-calculator/
├── pricing_calculator.html   # Standalone interactive WebUI (Light & Dark themes)
├── pricing_calculator.py     # Python CLI sizing & pricing engine
├── pricing_workflow.md       # Sizing methodology, formulas, & discovery guide
├── run_webui.py              # Local HTTP web server launcher (auto-opens browser)
├── start_webui.sh            # One-click executable launch script
├── README.md                 # Complete project documentation & benchmarks
└── .gitignore                # Git ignore configuration
```

---

## License
Apache 2.0. Copyright (c) Couchbase 2024–2026.
