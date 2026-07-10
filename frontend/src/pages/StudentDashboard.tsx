import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';

interface Lesson { id: number; start_utc: string; status: string; room_open: boolean; space_id: number }
interface Assignment { id: number; contest_title: string; deadline_at: string; attempt_status: string; score: number | null }
interface Space { id: number; title: string }

export default function StudentDashboard() {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      const today = new Date();
      const to = new Date(today);
      to.setDate(to.getDate() + 14);
      const [cal, asg, sp] = await Promise.all([
        api<{ lessons: Lesson[] }>(`/calendar?from=${today.toISOString().slice(0, 10)}&to=${to.toISOString().slice(0, 10)}`),
        api<Assignment[]>('/assignments'),
        api<Space[]>('/spaces'),
      ]);
      setLessons(cal.lessons.slice(0, 5));
      setAssignments(asg.slice(0, 5));
      setSpaces(sp);
      setLoading(false);
    };
    load();
  }, []);

  if (loading) return <><div className="header">Дашборд</div><div className="content"><div className="skeleton" /></div></>;

  return (
    <>
      <div className="header">Дашборд</div>
      <div className="content">
        {spaces.length === 0 ? (
          <div className="empty-state card">
            <h3>Подключитесь к репетитору</h3>
            <p>Введите код приглашения от вашего учителя</p>
            <button onClick={() => navigate('/join')} style={{ marginTop: 16 }}>Подключиться к репетитору</button>
          </div>
        ) : (
          <>
            <section style={{ marginBottom: 32 }}>
              <h2 style={{ marginBottom: 12 }}>Ближайшие занятия</h2>
              <div className="grid grid-2">
                {lessons.map((l) => (
                  <div key={l.id} className="card">
                    <div>{new Date(l.start_utc).toLocaleString()}</div>
                    {l.room_open && <button onClick={() => navigate(`/room/${l.id}`)}>Войти</button>}
                  </div>
                ))}
              </div>
            </section>

            <section style={{ marginBottom: 32 }}>
              <h2 style={{ marginBottom: 12 }}>Задания</h2>
              <Link to="/assignments">Все задания →</Link>
              <div className="grid grid-2" style={{ marginTop: 12 }}>
                {assignments.map((a) => (
                  <div key={a.id} className="card">
                    <strong>{a.contest_title}</strong>
                    <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>до {new Date(a.deadline_at).toLocaleString()}</div>
                    <span className="badge">{a.attempt_status}</span>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <h2 style={{ marginBottom: 12 }}>Мои материалы</h2>
              <button className="secondary" onClick={() => navigate('/storage')}>Открыть хранилище</button>
            </section>
          </>
        )}
      </div>
    </>
  );
}
