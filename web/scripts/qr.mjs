import { mkdir, writeFile } from "node:fs/promises";
import QRCode from "qrcode";

const TARGETS = {
  hub: "https://hub.uttg.oxis.cc",
  demo: "https://demo.uttg.oxis.cc",
  presentation: "https://presentation.uttg.oxis.cc",
};

const outputDirectory = new URL("../shared/qr/", import.meta.url);
await mkdir(outputDirectory, { recursive: true });
for (const [name, url] of Object.entries(TARGETS)) {
  const svg = await QRCode.toString(url, { type: "svg", margin: 1, errorCorrectionLevel: "M", color: { dark: "#111111", light: "#ffffff" } });
  await writeFile(new URL(`${name}.svg`, outputDirectory), svg);
}
