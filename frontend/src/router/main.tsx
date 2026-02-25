import type { RouteObject } from "react-router-dom";

import App from "@/App";
import MainLayout from "@/layouts/MainLayout";

export const mainRoutes: RouteObject[] = [
  {
    path: "/",
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <App />,
      },
    ],
  },
];
