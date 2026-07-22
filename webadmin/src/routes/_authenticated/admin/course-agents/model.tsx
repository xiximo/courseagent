import { createFileRoute, redirect } from '@tanstack/react-router'

/** 旧路径兼容：/admin/course-agents/model → /admin/models */
export const Route = createFileRoute('/_authenticated/admin/course-agents/model')({
  beforeLoad: () => {
    throw redirect({ to: '/admin/models' })
  },
})
