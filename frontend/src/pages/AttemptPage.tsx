import Editor from '@monaco-editor/react';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';

interface Question {
  id: number;
  type: string;
  prompt: string;
  points: number;
  config?: Record<string, unknown>;
  answer?: { selected?: string[]; text?: string; code?: string };
}

interface Attempt {
  id: number;
  status: string;
  score: number | null;
  max_score: number | null;
  questions: Question[];
}

export default function AttemptPage() {
  const { id } = useParams();
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<number, object>>({});
  const [submitted, setSubmitted] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api<Attempt>(`/attempts/${id}`).then((a) => {
      setAttempt(a);
      setSubmitted(a.status === 'graded' || a.status === 'submitted');
      const init: Record<number, object> = {};
      a.questions.forEach((q) => { if (q.answer) init[q.id] = q.answer; });
      setAnswers(init);
    });
  }, [id]);

  const saveAnswer = async (questionId: number, answer: object) => {
    setAnswers((a) => ({ ...a, [questionId]: answer }));
    await api(`/attempts/${id}/answers`, { method: 'PATCH', body: JSON.stringify({ question_id: questionId, answer }) });
  };

  const submit = async () => {
    if (!confirm('Сдать работу?')) return;
    const result = await api<{ score: number; max_score: number }>(`/attempts/${id}/submit`, { method: 'POST' });
    setSubmitted(true);
    setAttempt((a) => a ? { ...a, score: result.score, status: 'graded' } : a);
  };

  if (!attempt) return <div className="content"><div className="skeleton" /></div>;

  const q = attempt.questions[current];

  return (
    <>
      <div className="header" style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>Вопрос {current + 1} из {attempt.questions.length}</span>
        {submitted && <span>Итог: {attempt.score} / {attempt.max_score}</span>}
      </div>
      <div className="content" style={{ display: 'flex', gap: 16 }}>
        <nav style={{ width: 60 }}>
          {attempt.questions.map((_, i) => (
            <button
              key={i}
              className={current === i ? 'active' : 'secondary'}
              style={{ width: 40, height: 40, marginBottom: 4, borderRadius: 8 }}
              onClick={() => setCurrent(i)}
            >
              {i + 1}
            </button>
          ))}
        </nav>
        <div className="card" style={{ flex: 1 }}>
          <div style={{ marginBottom: 16, whiteSpace: 'pre-wrap' }}>{q.prompt}</div>

          {q.type === 'single_choice' && (
            <div>
              {((q.config?.options as { id: string; text: string }[]) || []).map((opt) => (
                <label key={opt.id} style={{ display: 'block', marginBottom: 8 }}>
                  <input
                    type="radio"
                    name={`q${q.id}`}
                    checked={(answers[q.id] as { selected?: string[] })?.selected?.[0] === opt.id}
                    onChange={() => saveAnswer(q.id, { selected: [opt.id] })}
                    disabled={submitted}
                  />
                  {opt.text}
                </label>
              ))}
            </div>
          )}

          {q.type === 'multi_choice' && (
            <div>
              {((q.config?.options as { id: string; text: string }[]) || []).map((opt) => (
                <label key={opt.id} style={{ display: 'block', marginBottom: 8 }}>
                  <input
                    type="checkbox"
                    checked={((answers[q.id] as { selected?: string[] })?.selected || []).includes(opt.id)}
                    onChange={(e) => {
                      const prev = (answers[q.id] as { selected?: string[] })?.selected || [];
                      const next = e.target.checked ? [...prev, opt.id] : prev.filter((x) => x !== opt.id);
                      saveAnswer(q.id, { selected: next });
                    }}
                    disabled={submitted}
                  />
                  {opt.text}
                </label>
              ))}
            </div>
          )}

          {q.type === 'short_answer' && (
            <input
              value={(answers[q.id] as { text?: string })?.text || ''}
              onChange={(e) => saveAnswer(q.id, { text: e.target.value })}
              disabled={submitted}
            />
          )}

          {q.type === 'flashcard' && (
            <div>
              <div className="card" style={{ padding: 40, textAlign: 'center', marginBottom: 16 }}>
                {(q.config as { front?: string })?.front || q.prompt}
              </div>
              <button className="secondary" onClick={() => alert((q.config as { back?: string })?.back || '')}>Показать ответ</button>
            </div>
          )}

          {q.type === 'coding' && (
            <div>
              <Editor
                height="200px"
                language="python"
                value={(answers[q.id] as { code?: string })?.code || (q.config?.starter_code as string) || ''}
                onChange={(v) => saveAnswer(q.id, { code: v || '' })}
                options={{ readOnly: submitted, minimap: { enabled: false } }}
              />
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 24 }}>
            <button className="secondary" disabled={current === 0} onClick={() => setCurrent((c) => c - 1)}>Назад</button>
            <button className="secondary" disabled={current >= attempt.questions.length - 1} onClick={() => setCurrent((c) => c + 1)}>Далее</button>
            {!submitted && <button onClick={submit} style={{ marginLeft: 'auto' }}>Сдать</button>}
          </div>
        </div>
      </div>
    </>
  );
}
