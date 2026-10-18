"""Optional LLM judge. The model never invents values: it picks a numbered grounded candidate, or copies a span
that we then verify is literally present in fetched text.

Backends (env AGENT_LLM):
  transformers  - load AGENT_MODEL (default /models/qwen) on the GPU (ROCm = torch 'cuda' device) in the resident server
  (vllm         - TODO v1: only if vLLM wheels exist for ROCm 10 / py3.14; transformers is the safe path)
  none          - rule-based only (CPU testing)
"""
from __future__ import annotations
import os, re, threading

_LOCK = threading.Lock()
SYSTEM = ("You extract one exact value from web page excerpts. Answer with the value only, copied exactly as it "
          "appears in the excerpts, with no extra words. If the excerpts do not contain the answer, reply NONE.")


class NoLLM:
    name = "none"

    def pick(self, q, cands):
        return None

    def extract(self, q, passages):
        return None


class HFLLM:
    def __init__(self, path):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        assert torch.cuda.is_available(), "GPU (ROCm) not visible"
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.bfloat16).to("cuda").eval()
        self.name = "transformers:" + os.path.basename(path.rstrip("/"))
        self._gen("ping", 4)  # warm-up kernels

    def _gen(self, user, max_new=48):
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        kw = {}
        try:
            prompt = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                                  enable_thinking=False)
        except TypeError:
            prompt = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        ids = self.tok(prompt, return_tensors="pt").to("cuda")
        with _LOCK, self.torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=max_new, do_sample=False, **kw)
        txt = self.tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
        return re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()

    def pick(self, q, cands):
        lines = [f"[{i+1}] {c['value']}  — context: …{c['ctx'][:300]}…" for i, c in enumerate(cands)]
        r = self._gen(f"Question: {q}\n\nCandidates:\n" + "\n".join(lines) +
                      "\n\nReply with the number of the candidate that answers the question, or 0 if none does.", 6)
        m = re.search(r"\d+", r)
        if m and 1 <= int(m.group(0)) <= len(cands):
            return int(m.group(0)) - 1
        return None

    def extract(self, q, passages):
        ctx = "\n\n".join(f"[Source {i+1}: {u}]\n{t}" for i, (_, t, u) in enumerate(passages))
        r = self._gen(f"Excerpts:\n{ctx}\n\nQuestion: {q}\nValue:", 40)
        r = r.strip().strip('"').strip()
        if not r or r.upper().startswith("NONE") or len(r) > 120:
            return None
        return r


def make():
    kind = os.environ.get("AGENT_LLM", "none").lower()
    if kind in ("transformers", "hf", "auto"):
        path = os.environ.get("AGENT_MODEL", "/models/qwen")
        try:
            return HFLLM(path)
        except Exception as e:
            fb = os.environ.get("AGENT_MODEL_FALLBACK")
            if fb:
                try:
                    return HFLLM(fb)
                except Exception:
                    pass
            print(f"[llm] load failed: {e!r}; rule-based mode", flush=True)
    return NoLLM()
