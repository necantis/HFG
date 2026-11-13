"""
Helper script to generate `notebooks/07_gpu_runtime.ipynb` and `01_gpu_coders.ipynb`
for Agent 07 — GPU Runtime (`run_20261111_002`).
"""

import json
from pathlib import Path


def make_notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11.2",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def md_cell(lines: list[str]) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line if line.endswith("\n") else line + "\n" for line in lines],
    }


def code_cell(lines: list[str]) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line if line.endswith("\n") else line + "\n" for line in lines],
    }


def _repo_bootstrap_lines() -> list[str]:
    """Return notebook lines that locate (or clone in Colab) the HFG repo root and set sys.path/cwd."""
    return [
        "import os",
        "import subprocess",
        "import sys",
        "from pathlib import Path",
        "",
        "def _find_repo_root():",
        "    candidates = [Path.cwd(), *Path.cwd().parents, Path('/content/HFG'), Path('/content')]",
        "    for p in candidates:",
        "        if (p / 'src').is_dir() and ((p / 'pyproject.toml').is_file() or (p / 'data').is_dir()):",
        "            return p.resolve()",
        "    return None",
        "",
        "REPO_ROOT = _find_repo_root()",
        "if REPO_ROOT is None and Path('/content').is_dir():",
        "    target = Path('/content/HFG')",
        "    print(f'Repository not found locally; cloning into {target}...')",
        "    try:",
        "        subprocess.run(['git', 'clone', 'https://github.com/necantis/HFG.git', str(target)], check=True)",
        "        REPO_ROOT = _find_repo_root()",
        "    except subprocess.CalledProcessError as exc:",
        "        raise RuntimeError(",
        "            'Automatic git clone failed. If the repo is private, clone it manually or mount Google Drive and cd into HFG.'",
        "        ) from exc",
        "",
        "if REPO_ROOT is None:",
        "    raise RuntimeError(f'Could not locate HFG repo root from {Path.cwd()}. Clone/open inside HFG first.')",
        "",
        "if str(REPO_ROOT) not in sys.path:",
        "    sys.path.insert(0, str(REPO_ROOT))",
        "os.chdir(REPO_ROOT)",
        "print(f'HFG repo root: {REPO_ROOT}')",
        "",
    ]


def build_07_gpu_runtime_notebook() -> dict:
    return make_notebook(
        [
            md_cell(
                [
                    "# 07 — GPU Runtime & Dual-Coder Server Benchmarking (`Agent 07`)",
                    "",
                    "- **Active Run ID**: `run_20261111_002`",
                    "- **Owner**: Agent 07 (`src/runtime/`, `src/model_runtime.py`)",
                    "- **Canonical Output**: `runs/run_20261111_002/gpu_runtime_config.json` (`gpu_runtime_config_v1`)",
                    "",
                    "## Mission & Architectural Invariants",
                    "1. **Runtime Hardware Detection**: Detect physical accelerator and available VRAM at runtime (never assume hardware from documentation).",
                    "2. **Model-Family Diversity**:",
                    "   - **Coder A**: DeepSeek reasoning-oriented 32B quantized model (`deepseek-ai/DeepSeek-R1-Distill-Qwen-32B-AWQ`).",
                    "   - **Coder B**: Independent multilingual model family (`mistralai/Mistral-Small-3.1-24B-Instruct-2503-AWQ` preferred; `google/gemma-3-27b-it-qat-q4_0-gguf` alternative). Qwen-derived substitutes for Coder B are strictly blocked.",
                    "3. **5-Stage Runtime Benchmark & Empirically Derived Memory Budgets**:",
                    "   - Stage 1: Coder A alone",
                    "   - Stage 2: Coder B alone",
                    "   - Stage 3: Both servers resident",
                    "   - Stage 4: One simultaneous structured request to each",
                    "   - Stage 5: Bounded concurrent requests & failure recovery",
                    "4. **Crash-Safe Atomic Question Checkpoints & Sequential Fallback**:",
                    "   - Every accepted response records `run_id`, `question_id`, `coder_id`, `prompt_hash`, `source_hash`, `model_repo`, `model_revision`, `quantization`, `generation_config`, `raw_response`, `parsed_response`, `schema_status`, `runtime_sec`, and `peak_vram_mb`.",
                ]
            ),
            code_cell(
                [
                    *_repo_bootstrap_lines(),
                    "import json",
                    "from src.runtime import (",
                    "    detect_hardware_profile,",
                    "    build_and_save_runtime_config,",
                    "    validate_model_family_diversity,",
                    "    DEFAULT_CODER_A_SPEC,",
                    "    DEFAULT_CODER_B_MISTRAL_SPEC,",
                    "    ALTERNATIVE_CODER_B_GEMMA_SPEC,",
                    ")",
                    "",
                    "hw = detect_hardware_profile()",
                    "print(json.dumps(hw.to_dict(), indent=2))",
                ]
            ),
            code_cell(
                [
                    "# Validate model-family diversity (Coder A DeepSeek 32B vs Coder B Mistral Small 3.1 24B / Gemma 3 27B)",
                    "validate_model_family_diversity(DEFAULT_CODER_A_SPEC, DEFAULT_CODER_B_MISTRAL_SPEC)",
                    "validate_model_family_diversity(DEFAULT_CODER_A_SPEC, ALTERNATIVE_CODER_B_GEMMA_SPEC)",
                    "print('Model-family diversity verified successfully.')",
                ]
            ),
            code_cell(
                [
                    "# Execute the 5-stage runtime benchmark and derive memory budgets from measurements",
                    "cfg, bench_report, cfg_path = build_and_save_runtime_config(run_id='run_20261111_002')",
                    "print(f'Saved config to: {cfg_path}')",
                    "print(json.dumps(bench_report['derived_memory_budget'], indent=2))",
                ]
            ),
        ]
    )


