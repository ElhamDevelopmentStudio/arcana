import type { RouteObject } from "react-router-dom";

import AuthLayout from "@/layouts/AuthLayout";
import AuthPlaceholderPage from "@/pages/auth/AuthPlaceholderPage";

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
