/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0B0C1F",
          900: "#12142B",
          800: "#1B1E3D",
          700: "#272B54",
        },
        marigold: {
          400: "#F7B84D",
          500: "#F5A623",
          600: "#D98C12",
        },
        tulsi: {
          500: "#4CAF7D",
          600: "#398F65",
        },
        sindoor: {
          500: "#D94A4A",
          600: "#B93838",
        },
        paper: "#F1EEE6",
      },
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
