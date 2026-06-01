"""Plan Synthesizer — 整合数据生成 2-3 个备选方案"""

import json
import logging
from typing import Any

from backend.agents.base import BaseAgent
from backend.llm.client import chat_with_tools
from backend.llm.prompts import SYNTHESIZER_PROMPT, CREATE_PLANS_TOOL
from backend.models.plan import Plan, PlanNode, PlanScore, PlanComparison

logger = logging.getLogger("weplan.synthesizer")


class SynthesizerAgent(BaseAgent):
    def __init__(self):
        super().__init__("synthesizer")

    async def _execute(self, thinking: list, **kwargs) -> dict:
        intent: dict = kwargs.get("intent", {})
        context: dict = kwargs.get("context", {})
        dining: dict = kwargs.get("dining", {})
        activity: dict = kwargs.get("activity", {})

        thinking.append({"step": "start", "message": "开始整合数据生成方案"})

        restaurants = dining.get("restaurants", [])
        activities = activity.get("activities", [])

        data_summary = _build_data_summary(intent, context, restaurants, activities)

        messages = [
            {"role": "system", "content": SYNTHESIZER_PROMPT},
            {"role": "user", "content": data_summary},
        ]

        plans_data: dict[str, Any] = {}

        # 使用简化版工具：将复杂 JSON 放在字符串参数中，避免 MiniMax 深度嵌套校验失败
        SIMPLE_PLANS_TOOL = {
            "type": "function",
            "function": {
                "name": "save_plans",
                "description": "保存生成的方案 JSON。plans_json 是完整的 JSON 字符串，包含 plans 数组、recommendation_index 和 recommendation_reason。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plans_json": {
                            "type": "string",
                            "description": "完整方案 JSON 字符串",
                        },
                    },
                    "required": ["plans_json"],
                },
            },
        }

        async def tool_executor(fn_name: str, fn_args: dict) -> str:
            if fn_name == "save_plans":
                try:
                    parsed = json.loads(fn_args.get("plans_json", "{}"))
                    plans_data.update(parsed)
                    thinking.append({"step": "plans_created", "count": len(parsed.get("plans", []))})
                except json.JSONDecodeError as e:
                    thinking.append({"step": "json_error", "error": str(e)})
                return json.dumps({"status": "ok"}, ensure_ascii=False)
            return json.dumps({"error": f"未知工具: {fn_name}"}, ensure_ascii=False)

        await chat_with_tools(
            messages=messages,
            tools=[SIMPLE_PLANS_TOOL],
            tool_executor=tool_executor,
            thinking=thinking,
            max_rounds=4,
        )

        if not plans_data or "plans" not in plans_data:
            thinking.append({"step": "fallback", "message": "LLM 未生成方案，使用兜底方案"})
            return _fallback_plans(intent, restaurants, activities)

        thinking.append({"step": "plans_created", "count": len(plans_data.get("plans", []))})
        comparison = _build_plan_comparison(plans_data)
        thinking.append({"step": "done", "plan_count": len(comparison["plans"])})
        return comparison


def _safe_transport(v: str | None) -> str | None:
    """只接受有效的交通方式，其余返回 None"""
    valid = {"walk", "drive", "transit", "taxi"}
    if v and isinstance(v, str) and v.strip() in valid:
        return v.strip()
    return None


def _clean_time(raw: str) -> str:
    """从 LLM 输出的时间字段中提取 HH:MM，去除混入的说明文字。
    例如 "16:00, 18:00开始用餐" → "16:00"。
    """
    import re
    if not raw:
        return ""
    m = re.match(r'(\d{1,2}:\d{2})', raw.strip())
    return m.group(1) if m else ""


def _build_data_summary(intent: dict, context: dict, restaurants: list, activities: list) -> str:
    """构造供 LLM 使用的数据摘要"""
    parts = [
        f"## 用户需求",
        f"- 场景: {intent.get('scene_type', 'friends')}",
        f"- 城市: {intent.get('city', '杭州')}",
        f"- 人数: {intent.get('group_size', 2)}",
        f"- 时长: {intent.get('duration_hours', 4)} 小时",
        f"- 开始时间: {intent.get('start_time', '14:00')}",
        f"- 预算: {intent.get('budget_per_person', '不限')} 元/人",
    ]

    if intent.get("child_age"):
        parts.append(f"- 孩子年龄: {intent['child_age']} 岁")
    if intent.get("dietary_requirements"):
        parts.append(f"- 饮食需求: {', '.join(intent['dietary_requirements'])}")
    if intent.get("interests"):
        parts.append(f"- 兴趣: {', '.join(intent['interests'])}")
    if intent.get("special_requests"):
        parts.append(f"- 特殊需求: {', '.join(intent['special_requests'])}")

    parts.append(f"\n## 环境信息")
    parts.append(f"- 天气: {context.get('weather', '晴')} {context.get('temperature', '25')}°C")
    parts.append(f"- 日期: {context.get('current_date', '')} {context.get('day_of_week', '')}")
    parts.append(f"- 建议: {context.get('outdoor_recommendation', '')}")

    parts.append(f"\n## 餐厅候选（共 {len(restaurants)} 家）")
    for i, r in enumerate(restaurants[:5], 1):
        name = r.get("name", "未知")
        addr = r.get("address", "")
        ptype = r.get("type", "")
        reason = r.get("recommendation_reason", "")
        parts.append(f"{i}. {name} [{ptype}] — {addr} {reason}")

    parts.append(f"\n## 活动/景点候选（共 {len(activities)} 个）")
    for i, a in enumerate(activities[:5], 1):
        name = a.get("name", "未知")
        addr = a.get("address", "")
        ptype = a.get("type", "")
        reason = a.get("recommendation_reason", "")
        parts.append(f"{i}. {name} [{ptype}] — {addr} {reason}")

    parts.append(f"\n请根据以上数据，生成 2-3 个各有特色的备选方案。")
    return "\n".join(parts)


