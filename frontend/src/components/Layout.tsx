import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const teacherNav = [
    { to: '/dashboard', label: 'Дашборд' },
    { to: '/spaces', label: 'Ученики и группы' },
    { to: '/storage', label: 'Хранилище' },
    { to: '/contests', label: 'Контесты' },
    { to: '/schedule', label: 'Расписание' },
    { to: '/analytics', label: 'Аналитика' },
  ];

  const studentNav = [
    { to: '/student', label: 'Дашборд' },
    { to: '/storage', label: 'Мои материалы' },
    { to: '/assignments', label: 'Задания' },
    { to: '/schedule', label: 'Расписание' },
  ];

  const nav = user?.role === 'teacher' ? teacherNav : studentNav;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="logo">Praxis</div>
        {nav.map((item) => (
          <NavLink key={item.to} to={item.to} className={({ isActive }) => isActive ? 'active' : ''}>
            {item.label}
          </NavLink>
        ))}
        <div className="bottom">
          <div style={{ padding: '8px 12px', fontSize: '0.85rem' }}>{user?.display_name}</div>
          <button className="secondary" style={{ width: '100%', marginTop: 8 }} onClick={handleLogout}>
            Выйти
          </button>
        </div>
      </aside>
      <div className="main">
        <Outlet />
      </div>
    </div>
  );
}
