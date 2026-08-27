import { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppShell } from './components/layout/AppShell';
import { LoginPage } from './components/auth/LoginPage';
import { ChatPage } from './components/chat/ChatPage';
import { AdminUsersPage } from './components/admin/AdminUsersPage';
import { AdminChatAsUser } from './components/admin/AdminChatAsUser';
import { SuperadminAdminsPage } from './components/superadmin/SuperadminAdminsPage';
import { SuperadminUsersPage } from './components/superadmin/SuperadminUsersPage';
import { SuperadminIngestPage } from './components/superadmin/SuperadminIngestPage';
import { ProfilePage } from './pages/ProfilePage';
import { RoleGuard, UnauthorizedPage } from './components/shared/RoleGuard';
import { Spinner } from './components/shared/ui';

// ─── View router ────────────────────────────────────────────────────────────
function AppRouter() {
  const { isAuthenticated, isLoading, role } = useAuth();
  const [currentView, setCurrentView] = useState(() => {
    // Default view based on role stored in session — will be resolved after hydration
    return 'chat';
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const renderView = () => {
    switch (currentView) {
      case 'chat':
        return (
          <RoleGuard allowedRoles={['user', 'admin', 'superadmin']} fallback={<UnauthorizedPage />}>
            <ChatPage />
          </RoleGuard>
        );

      case 'admin-users':
        return (
          <RoleGuard allowedRoles={['admin', 'superadmin']} fallback={<UnauthorizedPage />}>
            <AdminUsersPage />
          </RoleGuard>
        );

      case 'admin-chat-as-user':
        return (
          <RoleGuard allowedRoles={['admin', 'superadmin']} fallback={<UnauthorizedPage />}>
            <AdminChatAsUser />
          </RoleGuard>
        );

      case 'superadmin-admins':
        return (
          <RoleGuard allowedRoles={['superadmin']} fallback={<UnauthorizedPage />}>
            <SuperadminAdminsPage />
          </RoleGuard>
        );

      case 'superadmin-users':
        return (
          <RoleGuard allowedRoles={['superadmin']} fallback={<UnauthorizedPage />}>
            <SuperadminUsersPage />
          </RoleGuard>
        );

      case 'superadmin-ingest':
        return (
          <RoleGuard allowedRoles={['superadmin']} fallback={<UnauthorizedPage />}>
            <SuperadminIngestPage />
          </RoleGuard>
        );

      case 'profile':
        return <ProfilePage />;

      default:
        return <ChatPage />;
    }
  };

  return (
    <AppShell currentView={currentView} onNavigate={setCurrentView}>
      {renderView()}
    </AppShell>
  );
}

// ─── Root with providers ────────────────────────────────────────────────────
export default function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}