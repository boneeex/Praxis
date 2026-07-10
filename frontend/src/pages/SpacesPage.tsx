import { useEffect, useState } from 'react';
import { api } from '../api/client';

interface Space { id: number; title: string; kind: string; rate_cents: number | null; invite_code: string }
interface Member { user_id: number; display_name: string; joined_at: string }

export default function SpacesPage() {
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState('');
  const [kind, setKind] = useState<'single' | 'group'>('single');
  const [rate, setRate] = useState('');
  const [toast, setToast] = useState('');

  const load = () => api<Space[]>('/spaces').then(setSpaces);
  useEffect(() => { load(); }, []);

  const create = async () => {
    await api('/spaces', {
      method: 'POST',
      body: JSON.stringify({ kind, title, rate_cents: rate ? parseInt(rate) * 100 : null }),
    });
    setShowCreate(false);
    setTitle('');
    load();
  };

  const expand = async (id: number) => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    const m = await api<Member[]>(`/spaces/${id}/members`);
    setMembers(m);
  };

  const copyLink = (code: string) => {
    navigator.clipboard.writeText(`${window.location.origin}/join/${code}`);
    setToast('Ссылка скопирована');
    setTimeout(() => setToast(''), 3000);
  };

  const rotateCode = async (id: number) => {
    if (!confirm('Старая ссылка перестанет работать. Продолжить?')) return;
    await api(`/spaces/${id}/invite/rotate`, { method: 'POST' });
    load();
  };

  const removeMember = async (spaceId: number, userId: number) => {
    if (!confirm('Убрать ученика?')) return;
    await api(`/spaces/${spaceId}/members/${userId}`, { method: 'DELETE' });
    expand(spaceId);
  };

  const deleteSpace = async (id: number) => {
    if (!confirm('Удалить пространство и все материалы?')) return;
    await api(`/spaces/${id}`, { method: 'DELETE' });
    load();
  };

  return (
    <>
      <div className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Ученики и группы</span>
        <button onClick={() => setShowCreate(true)}>Создать пространство</button>
      </div>
      <div className="content">
        {toast && <div className="toast">{toast}</div>}
        <div className="grid grid-2">
          {spaces.map((s) => (
            <div key={s.id} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div>
                  <strong>{s.title}</strong>
                  <span className="badge" style={{ marginLeft: 8 }}>{s.kind === 'single' ? '1:1' : 'группа'}</span>
                  {s.rate_cents == null && <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: 4 }}>Укажите ставку для аналитики</div>}
                </div>
                <button className="secondary" onClick={() => expand(s.id)}>Детали</button>
              </div>
              {expanded === s.id && (
                <div style={{ marginTop: 16, borderTop: '1px solid #e2e5eb', paddingTop: 16 }}>
                  <div style={{ marginBottom: 12 }}>
                    <strong>Приглашение:</strong> {s.invite_code}
                    <button className="secondary" style={{ marginLeft: 8 }} onClick={() => copyLink(s.invite_code)}>Копировать ссылку</button>
                    <button className="secondary" style={{ marginLeft: 4 }} onClick={() => rotateCode(s.id)}>Обновить код</button>
                  </div>
                  <strong>Ученики:</strong>
                  {members.map((m) => (
                    <div key={m.user_id} style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
                      <span>{m.display_name}</span>
                      <button className="danger" style={{ padding: '4px 8px', fontSize: '0.8rem' }} onClick={() => removeMember(s.id, m.user_id)}>Убрать</button>
                    </div>
                  ))}
                  <button className="danger" style={{ marginTop: 16 }} onClick={() => deleteSpace(s.id)}>Удалить пространство</button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Создать пространство</h2>
            <div className="form-group">
              <label>Тип</label>
              <select value={kind} onChange={(e) => setKind(e.target.value as 'single' | 'group')}>
                <option value="single">1:1 (один ученик)</option>
                <option value="group">Группа</option>
              </select>
            </div>
            <div className="form-group">
              <label>Название</label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Иван — алгебра" />
            </div>
            <div className="form-group">
              <label>Ставка (руб/занятие, опц.)</label>
              <input type="number" value={rate} onChange={(e) => setRate(e.target.value)} />
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
