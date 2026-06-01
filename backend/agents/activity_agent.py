"""Activity Agent — 活动场所搜索与推荐"""

import json
from typing import Any

from backend.agents.base import BaseAgent
from backend.llm.client import chat_with_tools
from backend.llm.prompts import ACTIVITY_PROMPT, SEARCH_POI_TOOL
from backend.tools.amap import search_poi
from backend.config import DEFAULT_CITY, DEFAULT_LOCATION


class ActivityAgent(BaseAgent):
    def __init__(self):
        super().__init__("activity")

    async def _execute(self, thinking: list, **kwargs) -> dict:
        intent: dict = kwargs.get("intent", {})
        context: dict = kwargs.get("context", {})

        city = intent.get("city", DEFAULT_CITY)
        scene_type = intent.get("scene_type", "friends")
        interests = intent.get("interests", [])
        child_age = intent.get("child_age")
        weather = context.get("weather", "晴")
        outdoor_rec = context.get("outdoor_recommendation", "")

        thinking.append({"step": "start", "message": f"搜索 {city} 活动，场景={scene_type}"})

        # 构建搜索关键词
        keywords = _build_activity_keywords(scene_type, interests, child_age, weather)
        all_activities: list[dict] = []

        for kw in keywords:
            category = _get_poi_category(kw)
            result = await search_poi(keyword=kw, city=city, category=category)
            if result.success and result.data:
                thinking.append({"step": "search", "keyword": kw, "count": len(result.data), "source": result.source})
                all_activities.extend(result.data)
            else:
                thinking.append({"step": "search_fail", "keyword": kw, "error": result.error})

        # 去重并过滤不相关类型
        seen = set()
        unique = []
        for a in all_activities:
            name = a.get("name", "")
            ptype = a.get("type", "")
            if name and name not in seen and not _is_excluded_poi_type(ptype):
                seen.add(name)
                unique.append(a)

        # LLM 排序
        if unique:
            ranked = await _rank_activities(unique, intent, context, thinking)
        else:
            ranked = unique

        top5 = ranked[:5]
        thinking.append({"step": "done", "count": len(top5)})

        return {
            "activities": top5,
            "total_found": len(unique),
            "search_keywords": keywords,
        }


# POI 类型过滤：关键词 → 高德分类
_ACTIVITY_CATEGORY_MAP = {
    "景点": "风景名胜", "公园": "风景名胜", "湖滨": "风景名胜",
    "博物馆": "科教文化", "科技馆": "科教文化", "展览": "科教文化",
    "动物园": "科教文化", "海洋馆": "科教文化", "图书馆": "科教文化",
    "户外运动": "运动健身", "运动": "运动健身",
    "密室逃脱": "休闲娱乐", "桌游": "休闲娱乐", "KTV": "休闲娱乐",
    "儿童乐园": "休闲娱乐", "电影院": "休闲娱乐",
    "书店": "科教文化", "咖啡馆": "餐饮服务",
    # 观景/日落/风景
    "日落": "风景名胜", "看日落": "风景名胜", "观日落": "风景名胜",
    "风景": "风景名胜", "观景": "风景名胜",
    # 户外活动
    "骑行": "运动健身", "徒步": "运动健身", "划船": "运动健身", "爬山": "运动健身",
}

# 活动搜索需要排除的 POI 类型
_EXCLUDED_POI_TYPES = [
    "餐饮", "购物", "汽车", "医疗", "生活服务",
    "公司企业", "政府机构", "金融", "银行",
]


def _get_poi_category(keyword: str) -> str:
    if keyword in _ACTIVITY_CATEGORY_MAP:
        return _ACTIVITY_CATEGORY_MAP[keyword]
    # 未知关键词默认搜索风景名胜类，避免全类型搜索混入购物/零售
    return "风景名胜"


def _is_excluded_poi_type(ptype: str) -> bool:
    if not ptype:
        return False
    return any(t in ptype for t in _EXCLUDED_POI_TYPES)


def _build_activity_keywords(
    scene_type: str,
    interests: list[str],
    child_age: int | None,
    weather: str,
) -> list[str]:
    """根据场景和兴趣构建活动搜索关键词"""
    keywords = []

    # 根据兴趣直接搜索
    for interest in interests[:2]:
        keywords.append(interest)

    is_bad_weather = any(w in weather for w in ["雨", "雪", "雷", "暴"])

    if scene_type == "family":
        if child_age and child_age <= 6:
            keywords.extend(["儿童乐园", "海洋馆"])
        elif child_age and child_age <= 12:
            keywords.extend(["科技馆", "动物园"])
        else:
            keywords.extend(["公园", "博物馆"])
    elif scene_type == "friends":
        if is_bad_weather:
            keywords.extend(["密室逃脱", "桌游", "KTV"])
        else:
            keywords.extend(["户外运动", "景点"])
    elif scene_type == "couple":
        if is_bad_weather:
            keywords.extend(["电影院", "展览"])
        else:
            keywords.extend(["公园", "湖滨"])
    elif scene_type == "solo":
        keywords.extend(["书店", "咖啡馆", "博物馆"])

    if not keywords:
        keywords = ["景点", "公园"]

    return keywords[:4]


async def _rank_activities(activities: list[dict], intent: dict, context: dict, thinking: list) -> list[dict]:
    """使用 LLM 排序推荐活动"""
    activities_text = json.dumps(activities[:15], ensure_ascii=False, indent=2)
    intent_text = json.dumps(intent, ensure_ascii=False)

    messages = [
        {"role": "system", "content": ACTIVITY_PROMPT},
        {"role": "user", "content": f"""以下是搜索到的活动/景点列表：
{activities_text}

用户需求：{intent_text}
天气：{context.get('weather', '晴')}，{context.get('outdoor_recommendation', '')}

请选出最合适的 5 个活动，按推荐度排序。
注意：体育用品零售店（如迪卡侬、Nike 旗舰店等）、购物中心、商场都不是"活动/景点"，必须排除。只保留风景名胜、运动场馆、公园、博物馆、展览馆、休闲娱乐等实际可游玩的场所。
直接返回 JSON 数组，每个元素包含 name、address、location、type、recommendation_reason 字段。"""},
    ]

    try:
        from backend.llm.client import chat
        resp = await chat(messages, temperature=0.5)
        content = resp.content or ""
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        ranked = json.loads(content)
        if isinstance(ranked, list):
            thinking.append({"step": "rank", "message": "LLM 排序完成"})
            # 从原始数据恢复 location 字段（LLM 可能丢失或改变坐标）
            orig_map = {a.get("name", ""): a for a in activities}
            for item in ranked:
                name = item.get("name", "")
                orig = orig_map.get(name)
                if orig:
                    if not item.get("location"):
                        item["location"] = orig.get("location", "")
                    if not item.get("address"):
                        item["address"] = orig.get("address", "")
            return ranked
    except Exception as e:
        thinking.append({"step": "rank_error", "error": str(e)})

    return activities
