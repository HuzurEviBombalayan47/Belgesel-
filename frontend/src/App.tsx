import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import Home from "@/pages/Home";
import Editor from "@/pages/Editor";

// One <Route> per page in src/pages; BrowserRouter already wraps this in main.tsx.
export default function App() {
  return (
    <div className="min-h-svh bg-background font-sans text-foreground antialiased">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/projects/:id" element={<Editor />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster richColors position="bottom-right" />
    </div>
  );
}
