interface KpiPanelProps {
  hasData: boolean;
  kpis: {
    total: number;
    green: number;
    risk: number;
    totalDelay: number;
  };
}

export function KpiPanel({ kpis, hasData }: KpiPanelProps) {
  return (
    <section className="kpi-panel" aria-label="Показатели транспорта">
      <div className="kpi-card"><h2>Всего ТС на линии</h2><div className="value">{hasData ? kpis.total : '—'}</div></div>
      <div className="kpi-card"><h2>В графике</h2><div className="value green-text">{hasData ? kpis.green : '—'}</div></div>
      <div className="kpi-card"><h2>В зоне риска</h2><div className="value red-text">{hasData ? kpis.risk : '—'}</div></div>
      <div className="kpi-card"><h2>Суммарное отставание</h2><div className="value">{hasData ? `${Math.round(kpis.totalDelay)} сек` : '—'}</div></div>
    </section>
  );
}
