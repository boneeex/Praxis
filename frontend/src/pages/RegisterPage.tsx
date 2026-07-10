import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

const TIMEZONES = Intl.supportedValuesOf?.('timeZone') || ['UTC', 'Europe/Moscow', 'Europe/Berlin'];

export default function RegisterPage() {
  const [role, setRole] = useState<'teacher' | 'student'>('teacher');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password.length < 8) {
      setError('Пароль должен быть не менее 8 символов');
      return;
    }
    setLoading(true);
    try {
      const res = await authApi.register({ email, password, display_name: displayName, role, timezone });
      login(res.access, res.refresh, res.user);
      navigate(role === 'teacher' ? '/dashboard' : '/student');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка регистрации');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Создать аккаунт</h1>
        <div className="role-toggle">
          <button type="button" className={role === 'teacher' ? 'active' : ''} onClick={() => setRole('teacher')}>Я репетитор</button>
          <button type="button" className={role === 'student' ? 'active' : ''} onClick={() => setRole('student')}>Я ученик</button>
        </div>
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
          <div className="form-group">
            <label>Отображаемое имя</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Таймзона</label>
            <select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
              {TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
            </select>
          </div>
          <button type="submit" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Создание...' : 'Создать аккаунт'}
          </button>
        </form>
        <p style={{ marginTop: 16, textAlign: 'center' }}>
          <Link to="/login">Уже есть аккаунт? Войти</Link>
        </p>
      </div>
    </div>
  );
}
