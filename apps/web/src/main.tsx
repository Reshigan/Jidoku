import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
// Before app.css, so the @font-face rules exist by the time the variables that use them do.
// Generated from the installed @fontsource packages — see src/fonts.check.mjs.
import "./fonts.css";
import "./app.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
