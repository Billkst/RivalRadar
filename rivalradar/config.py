import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_DOUBAO_MODEL = "ep-20260514111325-xjmj7"


def ark_api_key() -> str | None:
    return os.getenv("ARK_API_KEY")


def ark_base_url() -> str:
    return os.getenv("ARK_BASE_URL", DEFAULT_BASE_URL)


def doubao_model() -> str:
    return os.getenv("DOUBAO_MODEL", DEFAULT_DOUBAO_MODEL)


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
