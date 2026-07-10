import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await authApi.login({ email, password });
      login(res.access, res.refresh, res.user);
      navigate(res.user.role === 'teacher' ? '/dashboard' : '/student');
    } catch (err) {
      setError('Неверный email или пароль');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Вход</h1>
        <p className="subtitle">Рабочее пространство для репетитора и учеников</p>
        {error && <div className="form-error">{error}</div>}
        <form onSubmit={submit}>
          <div className="form-group">
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Пароль</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <button type="submit" disabled={loading} style={{ width: '100%', marginTop: 8 }}>
            {loading ? 'Вход...' : 'Войти'}
          </button>
        </form>
        <p style={{ marginTop: 16, textAlign: 'center' }}>
          <Link to="/register">Создать аккаунт</Link>
        </p>
      </div>
    </div>
  );
}
