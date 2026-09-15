"""Opt-in Agent mount on the existing HSI application, services and lifecycle."""
from app.api.main import create_app as create_hsi_app
from app.api.agent_tools import create_tool_app


def create_app(**existing_hsi_settings):
    application = create_hsi_app(**existing_hsi_settings)
    tools = create_tool_app(lambda: application.state)
    application.mount("/hsi/v1", tools)
    return application
