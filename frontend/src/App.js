import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import ProjectStudio from "@/pages/ProjectStudio";
import Admin from "@/pages/Admin";
import Settings from "@/pages/Settings";
import Login from "@/pages/Login";
import { BillingCancel, BillingSuccess } from "@/pages/BillingResult";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/projects/:id" element={<ProjectStudio />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/billing/success" element={<BillingSuccess />} />
            <Route path="/billing/cancel" element={<BillingCancel />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="/login" element={<Login />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#121212",
            border: "1px solid rgba(255,255,255,0.1)",
            color: "#f5f5f5",
          },
        }}
      />
    </div>
  );
}

export default App;
