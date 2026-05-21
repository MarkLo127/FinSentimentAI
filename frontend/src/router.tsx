import { createBrowserRouter } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import Dashboard from './pages/Dashboard'
import StockDetail from './pages/StockDetail'
import NewsList from './pages/NewsList'
import NewsDetail from './pages/NewsDetail'
import Login from './pages/Login'
import Register from './pages/Register'
import Settings from './pages/Settings'

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      // Public
      { path: '/login', element: <Login /> },
      { path: '/register', element: <Register /> },
      // Everything else requires a logged-in user (per-user isolation)
      {
        element: <RequireAuth />,
        children: [
          { path: '/', element: <Dashboard /> },
          { path: '/stocks/:symbol', element: <StockDetail /> },
          { path: '/news', element: <NewsList /> },
          { path: '/news/:id', element: <NewsDetail /> },
          { path: '/settings', element: <Settings /> },
        ],
      },
    ],
  },
])
