import { Outlet } from 'react-router-dom'
import GlobalRefreshIndicator from './GlobalRefreshIndicator'
import TopBar from './TopBar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <TopBar />
      <GlobalRefreshIndicator />
      <main>
        <Outlet />
      </main>
    </div>
  )
}
