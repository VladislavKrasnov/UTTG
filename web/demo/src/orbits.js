import { degreesLat, degreesLong, eciToGeodetic, gstime, propagate, twoline2satrec } from "satellite.js";

const DEG = Math.PI / 180;

export function buildSatrecs(records) {
  const result = [];
  for (const record of records) {
    try {
      const satrec = twoline2satrec(record.tle_line1, record.tle_line2);
      if (satrec && !satrec.error) {
        result.push({ ...record, satrec });
      }
    } catch {
      continue;
    }
  }
  return result;
}

export function geodeticAt(satrec, date, gmst = gstime(date)) {
  const state = propagate(satrec, date);
  const position = state?.position;
  if (!position || typeof position !== "object" || Number.isNaN(position.x)) {
    return null;
  }
  const geodetic = eciToGeodetic(position, gmst);
  const velocity = state.velocity;
  return {
    latitude: degreesLat(geodetic.latitude),
    longitude: degreesLong(geodetic.longitude),
    altitudeKm: geodetic.height,
    speedKmS: velocity ? Math.hypot(velocity.x, velocity.y, velocity.z) : null,
  };
}

export function groundTrack(satrec, center, minutesBefore, minutesAfter, stepMinutes = 1) {
  const points = [];
  for (let offset = -minutesBefore; offset <= minutesAfter; offset += stepMinutes) {
    const point = geodeticAt(satrec, new Date(center.getTime() + offset * 60000));
    if (point) points.push(point);
  }
  return points;
}

export function toVector(latitude, longitude, radius) {
  const lat = latitude * DEG;
  const lon = longitude * DEG;
  return [
    radius * Math.cos(lat) * Math.cos(lon),
    radius * Math.sin(lat),
    -radius * Math.cos(lat) * Math.sin(lon),
  ];
}

export function subsolarPoint(date) {
  const days = date.getTime() / 86400000 - 10957.5;
  const meanLongitude = (280.46 + 0.9856474 * days) % 360;
  const meanAnomaly = ((357.528 + 0.9856003 * days) % 360) * DEG;
  const eclipticLongitude =
    (meanLongitude + 1.915 * Math.sin(meanAnomaly) + 0.02 * Math.sin(2 * meanAnomaly)) * DEG;
  const obliquity = (23.439 - 0.0000004 * days) * DEG;
  const rightAscension = Math.atan2(
    Math.cos(obliquity) * Math.sin(eclipticLongitude),
    Math.cos(eclipticLongitude),
  );
  const declination = Math.asin(Math.sin(obliquity) * Math.sin(eclipticLongitude));
  const longitude = ((rightAscension - gstime(date)) / DEG + 540) % 360 - 180;
  return { latitude: declination / DEG, longitude };
}

export function orbitalPeriodMinutes(satrec) {
  return (2 * Math.PI) / satrec.no;
}
