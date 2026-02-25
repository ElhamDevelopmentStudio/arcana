import type { RouteObject } from "react-router-dom";

import AuthLayout from "@/layouts/auth-layout";
import AuthPlaceholderPage from "@/pages/auth/auth-placeholder-page";

export const authRoutes: RouteObject[] = [
  {
    path: "/auth",
    element: <AuthLayout />,
    children: [
      {
        index: true,
        element: <AuthPlaceholderPage />,
      },
    ],
  },
];
