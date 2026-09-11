from pydantic import BaseModel, Field


class BillingPlanDto(BaseModel):
    code: str
    name: str
    priceLabel: str
    priceCents: int = 0
    chatLimit: int | None = None
    knowledgeBaseLimit: int | None = None
    features: list[str] = Field(default_factory=list)
    highlighted: bool = False


class BillingUsageDto(BaseModel):
    yearMonth: str
    used: int
    limit: int | None = None
    remaining: int | None = None


class BillingMeDto(BaseModel):
    planCode: str
    planName: str
    planUpgradedAt: str | None = None
    usage: BillingUsageDto
    canManageKnowledge: bool = True
    canUseHarnessAgent: bool = False
    knowledgeBaseLimit: int | None = None
    knowledgeBaseUsed: int = 0
    canCreateKnowledgeBase: bool = True


class CreateBillingOrderBody(BaseModel):
    planCode: str = "pro"


class BillingOrderDto(BaseModel):
    id: str
    planCode: str
    amountCents: int
    status: str
    channel: str = "alipay"
    providerTradeNo: str | None = None
    createdAt: str
    paidAt: str | None = None


class BillingPayOptionsDto(BaseModel):
    alipaySandbox: bool = True
    alipayReady: bool = False
    mockPayEnabled: bool = True
    gateway: str = ""
    stripeReady: bool = False
    stripeMode: str = "unknown"
    stripeCurrency: str = "cny"


class AlipayPagePayDto(BaseModel):
    orderId: str
    payUrl: str
    gateway: str


class StripeCheckoutDto(BaseModel):
    orderId: str
    payUrl: str
    sessionId: str
    mode: str


class UsageTrendPointDto(BaseModel):
    date: str
    chatCount: int
    activeUsers: int = 0


class UsageUserRankDto(BaseModel):
    userId: str
    username: str
    fullName: str
    chatCount: int


class AdminUsageStatsDto(BaseModel):
    totalChats: int
    activeUsers: int
    freeUsers: int
    proUsers: int
    trend: list[UsageTrendPointDto] = Field(default_factory=list)
    topUsers: list[UsageUserRankDto] = Field(default_factory=list)
