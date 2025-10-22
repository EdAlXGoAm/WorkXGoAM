import { Component, HostListener } from '@angular/core'

@Component({
  selector: 'app-floating-face-popup',
  standalone: true,
  template: `
  <div class="popup-root" (mouseenter)="onEnter()" (mouseleave)="onLeave()">
    <div class="placeholder">Floating Face Popup (sin contenido)</div>
  </div>
  `,
  styles: [
    `.popup-root{width:360px;height:540px;display:flex;align-items:center;justify-content:center;background:#ffffff}`,
    `.placeholder{color:#888;font-family:Segoe UI, Arial, sans-serif}`
  ]
})
export class FloatingFacePopupComponent {
  async onEnter(){
    try {
      const res = await fetch('http://127.0.0.1:8080/ui/popup/hover', {method:'POST',headers:{'Content-Type':'application/json'},body: JSON.stringify({hover:true})})
      void res
    } catch {}
  }
  async onLeave(){
    try {
      const res = await fetch('http://127.0.0.1:8080/ui/popup/hover', {method:'POST',headers:{'Content-Type':'application/json'},body: JSON.stringify({hover:false})})
      void res
    } catch {}
  }
}
