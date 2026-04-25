export function createTradingCalendar(holidaySetProvider) {
  function toDateStr(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  function isHoliday(d) {
    return holidaySetProvider().has(toDateStr(d));
  }

  function isWeekend(d) {
    const day = d.getDay();
    return day === 0 || day === 6;
  }

  function isTradingDay(d) {
    return !isWeekend(d) && !isHoliday(d);
  }

  function addDays(d, n) {
    const r = new Date(d);
    r.setDate(r.getDate() + n);
    return r;
  }

  function addTradingDays(start, n) {
    let count = 0;
    let cur = new Date(start);
    while (count < n) {
      cur = addDays(cur, 1);
      if (isTradingDay(cur)) count += 1;
    }
    return cur;
  }

  function countTradingDays(start, end) {
    let count = 0;
    let cur = new Date(start);
    while (cur <= end) {
      if (isTradingDay(cur)) count += 1;
      cur = addDays(cur, 1);
    }
    return count;
  }

  return { toDateStr, addTradingDays, countTradingDays };
}
