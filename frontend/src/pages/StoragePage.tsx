import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

interface Space { id: number; title: string }
interface Folder { id: number; name: string; parent_id: number | null }
interface Material { id: number; title: string; type: string; created_by_role: string; updated_at: string; folder_id: number | null }

const TYPE_LABELS: Record<string, string> = {
  board: 'Доска', code_snippet: 'Код', graph: 'График', pdf: 'PDF', image: 'Изображение', lesson_template: 'Шаблон урока',
};

export default function StoragePage() {
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [spaceId, setSpaceId] = useState<number | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [folderId, setFolderId] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newType, setNewType] = useState('board');
  const navigate = useNavigate();

  useEffect(() => {
    api<Space[]>('/spaces').then((sp) => {
      setSpaces(sp);
      if (sp[0]) setSpaceId(sp[0].id);
    });
  }, []);

  useEffect(() => {
    if (!spaceId) return;
    api<Folder[]>(`/spaces/${spaceId}/folders`).then(setFolders);
    const params = new URLSearchParams({ sort: 'recent' });
    if (folderId !== null) params.set('folder_id', String(folderId));
    if (search) params.set('q', search);
    if (typeFilter) params.set('type', typeFilter);
    api<Material[]>(`/spaces/${spaceId}/materials?${params}`).then(setMaterials);
  }, [spaceId, folderId, search, typeFilter]);

  const createMaterial = async () => {
    if (!spaceId) return;
    const m = await api<Material>(`/spaces/${spaceId}/materials`, {
      method: 'POST',
      body: JSON.stringify({ type: newType, title: newTitle, folder_id: folderId }),
    });
    setShowCreate(false);
    navigate(`/storage/${m.id}`);
  };

  const uploadFile = async (file: File, type: 'pdf' | 'image') => {
    if (!spaceId) return;
    const { material_id, put_url } = await api<{ material_id: number; put_url: string }>(
      `/spaces/${spaceId}/materials/upload-url`,
      { method: 'POST', body: JSON.stringify({ type, title: file.name, folder_id: folderId, size_bytes: file.size, content_type: file.type }) }
    );
    await fetch(put_url, { method: 'PUT', body: file, headers: { 'Content-Type': file.type } });
    await api(`/materials/${material_id}/complete-upload?size_bytes=${file.size}`, { method: 'POST' });
    navigate(`/storage/${material_id}`);
  };

  const createFolder = async () => {
    if (!spaceId) return;
    const name = prompt('Название папки');
    if (!name) return;
    await api(`/spaces/${spaceId}/folders`, { method: 'POST', body: JSON.stringify({ name, parent_id: folderId }) });
    api<Folder[]>(`/spaces/${spaceId}/folders`).then(setFolders);
  };

  return (
    <>
      <div className="header" style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
        <span>Хранилище</span>
        {spaces.length > 1 && (
          <select value={spaceId ?? ''} onChange={(e) => setSpaceId(Number(e.target.value))}>
            {spaces.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
          </select>
        )}
        <button onClick={() => setShowCreate(true)}>+ Создать</button>
      </div>
      <div className="content" style={{ display: 'flex', gap: 24 }}>
        <aside style={{ width: 200 }}>
          <button className="secondary" style={{ width: '100%', marginBottom: 8 }} onClick={() => setFolderId(null)}>Корень</button>
          {folders.filter((f) => f.parent_id === folderId || (folderId === null && !f.parent_id)).map((f) => (
            <button key={f.id} className="secondary" style={{ width: '100%', marginBottom: 4, textAlign: 'left' }} onClick={() => setFolderId(f.id)}>{f.name}</button>
          ))}
          <button className="secondary" style={{ width: '100%', marginTop: 8 }} onClick={createFolder}>+ Папка</button>
        </aside>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <input placeholder="Поиск..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ maxWidth: 200 }} />
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">Все типы</option>
              {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          {materials.length === 0 ? (
            <div className="empty-state card">Пусто. Создайте материал или загрузите файл</div>
          ) : (
            <div className="grid grid-3">
              {materials.map((m) => (
                <div key={m.id} className="card material-card" onClick={() => navigate(`/storage/${m.id}`)}>
                  <span className="badge">{TYPE_LABELS[m.type] || m.type}</span>
                  {m.created_by_role === 'student' && <span className="badge" style={{ marginLeft: 4 }}>ученик</span>}
                  <div style={{ marginTop: 8, fontWeight: 500 }}>{m.title}</div>
                  <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>{new Date(m.updated_at).toLocaleDateString()}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Создать материал</h2>
            <div className="form-group">
              <label>Тип</label>
              <select value={newType} onChange={(e) => setNewType(e.target.value)}>
                <option value="board">Доска</option>
                <option value="code_snippet">Код</option>
                <option value="graph">График</option>
                <option value="lesson_template">Шаблон урока</option>
              </select>
            </div>
            <div className="form-group">
              <label>Название</label>
              <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Или загрузить файл</label>
              <input type="file" accept=".pdf,image/*" onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadFile(f, f.type === 'application/pdf' ? 'pdf' : 'image');
              }} />
            </div>
            <div className="modal-actions">
              <button className="secondary" onClick={() => setShowCreate(false)}>Отмена</button>
              <button onClick={createMaterial} disabled={!newTitle}>Создать</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
