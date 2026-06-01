"""每个 Agent 的系统提示词"""

ORCHESTRATOR_PROMPT = """你是 WeekPlan 的意图解析助手。
用户会用一句自然语言描述周末活动需求，你需要精准提取以下信息：

1. scene_type — 场景类型：
   - family: 家庭出游（带孩子/老人）
   - friends: 朋友聚会
   - couple: 情侣约会
   - solo: 独自活动

2. city — 城市（默认杭州）
3. group_size — 总人数
4. duration_hours — 预计活动时长（小时）
5. budget_per_person — 每人预算（元，可为空）
6. child_age — 如有孩子，孩子年龄
7. dietary_requirements — 饮食需求（如素食、清真、不吃辣等）
8. interests — 兴趣关键词（如户外、文艺、美食、亲子、运动等）
9. start_time — 预计开始时间（HH:MM 格式）
10. special_requests — 其他特殊需求
11. location — 出发位置描述（如有）

请调用 parse_intent 函数输出结构化结果。即使信息不完整也要给出合理默认值。"""

CONTEXT_PROMPT = """你是 WeekPlan 的环境感知助手。
你的任务是收集当前环境信息，为活动规划提供背景数据。
请调用以下工具获取信息：
1. get_weather — 查询目标城市天气
2. get_current_time — 获取当前时间

根据天气和时间，给出户外/室内活动建议。
如果天气恶劣（暴雨/极端高温），应建议室内活动。"""

DINING_PROMPT = """你是 WeekPlan 的餐饮推荐助手。
根据用户的场景类型、人数、饮食需求和预算，搜索合适的餐厅。

筛选标准：
- 家庭场景优先选择：有儿童餐、包间、停车位的餐厅
- 朋友聚会优先选择：氛围好、适合多人聚餐的餐厅
- 情侣约会优先选择：环境好、有特色的餐厅
- 注意饮食需求（素食/清真/过敏原等）
- 人均消费在预算范围内

请使用搜索工具查找餐厅，返回 top 5 候选并说明推荐理由。"""

ACTIVITY_PROMPT = """你是 WeekPlan 的活动推荐助手。
根据用户的场景类型、兴趣、年龄、时长等信息，搜索合适的活动场所。

筛选标准：
- 家庭场景：注意年龄适宜性，优先亲子友好场所
- 朋友聚会：社交性强的活动（密室逃脱、桌游、运动等）
- 情侣约会：浪漫或独特的体验
- 考虑天气（雨天避免纯户外活动）
- 考虑交通便利性

请使用搜索工具查找活动场所，返回 top 5 候选并说明推荐理由。"""

SYNTHESIZER_PROMPT = """你是 WeekPlan 的方案生成助手。
根据环境数据、餐厅候选和活动候选，生成 2-3 个各有特色的备选方案。

每个方案要求：
1. 包含完整时间线：出发 → 活动/景点 → 用餐 → 活动（可选） → 返程
2. 每个节点包含：时间段、地点名、地址、预估费用、活动描述
3. 相邻节点间注明交通方式和预估时间
4. 方案之间要有差异性（比如：经济实惠型 vs 品质享受型 vs 文艺探索型）

时间安排硬性约束：
- 第一个节点的 time_start 必须等于用户指定的开始时间，严禁在用户出发时间之前安排任何节点
- 用餐必须安排在饭点：午餐 11:30-13:30，晚餐 18:00-20:00
- 如果用户出发时间晚于 13:30，不要安排午餐，只能安排晚餐
- 15:00-17:00 是下午茶/咖啡时间，不是正餐时间，禁止在此时间段安排正餐
- 活动时长合理：单个活动 1-2 小时，用餐 1 小时左右

输出格式要求：
直接输出 JSON 对象（不要用 markdown 代码块，不要用 function calling），格式：
{"plans": [...], "recommendation_index": 0, "recommendation_reason": "..."}
每个 plan 包含 title、summary、highlight、score、nodes。
每个 node 包含 time_start、time_end、title、category、venue_name、venue_address、cost_per_person、description、transport_to_next、transport_duration_min。
time_start 和 time_end 必须是纯时间格式 "HH:MM"，不要混入任何说明文字。

重要：category 为 "dining" 的节点必须从「餐厅候选」中选择，category 为 "activity" 的节点必须从「活动/景点候选」中选择。不可将餐厅当作活动安排。
同时注意场所类型标注（方括号内），排除购物商店、零售卖场等非游玩类场所，确保 activity 节点选的是实际可游玩或参观的地点（如景点、公园、博物馆、运动场馆等）。

同时为每个方案给出五维评分（0-100）：cost（花费合理性）、fun（趣味性）、convenience（便捷度）、fit（群体适合度）、uniqueness（特色程度）。"""

