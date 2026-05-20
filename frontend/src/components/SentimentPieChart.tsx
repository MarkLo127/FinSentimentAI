import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { getMarketToday } from '../services/api'
import { useChartTokens } from '../lib/chartTokens'
import { useIsMobile } from '../lib/useMediaQuery'
import { Card, CardHeader } from './ui'

export default function SentimentPieChart() {
  const { t } = useTranslation()
  const tokens = useChartTokens()
  const isMobile = useIsMobile()
  const { data, isLoading, error } = useQuery({
    queryKey: ['market', 'today'],
    queryFn: getMarketToday,
  })

  const chartData = data
    ? [
        {
          name: t('market.positive'),
          value: data.today.positive_count,
          fill: tokens.positive,
        },
        {
          name: t('market.neutral'),
          value: data.today.neutral_count,
          fill: tokens.neutral,
        },
        {
          name: t('market.negative'),
          value: data.today.negative_count,
          fill: tokens.negative,
        },
      ].filter((d) => d.value > 0)
    : []

  const total = chartData.reduce((sum, d) => sum + d.value, 0)

  return (
    <Card>
      <CardHeader
        title={t('pie.title')}
        meta={total > 0 ? t('pie.total', { count: total }) : undefined}
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
      {!isLoading && total === 0 && (
        <p className="text-text-subtle h-64 flex items-center text-sm">
          {t('pie.no_data_today')}
        </p>
      )}
      {total > 0 && (
        <div className="h-56 sm:h-60 md:h-64">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={isMobile ? 70 : 90}
                innerRadius={isMobile ? 42 : 55}
                stroke={tokens.tooltipBg}
                strokeWidth={2}
                label={({ name, value }) =>
                  isMobile
                    ? `${((value / total) * 100).toFixed(0)}%`
                    : `${name} ${((value / total) * 100).toFixed(0)}%`
                }
                labelLine={false}
              >
                {chartData.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip
                formatter={(v) =>
                  typeof v === 'number'
                    ? `${v} (${((v / total) * 100).toFixed(1)}%)`
                    : '—'
                }
                contentStyle={{
                  borderRadius: 10,
                  fontSize: 12,
                  background: tokens.tooltipBg,
                  border: `1px solid ${tokens.tooltipBorder}`,
                  color: tokens.text,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  )
}