def _build_plan_comparison(data: dict) -> dict:
    """将 LLM 输出转化为结构化方案"""
    plans = []
    for p in data.get("plans", []):
        nodes = []
        for n in p.get("nodes", []):
            node = PlanNode(
                time_start=_clean_time(n.get("time_start", "")),
                time_end=_clean_time(n.get("time_end", "")),
                title=n.get("title", ""),
                category=n.get("category", "activity"),
                venue_name=n.get("venue_name", n.get("title", "")),
                venue_address=n.get("venue_address", ""),
                venue_location=n.get("venue_location", ""),
                cost_per_person=n.get("cost_per_person", 0),
                description=n.get("description", ""),
                transport_to_next=_safe_transport(n.get("transport_to_next")),
                transport_duration_min=n.get("transport_duration_min", 0),
                booking_required=n.get("category") in ("dining",),
            )
            nodes.append(node)

        score_data = p.get("score", {})
        score = PlanScore(
            cost=score_data.get("cost", 70),
            fun=score_data.get("fun", 70),
            convenience=score_data.get("convenience", 70),
            fit=score_data.get("fit", 70),
            uniqueness=score_data.get("uniqueness", 70),
        )

        total_cost = sum(n.cost_per_person for n in nodes)
        total_hours = _calc_duration(nodes)
        logger.info(f"Plan '{p.get('title')}' duration={total_hours}h")

        plan = Plan(
            title=p.get("title", "方案"),
            summary=p.get("summary", ""),
            highlight=p.get("highlight", ""),
            nodes=nodes,
            total_cost_per_person=total_cost if total_cost > 0 else None,
            total_duration_hours=total_hours,
            score=score,
        )
        logger.info(f"Plan '{plan.title}' total_duration_hours={plan.total_duration_hours}")
        plans.append(plan)

    comparison = PlanComparison(
        plans=plans,
        recommendation_index=data.get("recommendation_index", 0),
        recommendation_reason=data.get("recommendation_reason", ""),
    )
    return comparison.model_dump()


def _calc_duration(nodes: list) -> float:
    """从节点列表中计算总时长（最早开始到最晚结束）"""
    if not nodes:
        return 0.0
    try:
        times = []
        for n in nodes:
            ts = getattr(n, 'time_start', '') or ''
            te = getattr(n, 'time_end', '') or ''
            if ts:
                h, m = map(int, ts.split(":"))
                times.append(h * 60 + m)
            if te:
                h, m = map(int, te.split(":"))
                times.append(h * 60 + m)
        if times:
            return round((max(times) - min(times)) / 60, 1)
    except (ValueError, IndexError):
        pass
    return 0.0


def _fallback_plans(intent: dict, restaurants: list, activities: list) -> dict:
    """兜底方案：简单拼接"""
    start_time = intent.get("start_time", "14:00")
    h, m = map(int, start_time.split(":"))

    nodes = []
    if activities:
        a = activities[0]
        nodes.append(PlanNode(
            time_start=f"{h:02d}:{m:02d}",
            time_end=f"{h+1:02d}:30",
            title=a.get("name", "游玩"),
            category="activity",
            venue_name=a.get("name", ""),
            venue_address=a.get("address", ""),
            description="游玩活动",
            transport_to_next="taxi",
            transport_duration_min=15,
        ))

    if restaurants:
        r = restaurants[0]
        nodes.append(PlanNode(
            time_start=f"{h+2:02d}:00",
            time_end=f"{h+3:02d}:00",
            title=f"在 {r.get('name', '餐厅')} 用餐",
            category="dining",
            venue_name=r.get("name", ""),
            venue_address=r.get("address", ""),
            description="用餐",
            booking_required=True,
        ))

    plan = Plan(
        title="默认方案",
        summary="由系统自动生成的基础方案",
        highlight="简单实用",
        nodes=nodes,
        total_duration_hours=_calc_duration(nodes),
    )

    return PlanComparison(
        plans=[plan],
        recommendation_index=0,
        recommendation_reason="系统默认推荐",
    ).model_dump()
