from langchain_core.messages import AIMessage


async def call_llm(llm, messages) -> AIMessage:
    """Call LLM with retry on transient errors."""
    for attempt in range(2):
        try:
            return await llm.ainvoke(messages)
        except Exception as exc:
            if any(code in str(exc) for code in ("429", "502", "503")) and attempt == 0:
                import asyncio

                import structlog

                structlog.get_logger().warning("llm_retry", attempt=attempt, error=str(exc)[:80])
                await asyncio.sleep(5)
                continue
            raise
