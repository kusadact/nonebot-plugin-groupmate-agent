from langchain.tools import tool
from simpleeval import simple_eval

from .types import AgentSkill, OptionalToolBundle, OptionalToolContext


async def build(ctx: OptionalToolContext) -> OptionalToolBundle:
    @tool("calculate_expression")
    def calculate_expression(expression: str) -> str:
        """
        一个用于精确执行数学计算的计算器。
        当你需要执行四则运算、代数计算、指数、对数或三角函数等复杂数学任务时使用。

        输入：一个标准的数学表达式字符串，例如 "45 * (2 + 3) / 7" 或 "math.sqrt(9) + math.log(10)".
        输出：计算结果的字符串形式。

        注意：可以使用如 math.sqrt() (开方), math.log() (自然对数), math.pi (圆周率) 等标准数学函数。
        """
        try:
            result = simple_eval(expression)
            return f"计算结果是：{result:.10f}" if isinstance(result, float) else str(result)
        except Exception as e:
            return f"计算失败。请检查表达式是否正确，错误信息: {e}"

    return OptionalToolBundle(
        name="calculator",
        tools=[calculate_expression],
        skills=[
            AgentSkill(
                name="calculator",
                description="执行需要精确结果的数学表达式计算。",
                prompt="- 精确数学计算使用 `calculate_expression`，不要心算复杂表达式。",
                tool_names=("calculate_expression",),
            )
        ],
    )
