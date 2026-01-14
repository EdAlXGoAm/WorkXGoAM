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
    <div class="app-selector-row">
      <span class="selector-label">Target App:</span>
      <label class="app-switch">
        <input type="checkbox" [checked]="usePartnerRoom" (change)="toggleTargetApp()">
        <span class="slider"></span>
        <span class="label-left">Remote Desktop</span>
        <span class="label-right">Partner Room</span>
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
    .app-selector-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 16px;
      padding: 8px 16px;
      background: #f8f9fa;
      border-radius: 8px;
    }
    .selector-label {
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 12px;
      font-weight: 600;
      color: #333;
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
    .app-switch {
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      user-select: none;
      position: relative;
    }
    .app-switch input {
      display: none;
    }
    .app-switch .slider {
      width: 44px;
      height: 22px;
      background: #4a90e2;
      border-radius: 11px;
      position: relative;
      transition: background 0.2s ease;
    }
    .app-switch .slider::after {
      content: '';
      position: absolute;
      width: 18px;
      height: 18px;
      background: #fff;
      border-radius: 50%;
      top: 2px;
      left: 2px;
      transition: transform 0.2s ease;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    .app-switch input:checked + .slider {
      background: #27ae60;
    }
    .app-switch input:checked + .slider::after {
      transform: translateX(22px);
    }
    .app-switch .label-left,
    .app-switch .label-right {
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 11px;
      font-weight: 500;
      color: #555;
    }
    .app-switch input:not(:checked) ~ .label-left {
      font-weight: 700;
      color: #4a90e2;
    }
    .app-switch input:checked ~ .label-right {
      font-weight: 700;
      color: #27ae60;
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
  usePartnerRoom = false;

  async ngOnInit() {
    // Cargar estado inicial del servidor
    try {
      const res = await fetch('http://127.0.0.1:8080/ui/state')
      const data = await res.json()
      if (data.status === 'ok' && data.data) {
        this.autoMode = !!data.data.auto_hide_rdp
        this.usePartnerRoom = !!data.data.use_partner_room
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

  async toggleTargetApp() {
    this.usePartnerRoom = !this.usePartnerRoom
    // Sincronizar con el servidor
    try {
      await fetch('http://127.0.0.1:8080/ui/target-app', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_partner_room: this.usePartnerRoom })
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
