import { getPartyColor } from '../config/partyBranding.js';

export const nulos2021 = [
  { id: 'pres1v', label: 'Presidencial 1.ª vuelta', blancos: 12.36, nulos: 6.34, validos: 81.3, participacion: 70.05 },
  { id: 'pres2v', label: 'Presidencial 2.ª vuelta', blancos: 0.644, nulos: 5.87, validos: 93.49, participacion: 74.57 },
  { id: 'congreso', label: 'Congresal 2021', blancos: 12.0, nulos: 15.44, validos: 72.56, participacion: 70.05 },
];

export const presidencial2026 = [
  { p: 'Fuerza Popular (Fujimori)', party: 'FP', valid: 18.6, cast: 13.8, color: getPartyColor('FP') },
  { p: 'País para Todos (Álvarez)', party: 'PPT', valid: 12.1, cast: 9.0, color: getPartyColor('PPT') },
  { p: 'Renovación Popular (López Aliaga)', party: 'RP', valid: 10.9, cast: 8.1, color: getPartyColor('RP') },
  { p: 'Juntos por el Perú (Sánchez)', party: 'JPP', valid: 9.0, cast: 6.7, color: getPartyColor('JPP') },
  { p: 'Partido del Buen Gobierno (Nieto)', party: 'PBG', valid: 5.6, cast: 4.2, color: getPartyColor('PBG') },
  { p: 'Alianza para el Progreso (Acuña)', party: 'APP', valid: 5.1, cast: 3.8, color: getPartyColor('APP') },
  { p: 'Ahora Nación (López-Chau)', party: 'AN', valid: 4.4, cast: 3.3, color: getPartyColor('AN') },
  { p: 'Blanco / ninguno / indeciso', party: 'NONE', valid: null, cast: 26.0, color: getPartyColor('NONE') },
];

export const senateNational = [
  { p: 'Fuerza Popular', pct: 14.6, scenarioSeats: 17, party: 'FP', color: getPartyColor('FP') },
  { p: 'Renovación Popular', pct: 13.2, scenarioSeats: 13, party: 'RP', color: getPartyColor('RP') },
  { p: 'Juntos por el Perú', pct: 9.6, scenarioSeats: 9, party: 'JPP', color: getPartyColor('JPP') },
  { p: 'Alianza para el Progreso', pct: 7.2, scenarioSeats: 7, party: 'APP', color: getPartyColor('APP') },
  { p: 'Partido del Buen Gobierno', pct: 5.8, scenarioSeats: 6, party: 'PBG', color: getPartyColor('PBG') },
  { p: 'Ahora Nación', pct: 5.5, scenarioSeats: 5, party: 'AN', color: getPartyColor('AN') },
];

export const senateDistrict = [
  { region: 'Lima', winner: 'Fuerza Popular', party: 'FP', color: getPartyColor('FP') },
  { region: 'Arequipa', winner: 'Renovación Popular', party: 'RP', color: getPartyColor('RP') },
  { region: 'La Libertad', winner: 'Alianza para el Progreso', party: 'APP', color: getPartyColor('APP') },
  { region: 'Piura', winner: 'Fuerza Popular', party: 'FP', color: getPartyColor('FP') },
  { region: 'Cusco', winner: 'Juntos por el Perú', party: 'JPP', color: getPartyColor('JPP') },
  { region: 'Junín', winner: 'Juntos por el Perú', party: 'JPP', color: getPartyColor('JPP') },
  { region: 'Áncash', winner: 'Alianza para el Progreso', party: 'APP', color: getPartyColor('APP') },
  { region: 'Puno', winner: 'Juntos por el Perú', party: 'JPP', color: getPartyColor('JPP') },
  { region: 'Cajamarca', winner: 'Sin dato de encuesta', party: 'NONE', color: getPartyColor('NONE') },
  { region: 'Loreto', winner: 'Sin dato de encuesta', party: 'NONE', color: getPartyColor('NONE') },
];

export const dataModel = [
  ['election_process', 'EG 2026, 2.ª vuelta, primarias previas'],
  ['contest', 'Presidencia | Senado nacional | Senado distrital | Diputados distritales'],
  ['district', 'Nacional, 27 circunscripciones, exterior - jerarquía parent_id'],
  ['measurement_source', 'ONPE, JNE, Ipsos, CPI, Datum, IEP, Aklla - is_official: bool'],
  ['measurement', 'poll | simulation | official_count | quick_count | projection'],
  ['measurement_value', 'vote_basis NOT NULL: cast_votes | valid_votes | official_valid | official_total'],
  ['ballot_quality', 'blank_pct, null_pct, valid_pct, annulment_risk'],
  ['seat_projection', 'scenario_seats, threshold_margin, passes_threshold'],
  ['acta_progress', 'coverage_pct, stale_minutes, last_update por district'],
  ['incident', 'incidencias operativas con district_id y timestamp'],
];
