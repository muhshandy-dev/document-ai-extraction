"""Research comparison T: fine-tuned LayoutLM (microsoft/layoutlm-base-uncased, MIT licence).

Python only; the website does not ship this model (about 450 MB). It labels
the same words with the same 13 labels as N, and its word probabilities go
through the same assembler and review rule, so H, N and T differ only in the
word labeller. Each word is labelled by its first sub-token. Pages longer
than MAX_LEN tokens are cut; words past the cut are labelled "O" and the
number of cut pages is reported.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

from .cord import LABELS
from .layout import Page

MODEL_NAME = "microsoft/layoutlm-base-uncased"
MAX_LEN = 512


def _box(v: float, size: float) -> int:
    if size <= 0:
        return 0
    return max(0, min(1000, int(1000 * v / size)))


class LayoutLMTagger:
    def __init__(self, model, tokenizer, labels: list[str] = list(LABELS)):  # noqa: B006
        self.model = model
        self.tokenizer = tokenizer
        self.labels = labels
        self.index = {lab: i for i, lab in enumerate(labels)}
        self.meta: dict = {"model": MODEL_NAME, "max_len": MAX_LEN}
        self.truncated = 0

    def encode(self, page: Page, gold: list[str] | None = None) -> tuple[dict, list[int]]:
        tok = self.tokenizer
        w_, h_ = page.width, page.height
        ids = [tok.cls_token_id]
        boxes = [[0, 0, 0, 0]]
        labs = [-100]
        first: list[int] = []
        for i, w in enumerate(page.words):
            pieces = tok.tokenize(w.text) or [tok.unk_token]
            if len(ids) + len(pieces) > MAX_LEN - 1:
                break
            x0, x1 = sorted((_box(w.x0, w_), _box(w.x1, w_)))
            y0, y1 = sorted((_box(w.y0, h_), _box(w.y1, h_)))
            first.append(len(ids))
            for j, piece in enumerate(pieces):
                ids.append(tok.convert_tokens_to_ids(piece))
                boxes.append([x0, y0, x1, y1])
                labs.append(self.index.get(gold[i], 0) if gold is not None and j == 0 else -100)
        ids.append(tok.sep_token_id)
        boxes.append([1000, 1000, 1000, 1000])
        labs.append(-100)
        return {"input_ids": ids, "bbox": boxes, "labels": labs}, first

    def predict_page(self, page: Page) -> tuple[list[str], list[float]]:
        import torch

        n = len(page.words)
        if n == 0:
            return [], []
        enc, first = self.encode(page)
        if len(first) < n:
            self.truncated += 1
        self.model.eval()
        with torch.no_grad():
            out = self.model(
                input_ids=torch.tensor([enc["input_ids"]]),
                bbox=torch.tensor([enc["bbox"]]),
                attention_mask=torch.ones(1, len(enc["input_ids"]), dtype=torch.long),
            )
            probs = torch.softmax(out.logits[0], dim=-1)
        labels = ["O"] * n
        conf = [1.0] * n
        for wi, ti in enumerate(first):
            p = probs[ti]
            k = int(torch.argmax(p))
            labels[wi] = self.labels[k]
            conf[wi] = float(p[k])
        return labels, conf


def _batches(encoded: list[dict], size: int, rnd: random.Random) -> list[list[dict]]:
    order = list(range(len(encoded)))
    rnd.shuffle(order)
    return [[encoded[i] for i in order[k : k + size]] for k in range(0, len(order), size)]


def _collate(batch: list[dict], pad_id: int):
    import torch

    n = max(len(e["input_ids"]) for e in batch)
    ids, boxes, labs, mask = [], [], [], []
    for e in batch:
        pad = n - len(e["input_ids"])
        ids.append(e["input_ids"] + [pad_id] * pad)
        boxes.append(e["bbox"] + [[0, 0, 0, 0]] * pad)
        labs.append(e["labels"] + [-100] * pad)
        mask.append([1] * len(e["input_ids"]) + [0] * pad)
    return (
        torch.tensor(ids),
        torch.tensor(boxes),
        torch.tensor(labs),
        torch.tensor(mask),
    )


def train_layoutlm(
    pages: list[Page],
    gold: list[list[str]],
    select: Callable[[LayoutLMTagger], float],
    epochs: int = 4,
    lr: float = 5e-5,
    batch_size: int = 8,
    seed: int = 0,
    model=None,
    tokenizer=None,
    log: Callable[[str], None] = print,
) -> tuple[LayoutLMTagger, list[dict]]:
    """Fine-tune and keep the epoch with the best validation score from `select`."""
    import copy

    import torch
    from transformers import get_linear_schedule_with_warmup

    torch.manual_seed(seed)
    rnd = random.Random(seed)
    if tokenizer is None:
        from transformers import LayoutLMTokenizerFast

        tokenizer = LayoutLMTokenizerFast.from_pretrained(MODEL_NAME)
    if model is None:
        from transformers import LayoutLMForTokenClassification

        model = LayoutLMForTokenClassification.from_pretrained(MODEL_NAME, num_labels=len(LABELS))
    tagger = LayoutLMTagger(model, tokenizer)
    encoded = [tagger.encode(p, g)[0] for p, g in zip(pages, gold, strict=True) if p.words]
    steps = epochs * math.ceil(len(encoded) / batch_size)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)
    history: list[dict] = []
    best_score, best_state = -math.inf, None
    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        batches = _batches(encoded, batch_size, rnd)
        for batch in batches:
            ids, boxes, labs, mask = _collate(batch, tokenizer.pad_token_id)
            out = model(input_ids=ids, bbox=boxes, attention_mask=mask, labels=labs)
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            total += float(out.loss)
        score = select(tagger)
        history.append({"epoch": epoch, "train_loss": round(total / max(1, len(batches)), 4), "selection_score": score})
        log(str(history[-1]))
        if score > best_score:
            best_score, best_state = score, copy.deepcopy(model.state_dict())
    assert best_state is not None
    model.load_state_dict(best_state)
    tagger.meta.update(
        epochs=epochs,
        lr=lr,
        batch_size=batch_size,
        seed=seed,
        chosen_epoch=max(history, key=lambda h: (h["selection_score"], -h["epoch"]))["epoch"],
        n_train_pages=len(encoded),
    )
    return tagger, history
