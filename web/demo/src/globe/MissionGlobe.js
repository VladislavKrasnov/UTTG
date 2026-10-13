import Globe from "globe.gl";
import { CanvasTexture, SRGBColorSpace } from "three";

const ACCENT = "#ff5c00";
const EARTH_RADIUS_KM = 6371;
const GEOMAGNETIC_POLE = { latitude: 80.7, longitude: -72.7 };
const DEG = Math.PI / 180;
const VIEW_ALTITUDE = { near: 1.4, default: 2.3, far: 3.6 };

export const globeAltitude = (altitudeKm) =>
  altitudeKm <= 2000 ? altitudeKm / EARTH_RADIUS_KM : 2000 / EARTH_RADIUS_KM + 0.12 * Math.log10(altitudeKm / 2000 + 1);

function discTexture() {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const context = canvas.getContext("2d");
  context.fillStyle = "#111111";
  context.beginPath();
  context.arc(size / 2, size / 2, size / 2 - 1, 0, 2 * Math.PI);
  context.fill();
  context.fillStyle = "#ffffff";
  context.beginPath();
  context.arc(size / 2, size / 2, size / 2 - 14, 0, 2 * Math.PI);
  context.fill();
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  return texture;
}

function auroraRing(kpIndex) {
  const colatitude = Math.min(40, 23 + 2 * kpIndex) * DEG;
  const poleLat = GEOMAGNETIC_POLE.latitude * DEG;
  const poleLng = GEOMAGNETIC_POLE.longitude * DEG;
  const points = [];
  for (let step = 0; step <= 180; step += 1) {
    const bearing = (step / 180) * 2 * Math.PI;
    const lat = Math.asin(Math.sin(poleLat) * Math.cos(colatitude) + Math.cos(poleLat) * Math.sin(colatitude) * Math.cos(bearing));
    const lng = poleLng + Math.atan2(Math.sin(bearing) * Math.sin(colatitude) * Math.cos(poleLat), Math.cos(colatitude) - Math.sin(poleLat) * Math.sin(lat));
    points.push([lat / DEG, ((lng / DEG + 540) % 360) - 180, 0.004]);
  }
  return points;
}

export class MissionGlobe {
  constructor(container, { onReady }) {
    this.container = container;
    this.tracks = [];
    this.aurora = null;
    this.globe = new Globe(container, { rendererConfig: { antialias: true, alpha: true } })
      .backgroundColor("rgba(0,0,0,0)")
      .globeImageUrl("/textures/earth-blue-marble.jpg")
      .bumpImageUrl("/textures/earth-topology.png")
      .showAtmosphere(true)
      .atmosphereColor("#9cc7ff")
      .atmosphereAltitude(0.14)
      .particlesList("items")
      .particleLat("latitude")
      .particleLng("longitude")
      .particleAltitude((item) => globeAltitude(item.altitudeKm))
      .particlesSize("size")
      .particlesSizeAttenuation(false)
      .particlesColor("color")
      .particlesTexture(discTexture())
      .pathPoints("points")
      .pathPointLat((point) => point[0])
      .pathPointLng((point) => point[1])
      .pathPointAlt((point) => point[2])
      .pathColor("color")
      .pathStroke("stroke")
      .pathDashLength("dash")
      .pathDashGap("gap")
      .pathDashAnimateTime("animate")
      .pathTransitionDuration(0)
      .ringColor(() => (progress) => `rgba(255, 92, 0, ${1 - progress})`)
      .ringMaxRadius(5)
      .ringPropagationSpeed(2.5)
      .ringRepeatPeriod(900)
      .labelText("text")
      .labelSize(0.9)
      .labelDotRadius(0.45)
      .labelColor(() => ACCENT)
      .labelResolution(3)
      .labelAltitude(0.01)
      .onGlobeReady(() => onReady?.());
    this.globe.controls().autoRotateSpeed = 0.35;
    this.globe.controls().enableDamping = true;
    this.globe.pointOfView({ lat: 25, lng: 40, altitude: VIEW_ALTITUDE.default }, 0);
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
  }

  resize() {
    const { clientWidth: width, clientHeight: height } = this.container;
    if (width && height) this.globe.width(width).height(height);
  }

  setSatellites(groups) {
    this.globe.particlesData(groups);
  }

  setTracks(tracks) {
    this.tracks = tracks;
    this.renderPaths();
  }

  setAurora(kpIndex) {
    this.aurora = kpIndex == null ? null : { points: auroraRing(kpIndex), color: ACCENT, stroke: 1.2, dash: 1, gap: 0, animate: 0 };
    this.renderPaths();
  }

  renderPaths() {
    this.globe.pathsData(this.aurora ? [...this.tracks, this.aurora] : this.tracks);
  }

  setSite(site) {
    this.globe.ringsData(site ? [{ lat: site.latitude, lng: site.longitude }] : []);
    this.globe.labelsData(site ? [{ lat: site.latitude, lng: site.longitude, text: site.label }] : []);
  }

  focus(latitude, longitude, zoom = "default", durationMs = 1200) {
    this.globe.controls().autoRotate = false;
    this.globe.pointOfView({ lat: latitude, lng: longitude, altitude: VIEW_ALTITUDE[zoom] ?? VIEW_ALTITUDE.default }, durationMs);
  }

  spin(zoom = "default") {
    const view = this.globe.pointOfView();
    if (Math.abs(view.altitude - (VIEW_ALTITUDE[zoom] ?? VIEW_ALTITUDE.default)) > 0.05) {
      this.globe.pointOfView({ altitude: VIEW_ALTITUDE[zoom] ?? VIEW_ALTITUDE.default }, 1200);
    }
    this.globe.controls().autoRotate = true;
  }

  dispose() {
    this.resizeObserver.disconnect();
    this.globe._destructor?.();
    this.container.replaceChildren();
  }
}
