import type {
  CourseAgentCitation,
  CourseAgentConstraints,
  CourseAgentMessage,
  CourseAgentRole,
  CourseAgentSession,
  CourseAgentSessionState,
} from '../data/types'

const STUDENT_COURSES = ['北京线下班', '上海线下班', '线上直播班'] as const
const TEACHER_COURSES = ['暑期集训班', '周末研修班'] as const

const MAX_INPUT_LENGTH = 500

function msgId() {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function assistant(
  content: string,
  extra?: Partial<CourseAgentMessage>
): CourseAgentMessage {
  return {
    id: msgId(),
    role: 'assistant',
    content,
    createdAt: new Date().toISOString(),
    ...extra,
  }
}

function countConstraints(c: CourseAgentConstraints): number {
  return [c.city, c.date, c.format, c.goal].filter(Boolean).length
}

function detectRole(text: string): CourseAgentRole | null {
  const t = text.toLowerCase()
  if (/学生|家长|孩子|报班/.test(t)) return 'student'
  if (/教师|老师|培训/.test(t)) return 'teacher'
  if (/机构|企业|平台|会员|合作/.test(t)) return 'org'
  if (t.includes('学生课程')) return 'student'
  if (t.includes('教师培训')) return 'teacher'
  if (t.includes('平台服务')) return 'org'
  return null
}

function extractConstraints(
  text: string,
  existing: CourseAgentConstraints
): CourseAgentConstraints {
  const next = { ...existing }
  const t = text.toLowerCase()

  if (!next.city) {
    if (/北京/.test(t)) next.city = '北京'
    else if (/上海/.test(t)) next.city = '上海'
    else if (/线上|直播|远程/.test(t)) next.city = '线上'
  }
  if (!next.date) {
    if (/7月|七月|暑假/.test(t)) next.date = '7月'
    else if (/8月|八月/.test(t)) next.date = '8月'
    else if (/周末/.test(t)) next.date = '周末'
  }
  if (!next.format) {
    if (/线下|现场/.test(t)) next.format = 'offline'
    else if (/线上|直播|远程/.test(t)) next.format = 'online'
  }
  if (!next.goal && /ai|人工智能|素养|学习/.test(t)) {
    next.goal = '提升 AI 素养'
  }
  return next
}

function missingConstraintPrompt(c: CourseAgentConstraints): string {
  if (!c.city) return '请问您倾向哪个城市或地点？（如北京、上海，或线上）'
  if (!c.date) return '请问您方便的上课时间？（如 7 月、8 月或周末）'
  if (!c.format) return '您更倾向线上还是线下班型？'
  if (!c.goal) return '请问您的学习目标是什么？（如提升 AI 素养）'
  return '请补充更多偏好，以便为您推荐合适班型。'
}

function pickCourses(
  role: CourseAgentRole,
  constraints: CourseAgentConstraints
): { courses: string[]; reasons: string[]; citations: CourseAgentCitation[] } {
  if (role === 'student') {
    const courses: string[] = []
    const reasons: string[] = []
    if (constraints.city === '北京' && constraints.format !== 'online') {
      courses.push('北京线下班')
      reasons.push('您倾向北京线下上课，与北京线下班地点匹配')
    }
    if (constraints.city === '上海' && constraints.format !== 'online') {
      courses.push('上海线下班')
      reasons.push('您倾向上海线下上课，与上海线下班地点匹配')
    }
    if (
      constraints.format === 'online' ||
      constraints.city === '线上' ||
      courses.length === 0
    ) {
      if (!courses.includes('线上直播班')) courses.push('线上直播班')
      reasons.push('您接受线上形式，或线下班型与约束不完全匹配时，线上直播班更灵活')
    }
    if (constraints.date?.includes('7')) {
      reasons.push('7 月档期与夏令营营期安排相符')
    }
    return {
      courses: courses.slice(0, 2),
      reasons: reasons.slice(0, 3),
      citations: [
        {
          document: '《素材A·暑期AI素养夏令营手册》',
          chapter: courses[0]?.includes('北京')
            ? '第3章「北京线下班安排」'
            : courses[0]?.includes('上海')
              ? '第4章「上海线下班安排」'
              : '第5章「线上直播班安排」',
        },
      ],
    }
  }

  if (role === 'teacher') {
    const courses =
      constraints.date?.includes('7') || constraints.format === 'offline'
        ? ['暑期集训班']
        : ['周末研修班']
    return {
      courses,
      reasons: [
        constraints.date?.includes('7')
          ? '暑期档期与集训班时间匹配'
          : '周末研修更适合在职教师持续学习',
        '培训目标聚焦教师 AI 素养提升',
      ],
      citations: [
        {
          document: '《素材B·教师AI素养培训体系介绍》',
          chapter: courses[0] === '暑期集训班' ? '第2章「暑期集训班」' : '第3章「周末研修班」',
        },
      ],
    }
  }

  return { courses: [], reasons: [], citations: [] }
}

function answerDetail(
  question: string,
  course: string,
  role: CourseAgentRole
): { content: string; citations: CourseAgentCitation[] } {
  const q = question.toLowerCase()
  const kb =
    role === 'student'
      ? '《素材A·暑期AI素养夏令营手册》'
      : '《素材B·教师AI素养培训体系介绍》'

  if (/多少钱|费用|价格/.test(q)) {
    const fee =
      course === '北京线下班'
        ? '3800 元/期（含材料费）'
        : course === '上海线下班'
          ? '3600 元/期'
          : course === '线上直播班'
            ? '2800 元/期'
            : course === '暑期集训班'
              ? '4200 元/期'
              : '1800 元/期'
    return {
      content: `${course}费用为 ${fee}。\n\n来源：${kb}${course.includes('北京') ? '第3章「费用说明」' : course.includes('上海') ? '第4章「费用说明」' : course.includes('线上') ? '第5章「费用说明」' : '第2章「费用说明」'}`,
      citations: [{ document: kb, chapter: '费用说明' }],
    }
  }
  if (/什么时候|时间|日程/.test(q)) {
    return {
      content: `${course}主要安排在 7—8 月，具体日程以手册为准。\n\n来源：${kb}对应班型章节「时间安排」`,
      citations: [{ document: kb, chapter: '时间安排' }],
    }
  }
  if (/带什么|准备|物资/.test(q)) {
    return {
      content: `参加${course}建议携带：笔记本电脑、充电器、笔记本；线下班另需携带身份证件。\n\n来源：${kb}「学员准备事项」`,
      citations: [{ document: kb, chapter: '学员准备事项' }],
    }
  }
  if (/报名/.test(q)) {
    return {
      content: `${course}报名方式：请通过 AI 教育中心官网填写报名表，或拨打资料中公布的咨询热线。如需确认余位，请联系人工客服。\n\n来源：${kb}「报名方式」`,
      citations: [{ document: kb, chapter: '报名方式' }],
    }
  }
  return {
    content: `关于${course}的详情，请具体说明您想了解时间、费用、师资还是大纲。\n\n来源：${kb}`,
    citations: [{ document: kb, chapter: '班型概述' }],
  }
}

function orgPlatformReply(text: string): CourseAgentMessage {
  const t = text.toLowerCase()
  if (/会员|价格|多少钱/.test(t)) {
    return assistant(
      'OPC 平台提供基础版、专业版与企业版会员，权益与定价详见平台白皮书。请注意：平台会员价格属于平台服务范畴，与学生/教师课程费用不同。\n\n来源：《素材C·OPC平台产品白皮书》第2章「会员体系与定价」',
      {
        citations: [
          {
            document: '《素材C·OPC平台产品白皮书》',
            chapter: '第2章「会员体系与定价」',
          },
        ],
      }
    )
  }
  return assistant(
    'OPC 平台面向机构提供 SaaS 服务、会员权益、企业合作与定制开发。如需了解合作模式，请说明您的机构类型与诉求。\n\n来源：《素材C·OPC平台产品白皮书》第1章「平台概述」',
    {
      citations: [
        {
          document: '《素材C·OPC平台产品白皮书》',
          chapter: '第1章「平台概述」',
        },
      ],
      quickActions: ['会员权益', '企业合作'],
    }
  )
}

function isResetCommand(text: string): boolean {
  return /重新开始|重来|取消|重置/.test(text)
}

function isListCoursesCommand(text: string): boolean {
  return /查看所有课程|全部班型|有哪些班/.test(text)
}

function isOutOfScope(text: string): boolean {
  return /天气|广州线下|深圳班/.test(text)
}

function isCrossBoundary(text: string, role: CourseAgentRole | null): boolean {
  if (role === 'student' && /会员价|平台会员/.test(text)) return true
  if (role === 'teacher' && /会员价|学生营/.test(text)) return true
  return false
}

export function createInitialSessionState(): CourseAgentSessionState {
  return {
    step: 'welcome',
    role: null,
    constraints: {},
    recommendedCourses: [],
  }
}

export function createWelcomeMessage(): CourseAgentMessage {
  return assistant(
    '您好！我是 AI 课程顾问，可为您提供学生夏令营、教师培训或 OPC 平台服务咨询。请问您需要哪类帮助？',
    { quickActions: ['学生课程', '教师培训', '平台服务'] }
  )
}

export function processCourseAgentMessage(
  session: CourseAgentSession,
  userText: string
): CourseAgentSession {
  const trimmed = userText.trim()
  const now = new Date().toISOString()
  const messages: CourseAgentMessage[] = [
    ...session.messages,
    {
      id: msgId(),
      role: 'user',
      content: trimmed,
      createdAt: now,
    },
  ]

  let state: CourseAgentSessionState = { ...session.state, constraints: { ...session.state.constraints } }

  if (!trimmed) {
    messages.push(assistant('请输入您的问题。'))
    return { ...session, messages, state, updatedAt: now }
  }

  if (trimmed.length > MAX_INPUT_LENGTH) {
    messages.push(
      assistant('输入过长，请精简后重新发送（限 500 字）。')
    )
    return { ...session, messages, state, updatedAt: now }
  }

  if (isResetCommand(trimmed)) {
    state = createInitialSessionState()
    messages.push(
      assistant('已为您重新开始。请问需要学生课程、教师培训还是平台服务？', {
        quickActions: ['学生课程', '教师培训', '平台服务'],
      })
    )
    return { ...session, messages, state, title: '新对话', updatedAt: now }
  }

  if (isOutOfScope(trimmed)) {
    if (/广州/.test(trimmed)) {
      messages.push(
        assistant(
          '该信息不在现有资料范围内，资料中暂无广州线下班，无法确认。建议联系人工客服。\n\n您也可以查看当前身份下的全部班型。',
          { quickActions: ['查看所有课程', '重新开始'] }
        )
      )
    } else {
      messages.push(
        assistant(
          '抱歉，我仅提供 AI 教育中心课程与平台服务咨询，无法回答该问题。请选择以下服务入口：',
          { quickActions: ['学生课程', '教师培训', '平台服务'] }
        )
      )
    }
    return { ...session, messages, state, updatedAt: now }
  }

  if (isCrossBoundary(trimmed, state.role)) {
    messages.push(
      assistant(
        '平台会员价格属于平台服务范畴，与学生/教师课程费用不同。如需了解平台会员，请切换至「平台服务」入口。',
        { quickActions: ['平台服务', '重新开始'] }
      )
    )
    return { ...session, messages, state, updatedAt: now }
  }

  if (state.step === 'welcome' || state.step === 'identity') {
    const role = detectRole(trimmed)
    if (!role) {
      state.step = 'identity'
      messages.push(
        assistant('请问您是为学生/家长咨询，教师咨询，还是机构/企业了解平台服务？', {
          quickActions: ['我是家长', '我是教师', '机构合作'],
        })
      )
      return { ...session, messages, state, updatedAt: now }
    }
    state.role = role
    if (role === 'org') {
      state.step = 'qa'
      messages.push(orgPlatformReply(trimmed))
      return { ...session, messages, state, updatedAt: now }
    }
    state.step = 'constraints'
    state.constraints = extractConstraints(trimmed, state.constraints)
    if (countConstraints(state.constraints) >= 2 && /推荐/.test(trimmed)) {
      // fall through to recommend below
    } else {
      messages.push(
        assistant(
          `已识别您为${role === 'student' ? '学生/家长' : '教师'}咨询。${missingConstraintPrompt(state.constraints)}`
        )
      )
      return { ...session, messages, state, updatedAt: now }
    }
  }

  if (state.role === 'org') {
    state.step = 'qa'
    messages.push(orgPlatformReply(trimmed))
    return { ...session, messages, state, updatedAt: now }
  }

  if (state.step === 'constraints') {
    if (/推荐/.test(trimmed) && !state.role) {
      messages.push(assistant('请先告诉我您的身份（学生/家长、教师或机构），再为您推荐班型。'))
      state.step = 'identity'
      return { ...session, messages, state, updatedAt: now }
    }

    state.constraints = extractConstraints(trimmed, state.constraints)
    const count = countConstraints(state.constraints)

    if (count < 2) {
      state.step = 'constraints'
      messages.push(assistant(missingConstraintPrompt(state.constraints)))
      return { ...session, messages, state, updatedAt: now }
    }

    const { courses, reasons, citations } = pickCourses(state.role!, state.constraints)
    state.step = 'recommend'
    state.recommendedCourses = courses
    state.lockedCourse = courses[0]
    const reasonText = reasons.map((r, i) => `${i + 1}. ${r}`).join('\n')
    messages.push(
      assistant(
        `根据您的需求，为您推荐以下班型：\n\n${courses.map((c) => `**${c}**`).join('\n')}\n\n推荐理由：\n${reasonText}\n\n如需了解费用、时间或报名，请继续提问。`,
        { citations, quickActions: ['这个班什么时候', '多少钱', '需要带什么', '查看所有课程'] }
      )
    )
    return { ...session, messages, state, updatedAt: now }
  }

  if (isListCoursesCommand(trimmed) && state.role) {
    const list =
      state.role === 'student'
        ? STUDENT_COURSES.join('、')
        : state.role === 'teacher'
          ? TEACHER_COURSES.join('、')
          : '平台服务（会员、企业合作、定制开发）'
    messages.push(assistant(`当前身份下可选内容：${list}`))
    return { ...session, messages, state, updatedAt: now }
  }

  if (/报名/.test(trimmed) && state.lockedCourse) {
    state.step = 'enroll'
    const { content, citations } = answerDetail(trimmed, state.lockedCourse, state.role!)
    messages.push(assistant(content, { citations }))
    return { ...session, messages, state, updatedAt: now }
  }

  if (state.lockedCourse || state.recommendedCourses.length > 0) {
    state.step = 'qa'
    const course = state.lockedCourse ?? state.recommendedCourses[0]!
    state.lockedCourse = course
    const { content, citations } = answerDetail(trimmed, course, state.role!)
    messages.push(assistant(content, { citations }))
    return { ...session, messages, state, updatedAt: now }
  }

  messages.push(
    assistant('请问需要学生课程、教师培训还是平台服务？', {
      quickActions: ['学生课程', '教师培训', '平台服务'],
    })
  )
  state.step = 'welcome'
  return { ...session, messages, state, updatedAt: now }
}

export function formatCitationFooter(citations?: CourseAgentCitation[]): string {
  if (!citations?.length) return ''
  return citations.map((c) => `来源：${c.document}${c.chapter}`).join('\n')
}

export { STUDENT_COURSES, TEACHER_COURSES, MAX_INPUT_LENGTH }
