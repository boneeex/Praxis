import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { BoardEditor, CodeEditor, GraphEditor } from '../components/SurfaceEditor';

interface Material {
  id: number;
  title: string;
  type: string;
  config: { code?: string; expressions?: string[]; viewport?: object } | null;
}

export default function EditorPage() {
  const { materialId } = useParams();
  const [material, setMaterial] = useState<Material | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    if (!materialId) return;
    api<Material>(`/materials/${materialId}`).then(setMaterial).finally(() => setLoading(false));
  }, [materialId]);

  if (loading || !material) return <><div className="header">Загрузка...</div><div className="content"><div className="skeleton" /></div></>;

  return (
    <>
      <div className="header" style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
        <button className="secondary" onClick={() => navigate('/storage')}>← Назад</button>
        <span>{material.title}</span>
      </div>
      <div style={{ height: 'calc(100vh - 60px)' }}>
        {material.type === 'board' && <BoardEditor materialId={material.id} />}
        {material.type === 'code_snippet' && <CodeEditor materialId={material.id} config={material.config || {}} />}
        {material.type === 'graph' && <GraphEditor materialId={material.id} config={material.config || {}} />}
        {material.type === 'pdf' && <div className="content"><p>PDF просмотр — откройте в комнате занятия для аннотаций</p></div>}
        {material.type === 'image' && <ImageView materialId={material.id} />}
      </div>
    </>
  );
}

function ImageView({ materialId }: { materialId: number }) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    api<{ url: string }>(`/materials/${materialId}/content`).then((c) => setUrl(c.url || ''));
  }, [materialId]);
  return url ? <img src={url} alt="" style={{ maxWidth: '100%' }} /> : null;
}
