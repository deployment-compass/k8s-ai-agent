from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "k8s-ai-agent"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    kubeconfig_file: Path = Path(".kube/config")

    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 30.0
    llm_temperature: float = 0.2
    llm_max_retries: int = 2
    llm_tool_mode: str = "auto"

    default_namespace: str = "default"
    agent_max_tool_iterations: int = 8
    agent_log_enabled: bool = True
    agent_log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
