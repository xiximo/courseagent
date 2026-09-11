import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useTheme } from '@/context/theme-provider'
import type { UsageTrendPoint, UsageUserRank } from '@/lib/api/billing'

function readCssColor(name: string, fallback: string) {
  if (typeof document === 'undefined') return fallback
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim()
  return value || fallback
}

function useChartTheme() {
  const { resolvedTheme } = useTheme()
  return useMemo(() => {
    const dark = resolvedTheme === 'dark'
    return {
      dark,
      text: readCssColor('--muted-foreground', dark ? '#94a3b8' : '#64748b'),
      title: readCssColor('--foreground', dark ? '#f8fafc' : '#0f172a'),
      border: readCssColor('--border', dark ? '#1e293b' : '#e2e8f0'),
      split: dark ? 'rgba(148,163,184,0.16)' : 'rgba(100,116,139,0.16)',
      primary: dark ? '#38bdf8' : '#0284c7',
      secondary: dark ? '#34d399' : '#059669',
      bar: dark ? '#818cf8' : '#4f46e5',
      tooltipBg: dark ? 'rgba(15,23,42,0.94)' : 'rgba(255,255,255,0.96)',
      tooltipText: dark ? '#e2e8f0' : '#0f172a',
    }
  }, [resolvedTheme])
}

function formatTrendDate(value: string) {
  const parts = value.split('-')
  if (parts.length >= 3) return `${parts[1]}-${parts[2]}`
  return value
}

function shortLabel(name: string) {
  return name.length > 8 ? `${name.slice(0, 8)}…` : name
}

export function UsageTrendChart({ data }: { data: UsageTrendPoint[] }) {
  const theme = useChartTheme()
  const option = useMemo<EChartsOption>(
    () => ({
      color: [theme.primary, theme.secondary],
      tooltip: {
        trigger: 'axis',
        backgroundColor: theme.tooltipBg,
        borderColor: theme.border,
        borderWidth: 1,
        textStyle: { color: theme.tooltipText, fontSize: 12 },
        axisPointer: {
          type: 'line',
          lineStyle: { color: theme.split, width: 1 },
        },
      },
      legend: {
        data: ['对话次数', '活跃用户'],
        right: 8,
        top: 4,
        icon: 'roundRect',
        itemWidth: 12,
        itemHeight: 8,
        textStyle: { color: theme.text, fontSize: 12 },
      },
      grid: { left: 44, right: 18, top: 44, bottom: 32, containLabel: false },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: data.map((item) => formatTrendDate(item.date)),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: theme.border } },
        axisLabel: { color: theme.text, fontSize: 11, hideOverlap: true },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { color: theme.text, fontSize: 11 },
        splitLine: { lineStyle: { color: theme.split, type: 'dashed' } },
      },
      series: [
        {
          name: '对话次数',
          type: 'line',
          smooth: 0.35,
          symbol: 'circle',
          showSymbol: false,
          symbolSize: 7,
          lineStyle: { width: 2.5 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: theme.dark ? 'rgba(56,189,248,0.28)' : 'rgba(2,132,199,0.18)' },
                { offset: 1, color: 'rgba(56,189,248,0)' },
              ],
            },
          },
          data: data.map((item) => item.chatCount),
        },
        {
          name: '活跃用户',
          type: 'line',
          smooth: 0.35,
          symbol: 'circle',
          showSymbol: false,
          symbolSize: 7,
          lineStyle: { width: 2.5 },
          data: data.map((item) => item.activeUsers),
        },
      ],
    }),
    [data, theme]
  )
  return <ReactECharts option={option} style={{ height: 300, width: '100%' }} />
}

export function UsageTopUsersChart({ data }: { data: UsageUserRank[] }) {
  const theme = useChartTheme()
  const rows = useMemo(
    () =>
      [...data]
        .sort((a, b) => b.chatCount - a.chatCount)
        .map((item, index) => ({
          rank: index + 1,
          name: item.fullName?.trim() || item.username,
          username: item.username,
          value: item.chatCount,
        })),
    [data]
  )
  const option = useMemo<EChartsOption>(
    () => ({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: theme.tooltipBg,
        borderColor: theme.border,
        textStyle: { color: theme.tooltipText, fontSize: 12 },
        formatter: (params) => {
          const point = Array.isArray(params) ? params[0] : params
          const idx = Number(point?.dataIndex ?? 0)
          const row = rows[idx]
          if (!row?.name) return ''
          return `NO.${row.rank} ${row.name}<br/>用户名：${row.username}<br/>对话次数：${row.value}`
        },
      },
      grid: { left: 48, right: 20, top: 36, bottom: 72 },
      xAxis: {
        type: 'category',
        data: rows.map((item) => shortLabel(item.name)),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: theme.border } },
        axisLabel: {
          color: theme.text,
          fontSize: 12,
          interval: 0,
          hideOverlap: false,
          lineHeight: 16,
        },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { color: theme.text, fontSize: 11 },
        splitLine: { lineStyle: { color: theme.split, type: 'dashed' } },
      },
      series: [
        {
          name: '对话次数',
          type: 'bar',
          barMaxWidth: 56,
          barMinHeight: 4,
          itemStyle: {
            borderRadius: [10, 10, 0, 0],
          },
          label: {
            show: true,
            position: 'top',
            color: theme.title,
            fontSize: 12,
            fontWeight: 600,
          },
          data: rows.map((item, index) => ({
            value: item.value,
            itemStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops:
                  index === 0
                    ? [
                        { offset: 0, color: theme.dark ? '#fde68a' : '#f59e0b' },
                        { offset: 1, color: theme.dark ? '#d97706' : '#b45309' },
                      ]
                    : index === 1
                      ? [
                          { offset: 0, color: theme.dark ? '#e2e8f0' : '#94a3b8' },
                          { offset: 1, color: theme.dark ? '#64748b' : '#475569' },
                        ]
                      : index === 2
                        ? [
                            { offset: 0, color: theme.dark ? '#fdba74' : '#fb923c' },
                            { offset: 1, color: theme.dark ? '#c2410c' : '#c2410c' },
                          ]
                        : [
                            { offset: 0, color: theme.dark ? '#a5b4fc' : '#818cf8' },
                            { offset: 1, color: theme.dark ? '#4f46e5' : '#4338ca' },
                          ],
              },
            },
          })),
        },
      ],
    }),
    [rows, theme]
  )

  if (rows.length === 0) {
    return (
      <p className='text-muted-foreground flex h-[340px] items-center justify-center text-sm'>
        暂无成员对话
      </p>
    )
  }

  return <ReactECharts option={option} style={{ height: 340, width: '100%' }} />
}
