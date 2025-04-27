import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ApiService } from '../services/api.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit {
  serverStatus = false;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.checkServerStatus();
  }

  checkServerStatus(): void {
    this.apiService.checkHealth().subscribe(status => {
      this.serverStatus = status;
      console.log('HomeComponent - Server status:', status ? 'Online' : 'Disconnected');
    });
  }
} 