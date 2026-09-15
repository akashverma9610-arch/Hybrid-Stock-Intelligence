"""Opt-in Agent mount on the existing HSI application, services and lifecycle."""
from app.api.main import create_app as create_hsi_app
from app.api.agent_tools import create_tool_app
from app.api.agent_market_scan import shared_scan_from_existing_state


def create_app(**existing_hsi_settings):
    application = create_hsi_app(**existing_hsi_settings)
    application.state.agent_market_scan_service = shared_scan_from_existing_state(lambda: application.state)
    tools = create_tool_app(lambda: application.state)
    application.mount("/hsi/v1", tools)
    return application
