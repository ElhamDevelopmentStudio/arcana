import { createBrowserRouter } from 'react-router-dom';

import { authRouter } from './auth';
import { mainRouter } from './main';

export const router = createBrowserRouter([
  {
    path: '/',
    children: mainRouter,
  },
  {
    path: '/auth',
    children: authRouter,
  },
]);
