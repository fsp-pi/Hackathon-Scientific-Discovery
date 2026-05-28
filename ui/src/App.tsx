import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./auth";
import { NavBar } from "./components/NavBar";
import { EventGate } from "./eventGate";
import { Browse } from "./pages/Browse";
import { GettingStarted } from "./pages/GettingStarted";
import { Activity } from "./pages/Activity";
import { PaperDetailPage } from "./pages/PaperDetail";
import { Reviews } from "./pages/Reviews";
import { Settings } from "./pages/Settings";
import { SignIn } from "./pages/SignIn";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="app-shell">Loading…</div>;
  if (!user) return <Navigate to="/sign-in" replace />;
  return children;
}

function Shell({ children }: { children: JSX.Element }) {
  return (
    <>
      <NavBar />
      <div className="app-shell">{children}</div>
    </>
  );
}

export function App() {
  return (
    <EventGate>
      <AuthProvider>
        <Routes>
          <Route path="/sign-in" element={<SignIn />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Shell>
                  <Browse />
                </Shell>
              </RequireAuth>
            }
          />
          <Route
            path="/papers/:id"
            element={
              <RequireAuth>
                <Shell>
                  <PaperDetailPage />
                </Shell>
              </RequireAuth>
            }
          />
          <Route
            path="/activity"
            element={
              <RequireAuth>
                <Shell>
                  <Activity />
                </Shell>
              </RequireAuth>
            }
          />
          <Route
            path="/reviews"
            element={
              <RequireAuth>
                <Shell>
                  <Reviews />
                </Shell>
              </RequireAuth>
            }
          />
          <Route
            path="/settings"
            element={
              <RequireAuth>
                <Shell>
                  <Settings />
                </Shell>
              </RequireAuth>
            }
          />
          <Route
            path="/getting-started"
            element={
              <RequireAuth>
                <Shell>
                  <GettingStarted />
                </Shell>
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </EventGate>
  );
}
