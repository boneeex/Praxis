import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';

interface Space { id: number; title: string; invite_code: string; kind: string }
interface Lesson { id: number; space_id: number; start_utc: string; end_utc: string; status: string; room_open: boolean }
interface Material { id: number; title: string; type: string; updated_at: string }

export default function TeacherDashboard() {
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      try {
        const today = new Date();
        const to = new Date(today);
        to.setDate(to.getDate() + 14);
        const [sp, cal] = await Promise.all([
          api<Space[]>('/spaces'),
          api<{ lessons: Lesson[] }>(`/calendar?from=${today.toISOString().slice(0, 10)}&to=${to.toISOString().slice(0, 10)}`),
        ]);
        setSpaces(sp);
        setLessons(cal.lessons.filter((l) => l.status !== 'cancelled').slice(0, 5));
        if (sp[0]) {
          const mats = await api<Material[]>(`/spaces/${sp[0].id}/materials?sort=recent`);
          setMaterials(mats.slice(0, 6));
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const copyInvite = (code: string) => {
    navigator.clipboard.writeText(`${window.location.origin}/join/${code}`);
  };

  if (loading) return <><div className="header">Дашборд</div><div className="content"><div className="skeleton" /></div></>;

  return (
    <>
      <div className="header">Дашборд</div>
      <div className="content">
        <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
          <button onClick={() => navigate('/schedule')}>Создать занятие</button>
          <button className="secondary" onClick={() => navigate('/storage')}>Создать материал</button>
          <button className="secondary" onClick={() => navigate('/contests')}>Создать контест</button>
        </div>

        {spaces.length === 0 ? (
          <div className="empty-state card">
            <h3>Добро пожаловать в Praxis</h3>
            <p>Создайте первое пространство и пригласите ученика</p>
            <button onClick={() => navigate('/spaces')} style={{ marginTop: 16 }}>Создать пространство</button>
          </div>
        ) : (
          <>
            <section style={{ marginBottom: 32 }}>
              <h2 style={{ marginBottom: 12 }}>Ближайшие занятия</h2>
              {lessons.length === 0 ? (
                <p className="empty-state">Нет запланированных занятий</p>
              ) : (
                <div className="grid grid-2">
                  {lessons.map((l) => (
                    <div key={l.id} className="card">
                      <div>{new Date(l.start_utc).toLocaleString()}</div>
                      <span className="badge">{l.status}</span>
                      {l.room_open && <button onClick={() => navigate(`/room/${l.id}`)} style={{ marginTop: 8 }}>Открыть комнату</button>}
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section style={{ marginBottom: 32 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                <h2>Ученики и группы</h2>
                <Link to="/spaces">Все ученики →</Link>
              </div>
              <div className="grid grid-2">
                {spaces.map((s) => (
                  <div key={s.id} className="card">
                    <strong>{s.title}</strong>
                    <span className="badge" style={{ marginLeft: 8 }}>{s.kind === 'single' ? '1:1' : 'группа'}</span>
                    <button className="secondary" style={{ marginTop: 8 }} onClick={() => copyInvite(s.invite_code)}>Копировать ссылку</button>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <h2 style={{ marginBottom: 12 }}>Недавние материалы</h2>
              <div className="grid grid-3">
                {materials.map((m) => (
                  <div key={m.id} className="card material-card" onClick={() => navigate(`/storage/${m.id}`)}>
                    <span className="badge">{m.type}</span>
                    <div style={{ marginTop: 8 }}>{m.title}</div>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </>
  );
}
