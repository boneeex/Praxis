import { getStroke } from 'perfect-freehand';
import { useCallback, useEffect, useRef, useState } from 'react';
import Editor from '@monaco-editor/react';
import { api } from '../api/client';

interface BoardObject {
  id: string;
  type: 'stroke' | 'text' | 'code';
  points?: number[][];
  x?: number;
  y?: number;
  content?: string;
  code?: string;
  output?: { stdout?: string; stderr?: string; status?: string };
  color?: string;
  size?: number;
}

interface BoardEditorProps {
  materialId: number;
  readOnly?: boolean;
  lessonId?: number;
}

export function BoardEditor({ materialId, readOnly = false, lessonId }: BoardEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [objects, setObjects] = useState<BoardObject[]>([]);
  const [tool, setTool] = useState<'select' | 'pen' | 'text' | 'code'>('pen');
  const [color, setColor] = useState('#1a1a1a');
  const [size, setSize] = useState(4);
  const [drawing, setDrawing] = useState<number[][]>([]);
  const [connected, setConnected] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#fafafa';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (const obj of objects) {
      if (obj.type === 'stroke' && obj.points) {
        const stroke = getStroke(obj.points, { size: obj.size || 4 });
        ctx.beginPath();
        ctx.fillStyle = obj.color || '#1a1a1a';
        if (stroke.length > 0) {
          ctx.moveTo(stroke[0][0], stroke[0][1]);
          for (let i = 1; i < stroke.length; i++) {
            ctx.lineTo(stroke[i][0], stroke[i][1]);
          }
          ctx.fill();
        }
      }
      if (obj.type === 'text' && obj.content) {
        ctx.fillStyle = obj.color || '#1a1a1a';
        ctx.font = '16px sans-serif';
        ctx.fillText(obj.content, obj.x || 0, obj.y || 0);
      }
    }
    if (drawing.length > 0) {
      const stroke = getStroke(drawing, { size });
      ctx.beginPath();
      ctx.fillStyle = color;
      if (stroke.length > 0) {
        ctx.moveTo(stroke[0][0], stroke[0][1]);
        for (let i = 1; i < stroke.length; i++) ctx.lineTo(stroke[i][0], stroke[i][1]);
        ctx.fill();
      }
    }
  }, [objects, drawing, color, size]);

  useEffect(() => { redraw(); }, [redraw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      canvas.width = canvas.parentElement?.clientWidth || 800;
      canvas.height = canvas.parentElement?.clientHeight || 600;
      redraw();
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, [redraw]);

  useEffect(() => {
    const token = localStorage.getItem('access');
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/docs/${materialId}?token=${token}`);
    wsRef.current = ws;
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    return () => ws.close();
  }, [materialId]);

  const getPos = (e: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
  };

  const onMouseDown = (e: React.MouseEvent) => {
    if (readOnly) return;
    if (tool === 'pen') setDrawing([getPos(e)]);
    if (tool === 'text') {
      const [x, y] = getPos(e);
      const content = prompt('Текст');
      if (content) setObjects((o) => [...o, { id: crypto.randomUUID(), type: 'text', x, y, content, color }]);
    }
    if (tool === 'code') {
      const [x, y] = getPos(e);
      setObjects((o) => [...o, { id: crypto.randomUUID(), type: 'code', x, y, code: 'print("Hello")', output: {} }]);
    }
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (!drawing.length || readOnly) return;
    setDrawing((d) => [...d, getPos(e)]);
  };

  const onMouseUp = () => {
    if (drawing.length > 1) {
      setObjects((o) => [...o, { id: crypto.randomUUID(), type: 'stroke', points: drawing, color, size }]);
    }
    setDrawing([]);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {!connected && <div className="banner">Соединение потеряно, переподключаемся…</div>}
      <div className="toolbar">
        {(['select', 'pen', 'text', 'code'] as const).map((t) => (
          <button key={t} className={tool === t ? 'active' : ''} onClick={() => setTool(t)} disabled={readOnly}>
            {t === 'select' ? 'V' : t === 'pen' ? 'P' : t === 'text' ? 'T' : 'C'}
          </button>
        ))}
        <input type="color" value={color} onChange={(e) => setColor(e.target.value)} disabled={readOnly} />
        <input type="range" min={1} max={20} value={size} onChange={(e) => setSize(Number(e.target.value))} disabled={readOnly} />
        <span style={{ marginLeft: 'auto', fontSize: '0.85rem', color: connected ? 'green' : 'orange' }}>
          {connected ? 'Сохранено' : 'Синхронизируется…'}
        </span>
      </div>
      <canvas
        ref={canvasRef}
        className="board-canvas"
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        style={{ cursor: readOnly ? 'default' : 'crosshair', flex: 1 }}
      />
      {objects.filter((o) => o.type === 'code').map((obj) => (
        <CodeCell key={obj.id} obj={obj} materialId={materialId} lessonId={lessonId} readOnly={readOnly} />
      ))}
    </div>
  );
}

function CodeCell({ obj, materialId, lessonId, readOnly }: { obj: BoardObject; materialId: number; lessonId?: number; readOnly?: boolean }) {
  const [code, setCode] = useState(obj.code || '');
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState(obj.output);

  const run = async () => {
    setRunning(true);
    try {
      const res = await api<{ run_id: number }>('/execute', {
        method: 'POST',
        body: JSON.stringify({ language: 'python', code, context: { source: 'board_cell', material_id: materialId, lesson_id: lessonId } }),
      });
      let status = 'queued';
      while (status === 'queued' || status === 'running') {
        await new Promise((r) => setTimeout(r, 500));
        const result = await api<{ status: string; stdout?: string; stderr?: string }>(`/execute/${res.run_id}`);
        status = result.status;
        if (status === 'done' || status === 'error' || status === 'timeout') {
          setOutput({ stdout: result.stdout, stderr: result.stderr, status });
        }
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="card" style={{ position: 'absolute', left: obj.x, top: obj.y, width: 400, zIndex: 10 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>Python</div>
      <Editor height="120px" language="python" value={code} onChange={(v) => setCode(v || '')} options={{ readOnly, minimap: { enabled: false } }} />
      <button onClick={run} disabled={running || readOnly} style={{ marginTop: 8 }}>{running ? 'Выполняется…' : 'Запустить'}</button>
      {output && (
        <pre style={{ marginTop: 8, fontSize: '0.85rem', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
          {output.stderr && <span style={{ color: 'red' }}>{output.stderr}</span>}
          {output.stdout}
        </pre>
      )}
    </div>
  );
}

export function CodeEditor({ materialId, config, readOnly }: { materialId: number; config: { code?: string }; readOnly?: boolean }) {
  const [code, setCode] = useState(config.code || '');
  const [stdin, setStdin] = useState('');
  const [output, setOutput] = useState<{ stdout?: string; stderr?: string; status?: string } | null>(null);
  const [running, setRunning] = useState(false);

  const save = async () => {
    await api(`/materials/${materialId}`, { method: 'PATCH', body: JSON.stringify({ config: { language: 'python', code } }) });
  };

  const run = async () => {
    setRunning(true);
    try {
      const res = await api<{ run_id: number }>('/execute', {
        method: 'POST',
        body: JSON.stringify({ language: 'python', code, stdin, context: { source: 'board_cell', material_id: materialId } }),
      });
      let status = 'queued';
      while (status === 'queued' || status === 'running') {
        await new Promise((r) => setTimeout(r, 500));
        const result = await api<{ status: string; stdout?: string; stderr?: string }>(`/execute/${res.run_id}`);
        status = result.status;
        if (['done', 'error', 'timeout'].includes(status)) setOutput(result);
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 16 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <span style={{ fontWeight: 600 }}>Python</span>
        <button onClick={save} disabled={readOnly}>Сохранить</button>
        <button onClick={run} disabled={running || readOnly}>{running ? 'В очереди…' : 'Запустить'}</button>
      </div>
      <Editor height="50%" language="python" value={code} onChange={(v) => setCode(v || '')} options={{ readOnly, minimap: { enabled: false } }} />
      <details style={{ marginTop: 8 }}>
        <summary>stdin</summary>
        <textarea value={stdin} onChange={(e) => setStdin(e.target.value)} rows={3} />
      </details>
      {output && (
        <pre style={{ marginTop: 8, flex: 1, background: '#1e1e1e', color: '#d4d4d4', padding: 12, borderRadius: 8, overflow: 'auto' }}>
          {output.stderr && <span style={{ color: '#f48771' }}>{output.stderr}</span>}
          {output.stdout}
          {output.status === 'timeout' && '\nПревышено время выполнения'}
        </pre>
      )}
    </div>
  );
}

export function GraphEditor({ materialId, config, readOnly }: { materialId: number; config: { expressions?: string[]; viewport?: object }; readOnly?: boolean }) {
  const [expressions, setExpressions] = useState<string[]>(config.expressions?.length ? config.expressions : ['x^2']);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const save = async () => {
    await api(`/materials/${materialId}`, { method: 'PATCH', body: JSON.stringify({ config: { expressions, viewport: config.viewport } }) });
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    canvas.width = canvas.parentElement?.clientWidth || 600;
    canvas.height = 400;
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#ccc';
    ctx.beginPath();
    ctx.moveTo(0, canvas.height / 2);
    ctx.lineTo(canvas.width, canvas.height / 2);
    ctx.moveTo(canvas.width / 2, 0);
    ctx.lineTo(canvas.width / 2, canvas.height);
    ctx.stroke();
    ctx.strokeStyle = '#4f46e5';
    ctx.beginPath();
    const scale = 20;
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    for (let px = 0; px < canvas.width; px++) {
      const x = (px - cx) / scale;
      let y = 0;
      try {
        const expr = expressions[0]?.replace(/\^/g, '**') || '0';
        y = Function('x', `return ${expr}`)(x);
      } catch { y = 0; }
      const py = cy - y * scale;
      if (px === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();
  }, [expressions]);

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div style={{ width: 220, padding: 16, borderRight: '1px solid #e2e5eb' }}>
        <h3>Выражения</h3>
        {expressions.map((ex, i) => (
          <input key={i} value={ex} onChange={(e) => {
            const next = [...expressions];
            next[i] = e.target.value;
            setExpressions(next);
          }} style={{ marginBottom: 8 }} disabled={readOnly} />
        ))}
        {!readOnly && <button className="secondary" onClick={() => setExpressions([...expressions, ''])}>Добавить</button>}
        {!readOnly && <button onClick={save} style={{ marginTop: 8, width: '100%' }}>Сохранить</button>}
      </div>
      <canvas ref={canvasRef} style={{ flex: 1 }} />
    </div>
  );
}
