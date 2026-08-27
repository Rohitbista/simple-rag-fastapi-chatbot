import { ReactNode } from 'react';
import { useAuth } from '../../context/AuthContext';

interface RoleGuardProps {
  allowedRoles: string[];
  children: ReactNode;
  fallback?: ReactNode;
}

export function RoleGuard({ allowedRoles, children, fallback = null }: RoleGuardProps) {
  const { role } = useAuth();
  if (!role || !allowedRoles.includes(role)) return <>{fallback}</>;
  return <>{children}</>;
}

export function UnauthorizedPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full py-24 text-center">
      <span className="text-5xl mb-4">🔒</span>
      <h2 className="text-lg font-semibold text-gray-800">Access denied</h2>
      <p className="text-sm text-gray-500 mt-1">You don't have permission to view this page.</p>
    </div>
  );
}