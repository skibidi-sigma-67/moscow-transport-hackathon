import type { HealthSettings } from '../contracts';
import type { HealthStatus } from '../hooks/useHealthCheck';
import { CsvUpload } from './CsvUpload';

const SETTING_FIELDS: { key: keyof HealthSettings; label: string }[] = [
  { key: 'prediction_cache_ttl', label: 'Время жизни кэша предиктов (сек)' },
  { key: 'telemetry_max_history', label: 'История телеметрии (записей)' },
  { key: 'stop_speed_threshold_kmh', label: 'Порог остановки (км/ч)' },
  { key: 'ml_telemetry_window_minutes', label: 'Окно ML модели (мин)' },
  { key: 'max_idle_gap_s', label: 'Макс. разрыв для простоя (сек)' },
  { key: 'historical_packet_delay_s', label: 'Задержка исторических пакетов (сек)' },
  { key: 'dashboard_websocket_update_interval_s', label: 'Интервал обновления дашборда (сек)' },
];

interface SettingsPageProps {
  settings: HealthSettings | null;
  healthStatus: HealthStatus;
  healthError: string | null;
}

export function SettingsPage({ settings, healthStatus, healthError }: SettingsPageProps) {
  return (
    <main className="settings-page" id="settings-panel">
      <section className="settings-card">
        <h2>Текущие настройки системы</h2>
        {settings ? (
          <div className="settings-grid">
            {SETTING_FIELDS.map(({ key, label }) => (
              <div className="setting-item" key={key}>
                <span>{label}</span><strong>{settings[key]}</strong>
              </div>
            ))}
          </div>
        ) : healthStatus === 'loading' ? (
          <p role="status">Загрузка настроек…</p>
        ) : (
          <p role="alert">Не удалось загрузить настройки. {healthError}</p>
        )}
      </section>
      <section className="settings-card">
        <h2>Загрузка данных</h2>
        <CsvUpload
          id="schedule-file"
          title="Загрузить расписание движения"
          description="Выберите CSV-файл с актуальным расписанием (schedule.csv)"
          endpoint="/api/v1/schedule/upload"
        />
        <CsvUpload
          id="devices-file"
          title="Привязка устройств к ТС"
          description="Выберите CSV-файл со связями трекеров и автобусов (traffic.csv)"
          endpoint="/api/v1/reference/devices/upload"
        />
      </section>
    </main>
  );
}
