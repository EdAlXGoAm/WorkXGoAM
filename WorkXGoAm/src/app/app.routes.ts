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
  // Route for Video Cutter
  {
    path: 'video-cutter',
    loadComponent: () => import('./video-cutter/video-cutter.component').then(m => m.VideoCutterComponent)
  },
  // Route for Floating Face Popup
  {
    path: 'floating-face-popup',
    loadComponent: () => import('./floating-face-popup/floating-face-popup.component').then(m => m.FloatingFacePopupComponent)
  },
  // Catch-all: redirect to home
  { path: '**', redirectTo: '' }
];
