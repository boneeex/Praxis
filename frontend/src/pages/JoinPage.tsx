import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

export default function JoinPage() {
  const { code: urlCode } = useParams();
  const [code, setCode] = useState(urlCode || '');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (urlCode) setCode(urlCode);
  }, [urlCode]);

  const join = async () => {
    setError('');
    try {
      const space = await api<{ title: string }>('/join', { method: 'POST', body: JSON.stringify({ invite_code: code }) });
      setToast(`Вы подключены к ${space.title}`);
      setTimeout(() => navigate('/student'), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Код недействителен');
    }
  };

  if (loading) return <div className="auth-page"><div className="skeleton auth-card" /></div>;

  if (!user) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>Приглашение</h1>
          <p className="subtitle">Войдите или зарегистрируйтесь, чтобы присоединиться</p>
          <p>Код: <strong>{code}</strong></p>
          <Link to={`/register`}><button style={{ width: '100%', marginTop: 16 }}>Регистрация ученика</button></Link>
          <Link to="/login"><button className="secondary" style={{ width: '100%', marginTop: 8 }}>Войти</button></Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Подключиться к репетитору</h1>
        {error && <div className="form-error">{error}</div>}
        {toast && <div style={{ color: 'green', marginBottom: 12 }}>{toast}</div>}
        <div className="form-group">
          <label>Код приглашения</label>
          <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="ABCD1234" />
        </div>
        <button onClick={join} style={{ width: '100%' }}>Подключиться</button>
      </div>
    </div>
  );
}
