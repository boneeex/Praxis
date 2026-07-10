import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

interface Lesson { id: number; space_id: number; start_utc: string; end_utc: string; status: string; room_open: boolean }
interface Deadline { id: number; contest_id: number; deadline_at: string; space_id: number }
interface Space { id: number; title: string }
interface AvailabilityRule { id?: number; weekday: number; start_time: string; end_time: string }

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

export default function SchedulePage() {
  const { user } = useAuth();
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [deadlines, setDeadlines] = useState<Deadline[]>([]);
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [rules, setRules] = useState<AvailabilityRule[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [showSlots, setShowSlots] = useState(false);
  const [slots, setSlots] = useState<{ start_utc: string; end_utc: string }[]>([]);
  const [spaceId, setSpaceId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState('');
  const [duration, setDuration] = useState(60);
  const [repeat, setRepeat] = useState(false);
  const navigate = useNavigate();
  const isTeacher = user?.role === 'teacher';

  const load = async () => {
    const from = new Date();
    const to = new Date();
    to.setDate(to.getDate() + 30);
    const [cal, avail, sp] = await Promise.all([
      api<{ lessons: Lesson[]; deadlines: Deadline[] }>(`/calendar?from=${from.toISOString().slice(0, 10)}&to=${to.toISOString().slice(0, 10)}`),
      api<{ rules: AvailabilityRule[] }>('/me/availability'),
      api<Space[]>('/spaces'),
    ]);
    setLessons(cal.lessons);
    setDeadlines(cal.deadlines);
    setRules(avail.rules);
    setSpaces(sp);
    if (sp[0]) setSpaceId(sp[0].id);
  };

  useEffect(() => { load(); }, []);

  const createLesson = async () => {
    if (!spaceId || !startDate) return;
    const start = new Date(startDate);
    if (repeat) {
      await api(`/spaces/${spaceId}/series`, {
        method: 'POST',
        body: JSON.stringify({
          weekday: start.getDay() === 0 ? 6 : start.getDay() - 1,
          start_time: `${String(start.getHours()).padStart(2, '0')}:${String(start.getMinutes()).padStart(2, '0')}:00`,
          duration_min: duration,
          timezone: user?.timezone || 'UTC',
          starts_on: start.toISOString().slice(0, 10),
        }),
      });
    } else {
      await api(`/spaces/${spaceId}/lessons`, {
        method: 'POST',
        body: JSON.stringify({ scheduled_start_utc: start.toISOString(), duration_min: duration }),
      });
    }
    setShowCreate(false);
    load();
  };

  const findSlots = async () => {
    if (!spaceId) return;
    const from = new Date();
    const to = new Date();
    to.setDate(to.getDate() + 14);
    const res = await api<{ slots: { start_utc: string; end_utc: string }[] }>(`/spaces/${spaceId}/find-slots`, {
      method: 'POST',
      body: JSON.stringify({ duration_min: duration, from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) }),
    });
    setSlots(res.slots);
    setShowSlots(true);
  };

  const saveRules = async () => {
    await api('/me/availability/rules', { method: 'PUT', body: JSON.stringify(rules) });
    alert('Сохранено');
  };

  const addRule = () => {
    setRules([...rules, { weekday: 0, start_time: '09:00:00', end_time: '18:00:00' }]);
  };

  const cancelLesson = async (id: number) => {
    if (!confirm('Отменить занятие?')) return;
    await api(`/lessons/${id}/cancel`, { method: 'POST', body: JSON.stringify({ scope: 'this' }) });
    load();
  };

  return (
    <>
      <div className="header" style={{ display: 'flex', gap: 12 }}>
        <span>Расписание</span>
        {isTeacher && (
          <>
            <button onClick={() => setShowCreate(true)}>Поставить занятие</button>
            <button className="secondary" onClick={findSlots}>Найти время</button>
          </>
        )}
      </div>
      <div className="content">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24 }}>
          <div>
            <h3 style={{ marginBottom: 12 }}>Занятия</h3>
            {lessons.length === 0 ? (
              <div className="empty-state card">Нет занятий</div>
            ) : (
              lessons.map((l) => (
                <div key={l.id} className="card" style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong>{new Date(l.start_utc).toLocaleString()}</strong>
                    <span className="badge" style={{ marginLeft: 8 }}>{l.status}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {(l.room_open || l.status === 'scheduled') && (
                      <button onClick={() => navigate(`/room/${l.id}`)}>{l.room_open ? 'Войти' : 'Комната'}</button>
                    )}
                    {isTeacher && l.status === 'scheduled' && (
                      <button className="danger" onClick={() => cancelLesson(l.id)}>Отменить</button>
                    )}
                  </div>
                </div>
              ))
            )}

            {deadlines.length > 0 && (
              <>
                <h3 style={{ margin: '24px 0 12px' }}>Дедлайны</h3>
                {deadlines.map((d) => (
                  <div key={d.id} className="card" style={{ marginBottom: 8, opacity: 0.8 }}>
                    Дедлайн контеста: {new Date(d.deadline_at).toLocaleString()}
                  </div>
                ))}
              </>
            )}
          </div>

          <div className="card">
            <h3>Моя доступность</h3>
            {rules.map((r, i) => (
              <div key={i} style={{ marginBottom: 8 }}>
                <select value={r.weekday} onChange={(e) => {
                  const next = [...rules];
                  next[i] = { ...r, weekday: Number(e.target.value) };
                  setRules(next);
                }}>
                  {WEEKDAYS.map((d, j) => <option key={j} value={j}>{d}</option>)}
                </select>
                <input type="time" value={r.start_time.slice(0, 5)} onChange={(e) => {
                  const next = [...rules];
                  next[i] = { ...r, start_time: e.target.value + ':00' };
                  setRules(next);
                }} style={{ width: 'auto', marginLeft: 4 }} />
                —
                <input type="time" value={r.end_time.slice(0, 5)} onChange={(e) => {
                  const next = [...rules];
                  next[i] = { ...r, end_time: e.target.value + ':00' };
                  setRules(next);
                }} style={{ width: 'auto' }} />
              </div>
            ))}
            <button className="secondary" onClick={addRule} style={{ width: '100%', marginBottom: 8 }}>+ Интервал</button>
            <button onClick={saveRules} style={{ width: '100%' }}>Сохранить</button>
          </div>
        </div>
      </div>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Новое занятие</h2>
            <div className="form-group">
              <label>Пространство</label>
              <select value={spaceId ?? ''} onChange={(e) => setSpaceId(Number(e.target.value))}>
                {spaces.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Дата и время</label>
              <input type="datetime-local" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Длительность (мин)</label>
              <input type="number" value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
            </div>
            <label><input type="checkbox" checked={repeat} onChange={(e) => setRepeat(e.target.checked)} /> Повторять еженедельно</label>
            <div className="modal-actions">
              <button className="secondary" onClick={() => setShowCreate(false)}>Отмена</button>
              <button onClick={createLesson}>Создать</button>
            </div>
          </div>
        </div>
      )}

      {showSlots && (
        <div className="modal-overlay" onClick={() => setShowSlots(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Общие свободные слоты</h2>
            {slots.length === 0 ? (
              <p>Недостаточно данных о доступности</p>
            ) : (
              slots.slice(0, 20).map((s, i) => (
                <button
                  key={i}
                  className="secondary"
                  style={{ display: 'block', width: '100%', marginBottom: 4, textAlign: 'left' }}
                  onClick={() => { setStartDate(new Date(s.start_utc).toISOString().slice(0, 16)); setShowSlots(false); setShowCreate(true); }}
                >
                  {new Date(s.start_utc).toLocaleString()} — {new Date(s.end_utc).toLocaleTimeString()}
                </button>
              ))
            )}
            <div className="modal-actions">
              <button onClick={() => setShowSlots(false)}>Закрыть</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
