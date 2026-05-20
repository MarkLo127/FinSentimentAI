import { useTranslation } from 'react-i18next'
import LatestNewsFeed from '../components/LatestNewsFeed'
import MarketSentimentCard from '../components/MarketSentimentCard'
import SentimentPieChart from '../components/SentimentPieChart'
import SentimentTrendChart from '../components/SentimentTrendChart'
import TopStockRanking from '../components/TopStockRanking'

export default function Dashboard() {
  const { t } = useTranslation()
  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 py-4 sm:py-6 md:py-8 space-y-4 sm:space-y-6 md:space-y-8">
      <header>
        <h1 className="text-xl sm:text-2xl md:text-3xl font-semibold text-text">
          {t('dashboard.title')}
        </h1>
        <p className="text-sm md:text-base text-text-muted mt-1">
          {t('dashboard.subtitle')}
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-5 md:gap-6">
        <MarketSentimentCard />
        <SentimentPieChart />
      </div>

      <SentimentTrendChart />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-5 md:gap-6">
        <TopStockRanking />
        <LatestNewsFeed />
      </div>
    </div>
  )
}
