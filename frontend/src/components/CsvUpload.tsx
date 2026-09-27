import { useEffect, useRef, useState } from 'react';
import { uploadCsv } from '../api';

interface CsvUploadProps {
  id: string;
  title: string;
  description: string;
  endpoint: '/api/v1/schedule/upload' | '/api/v1/reference/devices/upload';
}

type UploadStatus =
  | { kind: 'idle'; message: null }
  | { kind: 'loading'; message: string }
  | { kind: 'success'; message: string }
  | { kind: 'error'; message: string };

export function CsvUpload({ id, title, description, endpoint }: CsvUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<UploadStatus>({ kind: 'idle', message: null });
  const controllerRef = useRef<AbortController | null>(null);
  const pendingRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const submit = async () => {
    if (!file || pendingRef.current) return;
    pendingRef.current = true;
    const controller = new AbortController();
    controllerRef.current = controller;
    setStatus({ kind: 'loading', message: 'Загрузка файла…' });

    try {
      const result = await uploadCsv(endpoint, file, controller.signal);
      if (!controller.signal.aborted) {
        setStatus({ kind: 'success', message: `Загружено записей: ${result.inserted_count}` });
        setFile(null);
        if (inputRef.current) inputRef.current.value = '';
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setStatus({
          kind: 'error',
          message: error instanceof Error ? error.message : 'Не удалось загрузить файл',
        });
      }
    } finally {
      pendingRef.current = false;
      controllerRef.current = null;
    }
  };

  return (
    <section className="upload-section" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>{title}</h3>
      <p>{description}</p>
      <div className="upload-controls">
        <label htmlFor={id}>CSV-файл</label>
        <input
          ref={inputRef}
          type="file"
          id={id}
          accept=".csv,text/csv"
          disabled={status.kind === 'loading'}
          onChange={(event) => {
            setFile(event.currentTarget.files?.[0] ?? null);
            setStatus({ kind: 'idle', message: null });
          }}
        />
        <button type="button" onClick={() => void submit()} disabled={!file || status.kind === 'loading'}>
          {status.kind === 'loading' ? 'Загрузка…' : 'Загрузить'}
        </button>
      </div>
      {status.message && (
        <p className={`upload-feedback ${status.kind}`} role={status.kind === 'error' ? 'alert' : 'status'}>
          {status.message}
        </p>
      )}
    </section>
  );
}
