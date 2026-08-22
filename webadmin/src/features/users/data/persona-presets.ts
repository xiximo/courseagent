import type { UserPersonaProfile } from './types'

export type PersonaPreset = {
  id: string
  label: string
  profile: UserPersonaProfile
}

export const PERSONA_PRESETS: PersonaPreset[] = [
  {
    id: 'fat_loss',
    label: '减脂塑形',
    profile: {
      persona: 'fat_loss',
      personaLabel: '减脂塑形',
      summary:
        '久坐办公、BMI 偏高，希望科学减重、控制热量并搭配三餐。',
      goals: ['稳步减重', '外食可控热量'],
      constraints: ['工作日几乎不做饭', '不接受过度节食'],
      sampleQuestions: [
        '我想减重，每天大概吃多少热量合适？',
        '轻盈减脂方案怎么安排三餐？',
      ],
    },
  },
  {
    id: 'muscle_gain',
    label: '增肌强化',
    profile: {
      persona: 'muscle_gain',
      personaLabel: '增肌强化',
      summary: '规律力量训练，希望增加肌肉量并改善训练日饮食配比。',
      goals: ['增肌不猛增脂肪', '练后补充到位'],
      constraints: ['训练日晚饭较晚'],
      sampleQuestions: [
        '增肌期蛋白质一天要吃多少？',
        '力量增肌方案训练日怎么吃？',
      ],
    },
  },
  {
    id: 'chronic_care',
    label: '慢病调理',
    profile: {
      persona: 'chronic_care',
      personaLabel: '慢病调理',
      summary: '血糖或血压偏高，关注低 GI、控盐控糖与饮食禁忌。',
      goals: ['稳糖调理', '控盐控糖'],
      constraints: ['先饮食干预', '可能有食物过敏'],
      sampleQuestions: [
        '我血糖有点高，早餐怎么吃？',
        '稳糖调理方案怎么用？',
      ],
    },
  },
  {
    id: 'platform',
    label: '平台咨询',
    profile: {
      persona: 'platform',
      personaLabel: '平台咨询',
      summary: '了解会员订阅、企业健康管理与营养师服务，不咨询具体食谱。',
      goals: ['对比会员权益', '评估企业合作'],
      constraints: ['问题应走平台白皮书'],
      sampleQuestions: [
        '标准版和专业版会员有什么区别？',
        '企业健康管理 SaaS 怎么合作？',
      ],
    },
  },
  {
    id: 'custom',
    label: '自定义',
    profile: {
      persona: 'custom',
      personaLabel: '自定义',
      summary: '',
      goals: [],
      constraints: [],
      sampleQuestions: [],
    },
  },
]
