import { Routes } from "@angular/router";

export const routes: Routes = [
  // Root route loads HomeComponent
  {
    path: '',
    loadComponent: () => import('./home/home.component').then(m => m.HomeComponent)
  },
  // Route for TestWindow
  {
    path: 'test-window',
    loadComponent: () => import('./test-window/test-window.component').then(m => m.TestWindowComponent)
  },
  // Catch-all: redirect to home
  { path: '**', redirectTo: '' }
];
