import { createBrowserRouter } from 'react-router-dom';

import { authRouter } from './auth';
import { mainRouter } from './main';
import { LandingPage } from '@/pages/landing/landing-page';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <LandingPage />,
  },
  {
    path: '/',
    children: mainRouter,
  },
  {
    path: '/auth',
    children: authRouter,
  },
]);
