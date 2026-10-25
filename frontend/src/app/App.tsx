import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "../components/layout/AppLayout";
import { SessionProvider, useSession } from "../features/auth/session";
import { ChatProvider } from "../features/chat/chat-state";
import { BenefitsPage } from "../pages/BenefitsPage";
import { ChatPage } from "../pages/ChatPage";
import { ClaimsPage } from "../pages/ClaimsPage";
import { DocumentsPage } from "../pages/DocumentsPage";
import { LoginPage } from "../pages/LoginPage";
import { CasesPage } from "../pages/CasesPage";
import { AdminPage, AgentPage, ProviderWorkspacePage, ReadinessPage } from "../pages/PreparedPages";
import { NotFoundPage } from "../pages/StatusPages";
import { RequirePermission, RequireSession } from "./guards";
import { HOME_BY_ROLE, NAV_ITEMS } from "./navigation";

const anyOf = (path: string) => NAV_ITEMS.find((item) => item.path === path)?.anyOf ?? [];

function Home() {
  const { user } = useSession();
  return <Navigate to={user ? HOME_BY_ROLE[user.role] : "/login"} replace />;
}

export function AppRoutes() {
  const guarded = (path: string, element: JSX.Element) => (
    <Route path={path} element={<RequirePermission anyOf={anyOf(path)}>{element}</RequirePermission>} />
  );
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireSession>
            <AppLayout />
          </RequireSession>
        }
      >
        <Route index element={<Home />} />
        {guarded("/provider", <ProviderWorkspacePage />)}
        {guarded("/chat", <ChatPage />)}
        {guarded("/claims", <ClaimsPage />)}
        {guarded("/benefits", <BenefitsPage />)}
        {guarded("/documents", <DocumentsPage />)}
        {guarded("/readiness", <ReadinessPage />)}
        {guarded("/cases", <CasesPage />)}
        {guarded("/agent", <AgentPage />)}
        {guarded("/admin", <AdminPage />)}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <SessionProvider>
      <ChatProvider>
        <AppRoutes />
      </ChatProvider>
    </SessionProvider>
  );
}
