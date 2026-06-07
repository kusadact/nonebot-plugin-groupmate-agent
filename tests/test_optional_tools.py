import asyncio

from tests.helpers import install_package_stub, load_module

install_package_stub("groupmate_agent_tool_pkg")
install_package_stub("groupmate_agent_tool_pkg.agent")
install_package_stub("groupmate_agent_tool_pkg.agent.optional_tools")
types = load_module("groupmate_agent_tool_pkg.agent.optional_tools.types", "agent/optional_tools/types.py")
calculator = load_module(
    "groupmate_agent_tool_pkg.agent.optional_tools.calculator",
    "agent/optional_tools/calculator.py",
)


def test_calculator_tool_returns_integer_float_and_error_results():
    bundle = asyncio.run(calculator.build(None))
    assert isinstance(bundle, types.OptionalToolBundle)
    assert bundle.name == "calculator"

    tool = bundle.tools[0]
    assert tool.name == "calculate_expression"
    assert tool.invoke({"expression": "2 + 3 * 4"}) == "14"
    assert tool.invoke({"expression": "1 / 4"}) == "计算结果是：0.2500000000"
    assert tool.invoke({"expression": "unknown_name + 1"}).startswith("计算失败。请检查表达式是否正确")
