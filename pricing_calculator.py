#!/usr/bin/env python3
"""
Capella AI Data Plane Pricing Engine & Calculator
Based on Couchbase Capella AWS Credits & List Prices (us-east-1).

Usage:
  python pricing_calculator.py --help
  python pricing_calculator.py --node-size Medium --node-count 2 --hours 730 --structured-gib 250 --unstructured-pages 50 --caching
  python pricing_calculator.py --preset compliance-rag
  python pricing_calculator.py --interactive
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from typing import Dict, Optional, List


# ---------------------------------------------------------
# Rate Cards & Pricing Constants (AWS us-east-1 / N. Virginia)
# ---------------------------------------------------------

MODEL_NODE_PRICING = {
    "extra_small": {
        "name": "Extra Small",
        "vcpu": 4,
        "gpu_gb": 24,
        "credits_per_hr": 3.06,
        "dev_pro_usd_per_hr": None,
        "enterprise_usd_per_hr": 5.36,
        "description": "Lightweight embedding models, small classification models (e.g. <3B params)",
    },
    "small": {
        "name": "Small",
        "vcpu": 4,
        "gpu_gb": 48,
        "credits_per_hr": 4.75,
        "dev_pro_usd_per_hr": None,
        "enterprise_usd_per_hr": 8.31,
        "description": "Mid-tier embeddings, 7B/8B quantized LLMs (e.g. Llama 3 8B, Mistral 7B)",
    },
    "medium": {
        "name": "Medium",
        "vcpu": 48,
        "gpu_gb": 192,
        "credits_per_hr": 20.96,
        "dev_pro_usd_per_hr": None,
        "enterprise_usd_per_hr": 36.68,
        "description": "Multi-GPU inference, high-throughput 8B-14B models, or 70B quantized models",
    },
    "large": {
        "name": "Large",
        "vcpu": 96,
        "gpu_gb": 687,
        "credits_per_hr": 45.68,
        "dev_pro_usd_per_hr": None,
        "enterprise_usd_per_hr": 79.94,
        "description": "Large parameter LLMs (70B full precision), complex multi-modal models",
    },
    "extra_large": {
        "name": "Extra Large",
        "vcpu": 192,
        "gpu_gb": 687,
        "credits_per_hr": 84.31,
        "dev_pro_usd_per_hr": None,
        "enterprise_usd_per_hr": 147.54,
        "description": "Ultra high-throughput production clusters, massive concurrent inference workloads",
    },
}

DATA_PROCESSING_PRICING = {
    "capella_internal_json": {
        "name": "Data from Capella",
        "unit": "JSON Records",
        "credits_per_unit": 0.0,
        "dev_pro_usd_per_unit": 0.0,
        "enterprise_usd_per_unit": 0.0,
    },
    "structured_external_gib": {
        "name": "Structured Data from External",
        "unit": "GiB (JSON)",
        "credits_per_unit": 0.05,
        "dev_pro_usd_per_unit": 0.06,
        "enterprise_usd_per_unit": 0.09,
    },
    "unstructured_external_1k_pages": {
        "name": "Unstructured Data from External",
        "unit": "1K Pages (PDF/Doc/Other)",
        "credits_per_unit": 15.625,
        "dev_pro_usd_per_unit": 19.53,
        "enterprise_usd_per_unit": 27.34,
    },
}

# Add-on flat rate fees
CACHING_ASYNC_CREDITS_PER_HR = 0.50  # per tenant per region

# Standard credit conversions
ENTERPRISE_CREDIT_RATE = 1.75  # $1.75 per Capella Credit
DEV_PRO_CREDIT_RATE = 1.25     # $1.25 per Capella Credit

HOURS_PER_MONTH = 730  # Standard cloud billing monthly hours


@dataclass
class ModelDeploymentConfig:
    node_size_key: str
    node_count: int = 1
    active_hours_per_month: float = HOURS_PER_MONTH
    enable_guardrails: bool = False
    guardrails_overhead_pct: float = 0.0  # Optional overhead percentage if enabled


@dataclass
class DataProcessingConfig:
    structured_gib_per_month: float = 0.0
    unstructured_pages_per_month: float = 0.0  # in thousands of pages (e.g. 5.0 = 5,000 pages)
    capella_internal_gib_per_month: float = 0.0


@dataclass
class AddonConfig:
    enable_caching_async: bool = False
    caching_regions: int = 1
    data_transfer_fee_pct: float = 7.5  # rule of thumb: ~5-10% of bill


class CapellaAIPricingEstimator:
    def __init__(
        self,
        deployments: Optional[List[ModelDeploymentConfig]] = None,
        processing: Optional[DataProcessingConfig] = None,
        addons: Optional[AddonConfig] = None,
        credit_rate_enterprise: float = ENTERPRISE_CREDIT_RATE,
        credit_rate_dev_pro: float = DEV_PRO_CREDIT_RATE,
    ):
        self.deployments = deployments or []
        self.processing = processing or DataProcessingConfig()
        self.addons = addons or AddonConfig()
        self.credit_rate_enterprise = credit_rate_enterprise
        self.credit_rate_dev_pro = credit_rate_dev_pro

    def calculate(self) -> Dict:
        # 1. Model Compute Costs
        compute_breakdown = []
        total_compute_credits_monthly = 0.0
        total_compute_enterprise_usd_monthly = 0.0

        for d in self.deployments:
            key = d.node_size_key.lower().replace("-", "_").replace(" ", "_")
            if key not in MODEL_NODE_PRICING:
                raise ValueError(f"Unknown node size: {d.node_size_key}. Valid options: {list(MODEL_NODE_PRICING.keys())}")
            
            node_info = MODEL_NODE_PRICING[key]
            base_credits_hr = node_info["credits_per_hr"]
            guardrail_multiplier = 1.0 + (d.guardrails_overhead_pct / 100.0) if d.enable_guardrails else 1.0
            
            effective_credits_hr = base_credits_hr * guardrail_multiplier
            total_node_hrs = d.node_count * d.active_hours_per_month
            
            monthly_credits = effective_credits_hr * total_node_hrs
            # Direct enterprise hourly list rate if no guardrail modifier, else multiplied
            base_ent_usd_hr = node_info["enterprise_usd_per_hr"]
            effective_ent_usd_hr = base_ent_usd_hr * guardrail_multiplier
            monthly_ent_usd = effective_ent_usd_hr * total_node_hrs
            
            compute_breakdown.append({
                "node_size": node_info["name"],
                "vCPU_per_node": node_info["vcpu"],
                "gpu_gb_per_node": node_info["gpu_gb"],
                "node_count": d.node_count,
                "active_hours": d.active_hours_per_month,
                "credits_per_node_hr": round(effective_credits_hr, 2),
                "enterprise_usd_per_node_hr": round(effective_ent_usd_hr, 2),
                "guardrails_enabled": d.enable_guardrails,
                "monthly_credits": round(monthly_credits, 2),
                "monthly_enterprise_usd": round(monthly_ent_usd, 2),
            })
            
            total_compute_credits_monthly += monthly_credits
            total_compute_enterprise_usd_monthly += monthly_ent_usd

        # 2. Data Processing (Workflows) Costs
        proc_credits_monthly = 0.0
        proc_dev_pro_usd_monthly = 0.0
        proc_ent_usd_monthly = 0.0
        
        # Structured Data
        struct_units = self.processing.structured_gib_per_month
        struct_cfg = DATA_PROCESSING_PRICING["structured_external_gib"]
        struct_credits = struct_units * struct_cfg["credits_per_unit"]
        struct_dev_pro_usd = struct_units * struct_cfg["dev_pro_usd_per_unit"]
        struct_ent_usd = struct_units * struct_cfg["enterprise_usd_per_unit"]
        
        # Unstructured Data (in 1K pages units)
        unstruct_units = self.processing.unstructured_pages_per_month
        unstruct_cfg = DATA_PROCESSING_PRICING["unstructured_external_1k_pages"]
        unstruct_credits = unstruct_units * unstruct_cfg["credits_per_unit"]
        unstruct_dev_pro_usd = unstruct_units * unstruct_cfg["dev_pro_usd_per_unit"]
        unstruct_ent_usd = unstruct_units * unstruct_cfg["enterprise_usd_per_unit"]

        proc_credits_monthly = struct_credits + unstruct_credits
        proc_dev_pro_usd_monthly = struct_dev_pro_usd + unstruct_dev_pro_usd
        proc_ent_usd_monthly = struct_ent_usd + unstruct_ent_usd

        # 3. Add-ons (Caching & Async Processing)
        caching_credits_monthly = 0.0
        caching_ent_usd_monthly = 0.0
        if self.addons.enable_caching_async:
            caching_credits_monthly = CACHING_ASYNC_CREDITS_PER_HR * HOURS_PER_MONTH * self.addons.caching_regions
            caching_ent_usd_monthly = caching_credits_monthly * self.credit_rate_enterprise

        # Subtotal before data transfer
        subtotal_credits_monthly = total_compute_credits_monthly + proc_credits_monthly + caching_credits_monthly
        subtotal_ent_usd_monthly = total_compute_enterprise_usd_monthly + proc_ent_usd_monthly + caching_ent_usd_monthly

        # 4. Data Transfer Estimate
        dt_pct = self.addons.data_transfer_fee_pct / 100.0
        dt_credits_monthly = subtotal_credits_monthly * dt_pct
        dt_ent_usd_monthly = subtotal_ent_usd_monthly * dt_pct

        # Grand Totals
        grand_total_credits_monthly = subtotal_credits_monthly + dt_credits_monthly
        grand_total_ent_usd_monthly = subtotal_ent_usd_monthly + dt_ent_usd_monthly

        # Annualized
        grand_total_credits_annual = grand_total_credits_monthly * 12
        grand_total_ent_usd_annual = grand_total_ent_usd_monthly * 12

        return {
            "summary": {
                "monthly_credits": round(grand_total_credits_monthly, 2),
                "monthly_enterprise_usd": round(grand_total_ent_usd_monthly, 2),
                "annual_credits": round(grand_total_credits_annual, 2),
                "annual_enterprise_usd": round(grand_total_ent_usd_annual, 2),
            },
            "breakdown": {
                "compute": {
                    "deployments": compute_breakdown,
                    "monthly_credits": round(total_compute_credits_monthly, 2),
                    "monthly_enterprise_usd": round(total_compute_enterprise_usd_monthly, 2),
                },
                "data_processing": {
                    "structured_external_gib": struct_units,
                    "structured_credits": round(struct_credits, 2),
                    "structured_enterprise_usd": round(struct_ent_usd, 2),
                    "unstructured_external_1k_pages": unstruct_units,
                    "unstructured_credits": round(unstruct_credits, 2),
                    "unstructured_enterprise_usd": round(unstruct_ent_usd, 2),
                    "capella_internal_json": "Free",
                    "total_processing_credits": round(proc_credits_monthly, 2),
                    "total_processing_enterprise_usd": round(proc_ent_usd_monthly, 2),
                },
                "addons": {
                    "caching_async_enabled": self.addons.enable_caching_async,
                    "caching_regions": self.addons.caching_regions,
                    "caching_credits_monthly": round(caching_credits_monthly, 2),
                    "caching_enterprise_usd_monthly": round(caching_ent_usd_monthly, 2),
                },
                "network_data_transfer": {
                    "rate_buffer_pct": self.addons.data_transfer_fee_pct,
                    "monthly_credits": round(dt_credits_monthly, 2),
                    "monthly_enterprise_usd": round(dt_ent_usd_monthly, 2),
                },
            },
        }


def format_currency(val: float) -> str:
    return f"${val:,.2f}"


def format_credits(val: float) -> str:
    return f"{val:,.2f} credits"


def print_cli_report(res: Dict):
    print("=" * 80)
    print("      CAPELLA AI DATA PLANE PRICING ESTIMATE & SIZING SUMMARY")
    print("      AWS us-east-1 (N. Virginia) | Enterprise Tier List Rate ($1.75/credit)")
    print("=" * 80)
    
    print("\n--- 1. MODEL COMPUTE NODES ---")
    deployments = res["breakdown"]["compute"]["deployments"]
    if not deployments:
        print("  No model compute nodes configured.")
    else:
        for idx, d in enumerate(deployments, 1):
            print(f"  [{idx}] {d['node_size']} ({d['vCPU_per_node']} vCPU, {d['gpu_gb_per_node']} GB GPU)")
            print(f"      Quantity: {d['node_count']} node(s) | Operating Hours: {d['active_hours']} hrs/mo")
            print(f"      Rate: {d['credits_per_node_hr']} credits/hr ({format_currency(d['enterprise_usd_per_node_hr'])}/hr)")
            print(f"      Monthly Total: {format_credits(d['monthly_credits'])} | {format_currency(d['monthly_enterprise_usd'])}")
        print(f"  >> Compute Subtotal: {format_credits(res['breakdown']['compute']['monthly_credits'])} | {format_currency(res['breakdown']['compute']['monthly_enterprise_usd'])}/mo")

    print("\n--- 2. DATA PROCESSING & INGESTION (WORKFLOWS) ---")
    dp = res["breakdown"]["data_processing"]
    print(f"  - Structured Data (JSON): {dp['structured_external_gib']} GiB/mo -> {format_credits(dp['structured_credits'])} ({format_currency(dp['structured_enterprise_usd'])})")
    print(f"  - Unstructured Data:      {dp['unstructured_external_1k_pages']} (x1K pages)/mo -> {format_credits(dp['unstructured_credits'])} ({format_currency(dp['unstructured_enterprise_usd'])})")
    print(f"  - Capella Internal JSON:  Free")
    print(f"  >> Ingestion Subtotal:   {format_credits(dp['total_processing_credits'])} | {format_currency(dp['total_processing_enterprise_usd'])}/mo")

    print("\n--- 3. PLATFORM ADD-ONS & NETWORK ---")
    addons = res["breakdown"]["addons"]
    if addons["caching_async_enabled"]:
        print(f"  - Caching & Async Processing: Enabled ({addons['caching_regions']} region(s) @ 0.50 cr/hr)")
        print(f"    Monthly: {format_credits(addons['caching_credits_monthly'])} | {format_currency(addons['caching_enterprise_usd_monthly'])}")
    else:
        print("  - Caching & Async Processing: Disabled ($0.00)")
        
    nt = res["breakdown"]["network_data_transfer"]
    print(f"  - Data Transfer Fee Buffer: {nt['rate_buffer_pct']}% estimated")
    print(f"    Monthly: {format_credits(nt['monthly_credits'])} | {format_currency(nt['monthly_enterprise_usd'])}")

    print("\n" + "=" * 80)
    print("                           GRAND TOTAL ESTIMATE")
    print("=" * 80)
    s = res["summary"]
    print(f"  MONTHLY TOTAL:   {format_credits(s['monthly_credits']).rjust(18)}  |  {format_currency(s['monthly_enterprise_usd']).rjust(14)} / month")
    print(f"  ANNUALIZED:      {format_credits(s['annual_credits']).rjust(18)}  |  {format_currency(s['annual_enterprise_usd']).rjust(14)} / year")
    print("=" * 80)


def get_preset(preset_name: str) -> CapellaAIPricingEstimator:
    name = preset_name.lower().replace("_", "-")
    if name == "compliance-rag":
        # Realistic Western Union / Compliance Investigation RAG Pipeline
        # 1x Medium node for 70B quantized LLM / heavy inference
        # 2x Small nodes for embedding generation and re-ranking
        # 500 GiB structured transaction metadata ingestion
        # 100k pages (100 in 1K units) sanction/regulatory documents monthly
        return CapellaAIPricingEstimator(
            deployments=[
                ModelDeploymentConfig(node_size_key="medium", node_count=1, active_hours_per_month=730),
                ModelDeploymentConfig(node_size_key="small", node_count=2, active_hours_per_month=730),
            ],
            processing=DataProcessingConfig(
                structured_gib_per_month=500,
                unstructured_pages_per_month=100,  # 100k pages
            ),
            addons=AddonConfig(enable_caching_async=True, caching_regions=1, data_transfer_fee_pct=7.5),
        )
    elif name == "light-chatbot":
        # Low volume internal FAQ / lightweight assistant
        return CapellaAIPricingEstimator(
            deployments=[
                ModelDeploymentConfig(node_size_key="small", node_count=1, active_hours_per_month=730),
            ],
            processing=DataProcessingConfig(
                structured_gib_per_month=50,
                unstructured_pages_per_month=10,  # 10k pages
            ),
            addons=AddonConfig(enable_caching_async=False, data_transfer_fee_pct=5.0),
        )
    elif name == "enterprise-heavy":
        # Multi-model large-scale production setup
        return CapellaAIPricingEstimator(
            deployments=[
                ModelDeploymentConfig(node_size_key="large", node_count=2, active_hours_per_month=730),
                ModelDeploymentConfig(node_size_key="medium", node_count=2, active_hours_per_month=730),
            ],
            processing=DataProcessingConfig(
                structured_gib_per_month=2000,
                unstructured_pages_per_month=500,  # 500k pages
            ),
            addons=AddonConfig(enable_caching_async=True, caching_regions=2, data_transfer_fee_pct=10.0),
        )
    else:
        raise ValueError(f"Unknown preset '{preset_name}'. Options: compliance-rag, light-chatbot, enterprise-heavy")


def interactive_mode():
    print("\n--- Capella AI Data Plane Interactive Sizing Wizard ---")
    print("Select Model Node Size:")
    for idx, (k, v) in enumerate(MODEL_NODE_PRICING.items(), 1):
        print(f"  {idx}. {v['name']} ({v['vcpu']} vCPU, {v['gpu_gb']} GB GPU) - {v['credits_per_hr']} cr/hr (${v['enterprise_usd_per_hr']}/hr)")
    
    choice = input("Enter choice (1-5, default 2): ").strip() or "2"
    key_map = list(MODEL_NODE_PRICING.keys())
def size_from_customer_data(
    raw_pdf_gib: float = 0.0,
    total_pages: Optional[float] = None,
    structured_gib: float = 0.0,
    db_records_count: Optional[int] = None,
    db_record_kb: float = 2.0,
    monthly_delta_pct: float = 10.0,
    model_tier: str = "fast_assistant",
    concurrent_users: int = 10,
    vector_dim: int = 1536,
    enable_caching: bool = True,
) -> Dict:
    """
    Translates raw customer data volumes (database JSON records & unstructured documents)
    into hardware throughput capacity (docs/sec, tokens/sec, latency), Couchbase vector index RAM,
    and Capella AI compute node sizing recommendations.
    """
    # 1. Database Record Ingestion Conversion
    if db_records_count is not None and db_records_count > 0:
        struct_gib_from_records = (db_records_count * db_record_kb) / (1024.0 * 1024.0)
        structured_gib += struct_gib_from_records
        structured_records = float(db_records_count)
    else:
        structured_records = structured_gib * (1024.0 * 1024.0 / db_record_kb)

    # 2. Document Page & Chunk Conversion
    pages = total_pages if total_pages is not None else (raw_pdf_gib * 12500.0)
    doc_chunks = pages * 1.2  # ~1.2 chunks per page (512 token chunks with overlap)
    total_vectors = doc_chunks + structured_records

    # 3. Couchbase Search / Vector Index RAM (HNSW Graph overhead)
    vector_index_ram_gb = (total_vectors * vector_dim * 4.0 * 1.35) / (1024 ** 3)

    # 4. Ingestion Sizing (Initial Bulk vs Monthly Delta)
    initial_unstruct_1k_units = pages / 1000.0
    initial_struct_gib = structured_gib
    initial_ingestion_credits = (
        (initial_unstruct_1k_units * DATA_PROCESSING_PRICING["unstructured_external_1k_pages"]["credits_per_unit"]) +
        (initial_struct_gib * DATA_PROCESSING_PRICING["structured_external_gib"]["credits_per_unit"])
    )
    initial_ingestion_usd = initial_ingestion_credits * ENTERPRISE_CREDIT_RATE

    monthly_unstruct_1k_units = initial_unstruct_1k_units * (monthly_delta_pct / 100.0)
    monthly_struct_gib = initial_struct_gib * (monthly_delta_pct / 100.0)

    # 5. Hardware Throughput Benchmarks Dictionary
    # docs/sec for 2KB embedding, tokens/sec total pool, max zero-queue concurrent streams
    NODE_THROUGHPUT = {
        "extra_small": {"embed_docs_sec": 1000, "gen_tokens_sec": 100, "max_concurrent": 4, "avg_250t_latency_sec": 2.5},
        "small":       {"embed_docs_sec": 2200, "gen_tokens_sec": 300, "max_concurrent": 12, "avg_250t_latency_sec": 1.1},
        "medium":      {"embed_docs_sec": 8500, "gen_tokens_sec": 1000, "max_concurrent": 40, "avg_250t_latency_sec": 1.6},
        "large":       {"embed_docs_sec": 22000, "gen_tokens_sec": 2500, "max_concurrent": 100, "avg_250t_latency_sec": 1.0},
        "extra_large": {"embed_docs_sec": 45000, "gen_tokens_sec": 5000, "max_concurrent": 200, "avg_250t_latency_sec": 0.8},
    }

    # 6. Model Node Recommendation
    model_tier = model_tier.lower().replace("-", "_")
    if model_tier in ["embedding_only", "embed"]:
        node_size = "extra_small"
        node_count = max(1, int(concurrent_users / 50) + 1)
        reasoning = "Dedicated to embedding generation & semantic vector search. High throughput embedding pipeline (~1,000 docs/sec per node)."
    elif model_tier in ["fast_assistant", "8b", "llama3_8b"]:
        if concurrent_users <= 12:
            node_size = "small"
            node_count = 1
            reasoning = "Small (48 GB GPU) runs 8B FP16 models at ~300 tokens/sec. Delivers a 250-token answer in ~1.1s for up to 12 concurrent users without queuing."
        else:
            node_size = "small"
            node_count = max(2, int(concurrent_users / 12) + 1)
            reasoning = f"{node_count}x Small nodes provide horizontal scaling and load balancing for {concurrent_users} concurrent users."
    elif model_tier in ["deep_reasoning", "70b_quantized", "70b"]:
        if concurrent_users <= 35:
            node_size = "medium"
            node_count = 1
            reasoning = "Medium (192 GB GPU, 48 vCPU) runs 70B AWQ at ~1,000 tokens/sec. Delivers complex compliance/reasoning answers in ~1.6s for up to 35-40 concurrent streams."
        else:
            node_size = "medium"
            node_count = max(2, int(concurrent_users / 35) + 1)
            reasoning = f"{node_count}x Medium nodes for high-throughput enterprise 70B reasoning."
    elif model_tier in ["flagship", "70b_full", "multimodal"]:
        node_size = "large"
        node_count = max(1, int(concurrent_users / 80) + 1)
        reasoning = "Large (687 GB GPU, 96 vCPU) delivers ~2,500 tokens/sec for unquantized 70B FP16 models and multi-modal vision workloads."
    else:  # enterprise_cluster
        node_size = "extra_large"
        node_count = max(1, int(concurrent_users / 150) + 1)
        reasoning = "Extra Large (687 GB GPU, 192 vCPU) delivers ~5,000+ tokens/sec for mission-critical enterprise clusters."

    # Compute time to embed total dataset on chosen node
    perf = NODE_THROUGHPUT[node_size]
    total_embed_rate = perf["embed_docs_sec"] * node_count
    hours_to_embed_all = (total_vectors / (total_embed_rate * 3600.0)) if total_vectors > 0 else 0.0

    # 7. Run Pricing Estimator on ongoing steady-state
    estimator = CapellaAIPricingEstimator(
        deployments=[ModelDeploymentConfig(node_size_key=node_size, node_count=node_count, active_hours_per_month=730)],
        processing=DataProcessingConfig(
            structured_gib_per_month=monthly_struct_gib,
            unstructured_pages_per_month=monthly_unstruct_1k_units,
        ),
        addons=AddonConfig(enable_caching_async=enable_caching, data_transfer_fee_pct=7.5),
    )
    calc_res = estimator.calculate()

    return {
        "customer_data_summary": {
            "structured_database_records": int(structured_records),
            "structured_gib": round(structured_gib, 2),
            "total_documents_pages": int(pages),
            "total_vectors_to_index": int(total_vectors),
            "vector_dimensions": vector_dim,
            "couchbase_vector_ram_needed_gb": round(vector_index_ram_gb, 2),
            "monthly_growth_rate": f"{monthly_delta_pct}%",
        },
        "hardware_throughput_capacity": {
            "node_size": MODEL_NODE_PRICING[node_size]["name"],
            "node_count": node_count,
            "embedding_throughput_docs_per_sec": total_embed_rate,
            "time_to_embed_entire_dataset_hours": round(hours_to_embed_all, 2),
            "generational_token_speed_pool": perf["gen_tokens_sec"] * node_count,
            "avg_250_token_answer_latency_sec": perf["avg_250t_latency_sec"],
            "max_concurrent_active_streams": perf["max_concurrent"] * node_count,
        },
        "initial_one_time_ingestion": {
            "credits": round(initial_ingestion_credits, 2),
            "enterprise_usd": round(initial_ingestion_usd, 2),
        },
        "sizing_recommendation": {
            "recommended_node_size": MODEL_NODE_PRICING[node_size]["name"],
            "recommended_node_count": node_count,
            "gpu_vram_total_gb": MODEL_NODE_PRICING[node_size]["gpu_gb"] * node_count,
            "vcpu_total": MODEL_NODE_PRICING[node_size]["vcpu"] * node_count,
            "sizing_rationale": reasoning,
        },
        "ongoing_monthly_pricing": calc_res,
    }


def print_sizing_report(res: Dict):
    print("=" * 90)
    print("        CAPELLA AI DATA PLANE — HARDWARE THROUGHPUT & WORKLOAD SIZING REPORT")
    print("=" * 90)
    
    cds = res["customer_data_summary"]
    print("\n[1] DATA REPOSITORY & VECTOR INDEX SIZING:")
    print(f"  - Structured Database Records:{cds['structured_database_records']:,} records ({cds['structured_gib']} GiB)")
    print(f"  - Unstructured Document Pages:{cds['total_documents_pages']:,} pages")
    print(f"  - Total Vectors to Index:     {cds['total_vectors_to_index']:,} vectors (@ {cds['vector_dimensions']} dimensions)")
    print(f"  - Couchbase Vector RAM Sizing:{cds['couchbase_vector_ram_needed_gb']} GB (HNSW Index Memory in Couchbase Search)")
    print(f"  - Monthly Ingestion Delta:    {cds['monthly_growth_rate']} new data/month")

    hw = res["hardware_throughput_capacity"]
    print("\n[2] HARDWARE THROUGHPUT & PERFORMANCE BENCHMARK:")
    print(f"  - Embedding Ingestion Speed:  {hw['embedding_throughput_docs_per_sec']:,} docs/sec ({hw['embedding_throughput_docs_per_sec']*3600:,.0f} docs/hr)")
    print(f"  - Time to Vectorize Dataset:  {hw['time_to_embed_entire_dataset_hours']} hours (initial full index backfill)")
    print(f"  - Generation Output Speed:    ~{hw['generational_token_speed_pool']:,} tokens/sec total cluster pool")
    print(f"  - Response Latency (250 tok): ~{hw['avg_250_token_answer_latency_sec']} seconds per answer")
    print(f"  - Concurrency Capacity:       {hw['max_concurrent_active_streams']} simultaneous streams without queue delay")

    init = res["initial_one_time_ingestion"]
    print("\n[3] ONE-TIME INITIAL INGESTION (WORKFLOW LIST PRICE):")
    print(f"  - One-Time Ingestion Credits: {init['credits']:,.2f} credits")
    print(f"  - One-Time Ingestion USD:     ${init['enterprise_usd']:,.2f} (Enterprise List; Free if native in Capella)")

    rec = res["sizing_recommendation"]
    print("\n[4] RECOMMENDED CAPELLA AI COMPUTE ARCHITECTURE:")
    print(f"  - Sizing Selection:           {rec['recommended_node_count']}x {rec['recommended_node_size']} Node(s)")
    print(f"  - Dedicated Compute Specs:    {rec['gpu_vram_total_gb']} GB VRAM | {rec['vcpu_total']} vCPU")
    print(f"  - Sizing Rationale:           {rec['sizing_rationale']}")

    calc = res["ongoing_monthly_pricing"]
    print("\n[5] ONGOING MONTHLY RUN-RATE (STEADY-STATE 730h):")
    print(f"  - Monthly Capella Credits:    {calc['summary']['monthly_credits']:,.2f} credits / month")
    print(f"  - Monthly Enterprise List:    ${calc['summary']['monthly_enterprise_usd']:,.2f} / month")
    print(f"  - Annualized Commitment:      ${calc['summary']['annual_enterprise_usd']:,.2f} / year")
    print("=" * 90)


def interactive_mode():
    print("\n--- Capella AI Data Plane Interactive Sizing Wizard ---")
    print("Select Mode:")
    print("  1. Size Directly from Customer Data (Pages/GB & Users) [RECOMMENDED]")
    print("  2. Manual Node Selection & Rate Calculator")
    mode_choice = input("Enter choice (1 or 2, default 1): ").strip() or "1"

    if mode_choice == "1":
        pages_input = input("Total PDF / Document Pages (e.g. 100000 for 100k pages, or 0 if GB): ").strip() or "100000"
        pages = float(pages_input)
        
        struct_input = input("External Structured Data in GiB (default 100): ").strip() or "100"
        struct_gib = float(struct_input)
        
        delta_input = input("Monthly New Data Delta % (default 10%): ").strip() or "10"
        delta_pct = float(delta_input)
        
        print("\nSelect AI Model Intelligence Requirement:")
        print("  1. Fast Assistant / Standard RAG (Llama 3 8B / Mistral 7B) [DEFAULT]")
        print("  2. Deep Reasoning & Compliance Summarization (Llama 3 70B Quantized)")
        print("  3. Flagship Unquantized Multi-Modal / 70B Full Precision")
        print("  4. Embeddings & Semantic Search Only")
        model_map = {"1": "fast_assistant", "2": "deep_reasoning", "3": "flagship", "4": "embedding_only"}
        m_choice = input("Enter choice (1-4, default 1): ").strip() or "1"
        selected_model = model_map.get(m_choice, "fast_assistant")

        users_input = input("Target Concurrent Users / QPS (default 10): ").strip() or "10"
        users = int(users_input)

        sizing_res = size_from_customer_data(
            total_pages=pages,
            structured_gib=struct_gib,
            monthly_delta_pct=delta_pct,
            model_tier=selected_model,
            concurrent_users=users,
        )
        print_sizing_report(sizing_res)
        return

    # Manual node wizard
    print("\nSelect Model Node Size:")
    for idx, (k, v) in enumerate(MODEL_NODE_PRICING.items(), 1):
        print(f"  {idx}. {v['name']} ({v['vcpu']} vCPU, {v['gpu_gb']} GB GPU) - {v['credits_per_hr']} cr/hr (${v['enterprise_usd_per_hr']}/hr)")
    
    choice = input("Enter choice (1-5, default 2): ").strip() or "2"
    key_map = list(MODEL_NODE_PRICING.keys())
    selected_key = key_map[int(choice) - 1] if choice.isdigit() and 1 <= int(choice) <= 5 else "small"
    
    count_str = input("Number of nodes (default 1): ").strip() or "1"
    node_count = int(count_str) if count_str.isdigit() else 1
    
    hours_str = input("Active hours per month (default 730 for 24/7): ").strip() or "730"
    hours = float(hours_str)
    
    struct_str = input("External Structured Data Ingestion (GiB/month, default 100): ").strip() or "100"
    struct_gib = float(struct_str)
    
    unstruct_str = input("External Unstructured Data Ingestion (Thousands of Pages/month, e.g. 20 for 20k pages, default 10): ").strip() or "10"
    unstruct_pages = float(unstruct_str)
    
    caching_str = input("Enable Caching & Async Processing? (y/N): ").strip().lower()
    enable_caching = caching_str in ["y", "yes", "true", "1"]
    
    estimator = CapellaAIPricingEstimator(
        deployments=[ModelDeploymentConfig(node_size_key=selected_key, node_count=node_count, active_hours_per_month=hours)],
        processing=DataProcessingConfig(structured_gib_per_month=struct_gib, unstructured_pages_per_month=unstruct_pages),
        addons=AddonConfig(enable_caching_async=enable_caching, data_transfer_fee_pct=7.5),
    )
    result = estimator.calculate()
    print_cli_report(result)


def main():
    parser = argparse.ArgumentParser(description="Capella AI Data Plane Sizing & Pricing Engine (AWS us-east-1)")
    
    # Sizing from raw customer data
    parser.add_argument("--size-from-data", action="store_true", help="Auto-size node and ingestion from customer data volume and concurrency")
    parser.add_argument("--db-records", type=int, help="Total database records to ingest and vectorize (e.g. 5000000 for 5M records)")
    parser.add_argument("--db-record-kb", type=float, default=2.0, help="Average size per database record in KB (default 2.0 KB)")
    parser.add_argument("--pdf-pages", type=float, help="Total PDF / document pages (e.g. 100000)")
    parser.add_argument("--raw-pdf-gib", type=float, default=0.0, help="Raw GiB of PDF documents (used if --pdf-pages not given)")
    parser.add_argument("--monthly-delta-pct", type=float, default=10.0, help="Monthly new data ingestion delta percentage (default 10%%)")
    parser.add_argument("--model-tier", choices=["embedding-only", "fast-assistant", "deep-reasoning", "flagship", "enterprise-cluster"], default="fast-assistant", help="Model intelligence tier")
    parser.add_argument("--concurrency", type=int, default=10, help="Target concurrent users or peak QPS (default 10)")
    parser.add_argument("--vector-dim", type=int, default=1536, help="Vector embedding dimensions (default 1536)")

    # Manual node overrides
    parser.add_argument("--node-size", choices=list(MODEL_NODE_PRICING.keys()) + ["extra-small", "extra-large"], default="small", help="Model compute node size")
    parser.add_argument("--node-count", type=int, default=1, help="Number of model compute nodes")
    parser.add_argument("--hours", type=float, default=HOURS_PER_MONTH, help="Operating hours per month (default 730)")
    parser.add_argument("--structured-gib", type=float, default=0.0, help="Monthly external structured data in GiB")
    parser.add_argument("--unstructured-pages", type=float, default=0.0, help="Monthly external unstructured data in 1K pages (e.g. 50 = 50,000 pages)")
    parser.add_argument("--caching", action="store_true", help="Enable Caching and Async processing add-on")
    parser.add_argument("--caching-regions", type=int, default=1, help="Number of regions for caching/async fee")
    parser.add_argument("--guardrails", action="store_true", help="Enable Guardrails/Jailbreak security features")
    parser.add_argument("--guardrails-overhead", type=float, default=0.0, help="Guardrails compute overhead percentage (e.g. 10.0 for 10%%)")
    parser.add_argument("--data-transfer-pct", type=float, default=7.5, help="Estimated data transfer fee percentage (default 7.5%%)")
    parser.add_argument("--enterprise-rate", type=float, default=ENTERPRISE_CREDIT_RATE, help="Custom USD conversion rate per credit for Enterprise")
    parser.add_argument("--preset", type=str, help="Load a pre-configured architecture preset (compliance-rag, light-chatbot, enterprise-heavy)")
    parser.add_argument("--interactive", action="store_true", help="Run interactive sizing questionnaire")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
        return

    if args.size_from_data or args.db_records or args.pdf_pages or args.raw_pdf_gib:
        res = size_from_customer_data(
            raw_pdf_gib=args.raw_pdf_gib,
            total_pages=args.pdf_pages,
            structured_gib=args.structured_gib,
            db_records_count=args.db_records,
            db_record_kb=args.db_record_kb,
            monthly_delta_pct=args.monthly_delta_pct,
            model_tier=args.model_tier,
            concurrent_users=args.concurrency,
            vector_dim=args.vector_dim,
            enable_caching=args.caching or True,
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print_sizing_report(res)
        return

    if args.preset:
        estimator = get_preset(args.preset)
    else:
        estimator = CapellaAIPricingEstimator(
            deployments=[
                ModelDeploymentConfig(
                    node_size_key=args.node_size,
                    node_count=args.node_count,
                    active_hours_per_month=args.hours,
                    enable_guardrails=args.guardrails,
                    guardrails_overhead_pct=args.guardrails_overhead,
                )
            ],
            processing=DataProcessingConfig(
                structured_gib_per_month=args.structured_gib,
                unstructured_pages_per_month=args.unstructured_pages,
            ),
            addons=AddonConfig(
                enable_caching_async=args.caching,
                caching_regions=args.caching_regions,
                data_transfer_fee_pct=args.data_transfer_pct,
            ),
            credit_rate_enterprise=args.enterprise_rate,
        )

    res = estimator.calculate()
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print_cli_report(res)


if __name__ == "__main__":
    main()

