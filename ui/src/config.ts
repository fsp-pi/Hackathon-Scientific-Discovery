// Build-time configuration. Vite inlines `import.meta.env.VITE_*` variables
// when running `vite build`; the deploy script sets them before invoking it.
//
// Required:
//   VITE_API_URL              base URL of the FastAPI on ALB
//   VITE_COGNITO_USER_POOL_ID Cognito user pool id
//   VITE_COGNITO_CLIENT_ID    Cognito app client id
//   VITE_COGNITO_REGION       AWS region of the user pool (default us-east-1)

// VITE_LOCAL_DEV=1 short-circuits Cognito so the SPA can run against
// scripts/dev/up.sh without real AWS credentials. Set in ui/.env.local
// (gitignored). Has no effect in production builds since the var simply
// isn't set there.
const localDev = import.meta.env.VITE_LOCAL_DEV === "1";

function required(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name];
  if (!value) {
    if (localDev) return "local-dev-stub";
    throw new Error(
      `Missing build-time env var ${name}. Re-run \`npm run build\` with it set.`,
    );
  }
  return value;
}

// The API is fronted by the same CloudFront distribution that serves the
// SPA, under /api/*. Build-time override exists so we can point the SPA at
// localhost during dev without rebuilding CloudFront.
const apiUrl =
  import.meta.env.VITE_API_URL ?? "";

export const config = {
  apiUrl: `${apiUrl.replace(/\/$/, "")}/api`,
  userPoolId: required("VITE_COGNITO_USER_POOL_ID"),
  userPoolClientId: required("VITE_COGNITO_CLIENT_ID"),
  region: import.meta.env.VITE_COGNITO_REGION ?? "us-east-1",
  localDev,
};
