# AMD AI League - Match 4 (web retrieval) - v0
FROM rocm/pytorch:rocm10.0_ubuntu26.04_py3.14_pytorch_release_2.13.0

ENV PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
    AGENT_LLM=transformers AGENT_MODEL=/models/qwen AGENT_BUDGET_S=25 PYTHONPATH=/opt/deps

COPY requirements-gpu.txt /tmp/requirements-gpu.txt
RUN pip install --no-cache-dir --no-deps --target /opt/deps -r /tmp/requirements-gpu.txt \
 && python3 -c "import torch; assert torch.version.hip, 'ROCm torch was replaced!'; print('hip', torch.version.hip)"

# Weights are baked in (no download at eval time). Fetch them first with scripts/fetch_model.sh.
# Qwen3-8B bf16 ~16.4 GB -> image ~46 GB (< 60 GiB). Fallback: Qwen3-4B-Instruct-2507 (~8 GB).
COPY models/qwen /models/qwen

COPY app/ /app/
RUN mkdir -p /app/output

WORKDIR /app
# Resident server loads the model once; each graded query is a fresh `python3 /app/app.py ...` that talks to it.
CMD ["python3", "/app/app.py", "--serve"]
