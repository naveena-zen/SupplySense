import os
import json
import logging
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from backend.config import ANTHROPIC_API_KEY, GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

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
        try:
            logger.info("Dispatching call to Groq Llama")
            kwargs = {}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            model = os.getenv("GROQ_MODEL", GROQ_MODEL)
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
            logger.error(f"Groq API call failed: {e}")
            raise RuntimeError(f"All configured LLM providers failed. Last error: {e}")

    raise RuntimeError("No LLM provider keys (ANTHROPIC_API_KEY or GROQ_API_KEY) are configured in the environment.")
