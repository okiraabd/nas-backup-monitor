export const APP_TIME_ZONE = "Asia/Jakarta";
export const APP_TIME_ZONE_LABEL = "WIB";

type DateInput = string | number | Date | null | undefined;

function toValidDate(value: DateInput): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function getJakartaParts(value: DateInput) {
  const date = toValidDate(value);
  if (!date) return null;

  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: APP_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });

  return Object.fromEntries(
    formatter.formatToParts(date).map((part) => [part.type, part.value]),
  );
}

export function formatDateTimeWib(value: DateInput, options?: { seconds?: boolean; suffix?: boolean }) {
  const parts = getJakartaParts(value);
  if (!parts) return "-";

  const includeSeconds = options?.seconds ?? true;
  const suffix = options?.suffix ?? true;
  const time = includeSeconds
    ? `${parts.hour}:${parts.minute}:${parts.second}`
    : `${parts.hour}:${parts.minute}`;
  return `${parts.year}-${parts.month}-${parts.day} ${time}${suffix ? ` ${APP_TIME_ZONE_LABEL}` : ""}`;
}

export function formatTimeWib(value: DateInput, options?: { seconds?: boolean; suffix?: boolean }) {
  const parts = getJakartaParts(value);
  if (!parts) return "-";

  const includeSeconds = options?.seconds ?? false;
  const suffix = options?.suffix ?? false;
  const time = includeSeconds
    ? `${parts.hour}:${parts.minute}:${parts.second}`
    : `${parts.hour}:${parts.minute}`;
  return `${time}${suffix ? ` ${APP_TIME_ZONE_LABEL}` : ""}`;
}

export function formatLongDateTimeWib(value: DateInput) {
  const date = toValidDate(value);
  if (!date) return "-";

  return `${new Intl.DateTimeFormat("id-ID", {
    timeZone: APP_TIME_ZONE,
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date)} ${APP_TIME_ZONE_LABEL}`;
}

export function jakartaDateToUtcRange(dateText: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateText);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);

  // Asia/Jakarta is UTC+07: local midnight equals previous UTC day 17:00.
  const start = new Date(Date.UTC(year, month - 1, day, -7, 0, 0, 0));
  const end = new Date(Date.UTC(year, month - 1, day + 1, -7, 0, 0, -1));

  return {
    date_from: start.toISOString(),
    date_to: end.toISOString(),
  };
}