def build_01_gpu_coders_notebook() -> dict:
    return make_notebook(
        [
            md_cell(
                [
                    "# Stage 01 — GPU Dual-LLM Qualitative Coding & Reconciliation (`01_gpu_coders.ipynb`)",
                    "",
                    "- **Active Run ID**: `run_20261111_002`",
                    "- **Participating Agents**: Agent 07 (`src/runtime/`), Agent 02 (`src/nlp/`), Agent 03 (`src/evidence/`)",
                    "",
                    "## Gate Enforcement",
                    "Full-survey qualitative coding is strictly gated on:",
                    "1. **Agent 01 Gate 1**: `data/normalized/answers_normalized.parquet` ingested and verified.",
                    "2. **Agent 02 Coding Schemas**: `src/subtopic_extraction.py` and `src/value_extraction.py` validated.",
                ]
            ),
            code_cell(
                [
                    *_repo_bootstrap_lines(),
                    "import json",
                    "from src.runtime import (",
                    "    GPURuntimeConfig,",
                    "    DualCoderRuntimeManager,",
                    "    detect_hardware_profile,",
                    ")",
                    "",
                    "config_path = Path('runs/run_20261111_002/gpu_runtime_config.json')",
                    "cfg = GPURuntimeConfig.load(config_path) if config_path.is_file() else GPURuntimeConfig(run_id='run_20261111_002')",
                    "mgr = DualCoderRuntimeManager(config=cfg)",
                    "preflight = mgr.run_hardware_preflight()",
                    "print('Hardware Preflight:', json.dumps(preflight, indent=2))",
                ]
            ),
            code_cell(
                [
                    "# Check upstream Gate 1 (Agent 01) and Gate 2 (Agent 02) before authorizing full-survey coding",
                    "authorized, gate_status = mgr.verify_full_survey_coding_gates(Path.cwd())",
                    "print(f'Full Survey Coding Authorized: {authorized} ({gate_status})')",
                    "if not authorized:",
                    "    print('Skipping full-survey qualitative coding run until Gate 1 and Agent 02 schemas pass.')",
                ]
            ),
        ]
    )


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    nb_dir = root / "notebooks"
    nb_dir.mkdir(parents=True, exist_ok=True)

    nb07 = build_07_gpu_runtime_notebook()
    (nb_dir / "07_gpu_runtime.ipynb").write_text(json.dumps(nb07, indent=2) + "\n", encoding="utf-8")

    nb01 = build_01_gpu_coders_notebook()
    (nb_dir / "01_gpu_coders.ipynb").write_text(json.dumps(nb01, indent=2) + "\n", encoding="utf-8")
    print("Generated notebooks/07_gpu_runtime.ipynb and notebooks/01_gpu_coders.ipynb")
