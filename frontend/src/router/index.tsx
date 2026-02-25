import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { authRoutes } from "@/router/auth-routes";
import { mainRoutes } from "@/router/main-routes";

const routes: RouteObject[] = [...mainRoutes, ...authRoutes];

export const appRouter = createBrowserRouter(routes);
