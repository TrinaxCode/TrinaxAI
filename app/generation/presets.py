"""Preset resolution: Classification + Score → TaskSpec (Phase 8 param table).

This is the single place that decides the decoding regime for a turn. Values
are the concrete Ryzen 7 5700U + 16 GB defaults from the audit (Phase 8),
overridable per-parameter via environment variables so nothing is hard-locked.

Key safety rule (num_predict reservation): the output budget never exceeds
``num_ctx - estimated_prompt_tokens``. When space is tight we shrink the
*response* only after RAG has already been trimmed by the caller, so a long
prompt can never silently truncate the answer without us knowing.
"""

from __future__ import annotations

import os

import config
from app.generation.classifier import classify, strip_attachment_context
from app.generation.scoring import complexity_score
from app.generation.spec import Regime, TaskSpec


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


# ── Base per-regime decoding table (Phase 8) ──────────────────────────────
# num_predict here is the *desired* output ceiling; it is reservation-capped
# against num_ctx in build_task_spec.
_REGIME_BASE: dict[Regime, dict] = {
    Regime.GROUNDED_QA: dict(
        temperature=0.0, top_p=0.9, top_k=40, repeat_penalty=1.05,
        num_predict=1024, use_rag=True,
    ),
    Regime.CODE_GEN: dict(
        temperature=0.15, top_p=0.9, top_k=40, repeat_penalty=1.05,
        num_predict=3072, use_rag=False,
    ),
    Regime.REASONING: dict(
        # Maths / science / proofs / algorithm analysis. Low-but-not-greedy
        # temperature for step-by-step rigor, a generous output budget (exams
        # and multi-part problem sets are long), and — via _select_model — the
        # instruct model the CLI uses, never the small coder.
        temperature=0.2, top_p=0.95, top_k=40, repeat_penalty=1.05,
        num_predict=4096, use_rag=False,
    ),
    Regime.CREATIVE: dict(
        temperature=0.5, top_p=0.95, top_k=60, repeat_penalty=1.1,
        num_predict=5120, use_rag=False,
    ),
    Regime.EXPLAIN: dict(
        temperature=0.4, top_p=0.9, top_k=40, repeat_penalty=1.15,
        num_predict=2048, use_rag=False,
    ),
}

# Output-budget multipliers by complexity mode (applied to num_predict).
_MODE_PREDICT_SCALE = {
    "trivial": 0.35,
    "normal": 1.0,
    "complex": 1.25,
    "deep": 1.5,
}

# A hard floor so even trivial answers are not clipped.
_MIN_PREDICT = 512


def _select_model(regime: Regime, mode: str, is_code: bool, short: bool) -> str:
    """Choose the model, respecting the existing fleet + env overrides."""
    if short and regime in (Regime.EXPLAIN,) and not is_code:
        return config.MODEL_FAST
    if regime is Regime.REASONING:
        # Maths/science/proofs reason best on the instruct model (the one the
        # CLI uses successfully), NOT the small coder. Hard analysis (deep/
        # complex) earns the larger DEEP slot when the profile provides one.
        return config.MODEL_DEEP if mode == "deep" else config.MODEL_GENERAL
    if regime in (Regime.CODE_GEN, Regime.CREATIVE):
        # Deep/complex code prefers the DEEP slot (== CODE on 16gb, larger elsewhere).
        return config.MODEL_DEEP if mode in ("complex", "deep") else config.MODEL_CODE
    if regime is Regime.GROUNDED_QA:
        # Retrieval already supplies the evidence. A compact grounded answer
        # does not benefit enough from the 9B model to justify its CPU latency;
        # keep the coder for source-code context and use the fast multilingual
        # model for ordinary document QA.
        return config.MODEL_CODE if is_code else config.MODEL_FAST
    # EXPLAIN
    return config.MODEL_CODE if is_code else config.MODEL_GENERAL


