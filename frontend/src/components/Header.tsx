import type { HealthStatus } from '../hooks/useHealthCheck';
import type { SocketStatus } from '../hooks/useDashboardSocket';

export type Tab = 'DASHBOARD' | 'SETTINGS';

const HEALTH_LABELS: Record<HealthStatus, string> = {
  loading: 'Проверка системы',
  healthy: 'Система работает стабильно',
  degraded: 'Сбои в ML-модуле',
  offline: 'Нет связи с сервером',
};

const SOCKET_LABELS: Record<SocketStatus, string> = {
  connecting: 'Подключение к телеметрии',
  connected: 'Телеметрия обновляется',
  disconnected: 'Нет связи с телеметрией',
  'invalid-data': 'Некорректные данные телеметрии',
  stale: 'Телеметрия не обновляется',
};

interface HeaderProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  healthStatus: HealthStatus;
  socketStatus: SocketStatus;
  demoMode: boolean;
}

export function Header({ activeTab, onTabChange, healthStatus, socketStatus, demoMode }: HeaderProps) {
  return (
    <header className="header">
      <div className="header-left">
        <img src="/logos/MGT-logo-Ru-Hor-preview.jpg" alt="Мосгортранс" className="logo header-logo" />
        <h1 className="header-title">Дашборд диспетчера</h1>
      </div>
      <div className="header-status" aria-live="polite">
        {demoMode ? (
          <>
            <span className="status-indicator demo" aria-hidden="true" />
            <span>Тестовые данные</span>
          </>
        ) : (
          <>
            <span className={`status-indicator ${healthStatus}`} aria-hidden="true" />
            <span>{HEALTH_LABELS[healthStatus]}</span>
            <span className={`connection-status ${socketStatus}`}>{SOCKET_LABELS[socketStatus]}</span>
          </>
        )}
      </div>
      <nav className="header-tabs" aria-label="Разделы дашборда">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'DASHBOARD' ? 'active' : ''}`}
          aria-current={activeTab === 'DASHBOARD' ? 'page' : undefined}
          onClick={() => onTabChange('DASHBOARD')}
        >
          Карта
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'SETTINGS' ? 'active' : ''}`}
          aria-current={activeTab === 'SETTINGS' ? 'page' : undefined}
          onClick={() => onTabChange('SETTINGS')}
        >
          Настройки
        </button>
      </nav>
    </header>
  );
}
