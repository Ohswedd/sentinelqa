import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { Home } from "./routes/Home";
import { Login } from "./routes/Login";
import { Projects } from "./routes/Projects";
import { NotFound } from "./routes/NotFound";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Home /> },
      { path: "login", element: <Login /> },
      { path: "projects", element: <Projects /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

const container = document.getElementById("root");
if (!container) throw new Error("missing #root");
createRoot(container).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