NOTIFIER_PROMPT = """你是 WeekPlan 的通知生成助手。
根据确定的方案，生成一段自然、亲切的分享消息，适合发到微信群里。

要求：
- 口语化，像朋友之间的聊天
- 包含关键信息：时间、地点、费用、注意事项
- 如果有需要提前准备的（如穿运动鞋、带防晒），要提醒
- 结尾加一句鼓励/期待的话
- 控制在 200 字以内

示例风格：
"搞定啦！周六下午的安排：2点西湖边集合 → 骑行到曲院风荷（约40分钟）→ 4点去绿茶餐厅吃饭（人均80），已经订好位了～记得穿舒服的鞋子！期待周末🎉"
"""

# 工具定义 — Orchestrator 用
PARSE_INTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "parse_intent",
        "description": "解析用户自然语言输入为结构化意图",
        "parameters": {
            "type": "object",
            "properties": {
                "scene_type": {
                    "type": "string",
                    "enum": ["family", "friends", "couple", "solo"],
                    "description": "场景类型",
                },
                "city": {"type": "string", "description": "城市名称"},
                "group_size": {"type": "integer", "description": "总人数"},
                "duration_hours": {"type": "number", "description": "活动时长（小时）"},
                "budget_per_person": {
                    "type": "integer",
                    "description": "每人预算（元），不确定填 null",
                },
                "child_age": {
                    "type": "integer",
                    "description": "孩子年龄，没有孩子填 null",
                },
                "dietary_requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "饮食需求列表",
                },
                "interests": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "兴趣关键词列表",
                },
                "start_time": {
                    "type": "string",
                    "description": "预计开始时间 HH:MM",
                },
                "special_requests": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "特殊需求列表",
                },
                "location": {
                    "type": "string",
                    "description": "出发位置描述",
                },
            },
            "required": ["scene_type", "city", "group_size", "duration_hours", "start_time"],
        },
    },
}

# 工具定义 — Synthesizer 用
CREATE_PLANS_TOOL = {
    "type": "function",
    "function": {
        "name": "create_plans",
        "description": "创建 2-3 个备选活动方案",
        "parameters": {
            "type": "object",
            "properties": {
                "plans": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "方案标题"},
                            "summary": {"type": "string", "description": "方案简介"},
                            "highlight": {"type": "string", "description": "方案亮点"},
                            "score": {
                                "type": "object",
                                "properties": {
                                    "cost": {"type": "integer"},
                                    "fun": {"type": "integer"},
                                    "convenience": {"type": "integer"},
                                    "fit": {"type": "integer"},
                                    "uniqueness": {"type": "integer"},
                                },
                            },
                            "nodes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "time_start": {"type": "string"},
                                        "time_end": {"type": "string"},
                                        "title": {"type": "string"},
                                        "category": {
                                            "type": "string",
                                            "enum": ["activity", "dining", "transport", "rest"],
                                        },
                                        "venue_name": {"type": "string"},
                                        "venue_address": {"type": "string"},
                                        "cost_per_person": {"type": "number"},
                                        "description": {"type": "string"},
                                        "transport_to_next": {
                                            "type": "string",
                                            "enum": ["walk", "drive", "transit", "taxi"],
                                        },
                                        "transport_duration_min": {"type": "integer"},
                                    },
                                    "required": ["time_start", "time_end", "title", "category"],
                                },
                            },
                        },
                        "required": ["title", "summary", "nodes"],
                    },
                },
                "recommendation_index": {
                    "type": "integer",
                    "description": "推荐方案的索引 (0-based)",
                },
                "recommendation_reason": {
                    "type": "string",
                    "description": "推荐理由",
                },
            },
            "required": ["plans", "recommendation_index", "recommendation_reason"],
        },
    },
}

# 工具定义 — Dining / Activity Agent 用的搜索工具
SEARCH_POI_TOOL = {
    "type": "function",
    "function": {
        "name": "search_poi",
        "description": "搜索 POI（兴趣点），如餐厅、景点、商场等",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"},
                "city": {"type": "string", "description": "城市"},
                "category": {"type": "string", "description": "分类（如：餐饮、景点、运动）"},
            },
            "required": ["keyword", "city"],
        },
    },
}

SEARCH_NEARBY_TOOL = {
    "type": "function",
    "function": {
        "name": "search_nearby",
        "description": "搜索附近的 POI",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "中心坐标 lng,lat"},
                "keyword": {"type": "string", "description": "搜索关键词"},
                "radius": {"type": "integer", "description": "搜索半径（米）"},
            },
            "required": ["location", "keyword"],
        },
    },
}

GET_WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询城市天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"},
            },
            "required": ["city"],
        },
    },
}

GET_ROUTE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_route",
        "description": "查询两点间路线",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "起点坐标 lng,lat"},
                "destination": {"type": "string", "description": "终点坐标 lng,lat"},
                "mode": {
                    "type": "string",
                    "enum": ["driving", "walking", "transit"],
                    "description": "出行方式",
                },
            },
            "required": ["origin", "destination"],
        },
    },
}

GENERATE_SHARE_MESSAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_share_message",
        "description": "生成自然语言分享消息",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "分享消息内容"},
            },
            "required": ["message"],
        },
    },
}
