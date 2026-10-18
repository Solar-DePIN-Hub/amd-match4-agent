# AMD AI League - Match 4 (web retrieval). Reference Dockerfile.
# The published image is assembled by scripts/assemble.sh (crane: unmodified base layers + 2 layers, same result
# without pulling the 29 GiB base); this Dockerfile builds the equivalent image where docker + disk are available.
FROM rocm/pytorch:rocm10.0_ubuntu26.04_py3.14_pytorch_release_2.13.0

ENV PYTHONPATH=/opt/deps PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
    AGENT_LLM=transformers AGENT_MODEL=/models/qwen AGENT_BUDGET_S=25

# Weights baked in (no download at eval time): scripts/fetch_model.sh Qwen/Qwen3-4B-Instruct-2507 first (~8 GB).
COPY models/ /models/
COPY app/requirements.txt /app/requirements.txt
# --no-deps: nothing may replace the ROCm torch of the base image
RUN pip install --no-cache-dir --no-deps --target /opt/deps -r /app/requirements.txt \
 && python3 -c "import torch; assert torch.version.hip, 'ROCm torch was replaced!'; print('hip', torch.version.hip)"
COPY app/ /app/
RUN mkdir -p /app/output
WORKDIR /app
# Resident server loads the model once; each graded query is a fresh `python3 /app/app.py ...` that talks to it.
CMD ["python3", "/app/app.py", "--serve"]
