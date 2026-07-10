import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { BoardEditor, CodeEditor, GraphEditor } from '../components/SurfaceEditor';

interface RoomTab { id: number; material_id: number; position: number; material?: { id: number; title: string; type: string; config?: object } }
interface RoomData {
  lesson: { id: number; room_open: boolean; status: string; presented_tab_id: number | null };
  tabs: RoomTab[];
  messages: { id: number; user_id: number; body: string; display_name?: string; created_at: string }[];
  edit_grants: number[];
  presence: { user_id: number; display_name?: string; online?: boolean }[];
}

export default function RoomPage() {
  const { lessonId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [room, setRoom] = useState<RoomData | null>(null);
  const [activeTab, setActiveTab] = useState<number | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<RoomData['messages']>([]);
  const [followingPresent, setFollowingPresent] = useState(true);
  const [disconnected, setDisconnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const isTeacher = user?.role === 'teacher';
  const canEdit = isTeacher || (user && room?.edit_grants.includes(user.id));

  const load = async () => {
    if (!lessonId) return;
    const data = await api<RoomData>(`/lessons/${lessonId}/room`);
    setRoom(data);
    setMessages(data.messages);
    if (!activeTab && data.tabs[0]) setActiveTab(data.tabs[0].id);
  };

  useEffect(() => { load(); }, [lessonId]);

  useEffect(() => {
    if (!lessonId) return;
    const token = localStorage.getItem('access');
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/rooms/${lessonId}?token=${token}`);
    wsRef.current = ws;
    ws.onopen = () => setDisconnected(false);
    ws.onclose = () => setDisconnected(true);
    ws.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (event.type === 'chat') setMessages((m) => [...m, event.message]);
      if (event.type === 'tab_opened' || event.type === 'tab_closed' || event.type === 'present_changed') load();
      if (event.type === 'present_changed' && followingPresent) setActiveTab(event.tab_id);
    };
    const ping = setInterval(() => ws.send(JSON.stringify({ type: 'ping' })), 30000);
    return () => { clearInterval(ping); ws.close(); };
  }, [lessonId]);

  const openRoom = async () => {
    await api(`/lessons/${lessonId}/open`, { method: 'POST' });
    load();
  };

  const closeRoom = async () => {
    if (!confirm('Завершить занятие?')) return;
    await api(`/lessons/${lessonId}/close`, { method: 'POST' });
    navigate(isTeacher ? '/dashboard' : '/student');
  };

  const present = async () => {
    await api(`/lessons/${lessonId}/present`, { method: 'POST', body: JSON.stringify({ tab_id: activeTab }) });
  };

  const stopPresent = async () => {
    await api(`/lessons/${lessonId}/present`, { method: 'POST', body: JSON.stringify({ tab_id: null }) });
  };

  const sendMessage = async () => {
    if (!message.trim()) return;
    await api(`/lessons/${lessonId}/messages`, { method: 'POST', body: JSON.stringify({ body: message }) });
    setMessage('');
  };

  const grantEdit = async (userId: number, granted: boolean) => {
    await api(`/lessons/${lessonId}/grant-edit`, { method: 'POST', body: JSON.stringify({ user_id: userId, granted }) });
    load();
  };

  if (!room) return <div className="content"><div className="skeleton" /></div>;

  if (!room.lesson.room_open && !isTeacher) {
    return (
      <div className="content empty-state card" style={{ margin: 40 }}>
        <h3>Занятие ещё не началось</h3>
        <p>Ожидайте, пока учитель откроет комнату</p>
      </div>
    );
  }

  const currentTab = room.tabs.find((t) => t.id === activeTab);
  const material = currentTab?.material;

  return (
    <div className="room-layout">
      {disconnected && <div className="banner">Соединение потеряно, переподключаемся…</div>}
      <div className="header" style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '8px 16px' }}>
        <span>Комната #{lessonId}</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {room.presence.map((p) => (
            <span key={p.user_id} className="badge" title={p.display_name}>{p.display_name?.[0]}</span>
          ))}
          {isTeacher && !room.lesson.room_open && <button onClick={openRoom}>Открыть комнату</button>}
          {isTeacher && room.lesson.room_open && (
            <>
              <button className="secondary" onClick={present}>Показ</button>
              <button className="secondary" onClick={stopPresent}>Остановить показ</button>
              <button className="danger" onClick={closeRoom}>Завершить</button>
            </>
          )}
          {!isTeacher && !canEdit && <button className="secondary" onClick={() => setMessage('Можно право на редактирование?')}>Попросить право</button>}
        </div>
      </div>

      {room.lesson.presented_tab_id && !followingPresent && (
        <div className="banner">
          Вы вышли из показа <button onClick={() => { setFollowingPresent(true); setActiveTab(room.lesson.presented_tab_id); }}>Вернуться к показу</button>
        </div>
      )}

      <div className="room-tabs">
        {room.tabs.map((t) => (
          <div
            key={t.id}
            className={`room-tab ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => { setActiveTab(t.id); setFollowingPresent(false); }}
          >
            {t.material?.title || `Вкладка ${t.position + 1}`}
          </div>
        ))}
        {isTeacher && <button className="secondary" style={{ padding: '4px 12px' }} onClick={() => navigate('/storage')}>+ Из хранилища</button>}
      </div>

      <div className="room-body">
        <div className="room-canvas">
          {!canEdit && <div className="banner">Учитель не выдал право редактирования — только просмотр</div>}
          {material?.type === 'board' && <BoardEditor materialId={material.id} readOnly={!canEdit} lessonId={Number(lessonId)} />}
          {material?.type === 'code_snippet' && <CodeEditor materialId={material.id} config={(material.config as { code?: string }) || {}} readOnly={!canEdit} />}
          {material?.type === 'graph' && <GraphEditor materialId={material.id} config={(material.config as object) || {}} readOnly={!canEdit} />}
          {!material && <div className="empty-state">Выберите вкладку</div>}
        </div>

        {chatOpen && (
          <div className="room-panel">
            <div className="tabs">
              <button className="tab active">Чат</button>
              <button className="tab" onClick={() => setChatOpen(false)}>×</button>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
              {messages.map((m) => (
                <div key={m.id} style={{ marginBottom: 8 }}>
                  <strong>{m.display_name}</strong>: {m.body}
                </div>
              ))}
            </div>
            <div style={{ padding: 12, borderTop: '1px solid #e2e5eb', display: 'flex', gap: 8 }}>
              <input value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sendMessage()} />
              <button onClick={sendMessage}>→</button>
            </div>
            {isTeacher && room.presence.filter((p) => p.user_id !== user?.id).map((p) => (
              <div key={p.user_id} style={{ padding: '4px 12px', display: 'flex', justifyContent: 'space-between' }}>
                <span>{p.display_name}</span>
                <button className="secondary" style={{ fontSize: '0.75rem', padding: '2px 8px' }}
                  onClick={() => grantEdit(p.user_id, !room.edit_grants.includes(p.user_id))}>
                  {room.edit_grants.includes(p.user_id) ? 'Снять право' : 'Выдать право'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
