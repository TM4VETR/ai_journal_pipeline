import json
from typing import List, Dict

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification

from ner.chunking import pack_by_token_budget


def load_model_and_tokenizer(model_dir: str):
    """
    Load a fine-tuned token classification model and its tokenizer from disk.
    """
    tokenizer = AutoTokenizer.from_pretrained(model_dir, use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(model_dir)

    with open(f"{model_dir}/training_params.json", "r", encoding="utf-8") as f:
        params = json.load(f)

    return model, tokenizer, params




########################################
# Inference core
########################################

@torch.no_grad()
def predict_labels_for_tokens(
    model,
    tokenizer,
    params,
    tokens: List[str],
) -> List[str]:
    """
    Predict one BIO label per input token. Handles long inputs by chunking.
    """
    batch_size = params["training"]["batch_size"]
    max_length = params["preprocessing"]["max_length"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()

    # 1) Pack to chunks
    token_chunks = pack_by_token_budget(tokenizer, tokens, max_length=max_length)

    all_labels: List[str] = []
    # 2) Batched forward passes over chunks
    for start in range(0, len(token_chunks), batch_size):
        batch_tokens = token_chunks[start:start + batch_size]
        # tokenize as a batch of split words
        enc = tokenizer(
            batch_tokens,
            is_split_into_words=True,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt"
        ).to(device)

        logits = model(**enc).logits  # [B, T, C]
        pred_ids = logits.argmax(-1)  # [B, T]

        # 3) Align subwords → words: one label per original word
        for b_idx, word_list in enumerate(batch_tokens):
            word_ids = enc.word_ids(batch_index=b_idx)
            prev_w = None
            labels_this = []
            for t_idx, w_id in enumerate(word_ids):
                if w_id is None or w_id == prev_w:
                    continue
                lab_id = int(pred_ids[b_idx, t_idx].item())
                lab = model.config.id2label.get(lab_id, str(lab_id))
                labels_this.append(lab)
                prev_w = w_id

            # Sanity: ensure alignment length matches words in this chunk
            if len(labels_this) != len(word_list):
                # In rare edge cases (e.g., special tokens), pad with 'O'
                # to preserve alignment.
                if len(labels_this) < len(word_list):
                    labels_this += ["O"] * (len(word_list) - len(labels_this))
                else:
                    labels_this = labels_this[:len(word_list)]

            all_labels.extend(labels_this)

    # Final sanity: labels per token
    if len(all_labels) != len(tokens):
        # fallback pad/trim to keep 1:1 mapping
        if len(all_labels) < len(tokens):
            all_labels += ["O"] * (len(tokens) - len(all_labels))
        else:
            all_labels = all_labels[:len(tokens)]

    return all_labels


def recognize_entities(model, tokenizer, params: Dict, words: List[str]):
    labels = predict_labels_for_tokens(model, tokenizer, params, words)
    return labels
