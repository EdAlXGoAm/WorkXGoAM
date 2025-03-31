import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { TestWindowService } from '../services/test-window.service';

@Component({
  selector: 'app-test-window',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './test-window.component.html',
  styleUrls: ['./test-window.component.css']
})
export class TestWindowComponent implements OnInit {
  dataFromService: string = '';

  constructor(private router: Router, private testWindowService: TestWindowService) {}

  ngOnInit(): void {
    this.dataFromService = this.testWindowService.getTestData();
  }

  goBack(): void {
    this.router.navigate(['/']);
  }
} 