"""Jinja2 템플릿 공용 객체. 화면 라우터와 인증 라우터가 함께 쓴다."""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
