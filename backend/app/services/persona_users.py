"""赛题三类核心人群 + 平台咨询的初始测试账号。"""

from __future__ import annotations

from typing import Any

TEST_USER_PASSWORD = "test1234"

PERSONA_USERS: list[dict[str, Any]] = [
    {
        "username": "fatloss",
        "fullName": "林晓（减脂塑形）",
        "roleCodes": ["end_user"],
        "profile": {
            "persona": "fat_loss",
            "personaLabel": "减脂塑形",
            "summary": "32 岁互联网运营，久坐，BMI 偏高、体脂率超标，希望科学减重、控制热量并搭配三餐。",
            "goals": ["12 周减重 6–8kg", "午餐外食可控热量", "晚间加餐不踩坑"],
            "constraints": ["工作日几乎不做饭", "不接受过度节食", "对乳糖轻微不耐受"],
            "sampleQuestions": [
                "我想减重，每天大概吃多少热量合适？",
                "轻盈减脂方案怎么安排三餐？",
                "哪些主食 GI 比较低，晚饭能吃吗？",
            ],
        },
    },
    {
        "username": "muscle",
        "fullName": "周凯（增肌强化）",
        "roleCodes": ["end_user"],
        "profile": {
            "persona": "muscle_gain",
            "personaLabel": "增肌强化",
            "summary": "28 岁，每周力量训练 4 次，希望增加肌肉量、改善体成分，关心训练日蛋白质与碳水配比。",
            "goals": ["增肌不猛增脂肪", "练后补剂怎么选", "力量增肌方案落地"],
            "constraints": ["训练日晚饭较晚", "可接受鸡胸/鸡蛋/乳清", "无已知疾病"],
            "sampleQuestions": [
                "增肌期蛋白质一天要吃多少？",
                "力量增肌方案训练日怎么吃？",
                "练前练后碳水怎么配？",
            ],
        },
    },
    {
        "username": "wellness",
        "fullName": "陈敏（慢病调理）",
        "roleCodes": ["end_user"],
        "profile": {
            "persona": "chronic_care",
            "personaLabel": "慢病调理",
            "summary": "41 岁，体检血糖偏高、血压临界，有家族糖尿病史，关注低 GI、控盐控糖与饮食禁忌。",
            "goals": ["稳糖调理", "控盐控糖", "找到可替换食材"],
            "constraints": ["医生建议先饮食干预", "对海鲜过敏", "不接受极端生酮"],
            "sampleQuestions": [
                "我血糖有点高，早餐怎么吃？",
                "稳糖调理方案和控糖 321 餐盘怎么用？",
                "我对海鲜过敏，蛋白质有什么替换？",
            ],
        },
    },
    {
        "username": "member",
        "fullName": "赵倩（平台咨询）",
        "roleCodes": ["end_user"],
        "profile": {
            "persona": "platform",
            "personaLabel": "平台咨询",
            "summary": "企业 HR，想了解健康优选会员订阅、企业健康管理 SaaS 与营养师 1 对 1，不咨询具体食谱。",
            "goals": ["对比标准版/专业版会员", "评估企业合作", "了解服务边界"],
            "constraints": ["问题应走平台白皮书", "不应混入膳食方案价格"],
            "sampleQuestions": [
                "标准版和专业版会员有什么区别？",
                "企业健康管理 SaaS 怎么合作？",
                "营养师 1 对 1 怎么预约？",
            ],
        },
    },
]
