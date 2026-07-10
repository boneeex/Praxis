import { useEffect, useState } from 'react';
import { api } from '../api/client';

interface Overview {
  lessons_done: number;
  total_duration_min: number;
  lessons_cancelled: number;
  earnings_cents: number;
  storage_bytes_used: number;
  storage_quota_bytes: number;
  student_count: number;
}

interface Activity { date: string; count: number }

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [from, setFrom] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return d.toISOString().slice(0, 10);
  });
  const [to, setTo] = useState(() => new Date().toISOString().slice(0, 10));

  useEffect(() => {
    api<Overview>(`/analytics/overview?from=${from}&to=${to}`).then(setOverview);
    api<Activity[]>('/me/activity').then(setActivity);
  }, [from, to]);

  const formatBytes = (b: number) => `${(b / 1024 / 1024 / 1024).toFixed(1)} ГБ`;
  const storagePct = overview ? Math.round((overview.storage_bytes_used / overview.storage_quota_bytes) * 100) : 0;

  return (
    <>
      <div className="header">Аналитика</div>
      <div className="content">
        <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          <span>—</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>

        {overview && (
          <div className="grid grid-3" style={{ marginBottom: 32 }}>
            <div className="card">
              <div style={{ fontSize: '2rem', fontWeight: 700 }}>{overview.lessons_done}</div>
              <div style={{ color: '#6b7280' }}>Проведено занятий</div>
            </div>
            <div className="card">
              <div style={{ fontSize: '2rem', fontWeight: 700 }}>{Math.round(overview.total_duration_min / 60)}ч</div>
              <div style={{ color: '#6b7280' }}>Суммарная длительность</div>
            </div>
            <div className="card">
              <div style={{ fontSize: '2rem', fontWeight: 700 }}>{overview.lessons_cancelled}</div>
              <div style={{ color: '#6b7280' }}>Отменено</div>
            </div>
            <div className="card">
              <div style={{ fontSize: '2rem', fontWeight: 700 }}>{(overview.earnings_cents / 100).toFixed(0)} ₽</div>
              <div style={{ color: '#6b7280' }}>Заработок</div>
            </div>
            <div className="card">
              <div style={{ fontSize: '2rem', fontWeight: 700 }}>{overview.student_count}</div>
              <div style={{ color: '#6b7280' }}>Учеников</div>
            </div>
            <div className="card">
              <div style={{ fontSize: '2rem', fontWeight: 700 }}>{storagePct}%</div>
              <div style={{ color: '#6b7280' }}>Хранилище ({formatBytes(overview.storage_bytes_used)} / {formatBytes(overview.storage_quota_bytes)})</div>
            </div>
          </div>
        )}

        <section className="card">
          <h3 style={{ marginBottom: 16 }}>Активность</h3>
          <div className="heatmap">
            {activity.map((a) => (
              <div
                key={a.date}
                className={`cell ${a.count > 3 ? 'l4' : a.count > 2 ? 'l3' : a.count > 1 ? 'l2' : a.count > 0 ? 'l1' : ''}`}
                title={`${a.date}: ${a.count}`}
              />
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
