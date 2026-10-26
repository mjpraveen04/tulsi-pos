import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { RequireAuth, RequireManager } from "./auth/guards";
import TopBar from "./components/TopBar";
import Inventory from "./screens/Inventory";
import Login from "./screens/Login";
import Orders from "./screens/Orders";
import Register from "./screens/Register";
import Staff from "./screens/Staff";

function AppShell() {
  return (
    <div className="app">
      <TopBar />
      <Outlet />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/register" element={<Register />} />

          {/* Manager-only in the UI; the API enforces the same rule (FR-04). */}
          <Route element={<RequireManager />}>
            <Route path="/inventory" element={<Inventory />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/staff" element={<Staff />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/register" replace />} />
    </Routes>
  );
}
