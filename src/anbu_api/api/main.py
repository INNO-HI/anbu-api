"""FastAPI 앱(SFR-005/007) — 실시간 운영 대시보드 + 관리 API.

본교 서버 안에서 운영한다(과업지시서 SFR-005). 실행:
  .venv/bin/uvicorn anbu_api.api.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from anbu_api.api import deps
from anbu_api.api.auth import authenticate, create_token
from anbu_api.api.routers import admin, dashboard, data, public
from anbu_api.opslog import audit

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(
        title="anbu-api",
        description="제주 안부똑똑 데이터 관리·전송 체계 — 운영 대시보드·관리 API",
        version="0.1.0",
    )
    app.include_router(dashboard.router)
    app.include_router(data.router)
    app.include_router(admin.router)
    app.include_router(public.router)

    @app.post("/api/token")
    def login(
        form: OAuth2PasswordRequestForm = Depends(),
        ops: Session = Depends(deps.ops_db),
    ) -> dict:
        user = authenticate(ops, form.username, form.password)
        if user is None:
            raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")
        audit(ops, user.username, "login")
        ops.commit()
        return {
            "access_token": create_token(user.username, user.role),
            "token_type": "bearer",
            "role": user.role,
        }

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/dashboard")

    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def dashboard_page(request: Request):
        return templates.TemplateResponse(request, "dashboard.html")

    return app


app = create_app()
