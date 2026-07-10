import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

interface Contest { id: number; title: string; description: string | null; updated_at: string }

export default function ContestsPage() {
  const [contests, setContests] = useState<Contest[]>([]);
  const [title, setTitle] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const navigate = useNavigate();

  const load = () => api<Contest[]>('/contests').then(setContests);
  useEffect(() => { load(); }, []);

  const create = async () => {
    const c = await api<{ id: number }>('/contests', { method: 'POST', body: JSON.stringify({ title }) });
    setShowCreate(false);
    navigate(`/contests/${c.id}`);
  };

  return (
    <>
      <div className="header" style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>Контесты</span>
        <button onClick={() => setShowCreate(true)}>Создать контест</button>
      </div>
      <div className="content">
        {contests.length === 0 ? (
          <div className="empty-state card">
            <h3>Нет контестов</h3>
            <p>Создайте переиспользуемый шаблон теста</p>
          </div>
        ) : (
          <div className="grid grid-2">
            {contests.map((c) => (
              <div key={c.id} className="card material-card" onClick={() => navigate(`/contests/${c.id}`)}>
                <strong>{c.title}</strong>
                <div style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: 4 }}>{c.description}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Новый контест</h2>
            <div className="form-group">
              <label>Название</label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="modal-actions">
              <button className="secondary" onClick={() => setShowCreate(false)}>Отмена</button>
              <button onClick={create} disabled={!title}>Создать</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
