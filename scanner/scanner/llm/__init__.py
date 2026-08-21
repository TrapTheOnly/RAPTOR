from scanner.settings import ScanSettings


def build_llm_client(settings: ScanSettings):
    protocol = str(settings.protocol or "").strip().lower()
    if protocol == "anthropic":
        from scanner.llm.anthropic_messages import AnthropicMessagesClient

        return AnthropicMessagesClient(settings)
    if protocol == "openai":
        from scanner.llm.openai_chat import OpenAIChatClient

        return OpenAIChatClient(settings)
    raise ValueError(f"Unsupported LLM protocol: {settings.protocol}")
