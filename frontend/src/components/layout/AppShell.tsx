import { ReactNode, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../shared/ui';

interface NavItem {
  label: string;
  view: string;
  icon: string;
  roles: string[];
}

const navItems: NavItem[] = [
  { label: 'Chat', view: 'chat', icon: '💬', roles: ['user', 'admin', 'superadmin'] },
  { label: 'My Users', view: 'admin-users', icon: '👥', roles: ['admin', 'superadmin'] },
  { label: 'Admins', view: 'superadmin-admins', icon: '🛡️', roles: ['superadmin'] },
  { label: 'All Users', view: 'superadmin-users', icon: '🌐', roles: ['superadmin'] },
  { label: 'Data Ingest', view: 'superadmin-ingest', icon: '📥', roles: ['superadmin'] },
  { label: 'Profile', view: 'profile', icon: '👤', roles: ['user', 'admin', 'superadmin'] },
];

interface AppShellProps {
  currentView: string;
  onNavigate: (view: string) => void;
  children: ReactNode;
}

export function AppShell({ currentView, onNavigate, children }: AppShellProps) {
  const { user, role, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const visible = navItems.filter((item) => role && item.roles.includes(role));

  const roleBadgeColor: Record<string, string> = {
    superadmin: 'bg-purple-100 text-purple-700',
    admin: 'bg-indigo-100 text-indigo-700',
    user: 'bg-gray-100 text-gray-600',
  };

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-gray-100">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm">A</div>
          <span className="font-semibold text-gray-900 tracking-tight">Assistant</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {visible.map((item) => {
          const active = currentView === item.view;
          return (
            <button
              key={item.view}
              onClick={() => { onNavigate(item.view); setMobileOpen(false); }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                ${active
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* User footer */}
      <div className="px-4 py-4 border-t border-gray-100">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-semibold text-sm">
            {user?.username?.[0]?.toUpperCase() ?? '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{user?.username}</p>
            <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${roleBadgeColor[role ?? 'user'] ?? 'bg-gray-100 text-gray-600'}`}>
              {role}
            </span>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="w-full justify-start text-gray-500" onClick={logout}>
          Sign out
        </Button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-56 bg-white border-r border-gray-200 shrink-0">
        <SidebarContent />
      </aside>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setMobileOpen(false)} />
          <aside className="relative w-56 h-full bg-white shadow-xl">
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile topbar */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-200">
          <button
            onClick={() => setMobileOpen(true)}
            className="text-gray-600 hover:text-gray-900"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="font-semibold text-gray-900">Assistant</span>
        </header>

        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}