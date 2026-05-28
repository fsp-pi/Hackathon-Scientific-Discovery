import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Amplify } from "aws-amplify";

import { App } from "./App";
import { config } from "./config";
import "./index.css";

if (!config.localDev) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: config.userPoolId,
        userPoolClientId: config.userPoolClientId,
        // Email OTP is configured at the user-pool level (via signInPolicy).
        // The SDK picks the right flow at runtime when we call signIn with
        // authFlowType: "USER_AUTH".
      },
    },
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
