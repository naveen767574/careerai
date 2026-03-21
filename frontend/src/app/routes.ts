import { createBrowserRouter } from "react-router";
import { MainLayout } from "./components/MainLayout";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { Dashboard } from "./pages/Dashboard";
import { ResumeAnalyzer } from "./pages/ResumeAnalyzer";
import { Internships } from "./pages/Internships";
import { CareerPaths } from "./pages/CareerPaths";
import { ApplicationsTracker } from "./pages/ApplicationsTracker";
import { InterviewPrep } from "./pages/InterviewPrep";
import { LinkedInAnalyzer } from "./pages/LinkedInAnalyzer";
import { ResumeBuilder } from "./pages/ResumeBuilder";

export const router = createBrowserRouter([
  {
    path: "/login",
    Component: Login,
  },
  {
    path: "/register",
    Component: Register,
  },
  {
    path: "/",
    Component: MainLayout,
    children: [
      { index: true, Component: Dashboard },
      { path: "resume-analyzer", Component: ResumeAnalyzer },
      { path: "internships", Component: Internships },
      { path: "career-paths", Component: CareerPaths },
      { path: "applications", Component: ApplicationsTracker },
      { path: "interview-prep", Component: InterviewPrep },
      { path: "linkedin-analyzer", Component: LinkedInAnalyzer },
      { path: "resume-builder", Component: ResumeBuilder },
    ],
  },
]);
