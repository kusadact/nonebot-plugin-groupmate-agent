import sys
from types import ModuleType

from langchain_core.messages import AIMessage

from tests.helpers import install_package_stub, load_module

install_package_stub("graph_pkg")
install_package_stub("graph_pkg.agent")

reply_guard_module = ModuleType("graph_pkg.reply_guard")


async def _can_request_continue(session_id, request_id):
    return True


reply_guard_module.can_request_continue = _can_request_continue
sys.modules["graph_pkg.reply_guard"] = reply_guard_module

graph = load_module("graph_pkg.agent.graph", "agent/graph.py")


def test_llm_usage_parser_reads_usage_metadata_cache_details():
    message = AIMessage(
        content="ok",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "input_token_details": {"cache_read": 30},
        },
    )
    state = graph.make_agent_state([], "group-1", "req-1")

    usage = graph._log_llm_token_usage(message, state)

    assert usage == {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "cached_tokens": 30,
        "total_tokens": 120,
    }


def test_llm_usage_parser_reads_response_metadata_token_usage():
    message = AIMessage(
        content="ok",
        response_metadata={
            "token_usage": {
                "prompt_tokens": 40,
                "completion_tokens": 6,
                "total_tokens": 46,
                "prompt_tokens_details": {"cached_tokens": 12},
            }
        },
    )
    state = graph.make_agent_state([], "group-1", "req-1")

    usage = graph._log_llm_token_usage(message, state)

    assert usage == {
        "prompt_tokens": 40,
        "completion_tokens": 6,
        "cached_tokens": 12,
        "total_tokens": 46,
    }


def test_llm_usage_parser_reads_raw_usage_metadata():
    message = AIMessage(
        content="ok",
        response_metadata={
            "usage": {
                "prompt_tokens": 70,
                "completion_tokens": 8,
                "total_tokens": 78,
                "prompt_tokens_details": {"cache_read": 20},
            }
        },
    )
    state = graph.make_agent_state([], "group-1", "req-1")

    usage = graph._log_llm_token_usage(message, state)

    assert usage == {
        "prompt_tokens": 70,
        "completion_tokens": 8,
        "cached_tokens": 20,
        "total_tokens": 78,
    }
