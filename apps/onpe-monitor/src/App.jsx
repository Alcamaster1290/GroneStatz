import React from 'react';

import Badge from './components/Badge.jsx';
import { partyBranding } from './config/partyBranding.js';
import { alertRules } from './data/alerts.js';
import { dataModel, nulos2021, presidencial2026, senateDistrict, senateNational } from './data/elections.js';

const severityLabel = {
  critical: 'Critico',
  high: 'Alto',
  medium: 'Medio',
  info: 'Info',
};

const severityColor = {
  critical: '#ff4d6d',
  high: '#f59e0b',
  medium: '#4cc9f0',
  info: '#8ea0b8',
};

function formatPct(value) {
  if (value === null || value === undefined) {
    return '-';
  }
  return `${value.toFixed(1)}%`;
}

function PercentBar({ value, color, max = 30 }) {
  const width = Math.max(2, Math.min(100, (value / max) * 100));

  return (
    <div className="bar" aria-hidden="true">
      <span style={{ width: `${width}%`, background: color }} />
    </div>
  );
}

function CandidateRow({ item, index }) {
  const party = partyBranding[item.party] ?? partyBranding.NONE;

  return (
    <li className="candidate-row">
      <span className="rank">{String(index + 1).padStart(2, '0')}</span>
      <div className="candidate-main">
        <strong>{item.p}</strong>
        <PercentBar value={item.cast} color={item.color} />
      </div>
      <Badge label={party.shortName} color={item.color} />
      <span className="metric">{formatPct(item.cast)}</span>
    </li>
  );
}

function AlertRow({ alert }) {
  const color = severityColor[alert.severity] ?? severityColor.info;

  return (
    <li className="alert-row">
      <Badge label={severityLabel[alert.severity] ?? alert.severity} color={color} />
      <div>
        <strong>{alert.trigger}</strong>
        <span>{alert.action}</span>
      </div>
    </li>
  );
}

function DistrictChip({ item }) {
  return (
    <li className="district-chip" style={{ '--party-color': item.color }}>
      <span>{item.region}</span>
      <strong>{item.winner}</strong>
    </li>
  );
}

export default function App() {
  const presidentialContenders = presidencial2026.filter((item) => item.valid !== null);
  const leader = presidentialContenders[0];
  const blankOrUndecided = presidencial2026.find((item) => item.party === 'NONE');
  const criticalAlerts = alertRules.filter((rule) => rule.severity === 'critical' || rule.severity === 'high');

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">EG 2026</p>
          <h1>ONPE Monitor</h1>
        </div>
        <div className="status-strip" aria-label="Estado operativo">
          <span>Preconteo</span>
          <strong>Simulacion</strong>
        </div>
      </header>

      <section className="overview-grid" aria-label="Resumen presidencial">
        <article className="summary-panel">
          <p className="eyebrow">Presidencial</p>
          <h2>{leader.p}</h2>
          <div className="summary-metrics">
            <div>
              <span>Votos emitidos</span>
              <strong>{formatPct(leader.cast)}</strong>
            </div>
            <div>
              <span>Votos validos</span>
              <strong>{formatPct(leader.valid)}</strong>
            </div>
            <div>
              <span>Blanco / indeciso</span>
              <strong>{formatPct(blankOrUndecided?.cast)}</strong>
            </div>
          </div>
        </article>

        <article className="benchmark-panel">
          <p className="eyebrow">Benchmark 2021</p>
          <ul className="benchmark-list">
            {nulos2021.map((item) => (
              <li key={item.id}>
                <span>{item.label}</span>
                <strong>{formatPct(item.blancos + item.nulos)}</strong>
              </li>
            ))}
          </ul>
        </article>
      </section>

      <section className="content-grid">
        <article className="panel candidates-panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">Tracking</p>
              <h2>Carrera presidencial</h2>
            </div>
            <Badge label="cast votes" color="#00d4aa" />
          </div>
          <ol className="candidate-list">
            {presidencial2026.map((item, index) => (
              <CandidateRow key={item.party} item={item} index={index} />
            ))}
          </ol>
        </article>

        <article className="panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">Alertas</p>
              <h2>Senales criticas</h2>
            </div>
          </div>
          <ul className="alert-list">
            {criticalAlerts.map((alert) => (
              <AlertRow key={alert.id} alert={alert} />
            ))}
          </ul>
        </article>

        <article className="panel senate-panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">Senado</p>
              <h2>Escenario nacional</h2>
            </div>
          </div>
          <ul className="senate-list">
            {senateNational.map((item) => (
              <li key={item.party}>
                <span>{item.p}</span>
                <PercentBar value={item.pct} color={item.color} max={18} />
                <strong>{item.scenarioSeats}</strong>
              </li>
            ))}
          </ul>
        </article>

        <article className="panel district-panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">Distritos</p>
              <h2>Mapa operativo</h2>
            </div>
          </div>
          <ul className="district-grid">
            {senateDistrict.map((item) => (
              <DistrictChip key={item.region} item={item} />
            ))}
          </ul>
        </article>

        <article className="panel model-panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">Modelo</p>
              <h2>Contratos de datos</h2>
            </div>
          </div>
          <dl className="model-list">
            {dataModel.slice(0, 7).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </article>
      </section>
    </main>
  );
}
