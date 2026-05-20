import { Minus, TrendingDown, TrendingUp } from 'lucide-react'
import type { ReactElement } from 'react'
import { useTranslation } from 'react-i18next'
import type { SentimentLabel } from '../types/api'
import Badge, { type BadgeTone } from './ui/Badge'

const ICON: Record<SentimentLabel, ReactElement> = {
  positive: <TrendingUp size={12} />,
  negative: <TrendingDown size={12} />,
  neutral: <Minus size={12} />,
}

const TONE: Record<SentimentLabel, BadgeTone> = {
  positive: 'positive',
  negative: 'negative',
  neutral: 'neutral',
}

const I18N_KEY: Record<SentimentLabel, string> = {
  positive: 'sentiment.positive',
  negative: 'sentiment.negative',
  neutral: 'sentiment.neutral',
}

interface Props {
  label: SentimentLabel
  confidence?: number
  size?: 'sm' | 'md'
}

export default function SentimentBadge({ label, confidence, size = 'md' }: Props) {
  const { t } = useTranslation()
  return (
    <Badge tone={TONE[label]} size={size} icon={ICON[label]}>
      <span>{t(I18N_KEY[label])}</span>
      {confidence != null && (
        <span className="opacity-75 tabular-nums font-mono">
          {(confidence * 100).toFixed(0)}%
        </span>
      )}
    </Badge>
  )
}