def build_task_spec(
    messages: list[dict],
    *,
    model_override: str | None = None,
    has_index: bool = True,
    estimated_prompt_tokens: int = 0,
    retrieval_mode: str = "auto",
) -> TaskSpec:
    """Resolve the full generation plan for a conversation.

    ``model_override`` (from the PWA model selector / API) wins for the *model*
    but the regime and decoding params are still tuned to the task — so a user
    can force qwen2.5-coder:7b and still get the creative regime for a landing.
    ``has_index`` lets grounded-QA fall back to a free regime when no index
    exists. ``estimated_prompt_tokens`` feeds the num_predict reservation.
    """
    chat = [m for m in messages if m.get("role") in {"user", "assistant"}]
    user_turns = [m for m in chat if m.get("role") == "user"]
    current = str(user_turns[-1].get("content", "")) if user_turns else (
        str(chat[-1].get("content", "")) if chat else ""
    )
    history_text = " ".join(str(m.get("content", "")) for m in chat[:-1][-4:])

    if retrieval_mode not in {"auto", "knowledge", "model"}:
        raise ValueError(f"Unsupported retrieval mode: {retrieval_mode}")

    # Route/score on the user's actual instruction, not the appended document
    # dump: a huge attachment must not inflate the complexity score, flip the
    # "short" fast-path, or (via classify) force the code regime. classify()
    # strips the block internally too; we mirror it here for score/short.
    instruction = strip_attachment_context(current)
    has_attachment = instruction != current

    cls = classify(current, history_text)
    score = complexity_score(instruction, cls)
    mode = score.mode

    regime = cls.regime
    if retrieval_mode == "knowledge":
        # A user-selected Knowledge mode is an explicit grounding contract. It
        # must never depend on magic wording in the question.
        regime = Regime.GROUNDED_QA
    elif retrieval_mode == "model" and regime is Regime.GROUNDED_QA:
        # Conversely, Model means no retrieval even when the classifier sees a
        # repository/document phrase.
        regime = Regime.CODE_GEN if cls.is_code else Regime.EXPLAIN
    # If grounded-QA was chosen but there is no index, degrade to a free regime
    # (EXPLAIN or CODE_GEN) so we don't answer "not found in indexed documents"
    # to a question the model could answer from its own knowledge.
    if regime is Regime.GROUNDED_QA and not has_index and retrieval_mode != "knowledge":
        regime = Regime.CODE_GEN if cls.is_code else Regime.EXPLAIN

    base = dict(_REGIME_BASE[regime])

    # A terse instruction ("resume esto") that carries a document is NOT a
    # trivial turn: summarising/analysing the file is real work and must not be
    # downgraded to the tiny FAST model. Only treat as "short" when there is no
    # attachment behind it.
    short = len(instruction.strip()) < 25 and not has_attachment
    model = (model_override or "").strip() or _select_model(
        regime, mode, cls.is_code, short
    )

    # num_ctx policy (Phase 8): generation regimes run WITHOUT RAG, so the whole
    # window is available for prompt+output and we can afford a bigger window
    # than the profile's RAG-tuned default. RAG/grounded stays at the profile
    # value (retrieval already budgets around it). Everything overridable.
    base_ctx = config.NUM_CTX
    if regime in (Regime.CODE_GEN, Regime.CREATIVE, Regime.EXPLAIN, Regime.REASONING):
        # 8192 gives a 7B enough room for a full landing/module/proof on CPU
        # without the latency blow-up of 16k. Reasoning and complex/deep work
        # get the larger window; everything overridable.
        gen_ctx = 8192 if (mode in ("complex", "deep") or regime is Regime.REASONING) else max(base_ctx, 6144)
        base_ctx = max(base_ctx, gen_ctx)
    num_ctx = _env_int("TRINAXAI_GEN_NUM_CTX", base_ctx)

    # Output budget: base × mode scale, floored, then reservation-capped.
    predict_scale = _MODE_PREDICT_SCALE.get(mode, 1.0)
    if regime is Regime.REASONING:
        # Even a short maths/proof question needs room for a full step-by-step
        # solution — never apply the "trivial" (0.35) shrink to reasoning.
        predict_scale = max(predict_scale, 1.0)
    desired = int(base["num_predict"] * predict_scale)
    desired = max(_MIN_PREDICT, desired)
    # Reservation: prompt + output + margin must fit in num_ctx. If the prompt is
    # large we first try to SHRINK the output down to its floor; if even that
    # does not fit, we GROW the window (capped) rather than silently overflow.
    _MARGIN = 256
    _CTX_HARD_MAX = _env_int("TRINAXAI_GEN_NUM_CTX_MAX", 16384)
    if estimated_prompt_tokens > 0:
        room = num_ctx - estimated_prompt_tokens - _MARGIN
        if room < desired:
            # Preserve the full output budget by GROWING the window first (up to
            # the hard cap) — a long prompt should never silently steal tokens
            # from a long answer (e.g. a multi-part exam). Only when even the max
            # window cannot fit prompt+desired do we shrink the output, and never
            # below the floor.
            needed = estimated_prompt_tokens + desired + _MARGIN
            num_ctx = min(_CTX_HARD_MAX, max(num_ctx, needed))
            room = num_ctx - estimated_prompt_tokens - _MARGIN
            desired = max(_MIN_PREDICT, min(desired, room))
    num_predict = _env_int("TRINAXAI_GEN_NUM_PREDICT", desired)

    temperature = _env_float("TRINAXAI_GEN_TEMPERATURE_" + regime.name, base["temperature"])

    # Validation / fix policy (Phase 6/7): only for code-bearing complex work.
    do_validate = regime in (Regime.CODE_GEN, Regime.CREATIVE) and score.total >= 56
    # do_validate already implies score.total >= 56, so one fix pass whenever it is on.
    max_fix = 1 if do_validate else 0
    max_fix = _env_int("TRINAXAI_GEN_MAX_FIX", max_fix)

    # Keep ``True`` for forced Knowledge even without an index. The API layer
    # uses it to return the deterministic NO_INDEX response rather than silently
    # falling back to model knowledge.
    use_rag = base["use_rag"] and (has_index or retrieval_mode == "knowledge")
    # A code/creative task that explicitly references the repo keeps RAG on.
    if retrieval_mode != "model" and "rag_lookup" in cls.categories and has_index:
        use_rag = True

    return TaskSpec(
        model=model,
        regime=regime,
        categories=cls.categories,
        score=score.total,
        num_ctx=num_ctx,
        num_predict=num_predict,
        temperature=temperature,
        top_p=base["top_p"],
        top_k=base["top_k"],
        repeat_penalty=base["repeat_penalty"],
        stop=None,
        retrieval_mode=retrieval_mode,
        use_rag=use_rag,
        validate=do_validate,
        max_fix_passes=max_fix,
    )
