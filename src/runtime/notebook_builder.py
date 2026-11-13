"""
Helper script to generate `notebooks/07_gpu_runtime.ipynb` and `notebooks/01_gpu_coders.ipynb`
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
    """Locate or clone the HFG repository in Colab, honor optional HFG_BRANCH/HFG_COMMIT, and set sys.path/cwd."""
    return [
        "import importlib.util",
        "import os",
        "import subprocess",
        "import sys",
        "from pathlib import Path",
        "",
        "HFG_BRANCH = os.environ.get('HFG_BRANCH', 'main')",
        "HFG_COMMIT = os.environ.get('HFG_COMMIT', '').strip()",
        "HFG_GIT_PULL = os.environ.get('HFG_GIT_PULL', '0') == '1'",
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
        "    print(f'Repository not found locally; cloning branch {HFG_BRANCH} into {target}...')",
        "    try:",
        "        subprocess.run(['git', 'clone', '--branch', HFG_BRANCH, 'https://github.com/necantis/HFG.git', str(target)], check=True)",
        "        if HFG_COMMIT:",
        "            subprocess.run(['git', '-C', str(target), 'checkout', HFG_COMMIT], check=True)",
        "        REPO_ROOT = _find_repo_root()",
        "    except subprocess.CalledProcessError as exc:",
        "        raise RuntimeError(",
        "            'Automatic git clone failed. If the repo is private, clone it manually or mount Google Drive and cd into HFG.'",
        "        ) from exc",
        "elif REPO_ROOT is not None and (HFG_GIT_PULL or HFG_COMMIT):",
        "    subprocess.run(['git', '-C', str(REPO_ROOT), 'fetch', '--all', '--prune'], check=True)",
        "    if HFG_COMMIT:",
        "        subprocess.run(['git', '-C', str(REPO_ROOT), 'checkout', HFG_COMMIT], check=True)",
        "    elif HFG_GIT_PULL:",
        "        subprocess.run(['git', '-C', str(REPO_ROOT), 'checkout', HFG_BRANCH], check=True)",
        "        subprocess.run(['git', '-C', str(REPO_ROOT), 'pull', '--ff-only', 'origin', HFG_BRANCH], check=True)",
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


def _colab_dependency_check_lines() -> list[str]:
    """Ensure Colab runtime dependencies (vllm, huggingface_hub, pandas, pyarrow, pydantic, pyyaml) are installed."""
    return [
        "_REQUIRED_MODULES = {",
        "    'vllm': 'vllm>=0.7.0',",
        "    'huggingface_hub': 'huggingface_hub>=0.25.0',",
        "    'pydantic': 'pydantic>=2.0.0',",
        "    'pandas': 'pandas>=2.0.0',",
        "    'pyarrow': 'pyarrow>=14.0.0',",
        "    'yaml': 'pyyaml>=6.0.0',",
        "}",
        "_missing_pkgs = [pkg for mod, pkg in _REQUIRED_MODULES.items() if importlib.util.find_spec(mod) is None]",
        "if _missing_pkgs and (Path('/content').is_dir() or os.environ.get('HFG_AUTO_INSTALL') == '1') and os.environ.get('HFG_SKIP_PIP_INSTALL') != '1':",
        "    print(f'Installing missing Colab runtime dependencies: {_missing_pkgs}')",
        "    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *_missing_pkgs], check=True)",
        "else:",
        "    print('Dependency check:', {m: (importlib.util.find_spec(m) is not None) for m in _REQUIRED_MODULES})",
        "",
    ]


def build_07_gpu_runtime_notebook() -> dict:
    return make_notebook(
        [
            md_cell(
                [
                    "# 07 — GPU Runtime & Dual-Coder 5-Stage Live Benchmark (`Agent 07`)",
                    "",
                    "- **Active Run ID**: `run_20261111_002`",
                    "- **Owner**: Agent 07 (`src/runtime/`, `src/model_runtime.py`)",
                    "- **Canonical Outputs**: `runs/run_20261111_002/gpu_runtime_config.json` & `runs/run_20261111_002/gpu_runtime_benchmark.json`",
                    "",
                    "## Mission & Architectural Invariants",
                    "1. **Runtime Hardware Detection**: Detect the physical accelerator and available VRAM at runtime (never assume hardware from documentation).",
                    "2. **Model-Family Diversity & Exact Repo Provenance**:",
                    "   - **Coder A**: DeepSeek reasoning-oriented 32B quantized model (`deepseek-ai/DeepSeek-R1-Distill-Qwen-32B` derivative).",
                    "   - **Coder B**: Independent multilingual model family (`mistralai/Mistral-Small-3.1-24B-Instruct-2503` quantized preferred; `google/gemma-3-27b-it` quantized alternative). Qwen-derived substitutes for Coder B are strictly blocked.",
                    "3. **Real 5-Stage vLLM Benchmark & Empirically Derived Memory Budgets**:",
                    "   - Stage 1: Coder A alone",
                    "   - Stage 2: Coder B alone",
                    "   - Stage 3: Both localhost vLLM servers resident",
                    "   - Stage 4: One simultaneous structured request to each",
                    "   - Stage 5: Bounded concurrent requests & crash/failure recovery isolation",
                ]
            ),
            code_cell(
                [
                    *_repo_bootstrap_lines(),
                    *_colab_dependency_check_lines(),
                ]
            ),
            code_cell(
                [
                    "import json",
                    "import shutil",
                    "from src.runtime import (",
                    "    GPURuntimeConfig,",
                    "    detect_hardware_profile,",
                    "    resolve_dual_coder_specs,",
                    "    validate_model_family_diversity,",
                    "    build_and_save_runtime_config,",
                    ")",
                    "",
                    "if shutil.which('nvidia-smi'):",
                    "    subprocess.run(['nvidia-smi'], check=False)",
                    "",
                    "hw = detect_hardware_profile()",
                    "print('Detected Hardware Profile:')",
                    "print(json.dumps(hw.to_dict(), indent=2))",
                    "",
                    "if not hw.gpu_available and os.environ.get('HFG_ALLOW_CPU_DEMO') != '1':",
                    "    raise RuntimeError(",
                    "        'No physical NVIDIA GPU detected. Switch Google Colab Runtime -> Change runtime type -> GPU before running 07_gpu_runtime.ipynb.'",
                    "    )",
                ]
            ),
            code_cell(
                [
                    "# Resolve exact Hugging Face model repositories, pinned commit SHAs, and verify model-family diversity",
                    "cfg_probe = GPURuntimeConfig(run_id='run_20261111_002')",
                    "resolution = resolve_dual_coder_specs(cfg_probe, verify_remote=True, verify_tokenizer=False)",
                    "validate_model_family_diversity(cfg_probe.coder_a_spec, cfg_probe.coder_b_spec)",
                    "print('Verified Coder A:', cfg_probe.coder_a_spec.model_repo, '@', cfg_probe.coder_a_spec.model_revision)",
                    "print('Verified Coder B:', cfg_probe.coder_b_spec.model_repo, '@', cfg_probe.coder_b_spec.model_revision)",
                    "print(json.dumps({'audit_a': resolution['audit_a'], 'audit_b': resolution['audit_b']}, indent=2))",
                ]
            ),
            code_cell(
                [
                    "# Execute the 5-stage live GPU benchmark and derive memory budgets from measurements",
                    "cfg, bench_report, cfg_path = build_and_save_runtime_config(",
                    "    base_dir=REPO_ROOT,",
                    "    run_id='run_20261111_002',",
                    "    resolve_remote_models=True,",
                    "    verify_tokenizer=False,",
                    "    startup_timeout_sec=900.0,",
                    ")",
                    "print(f'Saved runtime config: {cfg_path}')",
                    "print('live_gpu_benchmark_status =', cfg.live_gpu_benchmark_status)",
                    "print('execution_mode =', cfg.execution_mode.value)",
                    "print('\\n=== 5-Stage Benchmark Summary ===')",
                    "print(json.dumps(bench_report['stages'], indent=2))",
                    "print('\\n=== Derived Memory Budget ===')",
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
                    "# Stage 01 — Production GPU Dual-LLM Qualitative Coding (`01_gpu_coders.ipynb`)",
                    "",
                    "- **Active Run ID**: `run_20261111_002`",
                    "- **Runtime Owner**: Agent 07 (`src/runtime/model_runtime.py`, `src/runtime/dual_coder_runner.py`)",
                    "- **Upstream Contracts**: Agent 01 (`answers_normalized.parquet`), Agent 02 (`src/nlp/`)",
                    "- **Outputs**: Unreconciled `data/processed/coder_a_outputs.json` & `data/processed/coder_b_outputs.json` + atomic checkpoint WAL under `.checkpoints/gpu_coder_wal/`",
                    "",
                    "## Execution Preconditions",
                    "1. **Gate 1 (`verify_gate_1`)** and **Agent 02 (`verify_full_survey_coding_gates`)** pass.",
                    "2. Live physical GPU attached (`hw.gpu_available == True`).",
                    "3. Live 5-stage benchmark passed (`notebooks/07_gpu_runtime.ipynb` -> `runs/run_20261111_002/gpu_runtime_benchmark.json`).",
                    "4. Does **not** run Agent 03 reconciliation; prepares verified unreconciled Coder A & Coder B evidence for `notebooks/04_validation.ipynb`.",
                ]
            ),
            code_cell(
                [
                    *_repo_bootstrap_lines(),
                    *_colab_dependency_check_lines(),
                ]
            ),
            code_cell(
                [
                    "import json",
                    "from src.hardcoding_scanner import verify_gate_1",
                    "from src.ingest.ingestion import ACTIVE_RUN_ID",
                    "from src.runtime import (",
                    "    GPURuntimeConfig,",
                    "    DualCoderRuntimeManager,",
                    "    validate_model_family_diversity,",
                    ")",
                    "",
                    "config_path = REPO_ROOT / 'runs' / ACTIVE_RUN_ID / 'gpu_runtime_config.json'",
                    "bench_path = REPO_ROOT / 'runs' / ACTIVE_RUN_ID / 'gpu_runtime_benchmark.json'",
                    "cfg = GPURuntimeConfig.load(config_path) if config_path.is_file() else GPURuntimeConfig(run_id=ACTIVE_RUN_ID)",
                    "mgr = DualCoderRuntimeManager(config=cfg)",
                    "preflight = mgr.run_hardware_preflight()",
                    "print('Hardware Preflight:', json.dumps(preflight, indent=2))",
                    "",
                    "gate1 = verify_gate_1(base_dir=REPO_ROOT, run_id=ACTIVE_RUN_ID)",
                    "gate2_ok, gate2_status = mgr.verify_full_survey_coding_gates(REPO_ROOT)",
                    "validate_model_family_diversity(cfg.coder_a_spec, cfg.coder_b_spec)",
                    "print('Gate 1:', gate1['status'], '| Gate 2:', gate2_ok, gate2_status)",
                    "print('Coder A:', cfg.coder_a_spec.model_repo, '@', cfg.coder_a_spec.model_revision)",
                    "print('Coder B:', cfg.coder_b_spec.model_repo, '@', cfg.coder_b_spec.model_revision)",
                    "",
                    "if gate1['status'] != 'PASS' or not gate2_ok:",
                    "    raise RuntimeError(f'Upstream coding gates failed: gate1={gate1[\"status\"]}, gate2={gate2_status}')",
                    "if not mgr.hardware.gpu_available:",
                    "    raise RuntimeError('No physical GPU detected. Attach a Colab GPU runtime before running 01_gpu_coders.ipynb.')",
                    "if cfg.live_gpu_benchmark_status != 'EXECUTED_LIVE_GPU' or not bench_path.is_file():",
                    "    raise RuntimeError('Run notebooks/07_gpu_runtime.ipynb first so the 5-stage live GPU benchmark passes.')",
                ]
            ),
            code_cell(
                [
                    "# Execute independent Coder A and Coder B full-corpus Phase 1 + Phase 2 qualitative coding",
                    "from src.runtime import run_dual_coder_production",
                    "",
                    "prod_result = run_dual_coder_production(",
                    "    base_dir=REPO_ROOT,",
                    "    run_id=ACTIVE_RUN_ID,",
                    "    require_live_gpu=True,",
                    "    startup_timeout_sec=900.0,",
                    ")",
                    "print('=== Production Dual-Coder Execution Summary ===')",
                    "print(json.dumps(prod_result, indent=2))",
                ]
            ),
            code_cell(
                [
                    "# Evaluate Agent 11 PipelineOrchestrator & verify Agent 03 release readiness (without running Agent 03)",
                    "from src.pipeline.orchestrator import PipelineOrchestrator",
                    "",
                    "orch_report = PipelineOrchestrator(base_dir=REPO_ROOT, run_id=ACTIVE_RUN_ID).evaluate(write_log=True)",
                    "print('Pipeline States:', json.dumps(orch_report.states, indent=2))",
                    "print('Agent 03 Release Checklist:', json.dumps(orch_report.agent_03_release_checklist, indent=2))",
                    "print(f'AGENT_03_RELEASE = {orch_report.agent_03_release_decision.value}')",
                    "if orch_report.blocking_reasons:",
                    "    print('Blocking reasons:', orch_report.blocking_reasons)",
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
