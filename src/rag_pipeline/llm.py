"""LLM backends returning (answer, confidence).

confidence = geometric-mean probability of the generated answer tokens (exp of mean log-prob),
the signal adaptive retrieval uses to decide the model is unsure.
"""
import math
import os
from dataclasses import dataclass

import requests

MODEL_ID = "meta-llama/Meta-Llama-3-8B-Instruct"

SYSTEM = (
    "You answer factual questions with a short phrase only (a few words), no explanation. "
    "If you do not know the answer, reply exactly: I don't know."
)


def build_messages(question: str, contexts: list[tuple[str, str]] | None = None) -> list[dict]:
    if contexts:
        ctx = "\n\n".join(f"[{t}] {p}" for t, p in contexts)
        user = f"Context:\n{ctx}\n\nUsing the context if relevant, answer the question.\nQuestion: {question}"
    else:
        user = f"Question: {question}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


@dataclass
class Generation:
    answer: str
    confidence: float


class HFBackend:
    """Llama-3-8B-Instruct in 4-bit NF4 via bitsandbytes (fits in 8 GB VRAM)."""

    def __init__(self, model_id: str = MODEL_ID, max_new_tokens: int = 24):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        self.torch = torch
        token = os.getenv("HF_TOKEN")
        self.tok = AutoTokenizer.from_pretrained(model_id, token=token, padding_side="left")
        self.tok.pad_token = self.tok.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            token=token,
            device_map="cuda:0",
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
            ),
        )
        self.model.eval()
        self.max_new_tokens = max_new_tokens
        self.stop_ids = [self.tok.eos_token_id, self.tok.convert_tokens_to_ids("<|eot_id|>")]
        self.name = f"{model_id}@nf4"

    def generate(self, batch: list[list[dict]]) -> list[Generation]:
        torch = self.torch
        prompts = [self.tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True) for m in batch]
        enc = self.tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda:0")
        with torch.inference_mode():
            out = self.model.generate(
                **enc, max_new_tokens=self.max_new_tokens, do_sample=False, temperature=None, top_p=None,
                eos_token_id=self.stop_ids, pad_token_id=self.tok.eos_token_id,
                output_scores=True, return_dict_in_generate=True,
            )
        new_tokens = out.sequences[:, enc["input_ids"].shape[1]:]
        logprobs = self.model.compute_transition_scores(out.sequences, out.scores, normalize_logits=True)
        results = []
        for toks, lps in zip(new_tokens, logprobs):
            keep = [i for i, t in enumerate(toks.tolist()) if t not in self.stop_ids]
            answer = self.tok.decode(toks[keep], skip_special_tokens=True).strip()
            conf = math.exp(lps[keep].float().mean().item()) if keep else 0.0
            results.append(Generation(answer, conf))
        return results


class OllamaBackend:
    """Fallback: local Ollama server (`ollama pull llama3:8b`). Needs Ollama >= 0.12 for logprobs."""

    def __init__(self, model: str = "llama3:8b", url: str = "http://localhost:11434"):
        self.model, self.url, self.name = model, url, f"ollama/{model}"

    def generate(self, batch: list[list[dict]]) -> list[Generation]:
        results = []
        for messages in batch:
            r = requests.post(f"{self.url}/api/chat", timeout=120, json={
                "model": self.model, "messages": messages, "stream": False, "logprobs": True,
                "options": {"temperature": 0, "num_predict": 24},
            })
            r.raise_for_status()
            body = r.json()
            lps = [x["logprob"] for x in body.get("logprobs") or []]
            conf = math.exp(sum(lps) / len(lps)) if lps else float("nan")
            results.append(Generation(body["message"]["content"].strip(), conf))
        return results


def load_backend(name: str | None = None):
    name = name or os.getenv("LLM_BACKEND", "hf")
    return OllamaBackend() if name == "ollama" else HFBackend()
