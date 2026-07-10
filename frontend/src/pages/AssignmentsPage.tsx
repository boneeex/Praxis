import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

interface Assignment { id: number; contest_title: string; deadline_at: string; attempt_status: string; score: number | null; contest_id: number }

export default function AssignmentsPage() {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    api<Assignment[]>('/assignments').then(setAssignments);
  }, []);

  const start = async (assignmentId: number) => {
    const attempt = await api<{ id: number }>(`/assignments/${assignmentId}/attempts`, { method: 'POST' });
    navigate(`/attempts/${attempt.id}`);
  };

  return (
    <>
      <div className="header">Задания</div>
      <div className="content">
        {assignments.length === 0 ? (
          <div className="empty-state card">Нет назначенных заданий</div>
        ) : (
          <div className="grid grid-2">
            {assignments.map((a) => {
              const overdue = new Date(a.deadline_at) < new Date() && a.attempt_status !== 'graded';
              return (
                <div key={a.id} className="card">
                  <strong>{a.contest_title}</strong>
                  <div style={{ fontSize: '0.85rem', color: overdue ? 'red' : '#6b7280' }}>
                    до {new Date(a.deadline_at).toLocaleString()}
                  </div>
                  <span className="badge">{a.attempt_status}</span>
                  {a.score != null && <span style={{ marginLeft: 8 }}>Балл: {a.score}</span>}
                  {a.attempt_status === 'not_started' || a.attempt_status === 'in_progress' ? (
                    <button style={{ marginTop: 8 }} onClick={() => start(a.id)}>
                      {a.attempt_status === 'in_progress' ? 'Продолжить' : 'Начать'}
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
