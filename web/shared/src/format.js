const MOSCOW = "Europe/Moscow";

const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  timeZone: MOSCOW,
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
});
const timeFormatter = new Intl.DateTimeFormat("ru-RU", {
  timeZone: MOSCOW,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});
const utcTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  timeZone: "UTC",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});
const integerFormatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
const decimalFormatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });

export const formatDateTime = (value) => dateTimeFormatter.format(new Date(value));
export const formatMoscowTime = (value) => timeFormatter.format(value);
export const formatUtcTime = (value) => utcTimeFormatter.format(value);
export const formatInteger = (value) => integerFormatter.format(value);
export const formatDecimal = (value) => decimalFormatter.format(value);

export function plural(count, one, few, many) {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

export function splitCountdown(milliseconds) {
  const total = Math.max(0, Math.floor(milliseconds / 1000));
  return {
    days: Math.floor(total / 86400),
    hours: Math.floor((total % 86400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
  };
}

export function formatAge(milliseconds) {
  const seconds = Math.max(0, Math.round(milliseconds / 1000));
  if (seconds < 60) return `${seconds} с назад`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} мин назад`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} ч назад`;
  return `${Math.round(hours / 24)} дн назад`;
}

export const pad2 = (value) => String(value).padStart(2, "0");
