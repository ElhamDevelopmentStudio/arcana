import type { RouteObject } from 'react-router-dom';

import { AuthPlaceholderPage } from '@/pages/auth/auth-placeholder-page';

export const authRouter: RouteObject[] = [
  {
    index: true,
    element: <AuthPlaceholderPage />,
  },
];
