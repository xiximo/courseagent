export const courseAgentKeys = {
  all: ['course-agents'] as const,
  list: () => [...courseAgentKeys.all, 'list'] as const,
}
