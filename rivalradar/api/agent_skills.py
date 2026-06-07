"""agent 技能持久化端点(Plan C:run 无关的 agent 配置,spec §6.3/§7.3)。

路由无 `/api` 前缀(前端 vite proxy 加)。db 依赖 = get_db_conn(per-request 连接)。
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from rivalradar.api.deps import get_db_conn
from rivalradar.storage import repository as repo

router = APIRouter(tags=["agent_skills"])


class AgentSkillIn(BaseModel):
    agent_id: str
    skill_id: str
    version: str = "v1"
    enabled: bool = True


@router.get("/agent-skills")
def get_agent_skills(conn: sqlite3.Connection = Depends(get_db_conn)) -> list[dict]:
    return repo.list_agent_skills(conn)


@router.put("/agent-skills")
def put_agent_skill(body: AgentSkillIn,
                    conn: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    repo.upsert_agent_skill(conn, body.agent_id, body.skill_id, body.version, body.enabled)
    return {"ok": True}


@router.delete("/agent-skills/{agent_id}/{skill_id}")
def delete_agent_skill_route(agent_id: str, skill_id: str,
                             conn: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    repo.delete_agent_skill(conn, agent_id, skill_id)
    return {"ok": True}
