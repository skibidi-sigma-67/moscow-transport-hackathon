import { lazy, Suspense, useCallback, useMemo, useState } from 'react';
import './App.css';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Header, type Tab } from './components/Header';
import { IncidentSidebar } from './components/IncidentSidebar';
import { KpiPanel } from './components/KpiPanel';
import { MapSection } from './components/MapSection';
import { SettingsPage } from './components/SettingsPage';
import type { DashboardStateResponse, VehicleState } from './contracts';
import { buildDashboardView } from './dashboardView';
import { useDashboardSocket } from './hooks/useDashboardSocket';
import { useHealthCheck } from './hooks/useHealthCheck';
import { useMockData } from './hooks/useMockData';

const ChartsPanel = lazy(() => import('./components/ChartsPanel').then(({ ChartsPanel }) => ({ default: ChartsPanel })));
const EMPTY_VEHICLES: VehicleState[] = [];
const DEMO_MODE = import.meta.env.DEV && new URLSearchParams(window.location.search).get('demo') === '1';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('DASHBOARD');
  const [selectedBusId, setSelectedBusId] = useState<number | null>(null);
  const [selectionRequest, setSelectionRequest] = useState(0);
  const health = useHealthCheck();
  const mockData = useMockData(DEMO_MODE);
  const handleSnapshot = useCallback((next: DashboardStateResponse) => {
    setSelectedBusId((current) => current !== null &&
      !next.vehicles.some(({ tr_id }) => tr_id === current) ? null : current);
  }, []);
  const dashboard = useDashboardSocket(
    health.settings?.dashboard_websocket_update_interval_s ?? null,
    handleSnapshot,
    !DEMO_MODE,
  );
  const data = DEMO_MODE ? mockData : dashboard.data;
  const vehicles = data?.vehicles ?? EMPTY_VEHICLES;
  const view = useMemo(() => buildDashboardView(vehicles), [vehicles]);
  const selectedVehicle = vehicles.find(({ tr_id }) => tr_id === selectedBusId) ?? null;

  const selectVehicle = useCallback((vehicle: VehicleState) => {
    setSelectedBusId(vehicle.tr_id);
    setSelectionRequest((request) => request + 1);
  }, []);

  return (
    <>
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        healthStatus={health.status}
        socketStatus={dashboard.status}
        demoMode={DEMO_MODE}
      />
      {activeTab === 'DASHBOARD' ? (
        <main className="app-container" id="dashboard-panel">
          <div className="main-content">
            {DEMO_MODE ? (
              <div className="data-notice demo-notice" role="status">
                Тестовый режим: отображаются синтетические данные. <a href="/">Вернуться к реальным данным</a>
              </div>
            ) : (dashboard.status !== 'connected' || !data) && (
              <div className="data-notice" role="status">
                {data
                  ? `Показаны последние полученные данные. ${dashboard.error ?? 'Ожидание обновления.'}`
                  : dashboard.status === 'connecting'
                    ? 'Подключение к телеметрии…'
                    : dashboard.error ?? 'Нет данных телеметрии'}
                {import.meta.env.DEV && <> <a href="?demo=1">Включить тестовые данные</a></>}
              </div>
            )}
            {data && (
              <p className="last-update">Данные на {new Date(data.timestamp).toLocaleString('ru-RU')}</p>
            )}
            <KpiPanel kpis={view.kpis} hasData={data !== null} />
            <ErrorBoundary fallback="Не удалось отобразить карту">
              <MapSection
                vehicles={vehicles}
                selectedBusId={selectedBusId}
                selectedVehicle={selectedVehicle}
                selectionRequest={selectionRequest}
                onSelect={selectVehicle}
              />
            </ErrorBoundary>
            <ErrorBoundary fallback="Не удалось отобразить графики">
              <Suspense fallback={<p className="chart-loading" role="status">Загрузка графиков…</p>}>
                <ChartsPanel
                  segmentChartData={view.segmentChartData}
                  riskChartData={view.riskChartData}
                  reasonChartData={view.reasonChartData}
                />
              </Suspense>
            </ErrorBoundary>
          </div>
          <IncidentSidebar
            incidents={view.incidents}
            hasData={data !== null}
            selectedBusId={selectedBusId}
            selectedVehicle={selectedVehicle}
            onSelect={selectVehicle}
          />
        </main>
      ) : (
        <SettingsPage
          settings={health.settings}
          healthStatus={health.status}
          healthError={health.error}
        />
      )}
      <footer className="footer">
        <div className="footer-content">
          <img src="/logos/MGT-logo-Ru-Hor-preview.jpg" alt="" className="logo" />
          <div>
            <p>Предиктор изменений в графике транспорта</p>
            <p>Дашборд был разработан командой skibidi-sigma-67</p>
          </div>
        </div>
      </footer>
    </>
  );
}
