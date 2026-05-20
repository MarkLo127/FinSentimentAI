import { createBrowserRouter } from 'react-router-dom'
import Layout from './components/Layout'
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
      { path: '/', element: <Dashboard /> },
      { path: '/stocks/:symbol', element: <StockDetail /> },
      { path: '/news', element: <NewsList /> },
      { path: '/news/:id', element: <NewsDetail /> },
      { path: '/settings', element: <Settings /> },
      { path: '/login', element: <Login /> },
      { path: '/register', element: <Register /> },
    ],
  },
])
