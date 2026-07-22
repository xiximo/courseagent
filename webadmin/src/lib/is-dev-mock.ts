export function isDevMock(): boolean {
  return (
    import.meta.env.VITE_DEV_MOCK === 'true' ||
    import.meta.env.VITE_QIBIAO_MOCK === 'true'
  )
}

export async function withMockDelay<T>(data: T, ms = 600): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, ms))
  return data
}
