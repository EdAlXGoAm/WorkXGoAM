import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ApiService } from '../services/api.service';
import { invoke } from '@tauri-apps/api/core';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit {
  serverStatus = false;
  private popupCheckTimer: any = null;
  private lastShown = false;
  private hideDelayMs = 350;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.checkServerStatus();
    this.startPopupWatcher();
  }

  checkServerStatus(): void {
    this.apiService.checkHealth().subscribe(status => {
      this.serverStatus = status;
      console.log('HomeComponent - Server status:', status ? 'Online' : 'Disconnected');
    });
  }

  async openTestWindow(): Promise<void> {
    try {
      await invoke('open_test_window');
    } catch (error) {
      console.error('Error opening Test Window:', error);
    }
  }

  async openVideoCutter(): Promise<void> {
    try {
      await invoke('open_video_cutter');
    } catch (error) {
      console.error('Error opening Video Cutter:', error);
    }
  }

  async openFloatingFacePopup(): Promise<void> {
    try {
      await invoke('show_floating_face_popup', { x: null, y: null });
    } catch (error) {
      console.error('Error opening Floating Face Popup:', error);
    }
  }

  private startPopupWatcher(){
    const tick = async () => {
      try{
        const s = (await this.apiService.getUiState().toPromise()) || { face_hover:false, popup_hover:false, face_rect:null };
        const wantVisible = !!((s as any).face_hover || (s as any).popup_hover);
        if (wantVisible){
          let x: number | null = null;
          let y: number | null = null;
          const rect: any = (s as any).face_rect as any;
          if (rect && Array.isArray(rect) && rect.length >= 4){
            const fx = rect[0];
            const fy = rect[1];
            const fw = rect[2];
            const fh = rect[3];
            x = fx + fw + 18;
            y = Math.max(0, Math.floor(fy - (540 - fh)/2));
          }
          try{ await invoke('show_floating_face_popup', { x, y }) } catch {}
          this.lastShown = true;
        } else if (this.lastShown) {
          setTimeout(async ()=>{
            try{
              const s2 = (await this.apiService.getUiState().toPromise()) || { face_hover:false, popup_hover:false } as any;
              if (!((s2 as any).face_hover || (s2 as any).popup_hover)){
                try{ await invoke('hide_floating_face_popup') } catch {}
                this.lastShown = false;
              }
            } catch{}
          }, this.hideDelayMs);
        }
      }catch{}
      this.popupCheckTimer = setTimeout(tick, 150);
    };
    if (!this.popupCheckTimer){
      this.popupCheckTimer = setTimeout(tick, 200);
    }
  }
} 