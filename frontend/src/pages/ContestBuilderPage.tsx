import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';

interface Question {
  id: number;
  position: number;
  type: string;
  prompt: string;
  points: number;
  config: Record<string, unknown>;
  tests?: { id: number; stdin: string; expected_stdout: string; is_sample: boolean; weight: number }[];
}

interface Contest {
  id: number;
  title: string;
  description: string | null;
  time_limit_sec: number | null;
  shuffle_questions: boolean;
  max_attempts: number | null;
  questions: Question[];
}

interface Space { id: number; title: string }

export default function ContestBuilderPage() {
  const { id } = useParams();
  const [contest, setContest] = useState<Contest | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [showAssign, setShowAssign] = useState(false);
  const [assignSpace, setAssignSpace] = useState<number | null>(null);
  const [deadline, setDeadline] = useState('');
  const navigate = useNavigate();

  const load = () => api<Contest>(`/contests/${id}`).then((c) => {
    setContest(c);
    if (c.questions[0] && !selected) setSelected(c.questions[0].id);
  });

  useEffect(() => { load(); api<Space[]>('/spaces').then(setSpaces); }, [id]);

  const addQuestion = async (type: string) => {
    await api(`/contests/${id}/questions`, {
      method: 'POST',
      body: JSON.stringify({ type, prompt: 'Новый вопрос', points: 1, config: type.includes('choice') ? { options: [{ id: 'a', text: 'Вариант A' }], correct: ['a'] } : {} }),
    });
    load();
  };

  const updateQuestion = async (qid: number, data: object) => {
    await api(`/questions/${qid}`, { method: 'PATCH', body: JSON.stringify(data) });
    load();
  };

  const addTest = async (qid: number) => {
    await api(`/questions/${qid}/tests`, {
      method: 'POST',
      body: JSON.stringify({ stdin: '', expected_stdout: '', is_sample: true, weight: 1 }),
    });
    load();
  };

  const assign = async () => {
    if (!assignSpace || !deadline) return;
    await api(`/contests/${id}/assign`, {
      method: 'POST',
      body: JSON.stringify({ space_id: assignSpace, deadline_at: new Date(deadline).toISOString() }),
    });
    setShowAssign(false);
    alert('Назначено!');
  };

  if (!contest) return <div className="content"><div className="skeleton" /></div>;

  const q = contest.questions.find((x) => x.id === selected);

  return (
    <>
      <div className="header" style={{ display: 'flex', gap: 12 }}>
        <button className="secondary" onClick={() => navigate('/contests')}>←</button>
        <span>{contest.title}</span>
        <button style={{ marginLeft: 'auto' }} onClick={() => setShowAssign(true)} disabled={!contest.questions.length}>
          Назначить
        </button>
      </div>
      <div className="content" style={{ display: 'flex', gap: 16, height: 'calc(100vh - 120px)' }}>
        <aside style={{ width: 240 }}>
          <button onClick={() => addQuestion('single_choice')} style={{ width: '100%', marginBottom: 8 }}>+ Вопрос</button>
          {contest.questions.map((question) => (
            <div
              key={question.id}
              className={`card ${selected === question.id ? '' : ''}`}
              style={{ marginBottom: 8, cursor: 'pointer', border: selected === question.id ? '2px solid #4f46e5' : undefined }}
              onClick={() => setSelected(question.id)}
            >
              <span className="badge">{question.type}</span>
              <div style={{ fontSize: '0.85rem', marginTop: 4 }}>{question.prompt.slice(0, 40)}...</div>
              <div style={{ fontSize: '0.75rem' }}>{question.points} б.</div>
            </div>
          ))}
        </aside>

        <main style={{ flex: 1 }} className="card">
          {q ? (
            <>
              <div className="form-group">
                <label>Условие</label>
                <textarea value={q.prompt} onChange={(e) => updateQuestion(q.id, { prompt: e.target.value })} rows={4} />
              </div>
              <div className="form-group">
                <label>Баллы</label>
                <input type="number" value={q.points} onChange={(e) => updateQuestion(q.id, { points: Number(e.target.value) })} style={{ maxWidth: 100 }} />
              </div>
              {q.type === 'coding' && (
                <div>
                  <h4>Тесты</h4>
                  <button className="secondary" onClick={() => addTest(q.id)}>+ Тест</button>
                  <table style={{ width: '100%', marginTop: 8, fontSize: '0.85rem' }}>
                    <thead><tr><th>stdin</th><th>expected</th><th>пример</th><th>вес</th></tr></thead>
                    <tbody>
                      {(q.tests || []).map((t) => (
                        <tr key={t.id}><td>{t.stdin}</td><td>{t.expected_stdout}</td><td>{t.is_sample ? 'да' : 'нет'}</td><td>{t.weight}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">Выберите вопрос</div>
          )}
        </main>

        <aside style={{ width: 220 }} className="card">
          <h3>Настройки</h3>
          <div className="form-group">
            <label>Лимит времени (сек)</label>
            <input type="number" value={contest.time_limit_sec || ''} onChange={(e) => api(`/contests/${id}`, { method: 'PATCH', body: JSON.stringify({ time_limit_sec: Number(e.target.value) || null }) }).then(load)} />
          </div>
          <label><input type="checkbox" checked={contest.shuffle_questions} onChange={(e) => api(`/contests/${id}`, { method: 'PATCH', body: JSON.stringify({ shuffle_questions: e.target.checked }) }).then(load)} /> Перемешивать</label>
        </aside>
      </div>

      {showAssign && (
        <div className="modal-overlay" onClick={() => setShowAssign(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Назначить контест</h2>
            <div className="form-group">
              <label>Пространство</label>
              <select value={assignSpace ?? ''} onChange={(e) => setAssignSpace(Number(e.target.value))}>
                <option value="">Выберите</option>
                {spaces.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Дедлайн</label>
              <input type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
            </div>
            <div className="modal-actions">
              <button className="secondary" onClick={() => setShowAssign(false)}>Отмена</button>
              <button onClick={assign}>Назначить</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
