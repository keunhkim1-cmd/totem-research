// 거래일 캘린더 — appState.holidays를 참조하는 단일 인스턴스.
import { createTradingCalendar } from '../trading_calendar.js?v=20260426-6';
import { appState } from './state.js?v=20260426-6';

const calendar = createTradingCalendar(() => appState.holidays);

export const { toDateStr, addTradingDays, countTradingDays } = calendar;
