import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { invoke } from "@tauri-apps/api/core";
import { ApiService } from './services/api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit {
  greetingMessage = "";
  serverMessage = "";
  serverStatus = false;

  constructor(private apiService: ApiService) {}
  
  ngOnInit(): void {
    this.checkServerStatus();
    this.getServerMessage();
  }

  greet(event: SubmitEvent, name: string): void {
    event.preventDefault();

    // Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
    invoke<string>("greet", { name }).then((text) => {
      this.greetingMessage = text;
    });
  }

  checkServerStatus(): void {
    this.apiService.checkHealth().subscribe(status => {
      this.serverStatus = status;
      console.log('Server status:', status ? 'Online' : 'Disconnected');
    });
  }

  getServerMessage(): void {
    this.apiService.getHello().subscribe(response => {
      this.serverMessage = response.message;
    });
  }
}
