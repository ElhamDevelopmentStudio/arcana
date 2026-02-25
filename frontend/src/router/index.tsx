import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { authRoutes } from "@/router/auth";
import { mainRoutes } from "@/router/main";

const routes: RouteObject[] = [...mainRoutes, ...authRoutes];

export const appRouter = createBrowserRouter(routes);
