from pydantic import SecretStr

from skene.llm.factory import create_llm_client
from skene.llm.providers.skene import PRODUCTION_ENDPOINT, SkeneClient


class _MockResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")

    def json(self) -> dict:
        return self._payload


class _MockAsyncClient:
    def __init__(self, *, timeout: float):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url: str, headers: dict, json: dict):
        _MockAsyncClient.last_call = {"url": url, "headers": headers, "json": json}
        return _MockResponse({"choices": [{"message": {"content": "hello from skene"}}]})


def test_factory_creates_skene_client():
    client = create_llm_client(
        provider="skene",
        api_key=SecretStr("test-key"),
        model_name="auto",
        base_url=None,
    )
    assert isinstance(client, SkeneClient)
    assert client.get_provider_name() == "skene"
    assert client.get_model_name() == "auto"


def test_factory_creates_skene_client_with_base_url():
    client = create_llm_client(
        provider="skene",
        api_key=SecretStr("test-key"),
        model_name="auto",
        base_url="http://localhost:3000/api/v1",
    )
    assert isinstance(client, SkeneClient)
    assert client._endpoint == "http://localhost:3000/api/v1/chat/completions"


def test_skene_client_normalizes_production_root_base_url():
    client = SkeneClient(
        api_key=SecretStr("secret"),
        model_name="auto",
        base_url="https://www.skene.ai",
    )
    assert client._endpoint == "https://www.skene.ai/api/v1/chat/completions"


def test_skene_client_normalizes_workspace_base_url():
    client = SkeneClient(
        api_key=SecretStr("secret"),
        model_name="auto",
        base_url="https://www.skene.ai/workspace/my-app",
    )
    assert client._endpoint == "https://www.skene.ai/api/v1/chat/completions"


async def test_skene_client_uses_production_endpoint(monkeypatch):
    from skene.llm.providers import skene as skene_module

    monkeypatch.setattr(skene_module.httpx, "AsyncClient", _MockAsyncClient)
    client = SkeneClient(
        api_key=SecretStr("secret"),
        model_name="auto",
        base_url=None,
    )
    content, usage = await client.generate_content_with_usage("Summarize this")

    assert content == "hello from skene"
    assert usage is None
    assert _MockAsyncClient.last_call["url"] == PRODUCTION_ENDPOINT
    assert _MockAsyncClient.last_call["headers"]["Authorization"] == "Bearer secret"
    assert _MockAsyncClient.last_call["json"]["stream"] is False
    assert _MockAsyncClient.last_call["json"]["max_tokens"] == 50000


async def test_skene_client_uses_local_endpoint_when_base_url_set(monkeypatch):
    from skene.llm.providers import skene as skene_module

    monkeypatch.setattr(skene_module.httpx, "AsyncClient", _MockAsyncClient)
    client = SkeneClient(
        api_key=SecretStr("secret"),
        model_name="google/gemini-3-flash-preview",
        base_url="http://localhost:3000/api/v1",
    )

    await client.generate_content_with_usage("Summarize this")
    assert _MockAsyncClient.last_call["url"] == "http://localhost:3000/api/v1/chat/completions"
