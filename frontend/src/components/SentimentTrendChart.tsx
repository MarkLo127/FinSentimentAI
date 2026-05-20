import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getMarketHistory, getStock, getStocks } from '../services/api'
import { useChartTokens } from '../lib/chartTokens'
import { useIsMobile } from '../lib/useMediaQuery'
import { Card, CardHeader } from './ui'

// Fixed lookback window — sentiment stats over ~3 months are enough context
// for the user to spot patterns; data volume is too sparse for a multi-range
// selector to add value.
const RANGE_DAYS = 90

interface DailyPoint {
  summary_date: string
  positive_count: number
  neutral_count: number
  negative_count: number
  total_count: number
}

const ALL = '__all__'

/** Grouped bar chart of daily sentiment counts (positive/neutral/negative).
 *  The user can scope the chart to a specific stock or aggregate across
 *  all monitored stocks via the dropdown. */
export default function SentimentTrendChart() {
  const { t } = useTranslation()
  const tokens = useChartTokens()
  const isMobile = useIsMobile()
  const [symbol, setSymbol] = useState<string>(ALL)

  const stocksQ = useQuery({
    queryKey: ['stocks', { limit: 200 }],
    queryFn: () => getStocks({ limit: 200 }),
  })

  const marketQ = useQuery({
    queryKey: ['market', 'history', RANGE_DAYS],
    queryFn: () => getMarketHistory(RANGE_DAYS),
    enabled: symbol === ALL,
  })

  const stockQ = useQuery({
    queryKey: ['stock', symbol, RANGE_DAYS],
    queryFn: () => getStock(symbol, RANGE_DAYS),
    enabled: symbol !== ALL,
  })

  const isLoading = symbol === ALL ? marketQ.isLoading : stockQ.isLoading
  const error = symbol === ALL ? marketQ.error : stockQ.error
  const data: DailyPoint[] =
    symbol === ALL ? (marketQ.data ?? []) : (stockQ.data?.trend ?? [])

  const chartData = data.map((p) => ({
    label: p.summary_date.slice(5),
    positive: p.positive_count,
    neutral: p.neutral_count,
    negative: p.negative_count,
  }))

  return (
    <Card>
      <CardHeader
        title={t('stats.title')}
        action={
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            aria-label={t('stats.select_stock')}
            title={t('stats.select_stock')}
            className="h-9 max-w-full rounded-lg border border-border bg-surface text-text text-sm px-3 pr-8 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          >
            <option value={ALL}>{t('stats.all_stocks')}</option>
            {(stocksQ.data ?? []).map((s) => (
              <option key={s.symbol} value={s.symbol}>
                {s.symbol} — {s.name}
              </option>
            ))}
          </select>
        }
      />

      {isLoading && (
        <p className="text-text-subtle h-64 flex items-center text-sm">
          {t('common.loading')}
        </p>
      )}
      {error && (
        <p className="text-sentiment-negative text-sm h-64 flex items-center">
          {t('common.failed_to_load')}：{String(error)}
        </p>
      )}
      {!isLoading && chartData.length === 0 && (
        <p className="text-text-subtle h-64 flex items-center text-sm">
          {t('trend.no_data_range')}
        </p>
      )}
      {chartData.length > 0 && (
        <div className="h-56 sm:h-64 md:h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              margin={{ top: 10, right: isMobile ? 4 : 20, bottom: 0, left: isMobile ? -20 : -10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={tokens.grid} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: isMobile ? 10 : 11, fill: tokens.axis }}
                stroke={tokens.grid}
                interval={isMobile ? Math.max(0, Math.floor(chartData.length / 6) - 1) : 'preserveStartEnd'}
                minTickGap={isMobile ? 8 : 4}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: isMobile ? 10 : 11, fill: tokens.axis }}
                stroke={tokens.grid}
                width={isMobile ? 28 : 40}
              />
              <Tooltip
                cursor={{ fill: tokens.grid, opacity: 0.4 }}
                contentStyle={{
                  borderRadius: 10,
                  fontSize: 12,
                  background: tokens.tooltipBg,
                  border: `1px solid ${tokens.tooltipBorder}`,
                  color: tokens.text,
                }}
                labelStyle={{ color: tokens.text }}
                formatter={(v, name) => [
                  v as number,
                  t(`sentiment.${String(name)}`),
                ]}
              />
              <Legend
                wrapperStyle={{ fontSize: 12, color: tokens.text }}
                formatter={(value) => t(`sentiment.${value}`)}
              />
              <Bar dataKey="positive" fill={tokens.positive} radius={[4, 4, 0, 0]} />
              <Bar dataKey="neutral" fill={tokens.neutral} radius={[4, 4, 0, 0]} />
              <Bar dataKey="negative" fill={tokens.negative} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="text-xs text-text-subtle mt-2">{t('stats.hint')}</p>
    </Card>
  )
}
