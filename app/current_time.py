import datetime

from app import util


def _get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def current_time(id: str) -> dict:
    return util.tool_call_result(id, _get_current_time())
