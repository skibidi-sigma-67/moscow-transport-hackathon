import { memo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { BRAND_COLORS } from '../palette';

interface ChartItem {
  name: string;
  value: number;
  color: string;
}

interface ChartsPanelProps {
  segmentChartData: { name: string; delay: number }[];
  riskChartData: ChartItem[];
  reasonChartData: ChartItem[];
}

export const ChartsPanel = memo(function ChartsPanel({
  segmentChartData,
  riskChartData,
  reasonChartData,
}: ChartsPanelProps) {
  return (
    <section className="charts-section" aria-label="Аналитика задержек">
      <div className="chart-wrapper">
        <h2>Топ-5 проблемных участков (сек)</h2>
        {segmentChartData.length ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={segmentChartData} margin={{ top: 10, right: 20, left: 0, bottom: 65 }}>
              <CartesianGrid stroke={BRAND_COLORS.gray} strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: BRAND_COLORS.black }} angle={-45} textAnchor="end" height={85} />
              <YAxis tick={{ fill: BRAND_COLORS.black }} />
              <Tooltip contentStyle={{ background: BRAND_COLORS.white, borderColor: BRAND_COLORS.gray, color: BRAND_COLORS.black }} />
              <Bar dataKey="delay" fill={BRAND_COLORS.blue} />
            </BarChart>
          </ResponsiveContainer>
        ) : <p className="chart-empty">Нет данных по задержкам</p>}
      </div>
      <div className="chart-wrapper">
        <h2>Распределение рисков</h2>
        {riskChartData.some(({ value }) => value > 0) ? (
          <>
            <ResponsiveContainer width="100%" height={210}>
              <PieChart>
                <Pie data={riskChartData} cx="50%" cy="50%" innerRadius={55} outerRadius={75} dataKey="value">
                  {riskChartData.map(({ name, color }) => <Cell key={name} fill={color} />)}
                </Pie>
                <Tooltip contentStyle={{ background: BRAND_COLORS.white, borderColor: BRAND_COLORS.gray, color: BRAND_COLORS.black }} />
              </PieChart>
            </ResponsiveContainer>
            <ul className="chart-legend">{riskChartData.map(({ name, color, value }) => (
              <li key={name}><span className="legend-dot" style={{ backgroundColor: color }} />{name}: {value}</li>
            ))}</ul>
          </>
        ) : <p className="chart-empty">Нет данных о транспорте</p>}
      </div>
      <div className="chart-wrapper">
        <h2>Причины задержек</h2>
        {reasonChartData.length ? (
          <>
            <ResponsiveContainer width="100%" height={210}>
              <PieChart>
                <Pie data={reasonChartData} cx="50%" cy="50%" innerRadius={55} outerRadius={75} dataKey="value">
                  {reasonChartData.map(({ name, color }) => <Cell key={name} fill={color} />)}
                </Pie>
                <Tooltip contentStyle={{ background: BRAND_COLORS.white, borderColor: BRAND_COLORS.gray, color: BRAND_COLORS.black }} />
              </PieChart>
            </ResponsiveContainer>
            <ul className="chart-legend">{reasonChartData.map(({ name, color, value }) => (
              <li key={name}><span className="legend-dot" style={{ backgroundColor: color }} />{name}: {value}</li>
            ))}</ul>
          </>
        ) : <p className="chart-empty">Нет зарегистрированных причин</p>}
      </div>
    </section>
  );
});
