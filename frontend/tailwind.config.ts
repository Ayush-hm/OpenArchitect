import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172027",
        panel: "#f7f8f6",
        line: "#d9dfd8",
        moss: "#3f6b57",
        copper: "#a86134",
        marine: "#285d78",
        signal: "#b33d3d",
      },
      boxShadow: {
        soft: "0 12px 32px rgba(23, 32, 39, 0.08)",
      },
    },
  },
  plugins: [],
} satisfies Config;
