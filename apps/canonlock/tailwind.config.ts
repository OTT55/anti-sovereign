import preset from "@anti-sovereign/design-system/tailwind-preset";
import type { Config } from "tailwindcss";

const config: Config = {
  presets: [preset as Config],
  content: ["./src/**/*.{ts,tsx}"],
};

export default config;
