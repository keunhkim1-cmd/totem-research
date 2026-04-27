// 거래일 캘린더 — appState.holidays를 참조하는 단일 인스턴스.
import { createTradingCalendar } from '../trading_calendar.js?v=20260427-1';
import { appState } from './state.js?v=20260427-1';

const calendar = createTradingCalendar(() => appState.holidays);

export const { toDateStr, addTradingDays, countTradingDays } = calendar;
