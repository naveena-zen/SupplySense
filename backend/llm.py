import os
import json
import logging
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from backend.config import ANTHROPIC_API_KEY, GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

# Groq model fallback chain — primary is set in .env, fallback is smaller/cheaper
GROQ_FALLBACK_MODELS = [
    GROQ_MODEL,                       # primary (e.g. llama-3.3-70b-versatile)
    "llama-3.1-8b-instant",            # smaller fallback
    "qwen/qwen3.6-27b",               # secondary fallback (active as of July 2026)
]

# Initialize clients lazily or conditionally
anthropic_client = None
openai_client = None

if ANTHROPIC_API_KEY:
    logger.info("Initializing Anthropic Claude client")
    anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
elif GROQ_API_KEY:
    logger.info("Initializing Groq OpenAI-compatible client")
    openai_client = AsyncOpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
else:
    logger.warning("No LLM keys found in environment. LLM calls will fail.")

async def call_llm(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False
) -> str:
    """
    Call the available LLM (Claude or Groq Llama) with a system prompt and user prompt.
    Returns the string completion.
    Tries Groq fallback models if the primary model hits rate limits.
    """
    global anthropic_client, openai_client

    # Re-check env dynamically in case keys were loaded/added later
    if not anthropic_client and os.getenv("ANTHROPIC_API_KEY"):
        anthropic_client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    if not openai_client and not anthropic_client and os.getenv("GROQ_API_KEY"):
        openai_client = AsyncOpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1"
        )

    if anthropic_client:
        try:
            logger.info("Dispatching call to Claude")
            # Anthropic call
            message = await anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            # Extracted content
            content = message.content[0].text
            return content.strip()
        except Exception as e:
            logger.error(f"Claude API failed: {e}. Attempting fallback to Groq...")
            # Fallback if both keys are present
            if os.getenv("GROQ_API_KEY"):
                openai_client = AsyncOpenAI(
                    api_key=os.getenv("GROQ_API_KEY"),
                    base_url="https://api.groq.com/openai/v1"
                )

    if openai_client:
        last_error = None
        groq_key = os.getenv("GROQ_API_KEY", GROQ_API_KEY)
        primary_model = os.getenv("GROQ_MODEL", GROQ_MODEL)
        
        # Build model chain: primary first, then fallbacks (excluding primary if already in list)
        models_to_try = [primary_model] + [m for m in GROQ_FALLBACK_MODELS if m != primary_model]
        
        for model in models_to_try:
            try:
                logger.info(f"Dispatching call to Groq model: {model}")
                kwargs = {}
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                
                response = await openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=4000,
                    temperature=0.1,
                    **kwargs
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                error_str = str(e)
                last_error = e
                # Check for rate limit errors (429) — try next model
                if "429" in error_str or "rate_limit" in error_str.lower() or "Rate limit" in error_str:
                    logger.warning(f"Groq model '{model}' hit rate limit. Trying next fallback...")
                    continue
                # For decommissioned or bad-request errors, also skip to next fallback
                if "400" in error_str or "model_decommissioned" in error_str or "413" in error_str:
                    logger.warning(f"Groq model '{model}' unavailable ({e}). Trying next fallback...")
                    continue
                # For other unexpected errors, raise immediately
                logger.error(f"Groq model '{model}' failed with unexpected error: {e}")
                raise RuntimeError(f"All configured LLM providers failed. Last error: {e}")
        
        raise RuntimeError(
            f"All Groq models exhausted their rate limits. "
            f"Models tried: {models_to_try}. Please wait and retry. Last error: {last_error}"
        )

    raise RuntimeError("No LLM provider keys (ANTHROPIC_API_KEY or GROQ_API_KEY) are configured in the environment.")
