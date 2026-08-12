"""Service — 协议层 / 服务入口

负责 FastAPI 路由、请求/响应模型、组合根（DI）。
依赖 logic + entity，不依赖 repository（组合根负责注入）。
"""
