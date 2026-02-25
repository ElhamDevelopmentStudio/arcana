import type { RouteObject } from "react-router-dom";

import ControlDeckPage from "@/pages/main/control-deck-page";
import MainLayout from "@/layouts/main-layout";

export const mainRoutes: RouteObject[] = [
  {
    path: "/",
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <ControlDeckPage />,
      },
    ],
  },
];
