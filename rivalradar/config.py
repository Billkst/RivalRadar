import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


def ark_api_key() -> str | None:
    return os.getenv("ARK_API_KEY")


def ark_base_url() -> str:
    return os.getenv("ARK_BASE_URL", DEFAULT_BASE_URL)


def doubao_model() -> str:
    """从 .env 强制读取 DOUBAO_MODEL endpoint ID,unset 立即 raise。

    KEY 纪律延伸:endpoint ID 与 API key 同等敏感(字节平台固定值,不可上传公开
    仓库)。**绝不**在代码中硬编码 default 值;只允许 .env(已 gitignore)持有。
    用户必须自己从 ARK 控制台拿 endpoint ID 填入 .env 才能调用。
    """
    model = os.getenv("DOUBAO_MODEL")
    if not model:
        raise ValueError(
            "DOUBAO_MODEL is not set; put endpoint ID in .env "
            "(get it from your ARK console — never commit to repo)"
        )
    return model


def tavily_api_key() -> str | None:
    return os.getenv("TAVILY_API_KEY")


def db_path() -> str:
    return os.getenv("RIVALRADAR_DB", "rivalradar.db")


def get_doubao_client():
    from openai import OpenAI

    key = ark_api_key()
    if not key:
        raise ValueError("ARK_API_KEY is not set; put it in .env")
    return OpenAI(api_key=key, base_url=ark_base_url())
