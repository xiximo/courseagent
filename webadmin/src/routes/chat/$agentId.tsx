import { createFileRoute } from '@tanstack/react-router'
import { PublicChatPage } from '@/features/course-agent'

export const Route = createFileRoute('/chat/$agentId')({
  component: PublicChatPage,
})
