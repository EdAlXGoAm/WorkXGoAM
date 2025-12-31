import { Component, OnInit } from '@angular/core'

@Component({
  selector: 'app-floating-face-popup',
  standalone: true,
  template: `
  <div class="popup-root" (mouseenter)="onEnter()" (mouseleave)="onLeave()">
    <div class="controls-row">
      <button class="hide-rdp-btn" (click)="hideRemoteDesktop()">
        Hide Windows App
      </button>
      <label class="auto-switch">
        <input type="checkbox" [checked]="autoMode" (change)="toggleAutoMode()">
        <span class="slider"></span>
        <span class="label">Auto</span>
      </label>
    </div>
    <div class="placeholder">Floating Face Popup (sin contenido)</div>
  </div>
  `,
  styles: [`
    .popup-root {
      width: 360px;
      height: 540px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
      background: #ffffff;
      padding-top: 12px;
    }
    .controls-row {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .hide-rdp-btn {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: #fff;
      border: none;
      border-radius: 6px;
      padding: 8px 18px;
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(102, 126, 234, 0.35);
      transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .hide-rdp-btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.45);
    }
    .hide-rdp-btn:active {
      transform: translateY(0);
    }
    .auto-switch {
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      user-select: none;
    }
    .auto-switch input {
      display: none;
    }
    .auto-switch .slider {
      width: 36px;
      height: 20px;
      background: #ccc;
      border-radius: 10px;
      position: relative;
      transition: background 0.2s ease;
    }
    .auto-switch .slider::after {
      content: '';
      position: absolute;
      width: 16px;
      height: 16px;
      background: #fff;
      border-radius: 50%;
      top: 2px;
      left: 2px;
      transition: transform 0.2s ease;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    .auto-switch input:checked + .slider {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .auto-switch input:checked + .slider::after {
      transform: translateX(16px);
    }
    .auto-switch .label {
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 12px;
      font-weight: 500;
      color: #555;
    }
    .placeholder {
      color: #888;
      font-family: 'Segoe UI', Arial, sans-serif;
      margin-top: auto;
      margin-bottom: auto;
    }
  `]
})
export class FloatingFacePopupComponent implements OnInit {
  autoMode = false;

  async ngOnInit() {
    // Cargar estado inicial del servidor
    try {
      const res = await fetch('http://127.0.0.1:8080/ui/state')
      const data = await res.json()
      if (data.status === 'ok' && data.data) {
        this.autoMode = !!data.data.auto_hide_rdp
      }
    } catch {}
  }

  async toggleAutoMode() {
    this.autoMode = !this.autoMode
    // Sincronizar con el servidor para que el sol ejecute la acción
    try {
      await fetch('http://127.0.0.1:8080/ui/auto-hide-rdp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: this.autoMode })
      })
    } catch {}
  }

  async onEnter() {
    try {
      await fetch('http://127.0.0.1:8080/ui/popup/hover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hover: true })
      })
    } catch {}
  }

  async onLeave() {
    try {
      await fetch('http://127.0.0.1:8080/ui/popup/hover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hover: false })
      })
    } catch {}
  }

  async hideRemoteDesktop() {
    try {
      await fetch('http://127.0.0.1:8080/windows/minimize-remote-desktop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
    } catch {}
  }
}
