import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, type RenderResult } from 'vitest-browser-react'
import { type Locator, userEvent } from 'vitest/browser'
import { SignUpForm } from './sign-up-form'

const FORM_MESSAGES = {
  orgEmpty: '请填写机构名称',
  passwordEmpty: '请输入密码',
  confirmPasswordEmpty: '请再次输入密码',
  passwordMismatch: '两次输入的密码不一致',
} as const

const navigate = vi.hoisted(() => vi.fn())
const setSession = vi.hoisted(() => vi.fn())
const registerOrganization = vi.hoisted(() => vi.fn())

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigate,
}))

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: () => ({ auth: { setSession } }),
}))

vi.mock('@/lib/api/auth', () => ({
  registerOrganization,
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

describe('SignUpForm', () => {
  let screen: RenderResult
  let orgInput: Locator
  let contactInput: Locator
  let usernameInput: Locator
  let passwordInput: Locator
  let confirmPasswordInput: Locator
  let submitButton: Locator

  beforeEach(async () => {
    vi.clearAllMocks()
    registerOrganization.mockResolvedValue({
      accessToken: 'token',
      tokenType: 'Bearer',
      expiresInSeconds: 3600,
      user: {
        id: '1',
        username: 'school01',
        fullName: '王老师',
        employeeNo: null,
        deptId: null,
        status: 'enabled',
        roleCodes: ['org_admin'],
        planCode: 'free',
        lastLoginAt: null,
      },
    })

    screen = await render(<SignUpForm />)
    orgInput = screen.getByLabelText(/^机构名称$/)
    contactInput = screen.getByLabelText(/^联系人$/)
    usernameInput = screen.getByLabelText(/^登录用户名$/)
    passwordInput = screen.getByLabelText(/^密码$/)
    confirmPasswordInput = screen.getByLabelText(/^确认密码$/)
    submitButton = screen.getByRole('button', { name: /开通并进入工作台/ })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders fields and submit button', async () => {
    await expect.element(orgInput).toBeInTheDocument()
    await expect.element(contactInput).toBeInTheDocument()
    await expect.element(usernameInput).toBeInTheDocument()
    await expect.element(passwordInput).toBeInTheDocument()
    await expect.element(confirmPasswordInput).toBeInTheDocument()
    await expect.element(submitButton).toBeInTheDocument()
  })

  it('shows validation messages when submitting empty form', async () => {
    await userEvent.click(submitButton)

    await expect.element(screen.getByText(FORM_MESSAGES.orgEmpty)).toBeInTheDocument()
    await expect.element(screen.getByText(FORM_MESSAGES.passwordEmpty)).toBeInTheDocument()
    await expect
      .element(screen.getByText(FORM_MESSAGES.confirmPasswordEmpty))
      .toBeInTheDocument()
  })

  it('shows a mismatch error when passwords do not match', async () => {
    await userEvent.fill(orgInput, '启明教育')
    await userEvent.fill(contactInput, '王老师')
    await userEvent.fill(usernameInput, 'school01')
    await userEvent.fill(passwordInput, '123456')
    await userEvent.fill(confirmPasswordInput, '654321')

    await userEvent.click(submitButton)
    await expect
      .element(screen.getByText(FORM_MESSAGES.passwordMismatch))
      .toBeInTheDocument()
  })

  it('registers the organization and enters /admin', async () => {
    await userEvent.fill(orgInput, '启明教育')
    await userEvent.fill(contactInput, '王老师')
    await userEvent.fill(usernameInput, 'school01')
    await userEvent.fill(passwordInput, '123456')
    await userEvent.fill(confirmPasswordInput, '123456')

    await userEvent.click(submitButton)

    await vi.waitFor(() => {
      expect(registerOrganization).toHaveBeenCalledWith({
        orgName: '启明教育',
        contactName: '王老师',
        username: 'school01',
        password: '123456',
      })
      expect(setSession).toHaveBeenCalled()
      expect(navigate).toHaveBeenCalledWith({ to: '/admin', replace: true })
    })
  })
})
